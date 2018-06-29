import re
from flask_wtf import FlaskForm
from wtforms import RadioField, StringField
from wtforms.validators import AnyOf, InputRequired, Length, Optional, Regexp, StopValidation, ValidationError

from dmutils.forms import StripWhitespaceStringField, EmailField, EmailValidator
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


class EditSupplierForm(FlaskForm):
    description = StripWhitespaceStringField('Supplier summary', validators=[
        word_length(50, 'Your summary must not be more than %d words')
    ])


class EditContactInformationForm(FlaskForm):
    contactName = StripWhitespaceStringField('Contact name', validators=[
        InputRequired(message="You must provide a contact name."),
        Length(max=255, message="You must provide a contact name under 256 characters."),
    ])
    email = EmailField('Contact email address', validators=[
        InputRequired(message="You must provide an email address."),
        EmailValidator(message="You must provide a valid email address."),
    ])
    phoneNumber = StripWhitespaceStringField('Contact phone number', validators=[
        InputRequired(message="You must provide a phone number."),
        Length(max=20, message="You must provide a phone number under 20 characters.")
    ])


class EditRegisteredAddressForm(FlaskForm):
    address1 = StripWhitespaceStringField('Building and street', validators=[
        InputRequired(message="You need to enter the street address."),
        Length(max=255, message="You must provide a building and street name under 256 characters."),
    ])
    city = StripWhitespaceStringField('Town or city', validators=[
        InputRequired(message="You need to enter the town or city."),
        Length(max=255, message="You must provide a town or city name under 256 characters."),
    ])
    postcode = StripWhitespaceStringField('Postcode', validators=[
        InputRequired(message="You need to enter the postcode."),
        Length(max=15, message="You must provide a valid postcode under 15 characters."),
    ])


class EditRegisteredCountryForm(FlaskForm):
    registrationCountry = StripWhitespaceStringField('Country', validators=[
        InputRequired(message="You need to enter a country."),
        AnyOf(values=[country[1] for country in COUNTRY_TUPLE], message="You must enter a valid country."),
    ])


# "Add" rather than "Edit" because this information can only be set once by a supplier
class AddCompanyRegisteredNameForm(FlaskForm):
    registered_company_name = StripWhitespaceStringField('Registered company name', validators=[
        InputRequired(message="You must provide a registered company name."),
        Length(max=255, message="You must provide a registered company name under 256 characters.")
    ])


class AddCompanyRegistrationNumberForm(FlaskForm):
    has_companies_house_number = RadioField(
        "Are you registered with Companies House?",
        validators=[InputRequired(message="You need to answer this question.")],
        choices=[('Yes', 'Yes'), ('No', 'No')]
    )
    companies_house_number = StripWhitespaceStringField(
        'Companies House number',
        default='',
        validators=[
            Optional(),
            Regexp(r'^([0-9]{2}|[A-Za-z]{2})[0-9]{6}$',
                   message="You must provide a valid 8 character Companies House number."
                   )
        ]
    )
    other_company_registration_number = StripWhitespaceStringField(
        'Other company registration number',
        default='',
        validators=[
            Optional(),
            Length(max=255, message="You must provide a registration number under 256 characters.")
        ]
    )

    def validate(self):
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
        if not super(AddCompanyRegistrationNumberForm, self).validate():
            valid = False
        if self.has_companies_house_number.data == "Yes" and not self.companies_house_number.data:
            self.companies_house_number.errors.append('You must enter a Companies House number.')
            valid = False

        if self.has_companies_house_number.data == "No" and not self.other_company_registration_number.data:
            self.other_company_registration_number.errors.append('You must provide an answer.')
            valid = False

        return valid


class CompanyPublicContactInformationForm(FlaskForm):
    company_name = StripWhitespaceStringField('Company name', validators=[
        InputRequired(message="You must provide a company name."),
        Length(max=255, message="You must provide a company name under 256 characters.")
    ])
    contact_name = StripWhitespaceStringField('Contact name', validators=[
        InputRequired(message="You must provide a contact name."),
        Length(max=255, message="You must provide a contact name under 256 characters.")
    ])
    email_address = StripWhitespaceStringField('Contact email address', validators=[
        InputRequired(message="You must provide an email address."),
        EmailValidator(message="You must provide a valid email address."),
    ])
    phone_number = StripWhitespaceStringField('Contact phone number', validators=[
        InputRequired(message="You must provide a phone number."),
        Length(max=20, message="You must provide a phone number under 20 characters.")
    ])


class DunsNumberForm(FlaskForm):
    duns_number = StripWhitespaceStringField('DUNS Number', validators=[
        InputRequired(message="You must enter a DUNS number with 9 digits."),
        Regexp(r'^\d{9}$', message="You must enter a DUNS number with 9 digits."),
    ])


class EmailAddressForm(FlaskForm):
    email_address = StripWhitespaceStringField('Email address', validators=[
        InputRequired(message="You must provide an email address."),
        EmailValidator(message="You must provide a valid email address."),
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

    organisation_size = RadioField('Organisation size',
                                   validators=[InputRequired(message="You must choose an organisation size.")],
                                   choices=[(o['value'], o['label']) for o in OPTIONS])


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

    trading_status = RadioField('Trading status',
                                validators=[InputRequired(message="You must choose a trading status.")],
                                choices=[(o['value'], o['label']) for o in OPTIONS])


class VatNumberForm(FlaskForm):
    NOT_VAT_REGISTERED_TEXT = "Not VAT registered"

    def stop_validation_if_not_registered(form, field):
        # If a user is not registered for VAT we don't care about validating something they have entered in the
        # VAT number input field. If a value for `vat_registered` is not sent in the POST request, WTForms sets the
        # value to `None`, hence its inclusion here
        if form.vat_registered.data in ('No', 'None'):
            raise StopValidation()

    vat_registered = RadioField(
        "VAT registered",
        validators=[InputRequired(message="You need to answer this question.")],
        choices=[('Yes', 'Yes'), ('No', 'No')],
    )
    vat_number = StringField(
        'VAT number',
        default="",
        # Filters to remove internal whitespace and uppercase the string.
        filters=[
            lambda x: re.sub(r'\s+', '', x),
            lambda x: x.upper(),
        ],
        validators=[
            stop_validation_if_not_registered,
            InputRequired(message="You must provide a VAT number from the UK."),
            Regexp(
                r'^(GB)?((\d{9})|(\d{12})|((GD|HA)\d{3}))$',
                message="You must provide a valid VAT number from the UK - they are usually either 9 or 12 digits."
            )
        ],
    )
