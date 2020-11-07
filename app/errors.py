from flask import render_template
from app import app, db
from flask_login import current_user
from app.emails import send_error_email


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
        send_error_email(error, 500, current_user.id)
    else:
        dark = None
    send_error_email(error, 500, None)
    db.session.rollback()
    return render_template('errors/500.html', error=error, dark=dark), 500


# <--
