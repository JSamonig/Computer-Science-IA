# routes.py importing modules and libraries
from app import app, handlefiles, OCR, forms, db, map
from app.emails import send_password_reset_email, send_email, send_verify_email, send_auth_email, send_reject_email
from app.models import User, reclaim_forms, reclaim_forms_details, Account_codes, cost_centres, get_token, verify_token
from flask import request, redirect, flash, render_template, url_for, send_file, Markup, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from python_http_client.exceptions import UnauthorizedError
from urllib.error import HTTPError
from http.client import IncompleteRead
from urllib import parse as urllib_parse
from werkzeug.urls import url_parse
from PIL import Image
import datetime
import io
import os
import uuid
import config as c
import numpy as np


@app.route("/")
@app.route("/index")
def index():
    """
    Index page which is currently redundant as it simply links to view_forms, if a user is logged in.
    """
    return redirect(url_for("view_forms"))


@app.route("/upload/<file_id>/<row>", methods=["GET", "POST"])
@login_required
def upload(file_id: str, row: str):
    """
    :param file_id: The file id of the excel sheet (this is a value from the database at app.db)
    :param row: Row inside the excel sheet (this is a value from the database at app.db). Row=0 if a new row is added.
    :return: HTML template contained in app/templates/forms
    purpose: Upload an image to an expenses form.
    """
    if row == "0":  # row=0 is used when a new row is added
        details = (
            db.session.query(db.func.max(reclaim_forms_details.row_id))
            .filter_by(made_by=current_user.id)
            .filter_by(form_id=file_id)
            .first()[0]
        )  # if a new row is added, look for the last row added
        if details:
            row = int(details) + 1  # if a new row is added, the index will be one more than the previous row
        else:
            row = 7  # If there are now previous rows, we will start at row 7 in the excel sheet.
    my_form = forms.UploadForm()
    if request.method == "POST" and "submit" in request.form:
        try:
            file = db.session.query(reclaim_forms).filter_by(id=file_id).first()  # find reclaim form
            handlefiles.revert_to_draft(file)
            details = (
                db.session.query(reclaim_forms_details)
                .filter_by(made_by=current_user.id)
                .filter_by(form_id=file_id)
                .filter_by(row_id=int(row))
                .first()
            )  # find specific entry
            if details:  # if the entry exists
                try:
                    if details.image_name:  # if an image is already uploaded
                        os.remove(
                            os.path.join(app.config["IMAGE_UPLOADS"], details.image_name)
                        )  # delete the existing image
                except FileNotFoundError:
                    details.image_name = None
                    db.session.commit()
            detected_extension = handlefiles.validate_image(my_form.file.data.stream)  # detect extension of image
            if detected_extension not in c.Config.ALLOWED_EXTENSIONS_IMAGES:
                flash(
                    "Incorrect file extension", category="alert alert-danger"
                )  # error if the extension is not allowed
                return render_template("forms/upload.html", form=my_form, dark=current_user.dark)
            filename = str(uuid.uuid4()) + "." + detected_extension  # make new filename
            my_form.file.data.save(app.config["IMAGE_UPLOADS"] + filename)  # save image under filename
            user = User.query.filter_by(id=current_user.id).first_or_404()  # get the user
            data = OCR.run(filename, user.use_taggun)  # run OCR, with users taggun option
            img = Image.open(app.config["IMAGE_UPLOADS"] + filename)  # resize image after OCR
            """
            From:
            https://stackoverflow.com/questions/273946/how-do-i-resize-an-image-using-pil-and-maintain-its-aspect-ratio
            """
            base_width = 500
            w_percent = base_width / float(img.size[0])
            h_size = int((float(img.size[1]) * float(w_percent)))
            img = img.resize((base_width, h_size), Image.ANTIALIAS)
            img.save(app.config["IMAGE_UPLOADS"] + filename)
            if not details:  # create new row if it doesn't exist
                details = reclaim_forms_details(
                    date_receipt=data["date_receipt"],
                    Total=data["Total"],
                    image_name=filename,
                    made_by=current_user.id,
                    row_id=row,
                    form_id=file_id,
                )
                db.session.add(details)  # add to session
            else:
                details.date_receipt = data["date_receipt"]
                details.Total = data["Total"]
                details.image_name = filename  # results of OCR
            db.session.commit()  # commit to DB
        except AttributeError:  # if any of the database values do not exist, or there is an unexpected AttributeError
            flash("Please try again or use a different file.", category="alert alert-danger")
            return render_template("forms/upload.html", form=my_form, dark=current_user.dark)
        if details.Total is None or details.date_receipt is None:  # If OCR could not find a value
            flash(
                "Could not recognise price or total. Optical character recognition is never 100% accurate.",
                category="alert alert-danger",
            )
        else:  # General warning
            flash(
                "Please check the information is correct. Optical character recognition is never 100% accurate.",
                category="alert alert-secondary",
            )
        return redirect("/edit_data/{}/{}".format(file_id, row))  # redirect to edit_data
    return render_template("forms/upload.html", form=my_form, dark=current_user.dark)  # GET request


