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


class EmailAddressForm(Form):
    email_address = StringField('Email address', validators=[
        DataRequired(message="Email can not be empty"),
        Email(message="Please enter a valid email address")
    ])


class ChangePasswordForm(Form):
    password = PasswordField('Password', validators=[
        DataRequired(message="Please enter a new password"),
        Length(min=10,
               max=50,
               message="Passwords must be between 10 and 50 characters"
               )
    ])
    confirm_password = PasswordField('Confirm password', validators=[
        DataRequired(message="Please confirm your new password"),
        EqualTo('password', message="The passwords you entered do not match")
    ])


class CreateUserForm(Form):
    name = StringField('Your name', validators=[
        DataRequired(message="Please enter a name"),
        Length(min=1,
               max=255,
               message="Names must be between 1 and 255 characters"
               )
    ])

    password = PasswordField('Password', validators=[
        DataRequired(message="Please enter a password"),
        Length(min=10,
               max=50,
               message="Passwords must be between 10 and 50 characters"
               )
    ])
