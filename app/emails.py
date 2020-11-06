from app import app
from flask import render_template, flash
from app.models import get_token
from threading import Thread
import config as c
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (Mail, Attachment, FileContent, FileName, FileType, Disposition)
import base64
import sys


#  --> Adapted from https://blog.miguelgrinberg.com/, https://app.sendgrid.com/guide/integrate/langs/python and
# https://stackoverflow.com/questions/1854216/raise-unhandled-exceptions-in-a-thread-in-the-main-thread

class send_async_email():
    def __init__(self, msg):
        self.msg = msg
        self.result = None
        self.exc_info = None

    def send_async_email_func(self):
        sg = SendGridAPIClient(c.Config.SENDGRID_API_KEY)
        response = sg.send(self.msg)
        return response.status_code

    def send(self):
        try:
            sg = SendGridAPIClient(c.Config.SENDGRID_API_KEY)
            self.result = sg.send(self.msg)
        except Exception as e:
            self.exc_info = sys.exc_info()

    def main(self):
        Thread(target=self.send).start()
        if self.exc_info:
            raise self.exc_info[1].with_traceback(self.exc_info[2])
        return self.result


def send_email(subject, sender, recipients, html_body, file=None):
    msg = Mail(from_email=sender, to_emails=recipients, subject=subject, html_content=html_body)
    if file:
        with open(c.Config.RECLAIM_ROUTE + file, "rb") as f:
            data = f.read()
            f.close()
        encoded_file = base64.b64encode(data).decode()
        attachedFile = Attachment(
            FileContent(encoded_file),
            FileName(file),
            FileType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            Disposition("attachment")
        )
        msg.attachment = attachedFile
    mail = send_async_email(msg=msg)
    mail.main()


def send_password_reset_email(user):
    token = get_token(my_object=user, word="reset_password")
    send_email('[Accounting app] Reset Your Password',
               sender=app.config['ADMINS'][0],
               recipients=[user.email],
               html_body=render_template('email/reset_password.html',
                                         user=user, token=token))


# <--
def send_verify_email(user):
    token = get_token(my_object=user, word="verify_email")
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