@app.route("/edit_data/<file_id>/<row>", methods=["GET", "POST"])
@login_required
def edit_data(file_id, row):
    """
    :param file_id: ID of file in the database
    :param row: ID of the row which is to be access
    :return: HTML template contained in app/templates/forms
    Edit any data which came in through Mileage or Upload
    """
    my_form = forms.EditOutput()
    details = (
        db.session.query(reclaim_forms_details)
        .filter_by(made_by=current_user.id)
        .filter_by(form_id=file_id)
        .filter_by(row_id=int(row))
        .first_or_404()
    )  # get row of reclaim form
    accounts = db.session.query(Account_codes).all()  # find all account codes
    file = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(id=file_id).first()
    handlefiles.revert_to_draft(file)
    accounts_list = []
    for account in accounts:
        accounts_list.append([str(account.account_id), str(account.account_name)])  # append all accounts to a list
    accounts_list.append(["N/A", "N/A"])
    if request.method == "POST":
        if my_form.validate_on_submit():
            if my_form.miles.data:  # if there is data for mileage
                if float(my_form.miles.data) < 0 or float(my_form.total.data) < 0:  # check if there are negatives
                    flash("Only input positive values", category="alert alert-danger")
                    return redirect(url_for("edit_data", file_id=file_id, row=row))  # reload
            else:  # if mileage isnt present, only total will be present, the below lines prevent an error from occuring
                if float(my_form.total.data) < 0:  # check if there are negatives
                    flash("Only input positive values", category="alert alert-danger")
                    return redirect(url_for("edit_data", file_id=file_id, row=row))  # reload
            if details:  # if there is a reclaim form
                details.date_receipt = my_form.date.data
                details.description = my_form.description.data  # load data into DB
                details.miles = my_form.miles.data
                # Format of account_id is for example: ART(110)-43214
                cost_centre = (
                    db.session.query(Account_codes).filter_by(account_id=my_form.accountCode.data).first_or_404()
                )  # number associated with 3 letter code (110)
                account_code = my_form.accountCode2.data  # this is the 43214 suffix
                if cost_centre.cost_centre:
                    details.account_id = "{}({})-{}".format(
                        str(cost_centre.account_id), str(cost_centre.cost_centre), str(account_code)
                    )  # format account_id
                else:  # some cost_centre values do not have a 3 digit number, so the letters only are used
                    details.account_id = "{}-{}".format(str(cost_centre.account_id), str(account_code))
                details.Total = (
                    my_form.total.data
                    if str(my_form.total.data) != "None"
                    else my_form.miles.data * c.Config.MILEAGE_RATE
                )
                # multiply by mileage rate
                db.session.commit()  # commit changes to DB
                today = datetime.datetime.now().date()  # save today's date
                result = (today - datetime.datetime.strptime(details.date_receipt, "%d/%m/%Y").date()).days > 29
                if result:  # Give a warning that expense is older than 4 weeks
                    flash(
                        "Warning: the date of expense for row {} is older than 4 weeks, refund is not guaranteed.".format(
                            str(int(row) - 6)
                        ),
                        category="alert alert-warning ",
                    )
            else:  # Throw error if details is not found
                flash("This row doesn't exist.", category="alert alert-danger")
            return redirect(url_for("edit_forms", file_id=file_id))
        elif "data" in dict(request.form):
            """
            AJAX
            To dynamically load options such as "flowers" from 3 letter "ART" in example above.
            Once an option for the first field ("ART") is selected, the below code will find associated options (such as
            Flowers, software or stationary, for example).
            """
            return_cost_centers = (
                db.session.query(cost_centres)
                .filter_by(cost_centre_id=dict(request.form)["data"])  # cost centres associated with 3 digit code
                .all()
            )  # dict(request.form)["data"] is the 3 letter code
            dict_cost_centres = {}
            for centre in return_cost_centers:
                dict_cost_centres[str(centre.purpose_id)] = centre.purpose_cost_centre
                # Associate purpose with code e.g. flowers with 12345
            if dict_cost_centres == {}:  # repeat the above but add all unique cost centres if the dict is empty
                return_cost_centers = db.session.query(db.distinct(cost_centres.purpose_cost_centre)).all()
                # return all unique cost centre purposes
                for centre in return_cost_centers:
                    individual_centre = (
                        db.session.query(cost_centres).filter_by(purpose_cost_centre=list(centre)[0]).first_or_404()
                    )
                    dict_cost_centres[str(individual_centre.purpose_id)] = individual_centre.purpose_cost_centre
            dict_cost_centres["N/A"] = "N/A"  # add a N/A option
            return jsonify({"Data": dict_cost_centres})  # return dict
    # GET request
    my_form.date.data = details.date_receipt
    my_form.description.data = details.description
    if details.account_id is not None:
        current_account = details.account_id.split("-")  # E.g. [ART(110), 43214]
        current_account[0] = current_account[0].split("(")[0]  # get account code 3 letter code [ART, 43214]
        account = [
            db.session.query(Account_codes).filter_by(account_id=str(current_account[0])).first_or_404().account_id,
            db.session.query(Account_codes).filter_by(account_id=str(current_account[0])).first_or_404().account_name,
        ]  # e.g. [ART, Art department]
        if account in accounts_list:
            accounts_list.pop(accounts_list.index(account))  # pop selected account to avoid duplicate accounts
        cost_centre = [
            current_account[1],
            db.session.query(cost_centres).filter_by(purpose_id=current_account[1]).first_or_404().purpose_cost_centre,
        ]  # Selected cost centre [43214, purpose]
    else:
        cost_centre, account = None, None
    if details.Total is not None:
        my_form.total.data = round(float(details.Total), 2)  # Round total
    if details.start and details.destination:  # if a route is attached
        destination = urllib_parse.quote_plus(details.destination)  # put start and destination into url format
        origin = urllib_parse.quote_plus(details.start)
        my_form.miles.data = details.miles  # load mileage into edit form
        return render_template(
            "forms/form.html",
            form=my_form,
            include=True,
            start=origin,
            end=destination,
            dark=current_user.dark,
            accounts=accounts_list,
            account=account,
            cost_centre=cost_centre,
        )
    """
        form.html parameters

        form = form object located in forms.py
        filename = path to receipt image
        dark = user's selected theme
        accounts = All accounts with associated purpose
        account = Selected account
        cost_centre = All cost centres associated with selected account
        include = render mileage field and map
        start = url encoded location for map
        end = url encoded location of destination for map

        """
    return render_template(
        "forms/form.html",
        form=my_form,
        filename=c.Config.IMAGE_ROUTE + details.image_name,
        dark=current_user.dark,
        accounts=accounts_list,
        account=account,
        cost_centre=cost_centre,
    )
    # Render same form, but with image of receipt instead of map


