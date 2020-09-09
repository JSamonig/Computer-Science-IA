# routes.py importing modules and libraries
from app import app, handlefiles, OCR, forms, db, handleExcel, map
from app.models import reclaim_forms, reclaim_forms_details, User
from app.emails import send_password_reset_email, send_email
from flask import Flask, request, redirect, flash, render_template, abort, url_for, send_file
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.urls import url_parse
import config as c
import urllib.parse
import uuid
import datetime
import os
import numpy as np


@app.route('/')
@app.route('/index')
def index():
    return redirect(url_for("view_forms"))


@app.route('/upload/<file_id>/<row>', defaults={'adding': True}, methods=['GET', 'POST'])
@app.route('/upload/<file_id>/<row>/<adding>', methods=['GET', 'POST'])
@login_required
def upload(file_id, row, adding):
    if adding == "True" or row == "0":
        details = \
            db.session.query(db.func.max(reclaim_forms_details.row_id)).filter_by(made_by=current_user.id).filter_by(
                form_id=file_id).first()[0]
        if details:
            row = int(details) + 1
        else:
            row = 7
    myform = forms.uploadForm()
    if myform.validate_on_submit():
        try:
            details = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
                form_id=file_id).filter_by(row_id=int(row)).first()
            if details:
                if details.image_name:
                    os.remove(os.path.join(app.config['IMAGE_UPLOADS'], details.image_name))
            detected_extension = handlefiles.validate_image(myform.file.data.stream)
            if detected_extension not in c.Config.ALLOWED_EXTENSIONS_IMAGES:
                flash('Incorrect file extension', category="alert alert-danger")
                return render_template('forms/upload.html', form=myform, dark=current_user.dark)
            filename = str(uuid.uuid4()) + "." + detected_extension
            myform.file.data.save(app.config['IMAGE_UPLOADS'] + filename)
            user = User.query.filter_by(id=current_user.id).first()
            data = OCR.run(filename, user.use_taggun)
            if not details:
                details = reclaim_forms_details(date_receipt=data["date_receipt"], Total=data["Total"],
                                                image_name=filename, made_by=current_user.id, row_id=row,
                                                form_id=file_id)
                db.session.add(details)
                db.session.commit()
            else:
                details.date_receipt = data["date_receipt"]
                details.Total = round(float(data["Total"]), 2)
                details.image_name = filename
                db.session.commit()
        except AttributeError:
            flash("Please try again or use a different file.", category="alert alert-danger")
            return render_template('forms/upload.html', form=myform, dark=current_user.dark)
        flash("Please check the information is correct. Optical character recognition is never 100% accurate.",
              category="alert alert-secondary")
        return redirect("/edit_data/{}/{}/{}".format(file_id, row, adding))
    return render_template('forms/upload.html', form=myform, dark=current_user.dark)


@app.route('/edit_data/<file_id>/<row>', defaults={'adding': True}, methods=['GET', 'POST'])
@app.route('/edit_data/<file_id>/<row>/<adding>', methods=['GET', 'POST'])
@login_required
def edit_data(file_id, row, adding):
    myform = forms.editOutput()
    details = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
        form_id=file_id).filter_by(row_id=int(row)).first_or_404()
    if myform.validate_on_submit():
        details = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
            form_id=file_id).filter_by(row_id=int(row)).first()
        if myform.miles.data:
            if float(myform.miles.data) < 0 or float(myform.total.data) < 0:
                flash("Only input positive values", category="alert alert-danger")
                return redirect(url_for('edit_data', file_id=file_id, row=row, adding=adding))
        else:
            if float(myform.total.data) < 0:
                flash("Only input positive values", category="alert alert-danger")
                return redirect(url_for('edit_data', file_id=file_id, row=row, adding=adding))
        if details:
            details.date_receipt = myform.date.data
            details.description = myform.description.data
            details.miles = myform.miles.data
            details.account_id = myform.accountCode.data
            details.Total = myform.total.data if str(myform.total.data) != "None" else myform.miles.data * 0.45
            db.session.commit()
            today = datetime.datetime.now().date()
            result = (today - datetime.datetime.strptime(details.date_receipt, '%d/%m/%Y').date()).days > 29
            if result:
                flash("Warning: the date of expense for row {} is older than 4 weeks.".format(str(int(row) - 6)),
                      category="alert alert-warning ")
        else:
            flash("This row doesn't exist.", category="alert alert-danger")
        return redirect(url_for('edit_forms', file_id=file_id))
    else:
        myform.date.data = details.date_receipt
        myform.description.data = details.description
        myform.accountCode.data = details.account_id
        myform.total.data = details.Total
        if details.start:
            origin = urllib.parse.quote_plus(details.destination)
            destination = urllib.parse.quote_plus(details.start)
            results = map.getMap(origin, destination)
            myform.total.data = round(float(results[2]), 2)
            myform.miles.data = results[1]
            return render_template('forms/form.html', form=myform, include=True, start=origin, end=destination,
                                   dark=current_user.dark)
        return render_template('forms/form.html', form=myform, filename=c.Config.IMAGE_ROUTE + details.image_name,
                               dark=current_user.dark)


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
    rows = reclaim_forms_details.query.filter_by(form_id=file_id).delete()
    file = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(
        id=file_id).delete()
    db.session.commit()
    return redirect(url_for('view_forms'))


@app.route('/download/<file_id>', methods=['GET'])
@login_required
def download(file_id):
    try:
        file = handlefiles.createExcel(file_id, current_user)
        file.date_sent = datetime.datetime.utcnow()
        db.session.commit()
        return send_file(c.Config.DOWNLOAD_ROUTE + file.filename, as_attachment=True, cache_timeout=0)
    except:
        flash('Error downloading file. Try renaming your file.', category="alert alert-danger")
        return redirect(url_for("view_forms"))


