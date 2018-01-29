from flask_wtf import Form
from wtforms import BooleanField, HiddenField
from wtforms.validators import DataRequired, InputRequired, Length

from dmutils.forms import StripWhitespaceStringField


class SignerDetailsForm(Form):
    signerName = StripWhitespaceStringField('Full name', validators=[
        DataRequired(message="You must provide the full name of the person signing on behalf of the company."),
        Length(max=255, message="You must provide a name under 256 characters.")
    ])
    signerRole = StripWhitespaceStringField(
        'Role at the company',
        validators=[
            DataRequired(message="You must provide the role of the person signing on behalf of the company."),
            Length(max=255, message="You must provide a role under 256 characters.")
        ],
        description='The person signing must have the authority to agree to the framework terms, '
                    'eg director or company secretary.'
    )


class ContractReviewForm(Form):
    authorisation = BooleanField(
        'Authorisation',
        validators=[DataRequired(message="You must confirm you have the authority to return the agreement.")]
    )


class AcceptAgreementVariationForm(Form):
    accept_changes = BooleanField(
        'I accept these proposed changes',
        validators=[
            DataRequired(message="You can only save and continue if you agree to the proposed changes.")
        ]
    )


class ReuseDeclarationForm(Form):
    """Form for the reuse declaration page. One yes no question.

    `reuse` is a yes no whether they want to reuse a framework.
    `old_framework` is a hidden field allowing us to pass back the framework slug of the framework they are choosing to
    reuse.
    """
    reuse = BooleanField(
        'Do you want to reuse the answers from your earlier declaration?',
        false_values={'False', 'false', ''},
        validators=[InputRequired(message='You must answer this question.')]
    )
    old_framework_slug = HiddenField()
