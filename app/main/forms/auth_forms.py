from wtforms import PasswordField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from dmutils.forms import DmForm, StripWhitespaceStringField


class LoginForm(DmForm):
    email_address = StripWhitespaceStringField('Email address', validators=[
        DataRequired(message="Email address must be provided"),
        Email(message="Please enter a valid email address")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Please enter your password")
    ])


class EmailAddressForm(DmForm):
    email_address = StripWhitespaceStringField('Email address', validators=[
        DataRequired(message="Email address must be provided"),
        Email(message="Please enter a valid email address")
    ])


class ChangePasswordForm(DmForm):
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


class CreateUserForm(DmForm):
    name = StripWhitespaceStringField('Your name', validators=[
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