@app.route("/edit_forms/<file_id>", methods=["GET", "POST"])
@login_required
def edit_forms(file_id):
    """
    :param file_id:  ID of the expenses form
    :return: HTML
    """
    rows = (
        db.session.query(reclaim_forms_details)
        .filter_by(made_by=current_user.id)
        .filter_by(form_id=file_id)
        .order_by(reclaim_forms_details.row_id)
        .all()
    )
    file = db.session.query(reclaim_forms).filter_by(id=file_id).first_or_404()
    sum_reclaimed = 0  # sum of reclaimed money in a form
    for row in rows:
        if row.Total:
            sum_reclaimed += float(row.Total)
        elif row.miles:
            row.Total = row.miles * c.Config.MILEAGE_RATE  # calculate total if no total present
            sum_reclaimed += float(row.Total)
        else:
            row.Total = 0  # if neither is present give total of zero
        if row.account_id is None:
            # delete the row is account_id is not present (i.e. incomplete form submission in edit_data() ).
            return redirect(url_for("delete_row", file_id=file_id, row=row.row_id))
    return render_template(
        "forms/edit_forms.html",
        forms=rows,
        file_id=file_id,
        name=file.filename,
        mysum=sum_reclaimed,
        dark=current_user.dark,
        authed=(file.sent == "Authorized"),
    )


@app.route("/delete_row/<file_id>/<row>", methods=["GET", "POST"])
@login_required
def delete_row(file_id, row):
    """
    :param file_id: ID of reclaim form
    :param row: Row number
    :return: HTML

    Deleting rows
    """
    row_number = row  # avoid duplicate variable names later
    row = (
        db.session.query(reclaim_forms_details)
        .filter_by(made_by=current_user.id)
        .filter_by(form_id=file_id)
        .filter_by(row_id=int(row_number))
        .first_or_404()
    )
    try:  # Try to remove image associated with a row
        if row.image_name is not None:
            os.remove(os.path.join(app.config["IMAGE_UPLOADS"], row.image_name))
    except FileNotFoundError:
        row.image_name = None
    reclaim_forms_details.query.filter_by(id=row.id).delete()  # delete row
    rows = (
        db.session.query(reclaim_forms_details)
        .filter_by(made_by=current_user.id)
        .filter_by(form_id=file_id)
        .order_by(reclaim_forms_details.row_id)
        .all()
    )  # get all rows
    for iterated_row in rows:
        if iterated_row.row_id > int(row_number):
            iterated_row.row_id -= 1  # move below rows up one
    db.session.commit()
    return redirect(url_for("edit_forms", file_id=file_id))


@app.route("/delete_file/<file_id>", methods=["GET", "POST"])
@login_required
def delete_file(file_id):
    """
    :param file_id: ID of reclaim form
    :return: HTML
    """
    rows = reclaim_forms_details.query.filter_by(form_id=file_id).all()
    for row in rows:
        if row.image_name:  # remove images
            try:
                os.remove(os.path.join(app.config["IMAGE_UPLOADS"], row.image_name))
            except FileNotFoundError:
                row.image_name = None
    file = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(id=file_id)
    if file.first().signature:
        try:  # remove signature
            os.remove(os.path.join(app.config["SIGNATURE_ROUTE"], file.first().signature))
        except FileNotFoundError:
            file.first().signature = None
    file.delete()  # delete file
    db.session.commit()
    return redirect(url_for("view_forms"))


@app.route("/download/<file_id>", methods=["GET"])
@login_required
def download(file_id):
    """
    :param file_id: ID of reclaim form
    :return: HTML
    """
    try:
        file = handlefiles.create_excel(file_id, current_user)  # create excel file dynamically
        db.session.commit()
        return send_file(c.Config.DOWNLOAD_ROUTE + file.filename, as_attachment=True, cache_timeout=0)
        # send file to user but do not cache it
    except (Exception, BaseException, FileNotFoundError) as e:
        flash("Error downloading file.", category="alert alert-danger")
        app.logger("Error in download: {}".format(e))
        return redirect(url_for("view_forms"))


