from flask_wtf import FlaskForm
from wtforms import RadioField
from wtforms.validators import AnyOf, InputRequired, Length, Optional, Regexp, ValidationError

from dmutils.forms.fields import DMBooleanField, DMStripWhitespaceStringField, DMEmailField
from dmutils.forms.validators import EmailValidator
from dmutils.forms.widgets import DMTextArea
from ..helpers.suppliers import COUNTRY_TUPLE


def word_length(limit=None, message=None):
    message = message or 'Must not be more than %d words'
    message = message % limit

    def _length(form, field):
        if not field.data or not limit:
            return field

        if len(field.data.split()) > limit:
            raise ValidationError(message)

    return _length


class EditSupplierInformationForm(FlaskForm):
    contactName = DMStripWhitespaceStringField(
        "Contact name",
        hint="This can be the name of the person or team you want buyers to contact",
        validators=[
            InputRequired(message="Enter a contact name"),
            Length(max=255, message="Contact name must be %(max)d characters or fewer"),
        ])
    email = DMEmailField(
        "Contact email address",
        hint="This is the email buyers will use to contact you",
        validators=[
            InputRequired(message="Enter an email address"),
            EmailValidator(message="Enter an email address in the correct format, like name@example.com"),
        ])
    phoneNumber = DMStripWhitespaceStringField(
        "Contact phone number",
        validators=[
            InputRequired(message="Enter a phone number"),
            Length(max=20, message="Phone number must be %(max)d characters or fewer")
        ])
    description = DMStripWhitespaceStringField(
        "Supplier summary",
        hint="50 words maximum",
        widget=DMTextArea(max_length_in_words=50),
        validators=[
            word_length(50, "Your summary must not be more than %d words"),
        ])


class EditRegisteredAddressForm(FlaskForm):
    street = DMStripWhitespaceStringField("Building and street", validators=[
        InputRequired(message="Enter a street address"),
        Length(max=255, message="Building and street name must be %(max)d characters or fewer"),
    ])
    city = DMStripWhitespaceStringField("Town or city", validators=[
        InputRequired(message="Enter a town or city"),
        Length(max=255, message="Town or city name must be %(max)d characters or fewer"),
    ])
    postcode = DMStripWhitespaceStringField("Postcode", validators=[
        InputRequired(message="Enter a postcode"),
        Length(max=15, message="Postcode must be %(max)d characters or fewer"),
    ])
    country = DMStripWhitespaceStringField("Country", validators=[
        InputRequired(message="Enter a country"),
        AnyOf(values=[country[1] for country in COUNTRY_TUPLE], message="Enter a valid country"),
    ])

    def validate(self, extra_validators=None):
        # If a user is trying to change the country and enters an invalid option (blank or not a country),
        # and submits the form, the country field is not submitted with the form.
        # The old value will be re-populated in the field (with the validation error message).
        # This could be confusing if there are multiple fields with errors, so clear the field for now.
        if not self.country.raw_data:
            self.country.data = ''
        return super(EditRegisteredAddressForm, self).validate(extra_validators=extra_validators)


# "Add" rather than "Edit" because this information can only be set once by a supplier
class AddCompanyRegisteredNameForm(FlaskForm):
    registered_company_name = DMStripWhitespaceStringField('Registered company name', validators=[
        InputRequired(message="Enter your registered company name"),
        Length(max=255, message="Registered company must be %(max)d characters or fewer")
    ])


class AddCompanyRegistrationNumberForm(FlaskForm):
    has_companies_house_number = RadioField(
        "Are you registered with Companies House?",
        id="input-has_companies_house_number-1",
        validators=[InputRequired(message="Select yes if you are registered with Companies House")],
        choices=[('Yes', 'Yes'), ('No', 'No')]
    )
    companies_house_number = DMStripWhitespaceStringField(
        'Companies House number',
        id="input-has_companies_house_number-1-companies_house_number",
        default='',
        validators=[
            Optional(),
            Regexp(r'^([0-9]{2}|[A-Za-z]{2})[0-9]{6}$',
                   message="Your Companies House number must be 8 characters"
                   )
        ]
    )
    other_company_registration_number = DMStripWhitespaceStringField(
        'Other company registration number',
        id="input-has_companies_house_number-2-other_company_registration_number",
        default='',
        validators=[
            Optional(),
            Length(max=255, message="Registration number must be %(max)d characters or fewer")
        ]
    )

    def validate(self, extra_validators=None):
        # If the form has been re-submitted following an error on a field which is now hidden we need to clear the
        # previously entered data before validating
        # For example, a user had an error submitting CH number but is now submitting other registration number,
        # (with CH number field hidden on the page) the previously submitted bad CH number should be cleared.
        # Similarly, we clear any validation errors on fields that were "hidden" when the form was submitted.
        if self.has_companies_house_number.data == "Yes":
            self.other_company_registration_number.raw_data = None
            self.other_company_registration_number.data = ""
        if self.has_companies_house_number.data == "No":
            self.companies_house_number.raw_data = None
            self.companies_house_number.data = ""

        valid = True
        if not super(AddCompanyRegistrationNumberForm, self).validate(extra_validators=extra_validators):
            valid = False
        if self.has_companies_house_number.data == "Yes" and not self.companies_house_number.data:
            self.companies_house_number.errors.append('Enter a Companies House number')
            valid = False

        if self.has_companies_house_number.data == "No" and not self.other_company_registration_number.data:
            self.other_company_registration_number.errors.append('Enter a company registration number')
            valid = False

        return valid


