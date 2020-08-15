# -*- coding: utf-8 -*-
import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    IMAGE_UPLOADS = './app/static/uploads/images/'
    IMAGE_ROUTE = '/static/uploads/images/'
    RECLAIM_ROUTE = './app/static/reclaims/'
    DOWNLOAD_ROUTE = "./static/reclaims/"
    STATIC = "./app/static/"
    ALLOWED_EXTENSIONS_IMAGES = {'png', 'jpg', 'jpeg', 'heif', 'heic'}
    PRICE_PATTERN = '^(([$€£]?)( *)(\d{1,})((,|\.)(\d{0,}))?)( *)([$€£]?)$'
    DATE_PATTERN = '(^(0?[1-9]|[1-2]\d|3[01])(\/|\.|-|\\| )(0?[1-9]|1[012])(\/|\.|-|\\| )(\d\d)?(\d\d)$)'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = 'smtp.sendgrid.net'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'apikey'
    MAIL_PASSWORD = "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"#os.environ.get('SENDGRID_API_KEY')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    ADMINS = ['reclaims@em1781.welly.org.uk']
    GOOGLEMAPS_KEY = os.environ.get('GOOGLE_API')
    MAPBOX_ACCESS_KEY = 'pk.eyJ1Ijoic2Ftb25paiIsImEiOiJja2R0Y3dpaWsxaDRjMnNvZGNmNjlxY3IwIn0.ISeSOe0iRfd0SCBksquOig'
