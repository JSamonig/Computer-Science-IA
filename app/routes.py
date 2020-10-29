# routes.py importing modules and libraries
from flask import request, redirect, flash, render_template, abort, url_for, send_file, Markup, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from app import app, handlefiles, OCR, forms, db, map
from app.emails import send_password_reset_email, send_email, send_verify_email, send_auth_email, send_reject_email
from app.models import reclaim_forms, reclaim_forms_details, User, Account_codes, cost_centres
import urllib.parse
import datetime
import io
import os
import urllib.parse
import uuid
import config as c
import numpy as np
from werkzeug.urls import url_parse
from PIL import Image


@app.route('/')
@app.route('/index')
def index():
    return redirect(url_for("view_forms"))


@app.route('/upload/<file_id>/<row>', methods=['GET', 'POST'])
@login_required
def upload(file_id: str, row: str):
    """
    :param file_id: The file id of the excel sheet (this is a value from the database at app.db)
    :param row: Row inside the excel sheet (this is a value from the database at app.db). Row=0 if a new row is added.
    :return: HTML template contained in app/templates/forms
    purpose: Upload an image to an expenses form.
    """
    if row == "0":  # row=0 is used when a new row is added
        details = \
            db.session.query(db.func.max(reclaim_forms_details.row_id)).filter_by(made_by=current_user.id).filter_by(
                form_id=file_id).first()[0]  # if a new row is added, look for the last row added
        if details:
            row = int(details) + 1  # if a new row is added, the index will be one more than the previous row
        else:
            row = 7  # If there are now previous rows, we will start at row 7 in the excel sheet.
    myform = forms.uploadForm()
    if request.method == 'POST' and 'submit' in request.form:
        try:
            file = db.session.query(reclaim_forms).filter_by(id=file_id).first()  # find reclaim form
            if file.sent == "Authorized":  # if a file is already authorized make it into a draft
                file.sent = "Draft"
            details = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
                form_id=file_id).filter_by(row_id=int(row)).first()  # find specific entry
            if details:  # if the entry exists
                if details.image_name:  # if an image is already uploaded
                    os.remove(
                        os.path.join(app.config['IMAGE_UPLOADS'], details.image_name))  # delete the existing image
            detected_extension = handlefiles.validate_image(myform.file.data.stream)  # detect extension of image
            if detected_extension not in c.Config.ALLOWED_EXTENSIONS_IMAGES:
                flash('Incorrect file extension',
                      category="alert alert-danger")  # error if the extension is not allowed
                return render_template('forms/upload.html', form=myform, dark=current_user.dark)
            filename = str(uuid.uuid4()) + "." + detected_extension  # make new filename
            myform.file.data.save(app.config['IMAGE_UPLOADS'] + filename)  # save image under filename
            user = User.query.filter_by(id=current_user.id).first_or_404()  # get the user
            data = OCR.run(filename, user.use_taggun)  # run OCR, with users taggun option
            if not details:  # create new row if it doesn't exist
                details = reclaim_forms_details(date_receipt=data["date_receipt"], Total=data["Total"],
                                                image_name=filename, made_by=current_user.id, row_id=row,
                                                form_id=file_id)
                db.session.add(details)  # add to session
            else:
                details.date_receipt = data["date_receipt"]
                details.Total = round(float(data["Total"]), 2)
                details.image_name = filename  # results of OCR
            db.session.commit()  # commit to DB
        except AttributeError:  # if any of the database values do not exist, or there is an unexpected AttributeError
            flash("Please try again or use a different file.", category="alert alert-danger")
            return render_template('forms/upload.html', form=myform, dark=current_user.dark)
        if details.Total is None or details.date_receipt:  # If OCR could not find a value
            flash("Could not recognise price or total. Optical character recognition is never 100% accurate.",
                  category="alert alert-danger")
        else:  # General warning
            flash("Please check the information is correct. Optical character recognition is never 100% accurate.",
                  category="alert alert-secondary")
        return redirect("/edit_data/{}/{}".format(file_id, row))  # redirect to edit_data
    return render_template('forms/upload.html', form=myform, dark=current_user.dark)  # GET request