class CompanyPublicContactInformationForm(FlaskForm):
    company_name = DMStripWhitespaceStringField('Company name', validators=[
        InputRequired(message="Enter your company name"),
        Length(max=255, message="Company name must be %(max)d characters or fewer")
    ])
    contact_name = DMStripWhitespaceStringField('Contact name', validators=[
        InputRequired(message="Enter a contact name"),
        Length(max=255, message="Contact name must be %(max)d characters or fewer")
    ])
    email_address = DMStripWhitespaceStringField('Contact email address', validators=[
        InputRequired(message="Enter an email address"),
        EmailValidator(message="Enter an email address in the correct format, like name@example.com"),
    ])
    phone_number = DMStripWhitespaceStringField('Contact phone number', validators=[
        InputRequired(message="Enter a phone number"),
        Length(max=20, message="Phone number must be %(max)d characters or fewer")
    ])


class DunsNumberForm(FlaskForm):
    duns_number = DMStripWhitespaceStringField('DUNS Number', validators=[
        InputRequired(message="Enter your 9 digit DUNS number"),
        Regexp(r'^\d{9}$', message="Your DUNS number must be 9 digits"),
    ])


class ConfirmCompanyForm(FlaskForm):
    confirmed = DMBooleanField(
        'Is this the company you want to create an account for?',
        false_values=("False", "false", ""),
        validators=[InputRequired(message="Select yes if this is the company you want to create an account for")]
    )


class EmailAddressForm(FlaskForm):
    email_address = DMStripWhitespaceStringField('Email address', validators=[
        InputRequired(message="Enter an email address"),
        EmailValidator(message="Enter an email address in the correct format, like name@example.com"),
    ])


class CompanyOrganisationSizeForm(FlaskForm):
    OPTIONS = [
        {
            "value": "micro",
            "label": "Micro",
            "description": "Under 10 employees and 2 million euros or less in either annual turnover or balance "
                           "sheet total",
        },
        {
            "value": "small",
            "label": "Small",
            "description": "Under 50 employees and 10 million euros or less in either annual turnover or balance "
                           "sheet total",
        },
        {
            "value": "medium",
            "label": "Medium",
            "description": "Under 250 employees and either 50 million euros or less in either annual turnover or "
                           "43 million euros or less in annual balance sheet total",
        },
        {
            "value": "large",
            "label": "Large",
            "description": "250 or more employees and either over 50 million euros in annual turnover or over 43 "
                           "million euros in balance sheet total",
        },
    ]

    organisation_size = RadioField(
        "What size is your organisation?",
        validators=[InputRequired(message="Select an organisation size")],
        choices=[(option["value"], option["label"]) for option in OPTIONS],
        id="input-organisation_size-1"  # TODO: change to input-organisation_size when on govuk-frontend~3
    )


class CompanyTradingStatusForm(FlaskForm):
    OPTIONS = [
        {
            'value': 'limited company (LTD)',
            'label': 'limited company (LTD)',
        },
        {
            'value': 'limited liability company (LLC)',
            'label': 'limited liability company (LLC)',
        },
        {
            'value': 'public limited company (PLC)',
            'label': 'public limited company (PLC)',
        },
        {
            'value': 'limited liability partnership (LLP)',
            'label': 'limited liability partnership (LLP)',
        },
        {
            'value': 'sole trader',
            'label': 'sole trader',
        },
        {
            'value': 'public body',
            'label': 'public body',
        },
        {
            'value': 'other',
            'label': 'other',
        },
    ]

    trading_status = RadioField(
        "What’s your trading status?",
        validators=[InputRequired(message="Select a trading status")],
        choices=[(option["value"], option["label"]) for option in OPTIONS],
        id="input-trading_status-1"  # TODO: change to input-trading_status when on govuk-frontend~3
    )
