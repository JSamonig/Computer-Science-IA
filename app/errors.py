from flask import render_template
from app import app, db
from flask_login import current_user
from app.emails import send_error_email


@app.errorhandler(400)
def bad_request(error):
    """
    :param error: Error message
    """
    # parameter error is needed to avoid TypeError: not_found_error() takes 0 positional arguments but 1 was given
    if current_user.is_authenticated:
        dark = current_user.dark
    else:
        dark = None
    return render_template('errors/400.html', dark=dark), 400


#  --> Adapted from https://blog.miguelgrinberg.com/

@app.errorhandler(404)
def not_found_error(error):
    """
    :param error: Error message
    """
    # parameter error is needed to avoid TypeError: not_found_error() takes 0 positional arguments but 1 was given
    if current_user.is_authenticated:
        dark = current_user.dark
    else:
        dark = None
    return render_template('errors/404.html', dark=dark), 404


@app.errorhandler(500)
def internal_error(error):
    """
    :param error: Error message
    """
    # parameter error is needed to avoid TypeError: not_found_error() takes 0 positional arguments but 1 was given
    if current_user.is_authenticated:
        dark = current_user.dark
        send_error_email(error, 500, current_user.id)
    else:
        dark = None
    send_error_email(error, 500, None)  # send an email to Admin notifying of 500 error
    db.session.rollback()  # rollback any database changes
    return render_template('errors/500.html', error=error, dark=dark), 500

# <--