@app.route("/view_forms", methods=["GET", "POST"])
@app.route("/view_forms", methods=["GET", "POST"])
@login_required
def view_forms():
    """
    :return: HTML
    """
    all_forms = (
        db.session.query(reclaim_forms)
        .filter_by(made_by=current_user.id)
        .order_by(reclaim_forms.date_created.desc())
        .all()
    )  # all reclaim forms made by a user sorted by date
    user = User.query.get(current_user.id)
    if user.accounting_email is None:  # if the user has not set an email
        my_form = forms.ModalSettings()
        new_user = True
        if my_form.validate_on_submit():  # render a form which asks for email and preffered theme
            user.accounting_email = my_form.accounting_email.data
            user.dark = my_form.dark.data
            db.session.commit()
            return render_template("forms/view_forms.html", forms=all_forms, dark=current_user.dark)
        return render_template(
            "forms/view_forms.html", forms=all_forms, dark=current_user.dark, setting=my_form, new_user=new_user
        )
    else:
        return render_template("forms/view_forms.html", forms=all_forms, dark=current_user.dark)


@app.route("/new_form", methods=["GET", "POST"])
@login_required
def new_form():
    """
    :return: HTML
    Creates a new form
    """
    my_form = forms.NewReclaim()
    user = User.query.filter_by(id=current_user.id).first()
    if my_form.validate_on_submit():
        filename = handlefiles.validate_excel(my_form.filename.data)
        file_id = str(uuid.uuid4())  # unique user id filename which is stored as a variable and in the database
        file = reclaim_forms(
            id=file_id, filename=filename, description=my_form.description.data, sent="Draft", made_by=current_user.id
        )  # New file, meaning it must be a draft
        db.session.add(file)
        db.session.commit()
        flash("Successfully created the form: {}".format(filename), category="alert alert-success")
        return redirect(url_for("edit_forms", file_id=file_id))
    elif request.method == "GET":
        my_form.filename.data = "Expenses {} {} {}".format(
            user.first_name[0], user.last_name, datetime.datetime.today().strftime("%d-%m-%Y")
        )
    return render_template("forms/new_form.html", form=my_form, title="Create a new form", dark=current_user.dark)


@app.route("/edit_form/<file>", methods=["GET", "POST"])  # edit reclaim form details
@login_required
def edit_form(file):
    """
    :param file: ID of reclaim id
    :return: HTML
    """
    my_form = forms.NewReclaim()
    user = User.query.filter_by(id=current_user.id).first()
    myfile = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(id=file).first_or_404()
    if my_form.validate_on_submit():
        filename = handlefiles.validate_excel(my_form.filename.data)  # make filename safe
        myfile.description = my_form.description.data
        myfile.filename = filename
        db.session.commit()
        return redirect(url_for("view_forms"))
    elif request.method == "GET":
        if myfile:
            my_form.filename.data = myfile.filename
            my_form.description.data = myfile.description  # preload fields
        else:
            my_form.filename.data = "Expenses_form_" + user.last_name + ".xlsx"
    return render_template("forms/new_form.html", form=my_form, title="Edit form", dark=current_user.dark, edit=True)


#  --> Adapted from https://blog.miguelgrinberg.com/


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Handles logic of login
    :return: HTML
    """
    if current_user.is_authenticated:
        return redirect(url_for("view_forms"))
    my_form = forms.LoginForm()
    if my_form.validate_on_submit():
        user = User.query.filter_by(email=my_form.email.data).first()
        if user is None or not user.check_password(my_form.password.data):
            flash("Invalid username or password", category="alert alert-danger")
            return redirect(url_for("login"))
        if user is None or not user.is_verified:
            flash(
                Markup(  # markup renders html into the flash
                    'Please check your emails to verify your email. Click <a href="{}" class="alert-link">here</a> to send '
                    "another email.".format(url_for("verify_email_request"))
                ),
                category="alert alert-danger",
            )
            return redirect(url_for("login"))
        login_user(user, remember=my_form.remember_me.data)
        next_page = request.args.get("next")
        if not next_page or url_parse(next_page).netloc != "":
            next_page = url_for("index")
        return redirect(next_page)  # redirect to next page (if the user was redirected from another page)
    return render_template("user/login.html", form=my_form)


@app.route("/logout")
@login_required
def logout():
    """
    Logout function
    :return: HTML
    """
    logout_user()
    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Register function
    :return: HTML
    """
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    my_form = forms.RegistrationForm()
    if my_form.validate_on_submit():
        user = User(first_name=my_form.first_name.data, last_name=my_form.last_name.data, email=my_form.email.data)
        user.set_password(my_form.password.data)
        db.session.add(user)
        db.session.commit()
        send_verify_email(user)
        logout_user()
        flash(
            Markup(
                'Congratulations, you are now a registered user! Please verify your email to login. Click <a href="{}" '
                'class="alert-link">here</a> to send another email.'.format(url_for("verify_email_request"))
            ),
            category="alert alert-success",
        )
        return redirect(url_for("login"))
    return render_template("user/register.html", title="Register", form_title="Register", form=my_form)


