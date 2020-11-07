from app import app
from app.models import User
from flask import render_template
from app.models import get_token
import config as c
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (Mail, Attachment, FileContent, FileName, FileType, Disposition)
import base64


#  --> Adapted from https://app.sendgrid.com/guide/integrate/langs/python

def send_email(subject, sender, recipients, html_body, file=None):
    msg = Mail(from_email=sender, to_emails=recipients, subject=subject, html_content=html_body)
    if file:
        with open(c.Config.RECLAIM_ROUTE + file, "rb") as f:
            data = f.read()
            f.close()
        encoded_file = base64.b64encode(data).decode()
        attached_file = Attachment(
            FileContent(encoded_file),
            FileName(file),
            FileType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            Disposition("attachment")
        )
        msg.attachment = attached_file
        sg = SendGridAPIClient(c.Config.SENDGRID_API_KEY)
        response = sg.send(msg)
        app.logger.info([response.status_code, response.headers, response.body])


def send_password_reset_email(user):
    token = get_token(my_object=user, word="reset_password", user=user)
    send_email('[Accounting app] Reset Your Password',
               sender=app.config['ADMINS'][0],
               recipients=[user.email],
               html_body=render_template('email/reset_password.html',
                                         user=user, token=token))


# <--
def send_verify_email(user):
    token = get_token(my_object=user, word="verify_email", user=user)
    send_email('[Accounting app] Confirm your email',
               sender=app.config['ADMINS'][0],
               recipients=[user.email],
               html_body=render_template('email/confirm_email.html',
                                         user=user, token=token))


def send_auth_email(user, mail):
    send_email('[Accounting app] Authorisation confirmation',
               sender=app.config['ADMINS'][0],
               recipients=[user.email],
               html_body=render_template('email/authed.html',
                                         user=user, auth_party=mail))


def send_reject_email(user, mail):
    send_email('[Accounting app] Authorisation declined',
               sender=app.config['ADMINS'][0],
               recipients=[user.email],
               html_body=render_template('email/not_authed.html',
                                         user=user, auth_party=mail))


def send_error_email(error, code, user):
    subject = "Error {} in IA".format(str(code))
    recipients = app.config['ADMINS'][1]
    try:
        user = User.query.filter_by(id=user).first().email
    except AttributeError:
        pass
    send_email(subject,
               sender=app.config['ADMINS'][0],
               recipients=recipients,
               html_body=render_template("email/Error.html", error=error, user=user))
