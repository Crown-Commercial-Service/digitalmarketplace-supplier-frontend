from flask_wtf import FlaskForm
from wtforms import HiddenField
from wtforms.validators import DataRequired, Length, InputRequired

from dmutils.forms.fields import DMBooleanField, DMStripWhitespaceStringField, DMRadioField
from dmutils.forms.widgets import DMSelectionButtonBase


class SignerDetailsForm(FlaskForm):
    signerName = DMStripWhitespaceStringField(
        "Full name",
        validators=[
            DataRequired(message="You must provide the full name of the person signing on behalf of the company."),
            Length(max=255, message="You must provide a name under 256 characters."),
        ],
    )
    signerRole = DMStripWhitespaceStringField(
        "Role at the company",
        hint="The person signing must have the authority to agree to the framework terms,"
             " eg director or company secretary.",
        validators=[
            DataRequired(message="You must provide the role of the person signing on behalf of the company."),
            Length(max=255, message="You must provide a role under 256 characters."),
        ],
    )


class ContractReviewForm(FlaskForm):
    authorisation = DMBooleanField(
        "I have the authority to return this agreement on behalf of {supplier_registered_name}",
        validators=[DataRequired(message="You must confirm you have the authority to return the agreement.")],
    )

    def __init__(self, supplier_registered_name, **kwargs):
        super().__init__(**kwargs)
        self.authorisation.question = self.authorisation.question.format(
            supplier_registered_name=supplier_registered_name
        )


class AcceptAgreementVariationForm(FlaskForm):
    accept_changes = DMBooleanField(
        "I accept these changes", validators=[DataRequired(message="You need to accept these changes to continue.")]
    )


class ReuseDeclarationForm(FlaskForm):
    """Form for the reuse declaration page. One yes no question.

    `reuse` is a yes no whether they want to reuse a framework.
    `old_framework` is a hidden field allowing us to pass back the framework slug of the framework they are choosing to
    reuse.
    """

    reuse = DMBooleanField(
        "Do you want to reuse the answers from your earlier declaration?",
        false_values=("False", "false", ""),
        widget=DMSelectionButtonBase(type="boolean"),
    )
    old_framework_slug = HiddenField()


class OneServiceLimitCopyServiceForm(FlaskForm):

    copy_service = DMBooleanField(
        "Do you want to reuse your previous {lot_name} service?",
        false_values=("False", "false", ""),
        widget=DMSelectionButtonBase(type="boolean"),
    )

    def __init__(self, lot_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.copy_service.question = self.copy_service.question.format(lot_name=lot_name)
        if lot_name == 'digital specialists':
            self.copy_service.question_advice = "You’ll need to review your previous answers. " \
                                                "Roles won’t be copied if they have new questions."
        else:
            self.copy_service.question_advice = "You still have to review your service and answer any new questions."


class LegalAuthorityForm(FlaskForm):
    HEADING = 'Do you have the legal authority to sign on behalf of your company?'
    HINT = "For example, you are a director or company secretary."
    OPTIONS = [
        {
            "value": "yes",
            "label": "Yes",
        },
        {
            "value": "no",
            "label": "No",
        },
    ]
    legal_authority = DMRadioField(
        HEADING,
        hint=HINT,
        validators=[InputRequired(message="Select yes if you have the legal authority"
                                          " to sign on behalf of your company")],
        options=OPTIONS)


class SignFrameworkAgreementForm(FlaskForm):
    def __init__(self, contract_title, **kw):
        super(SignFrameworkAgreementForm, self).__init__(**kw)
        self.signer_terms_and_conditions.label.text = f"I accept the terms and conditions of the {contract_title}"
        self.signer_terms_and_conditions.validators[0].message = f"Accept the terms and conditions of the" \
                                                                 f" {contract_title}."

    # Intended use of camel case here to match expected API fields
    signerName = DMStripWhitespaceStringField(
        "Your full name",
        validators=[
            DataRequired(message="Enter your full name."),
            Length(max=255, message="Name must be under 256 characters."),
        ],
    )

    signerRole = DMStripWhitespaceStringField(
        "Your role in the company",
        validators=[
            DataRequired(message="Enter your role in the company."),
            Length(max=255, message="Role must be under 256 characters."),
        ],
    )
    signer_terms_and_conditions = DMBooleanField(
        validators=[
            DataRequired()
        ]
    )
