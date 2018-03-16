from flask_wtf import Form
from wtforms.validators import InputRequired

from dmutils.forms import EmailField


class EmailAddressForm(Form):
    email_address = EmailField('Email address', validators=[
        InputRequired(message="Email address must be provided")
    ])
