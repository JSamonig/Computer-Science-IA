# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv

# load secret values from an environment file
load_dotenv("config.env", encoding="utf8")
# set base directory
basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    SECRET_KEY = os.environ.get("SECRET_KEY")
    IMAGE_UPLOADS = "./app/static/uploads/images/receipts/"
    IMAGE_ROUTE = "/static/uploads/images/receipts/"
    SIGNATURE_ROUTE = "./app/static/uploads/images/signatures/"
    RECLAIM_ROUTE = "./app/static/reclaims/"
    DOWNLOAD_ROUTE = "./static/reclaims/"
    STATIC = "./app/static/"
    TESSERACT_LOCATION = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    ALLOWED_EXTENSIONS_IMAGES = ["png", "jpg", "jpeg", "heif", "heic", "jfif"]
    MILEAGE_RATE = 0.45
    PRICE_PATTERN = "^(([$€£]?)( *)(\d{1,})((,|\.)(\d{0,}))?)( *)([$€£]?)$"
    DATE_PATTERN = "(^(0?[1-9]|[1-2]\d|3[01])(\/|\.|-|\\| )(0?[1-9]|1[012])(\/|\.|-|\\| )(\d\d)?(\d\d)$)"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "sqlite:///" + os.path.join(basedir, "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
    SENDGRID_DEFAULT_FROM = os.environ.get("MAIL_DEFAULT_SENDER")
    ADMINS = [os.environ.get("MAIL_DEFAULT_SENDER"), os.environ.get("ADMIN")]
    GOOGLEMAPS_KEY = os.environ.get("GOOGLE_API")
    TAGGUN_KEY = os.environ.get("TAGGUN_KEY")
