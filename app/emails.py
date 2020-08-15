from app import app
from flask import render_template
from threading import Thread
import config as c
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (Mail, Attachment, FileContent, FileName, FileType, Disposition)
import base64


#  --> Adapted from https://blog.miguelgrinberg.com/ and https://app.sendgrid.com/guide/integrate/langs/python

def send_async_email(app, msg):
    try:
        sg = SendGridAPIClient(c.Config.SENDGRID_API_KEY)
        response = sg.send(msg)
        print(response.status_code)
        print(response.body)
        print(response.headers)
    except Exception as e:
        print(e)


def send_email(subject, sender, recipients, html_body, file=None):
    msg = Mail(from_email=sender, to_emails=recipients, subject=subject, html_content=html_body)
    if file:
        import os
        print(os.path.dirname(os.path.realpath(__file__)))
        with open("./app/" + c.Config.DOWNLOAD_ROUTE + file, "rb") as f:
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
    Thread(target=send_async_email, args=(app, msg)).start()


def send_password_reset_email(user):
    token = user.get_reset_password_token()
    send_email('[Accounting app] Reset Your Password',
               sender=app.config['ADMINS'][0],
               recipients=[user.email],
               html_body=render_template('email/reset_password.html',
                                         user=user, token=token))

# <--
