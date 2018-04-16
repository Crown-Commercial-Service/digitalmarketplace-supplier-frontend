from flask_wtf import FlaskForm
from wtforms.validators import InputRequired

from dmutils.forms import EmailField


class EmailAddressForm(FlaskForm):
    email_address = EmailField('Email address', validators=[
        InputRequired(message="Email address must be provided")
    ])