@app.route('/edit_data/<file_id>/<row>', methods=['GET', 'POST'])
@login_required
def edit_data(file_id, row):
    """
    :param file_id: ID of file in the database
    :param row: ID of the row which is to be access
    :return: HTML template contained in app/templates/forms
    Edit any data which came in through Mileage or Upload
    """
    myform = forms.editOutput()
    details = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
        form_id=file_id).filter_by(row_id=int(row)).first_or_404()  # get row of reclaim form
    accounts = db.session.query(Account_codes).all()  # find all account codes
    accounts_list = []
    for account in accounts:
        accounts_list.append([str(account.account_id), str(account.account_name)])  # append all acounts to a list
    if request.method == "POST":
        if myform.validate_on_submit():
            if myform.miles.data:  # if there is data for mileage
                if float(myform.miles.data) < 0 or float(myform.total.data) < 0:  # check if there are negatives
                    flash("Only input positive values", category="alert alert-danger")
                    return redirect(url_for('edit_data', file_id=file_id, row=row))  # reload
            else:  # if mileage isnt present, only total will be present, the below lines prevent an error from occuring
                if float(myform.total.data) < 0:  # check if there are negatives
                    flash("Only input positive values", category="alert alert-danger")
                    return redirect(url_for('edit_data', file_id=file_id, row=row))  # reload
            if details:  # if there is a reclaim form
                details.date_receipt = myform.date.data
                details.description = myform.description.data  # load data into DB
                details.miles = myform.miles.data
                # Format of account_id is for example: ART(110)-43214
                cost_centre = db.session.query(Account_codes).filter_by(
                    account_id=myform.accountCode.data).first_or_404()  # number associated with 3 letter code (110)
                account_code = myform.accountCode2.data  # this is the 43214 suffix
                if cost_centre.cost_centre:
                    details.account_id = "{}({})-{}".format(str(cost_centre.account_id), str(cost_centre.cost_centre),
                                                            str(account_code))  # format account_id
                else:  # some cost_centre values do not have a 3 digit number, so the letters only are used
                    details.account_id = "{}-{}".format(str(cost_centre.account_id), str(account_code))
                details.Total = myform.total.data if str(myform.total.data) != "None" else myform.miles.data * 0.45
                # multiply by mileage rate
                db.session.commit()  # commit changes to DB
                today = datetime.datetime.now().date()  # save today's date
                result = (today - datetime.datetime.strptime(details.date_receipt, '%d/%m/%Y').date()).days > 29
                if result:  # Give a warning that expense is older than 4 weeks
                    flash("Warning: the date of expense for row {} is older than 4 weeks.".format(str(int(row) - 6)),
                          category="alert alert-warning ")
            else:  # Throw error if details is not found
                flash("This row doesn't exist.", category="alert alert-danger")
            return redirect(url_for('edit_forms', file_id=file_id))
        elif "data" in dict(request.form):
            '''
            AJAX 
            To dynamically load options such as "flowers" from 3 letter "ART" in example above.
            Once an option for the first field ("ART") is selected, the below code will find associated options (such as
            Flowers, software or stationary, for example).
            '''
            return_cost_centers = db.session.query(cost_centres).filter_by(  # cost centres associated with 3 digit code
                cost_centre_id=dict(request.form)["data"]).all()  # dict(request.form)["data"] is the 3 letter code
            dict_cost_centres = {}
            for centre in return_cost_centers:
                dict_cost_centres[str(centre.purpose_id)] = centre.purpose_cost_centre
                # Associate purpose with code e.g. flowers with 12345
            if dict_cost_centres == {}:  # repeat the above but add all unique cost centres if the dict is empty
                return_cost_centers = db.session.query(db.distinct(cost_centres.purpose_cost_centre)).all()
                # return all unique cost centre purposes
                for centre in return_cost_centers:
                    individual_centre = db.session.query(cost_centres).filter_by(
                        purpose_cost_centre=list(centre)[0]).first_or_404()
                    dict_cost_centres[str(individual_centre.purpose_id)] = individual_centre.purpose_cost_centre
            dict_cost_centres["N/A"] = "N/A"  # add a N/A option
            return jsonify({"Data": dict_cost_centres})  # return dict
    # GET request
    myform.date.data = details.date_receipt
    myform.description.data = details.description
    try:
        current_account = details.account_id.split("-")  # E.g. [ART(110), 43214]
        current_account[0] = current_account[0].split("(")[0]  # get account code 3 letter code [ART, 43214]
        account = [
            db.session.query(Account_codes).filter_by(account_id=str(current_account[0])).first_or_404().account_id,
            db.session.query(Account_codes).filter_by(
                account_id=str(current_account[0])).first_or_404().account_name]  # e.g. [ART, Art department]
        if account in accounts_list:
            accounts_list.pop(accounts_list.index(account))  # pop selected account to avoid duplicate accounts
        cost_centre = [current_account[1], db.session.query(cost_centres).filter_by(
            purpose_id=current_account[1]).first_or_404().purpose_cost_centre] # Selected cost centre [43214, purpose]
    except:  # If nothing has been selected yet
        cost_centre = None
        account = None
    try:
        myform.total.data = round(float(details.Total), 2)  # Round total
    except:
        myform.total.data = ""  # Leave blank if there is not Total (OCR didn't recongnise it)
    if details.start: # if a route is attached
        origin = urllib.parse.quote_plus(details.destination) # put start and destination into url format
        destination = urllib.parse.quote_plus(details.start)
        myform.miles.data = details.miles  # load mileage into edit form
        return render_template('forms/form.html', form=myform, include=True, start=origin, end=destination,
                               dark=current_user.dark, accounts=accounts_list, account=account,
                               cost_centre=cost_centre)
    '''
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

        '''
    return render_template('forms/form.html', form=myform, filename=c.Config.IMAGE_ROUTE + details.image_name,
                           dark=current_user.dark, accounts=accounts_list, account=account, cost_centre=cost_centre)
    # Render same form, but with image of receipt instead of map


