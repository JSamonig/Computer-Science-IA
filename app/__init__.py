from flask import Flask
import config as c
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
from flask_fontawesome import FontAwesome
from flask_moment import Moment
import logging
from logging.handlers import RotatingFileHandler
import os

#  --> Adapted from https://blog.miguelgrinberg.com/
app = Flask(__name__)
app.config.from_object(c.Config)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
bootstrap = Bootstrap(app)
login = LoginManager(app)
login.login_view = 'login'
login.login_message_category = "alert alert-danger"
fa = FontAwesome(app)
moment = Moment(app)

from app import routes, models, errors


if not app.debug:
    # ...
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240,
                                       backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('App startup')

# <--