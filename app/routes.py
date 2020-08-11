# routes.py
from app import app, handlefiles, OCR, forms, db, handleExcel
from app.models import reclaim_forms, reclaim_forms_details, User
from app.emails import send_password_reset_email, send_email
from flask import Flask, request, redirect, flash, render_template, abort, url_for, send_file, after_this_request
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.urls import url_parse
import config as c
import uuid
import datetime
import os


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
                abort(400)
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
                details.Total = data["Total"]
                details.image_name = filename

                flash(details.date_receipt)
                db.session.commit()
        except AttributeError:
            flash("Please try again or use a different file.", category="alert alert-danger")
            return render_template('upload.html', form=myform)
        return redirect("/edit_data/{}/{}/{}".format(file_id, row, adding))
    return render_template('upload.html', form=myform)


@app.route('/edit_data/<file_id>/<row>', defaults={'adding': True}, methods=['GET', 'POST'])
@app.route('/edit_data/<file_id>/<row>/<adding>', methods=['GET', 'POST'])
@login_required
def edit_data(file_id, row, adding):
    myform = forms.editOutput()
    details = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
        form_id=file_id).filter_by(row_id=int(row)).first_or_404()
    if myform.validate_on_submit():
        if str(myform.miles.data) == "None" or str(myform.total.data) == "None":
            flash("Row successfully added", category="alert alert-success")
        else:
            flash("Either enter miles or total: miles is automatically calculated.", category="alert alert-danger")
            return redirect(url_for("edit_data", file_id=file_id, row=row, adding=adding))
        details = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
            form_id=file_id).filter_by(row_id=int(row)).first()
        if details:
            details.date_receipt = myform.date.data
            details.description = myform.description.data
            details.miles = myform.miles.data
            details.account_id = myform.accountCode.data
            details.Total = myform.total.data if str(myform.total.data) != "None" else myform.miles.data * 0.45
            db.session.commit()
        else:
            flash("This row doesn't exist.", category="alert alert-danger")
        return redirect('/edit_forms/' + file_id)
    elif request.method == 'GET':
        myform.date.data = details.date_receipt
        myform.description.data = details.description
        myform.miles.data = details.miles
        myform.accountCode.data = details.account_id
        myform.total.data = details.Total
    return render_template('form.html', form=myform, filename=c.Config.IMAGE_ROUTE + details.image_name)


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
            if not row.description:
                return redirect(url_for("delete_row", file_id=file_id, row=row.row_id))
        rows = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
            form_id=file_id).order_by(reclaim_forms_details.row_id).all()
        return render_template('edit_forms.html', forms=rows, file_id=file_id, name=name, mysum=mysum)
    except AttributeError:
        abort(404)


@app.route('/delete_row/<file_id>/<row>', methods=['GET', 'POST'])
@login_required
def delete_row(file_id, row):
    try:
        myrow = row
        row = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(
            form_id=file_id).filter_by(row_id=int(row)).first_or_404()
        os.remove(os.path.join(app.config['IMAGE_UPLOADS'], row.image_name))
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


@app.route('/download/<file_id>', methods=['GET', 'POST'])
@login_required
def download(file_id):
    file = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(id=file_id).first()
    rows = db.session.query(reclaim_forms_details).filter_by(made_by=current_user.id).filter_by(form_id=file_id).all()
    user = User.query.get(current_user.id)
    date = datetime.datetime.now().strftime("%d/%m/%Y")
    handleExcel.requirements([user.first_name, user.last_name], str(date), file.filename)
    for row in rows:
        info = [row.date_receipt, row.description, row.miles, row.account_id,
                row.Total]
        handleExcel.editRow(info, file.filename, row.row_id)
        if row.miles:
            handleExcel.addImages(file.filename, row.row_id, row.image_name)
    return send_file(c.Config.DOWNLOAD_ROUTE + file.filename, as_attachment=True)


@app.route('/view_forms', methods=['GET', 'POST'])
@login_required
def view_forms():
    forms = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).order_by(
        reclaim_forms.date_created).all()
    return render_template('view_forms.html', forms=forms)


@app.route('/new_form', methods=['GET', 'POST'])
@login_required
def new_form():
    myform = forms.newReclaim()
    user = User.query.filter_by(id=current_user.id).first()
    if myform.validate_on_submit():
        filename = handlefiles.validate_excel(myform.filename.data)
        myform = reclaim_forms(id=str(uuid.uuid4()), filename=filename, description=myform.description.data,
                               sent=False,
                               made_by=current_user.id)
        db.session.add(myform)
        db.session.commit()
        return redirect(url_for('view_forms'))
    elif request.method == 'GET':
        myform.filename.data = "Expenses_form_"+user.last_name+".xlsx"
    return render_template('new_form.html', form=myform, title="Create a new form")

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
    return render_template('login.html', form=myform)


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
    return render_template('register.html', title='Register', form_title='Register',
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
        db.session.commit()
        return redirect(url_for('view_forms'))
    elif request.method == 'GET':
        myform.first_name.data = user.first_name
        myform.last_name.data = user.last_name
        myform.email.data = user.email
        myform.accounting_email.data = user.accounting_email
        myform.taggun.data = user.use_taggun
    return render_template('settings.html', form=myform, title="Settings")


@app.route('/send/<file_id>', methods=['GET', 'POST'])
@login_required
def send(file_id):
    user = User.query.filter_by(id=current_user.id).first()
    file = db.session.query(reclaim_forms).filter_by(made_by=current_user.id).filter_by(id=file_id).first()
    sender = app.config['ADMINS'][0]
    subject = "Reclaim form from " + user.first_name + user.last_name
    recipients = [user.accounting_email]
    text_body = render_template('email/sent_form.html', user=str(user.first_name + " " + user.last_name))
    html_body = render_template('email/sent_form.html', user=str(user.first_name + " " + user.last_name))
    file = file.filename
    try:
        send_email(subject=subject, sender=sender, recipients=recipients, text_body=text_body, html_body=html_body,
                   file=file)
        file.sent = 1
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
    return render_template('request_password_reset.html', title='Reset Password', form=myform)


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
        flash('Your password has been reset.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=myform)

# <--