@app.route('/edit_forms/<file_id>', methods=['GET', 'POST'])
@login_required
def edit_forms(file_id):
    try:
        rows = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
            form_id=file_id).order_by(reclaim_forms_details.row_id).all()
        name = db.session.query(reclaim_forms).filter_by(id=file_id).first_or_404().filename
        mysum = 0
        for row in rows:
            if row.Total:
                mysum += float(row.Total)
            elif row.miles:
                row.Total = row.miles * 0.45
                mysum += float(row.Total)
            else:
                row.Total = 0
            if row.account_id == None:
                return redirect(url_for("delete_row", file_id=file_id, row=row.row_id))
        rows = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
            form_id=file_id).order_by(reclaim_forms_details.row_id).all()
        return render_template('forms/edit_forms.html', forms=rows, file_id=file_id, name=name, mysum=mysum,
                               dark=current_user.dark)
    except AttributeError:
        abort(404)


@app.route('/delete_row/<file_id>/<row>', methods=['GET', 'POST'])
@login_required
def delete_row(file_id, row):
    try:
        myrow = row
        row = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
            form_id=file_id).filter_by(row_id=int(row)).first_or_404()
        try:
            os.remove(os.path.join(app.config['IMAGE_UPLOADS'], row.image_name))
        except:
            pass
        row = reclaim_forms_details.query.filter_by(id=row.id)
        row.delete()
        rows = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
            form_id=file_id).order_by(reclaim_forms_details.row_id).all()
        for row in rows:
            if row.row_id > int(myrow):
                row.row_id -= 1
        db.session.commit()
        return redirect(url_for('edit_forms', file_id=file_id))
    except:
        return redirect(url_for('edit_forms', file_id=file_id))


