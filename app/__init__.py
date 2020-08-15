from flask import Flask
import config as c
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
from flask_fontawesome import FontAwesome
from flask_sendgrid import SendGrid
from flask_mail import Mail

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

from app import routes, models, errors

# <--
