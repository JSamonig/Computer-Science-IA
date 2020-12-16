from app.models import User
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField,
    SubmitField,
    FloatField,
    TextAreaField,
    PasswordField,
    BooleanField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    Regexp,
    Length,
    EqualTo,
    ValidationError,
)
import config as c


class UploadForm(FlaskForm):
    file = FileField(
        validators=[
            DataRequired(),
            FileAllowed(
                c.Config.ALLOWED_EXTENSIONS_IMAGES,
                "Please input an image allowed extensions are "
                + " ".join(c.Config.ALLOWED_EXTENSIONS_IMAGES),
            ),
        ]
    )
    submit = SubmitField("Submit")


class EditOutput(FlaskForm):
    date = StringField(
        "Date",
        validators=[
            DataRequired(),
            Regexp(c.Config.DATE_PATTERN, 0, "Invalid date pattern"),
        ],
    )
    description = TextAreaField(
        "Description", validators=[DataRequired(), Length(min=1, max=300)]
    )
    miles = FloatField("Miles")
    accountCode = StringField("Department Code", validators=[DataRequired()])
    accountCode2 = StringField("Account Code", validators=[DataRequired()])
    total = FloatField("Total")
    submit = SubmitField("Submit")


#  --> Adapted from https://blog.miguelgrinberg.com/


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Sign In")


class RegistrationForm(FlaskForm):
    first_name = StringField("First name", validators=[DataRequired()])
    last_name = StringField("Surname", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField(
        "Password", validators=[DataRequired(), Length(min=8, max=200)]
    )
    password2 = PasswordField(
        "Repeat Password", validators=[DataRequired(), EqualTo("password")]
    )
    submit = SubmitField("Register")

    def validate_email(self, *args):
        user = User.query.filter_by(email=self.email.data).first()
        if user is not None:
            raise ValidationError("Please use a different email address.")


class ResetPasswordRequestForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Request Password Reset")


class ResetPasswordForm(FlaskForm):
    password = PasswordField(
        "Password", validators=[DataRequired(), Length(min=8, max=200)]
    )
    password2 = PasswordField(
        "Repeat Password", validators=[DataRequired(), EqualTo("password")]
    )
    submit = SubmitField("Request Password Reset")


# <--


class VerifyEmail(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    email2 = StringField(
        "Repeat email", validators=[DataRequired(), Email(), EqualTo("email")]
    )
    submit = SubmitField("Resend email verification")


class Settings(FlaskForm):
    first_name = StringField(
        "First name", validators=[DataRequired(), Length(min=1, max=50)]
    )
    last_name = StringField(
        "Surname", validators=[DataRequired(), Length(min=1, max=50)]
    )
    email = StringField("Email", validators=[DataRequired(), Email()])
    accounting_email = StringField(
        "Accounting email", validators=[DataRequired(), Email()]
    )
    taggun = BooleanField("Use TAGGUN API for OCR", validators=[])
    dark = BooleanField("Dark mode", validators=[])
    submit = SubmitField("Apply")

    def __init__(self, user_id, **kwargs):
        super().__init__(**kwargs)
        self.user_id = user_id

    def validate_email(self, email):
        current_user = User.query.filter_by(id=self.user_id).first()
        user = User.query.filter_by(email=email.data).first()
        if user is not None and current_user != user:
            raise ValidationError("Please use a different email address.")


class NewReclaim(FlaskForm):
    filename = StringField(
        "File name", validators=[DataRequired(), Length(min=1, max=50)]
    )
    description = TextAreaField("Description", validators=[Length(min=0, max=50)])
    submit = SubmitField("Submit")


class Description(FlaskForm):
    description = TextAreaField(
        "Purpose of journey", validators=[DataRequired(), Length(min=1, max=140)]
    )
    start = StringField(
        "Starting location", validators=[DataRequired(), Length(min=1, max=140)]
    )
    destination = StringField(
        "Ending location", validators=[DataRequired(), Length(min=1, max=140)]
    )
    return_trip = BooleanField("Is a return trip")
    date_start = StringField(
        "Starting date",
        validators=[
            DataRequired(),
            Regexp(c.Config.DATE_PATTERN, 0, "Invalid date pattern"),
        ],
    )
    date_end = StringField(
        "Ending date",
        validators=[
            DataRequired(),
            Regexp(c.Config.DATE_PATTERN, 0, "Invalid date pattern"),
        ],
    )
    submit = SubmitField("Submit")


class ModalSettings(FlaskForm):
    accounting_email = StringField(
        "Accounting email", validators=[DataRequired(), Email()]
    )
    dark = BooleanField("Use the dark theme")
    submit = SubmitField("Apply")


class Supervisor(FlaskForm):
    email_supervisor = StringField(
        "Email of line manager", validators=[DataRequired(), Email()]
    )
    submit = SubmitField("Request approval")
