from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField
from wtforms.validators import DataRequired, InputRequired, Length

from dmutils.forms.fields import DMStripWhitespaceStringField


class SignerDetailsForm(FlaskForm):
    signerName = DMStripWhitespaceStringField('Full name', validators=[
        DataRequired(message="You must provide the full name of the person signing on behalf of the company."),
        Length(max=255, message="You must provide a name under 256 characters.")
    ])
    signerRole = DMStripWhitespaceStringField(
        'Role at the company',
        validators=[
            DataRequired(message="You must provide the role of the person signing on behalf of the company."),
            Length(max=255, message="You must provide a role under 256 characters.")
        ],
        description='The person signing must have the authority to agree to the framework terms, '
                    'eg director or company secretary.'
    )


class ContractReviewForm(FlaskForm):
    authorisation = BooleanField(
        'Authorisation',
        validators=[DataRequired(message="You must confirm you have the authority to return the agreement.")]
    )


class AcceptAgreementVariationForm(FlaskForm):
    accept_changes = BooleanField(
        'I accept these changes',
        validators=[
            DataRequired(message="You need to accept these changes to continue.")
        ]
    )


class ReuseDeclarationForm(FlaskForm):
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


class OneServiceLimitCopyServiceForm(FlaskForm):

    def __init__(self, lot_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.copy_service.label.text = f"Do you want to reuse your previous {lot_name} service?"

    copy_service = BooleanField(
        'Do you want to reuse your previous service?',
        false_values={'False', 'false', ''},
        validators=[InputRequired(message='You must answer this question.')]
    )
