from flask.ext.wtf import Form
from wtforms import StringField
from wtforms.validators import DataRequired, Email


class ForgottenPasswordForm(Form):
    email_address = StringField('Email address', validators=[
        DataRequired(message="Email can not be empty"),
        Email(message="Please enter a valid email address")
        ])
