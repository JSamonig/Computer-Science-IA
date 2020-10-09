from app import db, login, app
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import jwt
import uuid
import time


#  --> Adapted from https://blog.miguelgrinberg.com/
@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64), index=True)
    last_name = db.Column(db.String(64), index=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(120))
    accounting_email = db.Column(db.String(120), index=True)
    use_taggun = db.Column(db.Boolean, nullable=False, default=True)
    dark = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_token(self, word, expires_in=600):
        return jwt.encode(
            {word: self.id, 'exp': time.time() + expires_in},
            app.config['SECRET_KEY'], algorithm='HS256').decode('utf-8')

    @staticmethod
    def verify_token(token, word):
        try:
            id = jwt.decode(token, app.config['SECRET_KEY'],
                            algorithms=['HS256'])[word] #pw =reset_password, email=verify_email, sign= sign_form
        except:
            return
        return User.query.get(id)

    def __repr__(self):
        return '<User {}>'.format(self.username)


# <--


class reclaim_forms(db.Model):
    __tablename__ = 'reclaim_forms'
    id = db.Column(db.String(36), index=True, primary_key=True, default=uuid.uuid4)
    filename = db.Column(db.String(60), index=True)  # need to edit once multiple users
    description = db.Column(db.String(120), index=True)
    sent = db.Column(db.String(20), default="Draft", nullable=False)
    made_by = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    date_created = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    date_sent = db.Column(db.DateTime, index=True, default=None)
    signature = db.Column(db.String(60), default=None)

    def __repr__(self):
        return '<id ={} \nFilename = {} \n description = {} \n sent = {} \n made_by = {} \n date_sent = {}\n date_created = {} >' \
            .format(self.id, self.filename, self.description, self.sent, self.made_by,self.date_sent,self.date_created)


class reclaim_forms_details(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_receipt = db.Column(db.String(10), index=True)
    made_by = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    description = db.Column(db.String(120), index=True)
    miles = db.Column(db.Float)
    Total = db.Column(db.Float)
    row_id = db.Column(db.Integer, nullable=False, default=0)
    account_id = db.Column(db.String(60), db.ForeignKey('account_codes.account_id'), index=True)
    image_name = db.Column(db.String(60), index=True)
    form_id = db.Column(db.Integer, db.ForeignKey('reclaim_forms.id'), index=True)
    start = db.Column(db.String(120), index=True)
    destination = db.Column(db.String(120), index=True)
    purpose = db.Column(db.String(120), index=True)
    end_date = db.Column(db.String(10), index=True)
    return_trip = db.Column(db.Boolean, default=False)


class Account_codes(db.Model):
    __tablename__ = 'account_codes'
    account_id = db.Column(db.String(60), primary_key=True)
    account_name = db.Column(db.String(60), index=True)
    cost_centre = db.Column(db.Integer, db.ForeignKey('cost_centres.cost_centre_id'),index=True, nullable=True)

class cost_centres(db.Model):
    __tablename__ = 'cost_centres'
    id = db.Column(db.Integer, primary_key=True)
    cost_centre_id = db.Column(db.String(60))
    purpose_cost_centre = db.Column(db.String(60))
    purpose_id = db.Column(db.Integer)