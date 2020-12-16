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
    """
    User table
    """

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

    def __repr__(self):  # function if object is printed
        return "<User {}>".format(self.email)

    # <--
    def __eq__(self, other):  # __eq__ is the method for comparing objects
        if not isinstance(other, User):
            return False
        return self.id == other.id


class reclaim_forms(db.Model):
    """
    reclaim form file table
    """

    __tablename__ = "reclaim_forms"
    id = db.Column(db.String(36), index=True, primary_key=True, default=uuid.uuid4)
    filename = db.Column(db.String(60), index=True)  # need to edit once multiple users
    description = db.Column(db.String(120), index=True)
    sent = db.Column(db.String(20), default="Draft", nullable=False)
    made_by = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    date_created = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    date_sent = db.Column(db.DateTime, index=True, default=None)
    signature = db.Column(db.String(60), default=None)

    def __repr__(self):
        return "<id ={} \nFilename = {} \n description = {} \n sent = {} \n made_by = {} \n date_sent = {}\n date_created = {} >".format(
            self.id,
            self.filename,
            self.description,
            self.sent,
            self.made_by,
            self.date_sent,
            self.date_created,
        )


class reclaim_forms_details(db.Model):
    """
    reclaim form row table
    """

    id = db.Column(db.Integer, primary_key=True)
    date_receipt = db.Column(db.String(10), index=True)
    made_by = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    description = db.Column(db.String(120), index=True)
    miles = db.Column(db.Float)
    Total = db.Column(db.Float)
    row_id = db.Column(db.Integer, nullable=False, default=0)
    account_id = db.Column(
        db.String(60), db.ForeignKey("account_codes.account_id"), index=True
    )
    image_name = db.Column(db.String(60), index=True)
    form_id = db.Column(db.Integer, db.ForeignKey("reclaim_forms.id"), index=True)
    start = db.Column(db.String(120), index=True)
    destination = db.Column(db.String(120), index=True)
    purpose = db.Column(db.String(120), index=True)
    end_date = db.Column(db.String(10), index=True)
    return_trip = db.Column(db.Boolean, default=False)


class Account_codes(db.Model):
    """
    account code table
    """

    __tablename__ = "account_codes"
    account_id = db.Column(db.String(60), primary_key=True)
    account_name = db.Column(db.String(60), index=True)
    cost_centre = db.Column(
        db.Integer,
        db.ForeignKey("cost_centres.cost_centre_id"),
        index=True,
        nullable=True,
    )


class cost_centres(db.Model):
    """
    cost centre table (number associated with account code)
    """

    __tablename__ = "cost_centres"
    id = db.Column(db.Integer, primary_key=True)
    cost_centre_id = db.Column(db.String(60))
    purpose_cost_centre = db.Column(db.String(60))
    purpose_id = db.Column(db.Integer)


def get_token(my_object, word, user, expires_in=600):
    """
    Generates a token
    :param my_object: a database entry of type = object
    :param word: token name (pw = reset_password, email=verify_email, sign= sign_form)
    :param user: user for which the token is made (email or object)
    :param expires_in: time for the token to expire in
    :return: token string
    """
    to_decode = my_object.id
    if hasattr(user, "email"):  # if user is an object not a string
        return jwt.encode(
            {word: to_decode, "exp": time.time() + expires_in, "user": user.email},
            app.config["SECRET_KEY"],
            algorithm="HS256",
        ).decode("utf-8")
    return jwt.encode(
        {word: to_decode, "exp": time.time() + expires_in, "user": user},
        app.config["SECRET_KEY"],
        algorithm="HS256",
    ).decode("utf-8")


def verify_token(token, word, table=User, attribute="id"):
    """
    Verify a token
    :param token: token string
    :param word: word to decode (pw = reset_password, email=verify_email, sign= sign_form)
    :param table: table from which the return value should origniate from
    :param attribute: attribute of object which is to be returned
    :return: Database entry
    """
    try:
        decoded = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        returned_id = decoded[
            word
        ]  # pw = reset_password, email=verify_email, sign= sign_form
        if decoded["exp"] > time.time():
            if attribute == "id":
                return db.session.query(table).filter_by(id=returned_id).first()
            elif attribute == "email" and table == User:
                return returned_id
    except (
        jwt.exceptions.DecodeError,
        AttributeError,
        jwt.ExpiredSignature,
        TypeError,
    ):
        return None
