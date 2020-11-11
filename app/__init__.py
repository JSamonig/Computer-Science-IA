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
from flask_wtf import CSRFProtect
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

#  --> Adapted from https://blog.miguelgrinberg.com/
app = Flask(__name__)
app.config.from_object(c.Config)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
bootstrap = Bootstrap(app)
login = LoginManager(app)
login.login_view = "login"
login.login_message_category = "alert alert-danger"
# initial message of along the lines of you need to log in to access this page will be in red ("alert-danger")
fa = FontAwesome(app)
moment = Moment(app)
CSRFProtect(app)
sentry_sdk.init(
    dsn="https://0386a46bc44b4d91b52e0253aec73695@o474175.ingest.sentry.io/5510069",
    integrations=[FlaskIntegration()],
    traces_sample_rate=1.0,
)
# sentry logging

from app import routes, models, errors

if not app.debug:
    # Adapted from https://blog.miguelgrinberg.com/
    # Logging
    if not os.path.exists("logs"):
        os.mkdir("logs")
    file_handler = RotatingFileHandler("logs/app.log", maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("App startup")
# <--
