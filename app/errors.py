from flask import render_template
from app import app, db
from app.models import User
from flask_login import current_user
from app.emails import send_email


@app.errorhandler(400)
def bad_request():
    if current_user.is_authenticated:
        dark = current_user.dark
    else:
        dark = None
    return render_template('errors/400.html', dark=dark), 400


#  --> Adapted from https://blog.miguelgrinberg.com/

@app.errorhandler(404)
def not_found_error():
    if current_user.is_authenticated:
        dark = current_user.dark
    else:
        dark = None
    return render_template('errors/404.html', dark=dark), 404


@app.errorhandler(500)
def internal_error(error):
    if current_user.is_authenticated:
        dark = current_user.dark
    else:
        dark = None
    email(error, 500)
    db.session.rollback()
    return render_template('errors/500.html', error=error, dark=dark), 500


# <--

def email(error, code):
    subject = "Error {} in IA".format(str(code))
    recipients = ["samonij@wellingtoncollege.org.uk"]
    user = User.query.filter_by(id=current_user.id).first().email
    send_email(subject,
               sender=app.config['ADMINS'][0],
               recipients=recipients,
               html_body="<p>{}<p/><p>User = {}<p/>".format(error, user))