# <--


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """
    Settings page
    :return: HTML
    """
    my_form = forms.Settings(current_user.id)
    user = User.query.get(current_user.id)
    if my_form.validate_on_submit():
        user.first_name = my_form.first_name.data
        user.last_name = my_form.last_name.data
        user.accounting_email = my_form.accounting_email.data
        if my_form.email.data != user.email:
            # if email is changed, logout user and make them verify the new email
            user.email = my_form.email.data
            user.is_verified = False
            send_verify_email(user)
            logout_user()
            flash(
                Markup(
                    'You have been logged out. Please verify {} to login. Click <a href="{}" class="alert-link">here</a> '
                    "to send another email.".format(my_form.accounting_email.data, url_for("verify_email_request"))
                ),
                category="alert alert-success",
            )
        user.use_taggun = my_form.taggun.data
        user.dark = my_form.dark.data
        db.session.commit()
        return redirect(url_for("view_forms"))
    elif request.method == "GET":
        # prefill fields
        my_form.first_name.data = user.first_name
        my_form.last_name.data = user.last_name
        my_form.email.data = user.email
        my_form.accounting_email.data = user.accounting_email
        my_form.taggun.data = user.use_taggun
        my_form.dark.data = user.dark
    return render_template(
        "user/settings.html", form=my_form, title="Settings", dark=current_user.dark, email=user.email
    )  # pass email to give an onchange message


@app.route("/send/<file_id>", methods=["GET", "POST"])
@login_required
def send(file_id):
    """
    Send the reclaim form to supervisor
    :param file_id: ID of reclaim form
    :return: HTML
    """
    my_form = forms.Supervisor()
    user = User.query.get(current_user.id)
    file_db = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(id=file_id).first()
    user_token = get_token(my_object=file_db, word="sign_form", expires_in=10 ** 20, user=user)
    # generate a token for the user (if the user is a HoD, the user will not need to email him/herself
    if my_form.validate_on_submit():
        sender = app.config["ADMINS"][0]
        subject = "Reclaim form from " + user.first_name + " " + user.last_name
        recipients = [my_form.email_supervisor.data]
        token = get_token(my_object=file_db, word="sign_form", expires_in=10 ** 20, user=my_form.email_supervisor.data)
        # Basically infinity (3,170,979,198.38 millenia)
        html_body = render_template("email/request_auth.html", token=token, user=user.first_name + " " + user.last_name)
        file = handlefiles.create_excel(file_id=file_id, current_user=current_user)  # create excel sheet
        try:  # send email, with link for supervisor to sign a reclaim form (and thus authorise it)
            send_email(subject=subject, sender=sender, recipients=recipients, html_body=html_body, file=file.filename)
            file_db.sent = "Awaiting authorization"
            file_db.date_sent = datetime.datetime.utcnow()
            db.session.commit()
            flash("Email successfully sent to {}".format(my_form.email_supervisor.data), category="alert alert-success")
        except (Exception, HTTPError, IncompleteRead, UnauthorizedError, BaseException) as e:
            app.logger.error("Error in function: send, signing form {}".format(e))
            flash("Error sending email. Please try again later.", category="alert alert-danger")
        return redirect(url_for("index"))
    return render_template("manager/manager_email.html", form=my_form, dark=current_user.dark, token=user_token)


@app.route("/send_accounting/<file_id>/<user_id>", methods=["GET", "POST"])
@login_required
def send_accounting(file_id, user_id):
    """
    Sends reclaim form to accounting, after is has been authorised
    :param file_id: ID of reclaim form
    :param user_id: User id of person who is making reclaims
    :return: HTML (redirect)
    """
    user = User.query.filter_by(id=user_id).first()
    file_db = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(id=file_id).first()
    sender = app.config["ADMINS"][0]
    subject = "Reclaim form from " + user.first_name + " " + user.last_name
    recipients = [user.accounting_email]
    html_body = render_template(
        "email/sent_form.html", user=str(user.first_name + " " + user.last_name), dark=current_user.dark
    )
    file = handlefiles.create_excel(file_id=file_id, current_user=current_user, signature=file_db.signature)
    try:
        send_email(subject=subject, sender=sender, recipients=recipients, html_body=html_body, file=file.filename)
    except (Exception, HTTPError, IncompleteRead, UnauthorizedError, BaseException) as e:
        app.logger.error("Error in send_accounting, signing form {}".format(e))
        flash("Unexpected error while authorising expenses form.", category="alert alert-danger")
    return redirect(url_for("view_forms"))


#  --> Adapted from https://blog.miguelgrinberg.com/


