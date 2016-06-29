from flask.ext.wtf import Form
from wtforms import BooleanField
from wtforms.validators import DataRequired, Length
from dmutils.forms import StripWhitespaceStringField


class SignerDetailsForm(Form):
    full_name = StripWhitespaceStringField('Full name', validators=[
        DataRequired(message="You must provide the full name of the person signing on behalf of the company."),
        Length(max=255, message="You must provide a name under 256 characters.")
    ])
    role = StripWhitespaceStringField(
        'Role at the company',
        validators=[
            DataRequired(message="You must provide the role of the person signing on behalf of the company."),
            Length(max=255, message="You must provide a role under 256 characters.")
        ],
        description='The person signing must have the authority to agree to the framework terms, '
                    'eg director or company secretary.'
    )


class ContractReviewForm(Form):

    authority = BooleanField(
        'Authorisation',
        validators=[DataRequired(message="You must confirm you have the authority to return the agreement.")]
    )
