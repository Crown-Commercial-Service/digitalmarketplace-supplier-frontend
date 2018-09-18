from flask_wtf import FlaskForm
from wtforms.validators import InputRequired

from dmutils.forms.fields import DMEmailField


class EmailAddressForm(FlaskForm):
    email_address = DMEmailField(
        "Email address",
        hint="An invite will be sent asking the recipient to register as a contributor.",
        validators=[
            InputRequired(message="Email address must be provided")
        ]
    )