@app.route("/reset_password_request", methods=["GET", "POST"])
def reset_password_request():
    """
    Request a password reset
    :return: HTML
    """
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    my_form = forms.ResetPasswordRequestForm()
    if my_form.validate_on_submit():
        user = User.query.filter_by(email=my_form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash("Check your email for the instructions to reset your password", category="alert alert-success")
        return redirect(url_for("login"))
    return render_template("user/request_password_reset.html", title="Reset Password", form=my_form)


@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """
    Enables a user to reset their password
    :param token: Encoded string which will validate a password reset request, see
    :return: HTML
    """
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    user = verify_token(token, "reset_password")  # decode token to get the user
    if not user:
        return redirect(url_for("index"))
    my_form = forms.ResetPasswordForm()
    if my_form.validate_on_submit():
        user.set_password(my_form.password.data)
        db.session.commit()
        flash("Your password has been reset.", category="alert alert-success")
        return redirect(url_for("login"))
    return render_template("user/reset_password.html", form=my_form)


# <--
@app.route("/verify_email/<token>", methods=["GET", "POST"])
def verify_email(token):
    """
    :param token: Encoded string from which user can be decoded
    :return: HTML (redirect)
    """
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    user = verify_token(token, "verify_email")  # decode to get user
    if not user:
        return redirect(url_for("index"))
    user.is_verified = True  # verify user
    db.session.commit()
    flash("Your email has been verified.", category="alert alert-success")
    login_user(user)
    return redirect(url_for("index"))


@app.route("/verify_email_request", methods=["GET", "POST"])
def verify_email_request():
    """
    Show form to enter email which is to be requested, again.
    :return: HTML
    """
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    my_form = forms.VerifyEmail()
    if my_form.validate_on_submit():
        user = User.query.filter_by(email=my_form.email.data).first()
        try:
            if user:
                send_verify_email(user)
            flash("Check {} to verify your mail.".format(my_form.email.data), category="alert alert-success")
        except (Exception, HTTPError, IncompleteRead, UnauthorizedError, BaseException) as e:
            flash("Error sending email. Please try again later.", category="alert alert-danger")
            app.logger.error("Error in verify_email_request, signing form {}".format(e))
        return redirect(url_for("login"))
    return render_template("user/verify_email.html", title="Reset Password", form=my_form)


@app.route("/mileage/<file_id>/<row>", methods=["GET", "POST"])
@login_required
def mileage(file_id, row):
    """
    Enter a route as a form of reclaim (mileage expense reclaim)
    :param file_id: ID of reclaim form
    :param row: Row number in reclaim form
    :return: HTML (redirect to edit_data)
    """
    if row == "0":  # if new row is being added
        details = (
            db.session.query(db.func.max(reclaim_forms_details.row_id))
            .filter_by(made_by=current_user.id)
            .filter_by(form_id=file_id)
            .first()[0]
        )  # Find last row
        if details:
            row = int(details) + 1
        else:
            row = 7  # default
    my_form = forms.Description()
    details = (
        db.session.query(reclaim_forms_details)
        .filter_by(made_by=current_user.id)
        .filter_by(form_id=file_id)
        .filter_by(row_id=int(row))
        .first()
    )
    file = db.session.query(reclaim_forms).filter_by(id=file_id).first_or_404()
    handlefiles.revert_to_draft(file)
    if my_form.validate_on_submit():
        # date validator i.e. don't allow negative trip durations
        end = datetime.datetime.strptime(my_form.date_end.data, "%d/%m/%Y").date()
        start = datetime.datetime.strptime(my_form.date_start.data, "%d/%m/%Y").date()
        if start > end:
            flash("Error: negative trip duration", category="alert alert-danger")
            return render_template(
                "forms/miles.html",
                title="Add from mileage",
                form=my_form,
                dark=current_user.dark,
                start=urllib_parse.quote_plus(my_form.start.data),
                end=urllib_parse.quote_plus(my_form.destination.data),
            )
        description = (
            "Description: "
            + my_form.description.data
            + " Start: "
            + my_form.start.data
            + " End: "
            + my_form.destination.data
            + " Starting date: "
            + my_form.date_start.data
            + " Ending date: "
            + my_form.date_end.data
            + " Return trip: "
            + str(my_form.return_trip.data)
        )
        results = map.get_map(my_form.start.data, my_form.destination.data)  # [cords, miles, total, status]
        if not details:  # make a new row
            if results[3] != "OK":
                total, miles = None, None
            elif my_form.return_trip.data:
                total = round(float(results[2] * 2), 2)  # times 2 if return trip
                miles = results[1] * 2
            else:
                total = round(float(results[2]), 2)
                miles = results[1]
            details = reclaim_forms_details(
                description=description,
                date_receipt=my_form.date_start.data,
                made_by=current_user.id,
                row_id=row,
                form_id=file_id,
                start=my_form.start.data,
                destination=my_form.destination.data,
                miles=miles,
                Total=total,
                end_date=my_form.date_end.data,
                purpose=my_form.description.data,
                return_trip=my_form.return_trip.data,
            )  # new row entry
            db.session.add(details)
            db.session.commit()
        else:
            details.description = description
            details.date_receipt = my_form.date_end.data
            details.start = my_form.start.data
            details.destination = my_form.destination.data
            if results[3] != "OK":
                details.miles = None
                details.Total = None
                flash(
                    "The route could not be identified, and a mileage was not calculated. Please check the spelling "
                    "of locations.",
                    category="alert alert-danger",
                )
            elif my_form.return_trip.data is True and details.return_trip is False:
                # multiply or divide based on changed option
                details.miles = results[1] * 2
                details.Total = round(float(results[2]), 2) * 2
            elif my_form.return_trip.data is False and details.return_trip is True:
                details.miles = results[1] * 0.5
                details.Total = round(float(results[2]), 2) * 0.5
            else:
                details.miles = results[1]
                details.Total = round(float(results[2]), 2)
            details.end_date = my_form.date_end.data
            details.purpose = my_form.description.data
            details.return_trip = my_form.return_trip.data
            db.session.commit()
        return redirect("/edit_data/{}/{}".format(file_id, row))
    elif request.method == "GET":
        if details:
            my_form.date_start.data = details.date_receipt
            my_form.start.data = details.start
            my_form.destination.data = details.destination
            my_form.description.data = details.purpose
            my_form.date_end.data = details.end_date
            my_form.return_trip.data = details.return_trip
            if details.start:
                origin = urllib_parse.quote_plus(details.destination)
                # pass destinations into url format to use google maps api
                destination = urllib_parse.quote_plus(details.start)
                return render_template(
                    "forms/miles.html", form=my_form, start=origin, end=destination, dark=current_user.dark
                )
        my_form.start.data = "Wellington College, Duke's Ride, RG457PU"  # default value
    return render_template("forms/miles.html", title="Add from mileage", form=my_form, dark=current_user.dark)


@app.route("/delete_user", methods=["GET", "POST"])
@login_required
def delete_user():
    """
    Function to delete a user
    :return: HTML
    """
    files = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).all()
    for file in files:
        if file.signature is not None:  # remove signature
            os.remove(os.path.join(app.config["SIGNATURE_ROUTE"], file.signature))
        rows = (
            db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(form_id=file.id).all()
        )
        for row in rows:
            if row.image_name is not None:  # remove images
                os.remove(os.path.join(app.config["IMAGE_UPLOADS"], row.image_name))
        reclaim_forms_details.query.filter_by(form_id=file.id).delete()  # delete row
    db.session.query(reclaim_forms).filter_by(made_by=current_user.id).delete()  # delete all files
    User.query.filter_by(id=current_user.id).delete()  # remove user
    db.session.commit()
    flash("Successfully deleted account", category="alert alert-success")
    return redirect(url_for("logout"))