@app.route('/view_forms', methods=['GET', 'POST'])
@login_required
def view_forms():
    forms = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).order_by(
        reclaim_forms.date_created.desc()).all()
    return render_template('forms/view_forms.html', forms=forms, dark=current_user.dark)


@app.route('/new_form', methods=['GET', 'POST'])
@login_required
def new_form():
    myform = forms.newReclaim()
    user = User.query.filter_by(id=current_user.id).first()
    if myform.validate_on_submit():
        filename = handlefiles.validate_excel(myform.filename.data)
        id=str(uuid.uuid4())
        myform = reclaim_forms(id=id, filename=filename, description=myform.description.data,
                               sent=False,
                               made_by=current_user.id)
        db.session.add(myform)
        db.session.commit()
        return redirect(url_for('edit_forms', file_id=id))
    elif request.method == 'GET':

        myform.filename.data = datetime.datetime.today().strftime('%m-%Y')+"_Expenses_form_" + user.last_name + ".xlsx"
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
    return render_template('forms/new_form.html', form=myform, title="Edit form", dark=current_user.dark)


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
        flash('Congratulations, you are now a registered user!', category='alert alert-success')
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
        user.email = myform.email.data
        user.accounting_email = myform.accounting_email.data
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
    return render_template('user/settings.html', form=myform, title="Settings", dark=current_user.dark)


@app.route('/send/<file_id>', methods=['GET', 'POST'])
@login_required
def send(file_id):
    user = User.query.filter_by(id=current_user.id).first()
    file_db = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(id=file_id).first()
    sender = app.config['ADMINS'][0]
    subject = "Reclaim form from " + user.first_name + " " + user.last_name
    recipients = [user.accounting_email]
    html_body = render_template('email/sent_form.html', user=str(user.first_name + " " + user.last_name),
                                dark=current_user.dark)
    file = handlefiles.createExcel(file_id=file_id, current_user=current_user)
    try:
        send_email(subject=subject, sender=sender, recipients=recipients, html_body=html_body,
                   file=file.filename)
        file_db.sent = 1
        file_db.date_sent = datetime.datetime.utcnow()
        db.session.commit()
        flash("Email successfully sent to {}".format(user.accounting_email), category="alert alert-success")
    except:
        flash("Error sending email. Please try again later.", category="alert alert-danger")
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
    return render_template('user/request_password_reset.html', title='Reset Password', form=myform)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
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

@app.route('/mileage/<file_id>/<row>', defaults={'adding': True}, methods=['GET', 'POST'])
@app.route('/mileage/<file_id>/<row>/<adding>', methods=['GET', 'POST'])
@login_required
def mileage(file_id, row, adding):
    if adding == "True" or row == "0":
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
    if myform.validate_on_submit():
        # date validator
        end = datetime.datetime.strptime(myform.date_end.data, "%d/%m/%Y").date()
        start = datetime.datetime.strptime(myform.date_start.data, "%d/%m/%Y").date()
        if start > end:
            flash("Error: negative trip duration", category="alert alert-danger")
            return render_template('forms/miles.html', title="Add from mileage", form=myform, dark=current_user.dark,
                                   start=myform.start.data, end=myform.destination.data)
        description = "Description: " + myform.description.data + " Start: " + myform.start.data + " End: " + myform.destination.data + " Starting date: " + myform.date_start.data + " Ending date: " + myform.date_end.data
        results = map.getMap(myform.start.data, myform.destination.data)
        if not details:
            details = reclaim_forms_details(description=description, date_receipt=myform.date_start.data,
                                            made_by=current_user.id, row_id=row,
                                            form_id=file_id, start=myform.start.data,
                                            destination=myform.destination.data, miles=results[1],
                                            Total=round(float(results[2]), 2),
                                            end_date=myform.date_end.data, purpose=myform.description.data)
            db.session.add(details)
            db.session.commit()
        else:
            details.description = description
            details.date_receipt = myform.date_end.data
            details.start = myform.start.data
            details.destination = myform.destination.data
            details.miles = results[1]
            details.Total = round(float(results[2]), 2)
            details.end_date = myform.date_end.data
            details.purpose = myform.description.data
            db.session.commit()
        return redirect("/edit_data/{}/{}/{}".format(file_id, row, adding))
    elif request.method == 'GET':
        if details:
            myform.date_start.data = details.date_receipt
            myform.start.data = details.start
            myform.destination.data = details.destination
            myform.description.data = details.purpose
            myform.date_end.data = details.end_date
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

    return render_template('iframes/pie.html', title='Pie chart', values=values, labels=labels, colours=colours)


@app.route('/line/<year>')  # define URL
@app.route('/line', defaults={'year': datetime.datetime.today().year})
@login_required  # user must be logged in to see content
def line(year):
    labels = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
              'November', 'December']  # lables at bottom of graph
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
            rows = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
                form_id=file.id).all()  # rows of given file
            for row in rows:  # for every row
                if row.account_id is not None:  # if a row id exists (not None because a row id 0 could exist)
                    if row.account_id in accounts[i - 1].keys():  # if the account is already added to dictionary
                        pass  # I add all accounts to a dictionary in a list of months this way I can track Totals
                    else:
                        accounts[i - 1][row.account_id] = 0  # Add a account code to dictionary for month with value 0
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
    colours = handlefiles.createDistinctColours(len(unique_accounts))  # Create distinct colours
    return render_template('iframes/line.html', labels=labels, set=zip(data, unique_accounts, colours))  # To template
