from flask import render_template
from app import app, db


@app.errorhandler(400)
def bad_request(error):
    return render_template('errors/400.html'), 400

#  --> Adapted from https://blog.miguelgrinberg.com/

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html', error=error), 500

# <--