@app.route("/load_map/<start>/<end>", methods=["GET", "POST"])
@login_required
def load_map(end, start):
    """
    Loads coordinates for map iframe
    :param end: URL encoded end location
    :param start: URL encoded start location
    :return: HTML of map
    """
    results = map.get_map(start, end)  # render coordinates of a route
    cords = results[0]
    return render_template("iframes/map.html", cords=cords, key=c.Config.GOOGLEMAPS_KEY, dark=current_user.dark)


@app.route("/pie")
@login_required
def pie():
    """
    iframe which loads pie chart for dashboard
    Pie chart of amount reclaim by account code
    :return: HTML
    """
    values = []
    labels = []
    files = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).all()
    for file in files:
        if file.sent == "Authorized":
            rows = (
                db.session.query(reclaim_forms_details)
                .filter_by(made_by=current_user.id)
                .filter_by(form_id=file.id)
                .all()
            )
            for row in rows:
                if row.account_id in labels and row.account_id is not None and row.Total is not None:
                    values[labels.index(row.account_id)] += row.Total  # add total of each row for each account code
                elif row.account_id in labels and row.account_id is not None and row.Total is None:
                    pass
                elif row and row.account_id is not None:
                    labels.append(row.account_id)
                    values.append(row.Total)  # append new label for a new row account id

    colours = handlefiles.create_distinct_colours(len(labels) + 1)[: len(labels)]
    if values:
        return render_template("iframes/pie.html", title="Pie chart", values=values, labels=labels, colours=colours)
    else:
        values = [1]  # full pie chart in grey colour
        labels = ["No expenses forms authorized yet"]
        return render_template("iframes/pie.html", title="Pie chart", values=values, labels=labels, colours=colours)


