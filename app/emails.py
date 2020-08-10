from flask_mail import Message
from app import mail, app
from flask import render_template
from threading import Thread
import config as c

#  --> Adapted from https://blog.miguelgrinberg.com/

def send_async_email(app, msg):
    mail.connect()
    with app.app_context():
        mail.send(msg)

def send_email(subject, sender, recipients, text_body, html_body, file=None):
    msg = Message(subject, sender=sender, recipients=recipients)
    if file:
        with app.open_resource(c.Config.DOWNLOAD_ROUTE+ file) as fp:
            msg.attach(filename=file, content_type ="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", data=fp.read())
    msg.body = text_body
    msg.html = html_body
    Thread(target=send_async_email, args=(app, msg)).start()

def send_password_reset_email(user):
    token = user.get_reset_password_token()
    send_email('[Accounting app] Reset Your Password',
               sender=app.config['ADMINS'][0],
               recipients=[user.email],
               text_body=render_template('email/reset_password.html',
                                         user=user, token=token),
               html_body=render_template('email/reset_password.html',
                                         user=user, token=token))

# <--