@app.route('/delete_file/<file_id>', methods=['GET', 'POST'])
@login_required
def delete_file(file_id):
    rows = reclaim_forms_details.query.filter_by(form_id=file_id).all()
    for row in rows:
        try:
            os.remove(os.path.join(app.config['IMAGE_UPLOADS'], row.image_name))
        except:
            pass
    file = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(id=file_id)
    try:
        os.remove(os.path.join(app.Config["SIGNATURE_ROUTE"], file.first().signature))
    except:
        pass
    file.delete()
    db.session.commit()
    return redirect(url_for('view_forms'))


@app.route('/download/<file_id>', methods=['GET'])
@login_required
def download(file_id):
    try:
        file = handlefiles.createExcel(file_id, current_user)
        db.session.commit()
        return send_file(c.Config.DOWNLOAD_ROUTE + file.filename, as_attachment=True, cache_timeout=0)
    except:
        flash('Error downloading file. Try renaming your file.', category="alert alert-danger")
        return redirect(url_for("view_forms"))


@app.route('/view_forms', methods=['GET', 'POST'])
@app.route('/view_forms', methods=['GET', 'POST'])
@login_required
def view_forms(new_user=False):
    allforms = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).order_by(
        reclaim_forms.date_created.desc()).all()
    user = User.query.get(current_user.id)
    if user.accounting_email == None:
        myform = forms.modalSettings()
        new_user = True
        if myform.validate_on_submit():
            user.accounting_email = myform.accounting_email.data
            user.dark = myform.dark.data
            db.session.commit()
            return render_template('forms/view_forms.html', forms=allforms, dark=current_user.dark)
        return render_template('forms/view_forms.html', forms=allforms, dark=current_user.dark, setting=myform,
                               new_user=new_user)
    else:
        return render_template('forms/view_forms.html', forms=allforms, dark=current_user.dark)


@app.route('/new_form', methods=['GET', 'POST'])
@login_required
def new_form():
    myform = forms.newReclaim()
    user = User.query.filter_by(id=current_user.id).first()
    if myform.validate_on_submit():
        filename = handlefiles.validate_excel(myform.filename.data)
        id = str(uuid.uuid4())
        myform = reclaim_forms(id=id, filename=filename, description=myform.description.data,
                               sent="Draft",
                               made_by=current_user.id)
        db.session.add(myform)
        db.session.commit()
        flash("Successfully created the form: {}".format(filename), category="alert alert-success")
        return redirect(url_for('edit_forms', file_id=id))
    elif request.method == 'GET':
        myform.filename.data = datetime.datetime.today().strftime(
            '%m-%Y') + "_Expenses_form_" + user.last_name + ".xlsx"
    return render_template('forms/new_form.html', form=myform, title="Create a new form", dark=current_user.dark)


@app.route('/edit_form/<file>', methods=['GET', 'POST'])
@login_required
def edit_form(file):
    myform = forms.newReclaim()
    user = User.query.filter_by(id=current_user.id).first()
    myfile = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(id=file).first_or_404()
    if myform.validate_on_submit():
        filename = handlefiles.validate_excel(myform.filename.data)
        myfile.description = myform.description.data
        myfile.filename = filename
        db.session.commit()
        return redirect(url_for('view_forms'))
    elif request.method == 'GET':
        if myfile:
            myform.filename.data = myfile.filename
            myform.description.data = myfile.description
        else:
            myform.filename.data = "Expenses_form_" + user.last_name + ".xlsx"
    return render_template('forms/new_form.html', form=myform, title="Edit form", dark=current_user.dark, edit=True)


