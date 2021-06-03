from flask_wtf import FlaskForm
from wtforms import HiddenField, RadioField
from wtforms.validators import DataRequired, Length, InputRequired

from dmutils.forms.fields import DMBooleanField, DMStripWhitespaceStringField, DMRadioField


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

    reuse = RadioField(
        "Do you want to reuse the answers from your earlier declaration?",
        id="input-reuse-1",  # TODO: change to input-reuse when on govuk-frontend~3
        choices=[("yes", "Yes"), ("no", "No")],
        validators=[InputRequired("Select yes if you want to reuse your earlier answers")],
    )
    old_framework_slug = HiddenField()


class OneServiceLimitCopyServiceForm(FlaskForm):
    copy_service = RadioField(
        id="input-copy_service-1",  # TODO: change to input-copy_service when on govuk-frontend~3
        choices=[("yes", "Yes"), ("no", "No")],
        validators=[InputRequired("Select yes if you want to reuse your previous service")],
    )

    def __init__(self, lot_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.copy_service.label.text = f"Do you want to reuse your previous {lot_name} service?"

        if lot_name == 'digital specialists':
            self.copy_service.description = "You’ll need to review your previous answers. " \
                                            "Roles won’t be copied if they have new questions."
        else:
            self.copy_service.description = "You still have to review your service and answer any new questions."


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
