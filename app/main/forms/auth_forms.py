from flask.ext.wtf import Form
from wtforms import StringField, PasswordField, HiddenField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class LoginForm(Form):
    email_address = StringField('Email address', validators=[
        DataRequired(message="Email can not be empty"),
        Email(message="Please enter a valid email address")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Please enter your password")
    ])


class ForgottenPasswordForm(Form):
    email_address = StringField('Email address', validators=[
        DataRequired(message="Email can not be empty"),
        Email(message="Please enter a valid email address")
        ])


class ChangePasswordForm(Form):
    email_address = HiddenField('Email address', validators=[
        DataRequired(message="Email can not be empty"),
        Email(message="Please enter a valid email address")
    ])
    user_id = HiddenField('User ID')
    password = PasswordField('Password', validators=[
        DataRequired(message="Please enter a new password"),
        Length(min=10,
               max=50,
               message="Passwords must be between 10 and 50 characters long"
        )
    ])
    confirm_password = PasswordField('Confirm password', validators=[
        DataRequired(message="Please confirm your new password"),
        EqualTo('password', message="The passwords you entered do not match")
    ])