#  --> Adapted from https://blog.miguelgrinberg.com/

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('view_forms'))
    myform = forms.LoginForm()
    if myform.validate_on_submit():
        user = User.query.filter_by(email=myform.email.data).first()
        if user is None or not user.check_password(myform.password.data):
            flash('Invalid username or password', category="alert alert-danger")
            return redirect(url_for('login'))
        if user is None or not user.is_verified:
            flash(Markup(
                'Please check your emails to verify your email. Click <a href="{}" class="alert-link">here</a> to send another email.'.format(
                    url_for("verify_email_request"))), category="alert alert-danger")
            return redirect(url_for('login'))
        login_user(user, remember=myform.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('user/login.html', form=myform)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    myform = forms.RegistrationForm()
    if myform.validate_on_submit():
        user = User(first_name=myform.first_name.data, last_name=myform.last_name.data, email=myform.email.data)
        user.set_password(myform.password.data)
        db.session.add(user)
        db.session.commit()
        send_verify_email(user)
        logout_user()
        flash(Markup(
            'Congratulations, you are now a registered user! Please verify your email to login. Click <a href="{}" class="alert-link">here</a> to send another email.'.format(
                url_for("verify_email_request"))), category="alert alert-success")
        return redirect(url_for('login'))
    return render_template('user/register.html', title='Register', form_title='Register',
                           form=myform)


# <--

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    myform = forms.settings(current_user.id)
    user = User.query.get(current_user.id)
    if myform.validate_on_submit():
        user.first_name = myform.first_name.data
        user.last_name = myform.last_name.data
        user.accounting_email = myform.accounting_email.data
        if myform.email.data != user.email:
            user.email = myform.email.data
            user.is_verified = False
            send_verify_email(user)
            logout_user()
            flash(Markup(
                'You have been logged out. Please verify {} to login. Click <a href="{}" class="alert-link">here</a> to send another email.'.format(
                    myform.accounting_email.data, url_for("verify_email_request"))), category="alert alert-success")
        user.use_taggun = myform.taggun.data
        user.dark = myform.dark.data
        db.session.commit()
        return redirect(url_for('view_forms'))
    elif request.method == 'GET':
        myform.first_name.data = user.first_name
        myform.last_name.data = user.last_name
        myform.email.data = user.email
        myform.accounting_email.data = user.accounting_email
        myform.taggun.data = user.use_taggun
        myform.dark.data = user.dark
    return render_template('user/settings.html', form=myform, title="Settings", dark=current_user.dark,
                           email=user.email)


@app.route('/send/<file_id>', methods=['GET', 'POST'])
@login_required
def send(file_id):
    myform = forms.supervisor()
    if myform.validate_on_submit():
        user = User.query.get(current_user.id)
        file_db = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(id=file_id).first()
        sender = app.config['ADMINS'][0]
        subject = "Reclaim form from " + user.first_name + " " + user.last_name
        recipients = [myform.email_supervisor.data]
        token = user.get_token("sign_form", expires_in=10 ** 20)
        html_body = render_template('email/request_auth.html', token=token, user=user.first_name + " " + user.last_name)
        file = handlefiles.createExcel(file_id=file_id, current_user=current_user)
        try:
            send_email(subject=subject, sender=sender, recipients=recipients, html_body=html_body,
                       file=file.filename)
            file_db.sent = "Awaiting authorization"
            file_db.date_sent = datetime.datetime.utcnow()
            db.session.commit()
            flash("Email successfully sent to {}".format(myform.email_supervisor.data), category="alert alert-success")
        except:
            flash("Error sending email. Please try again later.", category="alert alert-danger")
        return redirect(url_for("index"))
    return render_template("email/manager_email.html", form=myform, dark=current_user.dark)


@app.route('/send_accounting/<file_id>/<user_id>', methods=['GET', 'POST'])
@login_required
def send_accounting(file_id, user_id):
    user = User.query.filter_by(id=user_id).first()
    file_db = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(id=file_id).first()
    sender = app.config['ADMINS'][0]
    subject = "Reclaim form from " + user.first_name + " " + user.last_name
    recipients = [user.accounting_email]
    html_body = render_template('email/sent_form.html', user=str(user.first_name + " " + user.last_name),
                                dark=current_user.dark)
    file = handlefiles.createExcel(file_id=file_id, current_user=current_user, signature=file_db.signature)
    try:
        send_email(subject=subject, sender=sender, recipients=recipients, html_body=html_body,
                   file=file.filename)
    except:
        pass
    return redirect(url_for("view_forms"))


#  --> Adapted from https://blog.miguelgrinberg.com/

@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    myform = forms.ResetPasswordRequestForm()
    if myform.validate_on_submit():
        user = User.query.filter_by(email=myform.email.data).first()
        if user:
            send_password_reset_email(user)
        flash('Check your email for the instructions to reset your password', category="alert alert-success")
        return redirect(url_for('login'))
    return render_template('user/request_password_reset.html', title='Reset Password', form=myform,
                           dark=current_user.dark)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_token(token, "reset_password")
    if not user:
        return redirect(url_for('index'))
    myform = forms.ResetPasswordForm()
    if myform.validate_on_submit():
        user.set_password(myform.password.data)
        db.session.commit()
        flash('Your password has been reset.', category="alert alert-success")
        return redirect(url_for('login'))
    return render_template('user/reset_password.html', form=myform)


# <--
@app.route('/verify_email/<token>', methods=['GET', 'POST'])
def verify_email(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_token(token, "verify_email")
    if not user:
        return redirect(url_for('index'))
    user.is_verified = True
    db.session.commit()
    flash('Your email has been verified.', category="alert alert-success")
    login_user(user)
    return redirect(url_for('index'))


@app.route('/verify_email_request', methods=['GET', 'POST'])
def verify_email_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    myform = forms.verfify_email()
    if myform.validate_on_submit():
        user = User.query.filter_by(email=myform.email.data).first()
        try:
            if user:
                send_verify_email(user)
            flash('Check {} to verify your mail.'.format(myform.email.data), category="alert alert-success")
        except:
            flash("Error sending email. Please try again later.", category="alert alert-danger")
        return redirect(url_for('login'))
    return render_template('user/verify_email.html', title='Reset Password', form=myform)


@app.route('/mileage/<file_id>/<row>', methods=['GET', 'POST'])
@login_required
def mileage(file_id, row):
    if row == "0":
        details = \
            db.session.query(db.func.max(reclaim_forms_details.row_id)).filter_by(made_by=current_user.id).filter_by(
                form_id=file_id).first()[0]
        if details:
            row = int(details) + 1
        else:
            row = 7
    myform = forms.description()
    details = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
        form_id=file_id).filter_by(row_id=int(row)).first()
    file = db.session.query(reclaim_forms).filter_by(id=file_id).first_or_404()
    if file.sent == "Authorized":
        file.sent = "Draft"
    if myform.validate_on_submit():
        # date validator
        end = datetime.datetime.strptime(myform.date_end.data, "%d/%m/%Y").date()
        start = datetime.datetime.strptime(myform.date_start.data, "%d/%m/%Y").date()
        if start > end:
            flash("Error: negative trip duration", category="alert alert-danger")
            return render_template('forms/miles.html', title="Add from mileage", form=myform, dark=current_user.dark,
                                   start=myform.start.data, end=myform.destination.data)
        description = "Description: " + myform.description.data + " Start: " + myform.start.data + " End: " + myform.destination.data + " Starting date: " + myform.date_start.data + " Ending date: " + myform.date_end.data + " Return trip: " + str(
            myform.return_trip.data)
        results = map.getMap(myform.start.data, myform.destination.data)
        if not details:
            if myform.return_trip.data:
                results[2] *= 2
                results[1] *= 2
            details = reclaim_forms_details(description=description, date_receipt=myform.date_start.data,
                                            made_by=current_user.id, row_id=row,
                                            form_id=file_id, start=myform.start.data,
                                            destination=myform.destination.data, miles=results[1],
                                            Total=round(float(results[2]), 2),
                                            end_date=myform.date_end.data, purpose=myform.description.data,
                                            return_trip=myform.return_trip.data)
            db.session.add(details)
            db.session.commit()
        else:
            details.description = description
            details.date_receipt = myform.date_end.data
            details.start = myform.start.data
            details.destination = myform.destination.data
            if myform.return_trip.data is True and details.return_trip is False:
                details.miles = results[1] * 2
                details.Total = round(float(results[2]), 2) * 2
            elif myform.return_trip.data is False and details.return_trip is True:
                details.miles = results[1] * 0.5
                details.Total = round(float(results[2]), 2) * 0.5
            else:
                details.miles = results[1]
                details.Total = round(float(results[2]), 2)
            details.end_date = myform.date_end.data
            details.purpose = myform.description.data
            details.return_trip = myform.return_trip.data
            db.session.commit()
        return redirect("/edit_data/{}/{}".format(file_id, row))
    elif request.method == 'GET':
        if details:
            myform.date_start.data = details.date_receipt
            myform.start.data = details.start
            myform.destination.data = details.destination
            myform.description.data = details.purpose
            myform.date_end.data = details.end_date
            myform.return_trip.data = details.return_trip
            if details.start:
                origin = urllib.parse.quote_plus(details.destination)
                destination = urllib.parse.quote_plus(details.start)
                return render_template('forms/miles.html', form=myform, start=origin, end=destination,
                                       dark=current_user.dark)
        myform.start.data = "Wellington College, Duke's Ride, RG457PU"
    return render_template('forms/miles.html', title="Add from mileage", form=myform, dark=current_user.dark)


@app.route('/delete_user', methods=['GET', 'POST'])
@login_required
def delete_user():
    files = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).all()
    for file in files:
        rows = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
            form_id=file.id).all()
        for row in rows:
            try:
                os.remove(os.path.join(app.config['IMAGE_UPLOADS'], row.image_name))
            except:
                pass
        reclaim_forms_details.query.filter_by(form_id=file.id).delete()
    db.session.query(reclaim_forms).filter_by(made_by=current_user.id).delete()
    User.query.filter_by(id=current_user.id).delete()
    db.session.commit()
    flash("Successfully deleted user account", category="alert alert-success")
    return redirect(url_for("logout"))


