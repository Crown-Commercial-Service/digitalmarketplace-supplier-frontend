from flask_wtf import FlaskForm
from wtforms.validators import InputRequired

from dmutils.forms.fields import DMEmailField


class EmailAddressForm(FlaskForm):
    email_address = DMEmailField('Email address', validators=[
        InputRequired(message="Email address must be provided")
    ])
