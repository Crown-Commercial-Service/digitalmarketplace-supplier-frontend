from flask.ext.wtf import Form
from wtforms import StringField, PasswordField
from wtfforms.validators import Required

class LoginForm(Form):
    email_address = StringField('Email address', validators=[Required()])
    password = PasswordField('Passphrase', validators=[Required()])