@app.route('/load_map/<start>/<end>', methods=['GET', 'POST'])
@login_required
def load_map(end, start):
    cords = map.getMap(start, end)[0]
    return render_template("iframes/map.html", cords=cords, key=c.Config.GOOGLEMAPS_KEY, dark=current_user.dark)


@app.route('/pie')
@login_required
def pie():
    values = []
    labels = []
    colours = []
    files = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).all()
    for file in files:
        if file.sent == "Authorized":
            rows = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
                form_id=file.id).all()
            for row in rows:
                if row.account_id in labels and row.account_id != None:
                    values[labels.index(row.account_id)] += row.Total
                elif row and row.account_id != None:
                    labels.append(row.account_id)
                    values.append(row.Total)
                else:
                    pass
    colours = handlefiles.createDistinctColours(len(labels) + 1)[:len(labels)]
    if values:
        return render_template('iframes/pie.html', title='Pie chart', values=values, labels=labels, colours=colours)
    else:
        values = [1]
        labels = ["No expenses forms authorized yet"]
        return render_template('iframes/pie.html', title='Pie chart', values=values, labels=labels, colours=colours)


@app.route('/line/<year>')  # define URL
@app.route('/line', defaults={'year': datetime.datetime.today().year})
@login_required  # user must be logged in to see content
def line(year):
    labels = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
              'November', 'December']  # labels at bottom of graph
    month = datetime.datetime.today().month  # current month
    labels = labels[:month + 1]  # display up to current month +1
    colours = []
    accounts = [{} for i in range(len(labels))]  # 12 dictionaries for each month
    unique_accounts = []  # keep track of unique accounts (for key at top)
    for i in range(1, 13):  # for every month        ----- This part of the function queries the database -----
        datestart = datetime.datetime(int(year), i, 1)  # starting date is first of month
        dateend = datestart + datetime.timedelta(days=31)  # ending date is 31 days later
        files = reclaim_forms.query.filter(reclaim_forms.date_sent >= datestart).filter(
            reclaim_forms.date_sent < dateend).filter(
            reclaim_forms.made_by == current_user.id).all()  # files sent in that month
        for file in files:  # for every file
            if file.sent == "Authorized":
                rows = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
                    form_id=file.id).all()  # rows of given file
                for row in rows:  # for every row
                    if row.account_id is not None:  # if a row id exists (not None because a row id 0 could exist)
                        if row.account_id in accounts[i - 1].keys():  # if the account is already added to dictionary
                            pass  # I add all accounts to a dictionary in a list of months this way I can track Totals
                        else:
                            accounts[i - 1][
                                row.account_id] = 0  # Add a account code to dictionary for month with value 0
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
            if current_index != None:  # if the data point is in the correct position
                pass  # do nothing
            else:  # if the data point is in the wrong position
                # ----Lines 523 to 526 find the index of the total of the month before (if it remains constant)
                indexBefore = None
                for i in account:  # for every month in the account code
                    if i[1] == current_month:  # if the month of a data point is equal to the month iterator
                        indexBefore = account.index(i)  # The indexBefore varaible is this datapoint index
                if indexBefore is not None:  # if the dataPoint for an account code does not exist
                    data[data.index(account)].append([account[indexBefore][0], current_month])
                    # append [the previous months value, month]
                else:
                    # If there is no datapoint before, just append [0, month]
                    data[data.index(account)].append([0, current_month])
        data[data.index(account)] = sorted(account, key=lambda l: l[1])  # Sort the array
    for account in data:
        for j in range(1, len(account)):
            data[data.index(account)][j][0] += account[j - 1][0]  # Create a cumulative nature to the data points
    for account in data:
        for j in account:
            data[data.index(account)][account.index(j)] = j[0]  # Get rid of the month in [total, month]
    total = np.array([0 for i in range(month)])  # Now create a np array for the totals (allows for array adding)
    for account in data:  # for every account
        account = np.array(account)  # Make account and np array
        total = np.add(total, account)  # Add account totals to the overall Total
    total = list(total)  # Turn total back to a normal array
    data.append(total)  # Append to data
    unique_accounts.append("Total")  # Append to key at top
    if unique_accounts == ['Total']:
        unique_accounts = ["No expenses forms authorized yet"]
        colours = ['#E5E5E5']
    else:
        colours = handlefiles.createDistinctColours(len(unique_accounts))  # Create distinct colours
    return render_template('iframes/line.html', labels=labels, set=zip(data, unique_accounts, colours))  # To template