@app.route("/line/<year>")  # define URL
@app.route("/line", defaults={"year": datetime.datetime.today().year})
@login_required  # user must be logged in to see content
def line(year):
    """
    iframe of a line graph
    Cumulative reclaimed amount over time by individual account codes, and the overall total
    :param year: Current year (explicit)
    :return: Line graph HTML
    """
    labels = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]  # labels at bottom of graph
    month = datetime.datetime.today().month  # current month
    labels = labels[: month + 1]  # display up to current month +1
    accounts = [{} for _ in range(len(labels))]  # 12 dictionaries for each month
    unique_accounts = []  # keep track of unique accounts (for key at top)
    for i in range(1, 13):  # for every month        ----- This part of the function queries the database -----
        date_start = datetime.datetime(int(year), i, 1)  # starting date is first of month
        date_end = date_start + datetime.timedelta(days=31)  # ending date is 31 days later
        files = (
            reclaim_forms.query.filter(reclaim_forms.date_sent >= date_start)
            .filter(reclaim_forms.date_sent < date_end)
            .filter(reclaim_forms.made_by == current_user.id)
            .all()
        )  # files sent in that month
        for file in files:  # for every file
            if file.sent == "Authorized":
                rows = (
                    db.session.query(reclaim_forms_details)
                    .filter_by(made_by=current_user.id)
                    .filter_by(form_id=file.id)
                    .all()
                )  # rows of given file
                for row in rows:  # for every row
                    if row.account_id is not None:  # if a row id exists (not None because a row id 0 could exist)
                        if row.account_id in accounts[i - 1].keys():  # if the account is already added to dictionary
                            pass  # I add all accounts to a dictionary in a list of months this way I can track Totals
                        else:
                            accounts[i - 1][row.account_id] = 0
                            # Add a account code to dictionary for month with value 0
                        if row.account_id not in unique_accounts:
                            unique_accounts.append(row.account_id)  # Add to key at top
                        accounts[i - 1][row.account_id] += row.Total  # Adding to the total for account code that month
    data = [[] for i in range(len(unique_accounts))]  # create a 2d array with length of all accounts
    for i in accounts:  # for every month
        for j in i.keys():  # for every account in that month
            data[unique_accounts.index(j)].append([i[j], accounts.index(i) + 1])
            # Append to account array the [ total reclaimed, month ]

    # ----- This part of the function sorts the data-points and adds data in between (which have not changed) -----
    for account in data:  # for every account in the data array
        for current_month in range(1, month + 1):  # For every month
            current_index = None  # ----Lines 515 to 518 find the index of the item that corresponds to a specific month
            for i in account:  # For every data point in for the specific account
                if i[1] == current_month:  # if the data point is equal to the month iterator
                    current_index = account.index(i)  # Record position of data point
            if current_index is not None:  # if the data point is in the correct position
                pass  # do nothing
            else:  # if the data point is in the wrong position
                # ----Find the index of the total of the month before (if it remains constant)
                index_before = None
                for i in account:  # for every month in the account code
                    if i[1] == current_month:  # if the month of a data point is equal to the month iterator
                        index_before = account.index(i)  # The indexBefore variable is this data-point index
                if index_before is not None:  # if the dataPoint for an account code does not exist
                    data[data.index(account)].append([account[index_before][0], current_month])
                    # append [the previous months value, month]
                else:
                    # If there is no data-point before, just append [0, month]
                    data[data.index(account)].append([0, current_month])
        data[data.index(account)] = sorted(account, key=lambda l: l[1])  # Sort the array
    for account in data:
        for j in range(1, len(account)):
            data[data.index(account)][j][0] += account[j - 1][0]  # Create a cumulative nature to the data points
    for account in data:
        for j in account:
            data[data.index(account)][account.index(j)] = j[0]  # Get rid of the month in [total, month]
    total = np.array([0 for _ in range(month)])  # Now create a np array for the totals (allows for array adding)
    for account in data:  # for every account
        account = np.array(account)  # Make account and np array
        total = np.add(total, account)  # Add account totals to the overall Total
    total = list(total)  # Turn total back to a normal array
    data.append(total)  # Append to data
    unique_accounts.append("Total")  # Append to key at top
    if unique_accounts == ["Total"]:
        unique_accounts = ["No expenses forms authorized yet"]
        colours = ["#E5E5E5"]
    else:
        colours = handlefiles.create_distinct_colours(len(unique_accounts))  # Create distinct colours
    return render_template("iframes/line.html", labels=labels, set=zip(data, unique_accounts, colours))  # To template


@app.route("/sign_form/<form_hash>/<is_hod>", methods=["GET", "POST"])
@app.route("/sign_form/<form_hash>", defaults={"is_hod": 0})
def sign_form(form_hash, is_hod):
    """
    Authorise a reclaim form, by signing it
    :param is_hod: Whether the user is authorizing their own form or not (in the case they are the corresponding HoD)
    :param form_hash: string which decodes to give the user who requested the form
    :return: HTML
    """
    form = verify_token(token=form_hash, word="sign_form", table=reclaim_forms)
    email_user = verify_token(token=form_hash, word="user", table=User, attribute="email")
    # for_user is the user for which the current user is authorising for
    if email_user and form:  # Authorization. Here, for_user is the tokens intended recipient
        for_user = (
            db.session.query(User).filter_by(id=form.made_by).first()
        )  # Here, for_user is the person who want to be authed
        if is_hod:
            form.sent = "Awaiting authorization"
            if form.signature:
                try:  # remove signature
                    os.remove(os.path.join(app.config["SIGNATURE_ROUTE"], form.signature))
                except FileNotFoundError:
                    form.signature = None
                    db.session.commit()
        if form.sent != "Awaiting authorization":
            flash("This authorization link has expired.", category="alert alert-danger")
            return redirect(url_for("index"))
        name = for_user.first_name + " " + for_user.last_name
        data = handlefiles.create_signature_back(email_user.split("@")[0])  # create image to sign over
        if request.method == "POST":
            if request.data:
                returned_bytes = bytearray(request.data)  # get back signature
                image = Image.open(io.BytesIO(returned_bytes))  # convert bytes to image
                signature = str(uuid.uuid4()) + ".png"
                image.save(c.Config.SIGNATURE_ROUTE + signature)
                form.signature = signature
                form.sent = "Authorized"
                send_auth_email(for_user, email_user)
                form.date_sent = datetime.datetime.utcnow()
                db.session.commit()
                flash("Signed expenses form successfully for {}!".format(name), category="alert alert-success")
                return jsonify({"redirect": "/send_accounting/{}/{}".format(form.id, for_user.id)})  # redirect
            else:
                try:
                    send_reject_email(for_user, email_user)
                    flash(
                        "Rejected form for {}. He/She has been notified.".format(name), category="alert alert-success"
                    )
                except (Exception, HTTPError, IncompleteRead, UnauthorizedError, BaseException) as e:
                    flash(
                        "Rejected form for {}. There was an error in sending an email to him/her.".format(name),
                        category="alert alert-danger",
                    )
                    app.logger.error("Error in sign_form, signing form {}".format(e))
                form.sent = "Rejected"
                db.session.commit()
                return jsonify({"redirect": "/index"})  # redirect to index
        return render_template("manager/sign_form.html", background=data, for_user=name, dark=current_user.dark)
    flash("Unknown token. Access denied", category="alert alert-danger")
    return redirect(url_for("index"))


@app.route("/debug-sentry")
@login_required
def trigger_error():
    print(1 / 0)
