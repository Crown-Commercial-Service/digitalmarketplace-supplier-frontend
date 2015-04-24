from flask.ext.wtf import Form
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Email


class LoginForm(Form):
    email_address = StringField('Email address',
                                validators=[DataRequired(), Email()])
    password = PasswordField('Password',
                             validators=[
                                 DataRequired()
                             ])