@app.route('/sign_form/<form_hash>', methods=['GET', 'POST'])
@login_required
def sign_form(form_hash):
    user = User.query.get(current_user.id)
    for_user = User.verify_token(form_hash, "sign_form")
    if for_user:
        name = for_user.first_name + " " + for_user.last_name
        data = handlefiles.createSignatureBack(user.first_name, user.last_name)
        if request.method == 'POST':
            form = db.session.query(reclaim_forms).filter_by(made_by=for_user.id).first()
            if request.data:
                if form.sent == "Awaiting authorization":
                    bytes = bytearray(request.data)
                    image = Image.open(io.BytesIO(bytes))
                    signature = str(uuid.uuid4()) + ".png"
                    image.save(c.Config.SIGNATURE_ROUTE + signature)
                    form.signature = signature
                    form.sent = "Authorized"
                    send_auth_email(for_user, user.email)
                    form.date_sent = datetime.datetime.utcnow()
                    db.session.commit()
                    flash("Signed expenses form successfully for {}!".format(name), category="alert alert-success")
                    return jsonify({"redirect": "/send_accounting/{}/{}".format(form.id, for_user.id)})
                flash("This authorization link has expired.")
                return jsonify({"redirect": "/index"})
            else:
                try:
                    send_reject_email(for_user, user.email)
                    flash("Rejected form for {}. He/She has been notified.".format(name),
                          category="alert alert-success")
                except:
                    flash("Rejected form for {}. There was an error in sending an email to him/her.".format(name),
                          category="alert alert-danger")
                form.sent = "Rejected"
                db.session.commit()
                return jsonify({"redirect": "/index"})
        return render_template('manager/sign_form.html', background=data, for_user=name)
    abort(400)
