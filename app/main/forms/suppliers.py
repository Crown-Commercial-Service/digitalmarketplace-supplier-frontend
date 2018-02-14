from flask_wtf import Form
from wtforms import IntegerField, RadioField
from wtforms.validators import DataRequired, ValidationError, Length, Optional, Regexp, InputRequired

from dmutils.forms import StripWhitespaceStringField, EmailField, EmailValidator


def word_length(limit=None, message=None):
    message = message or 'Must not be more than %d words'
    message = message % limit

    def _length(form, field):
        if not field.data or not limit:
            return field

        if len(field.data.split()) > limit:
            raise ValidationError(message)

    return _length


class EditSupplierForm(Form):
    description = StripWhitespaceStringField('Supplier summary', validators=[
        word_length(50, 'Your summary must not be more than %d words')
    ])


class EditContactInformationForm(Form):
    id = IntegerField()
    contactName = StripWhitespaceStringField('Contact name', validators=[
        DataRequired(message="You must provide a contact name"),
    ])
    email = EmailField('Contact email address', validators=[
        DataRequired(message="You must provide an email address"),
    ])
    phoneNumber = StripWhitespaceStringField('Contact phone number')
    address1 = StripWhitespaceStringField('Building and street')
    city = StripWhitespaceStringField('Town or city')
    postcode = StripWhitespaceStringField('Postcode')


class DunsNumberForm(Form):
    duns_number = StripWhitespaceStringField('DUNS Number', validators=[
        DataRequired(message="You must enter a DUNS number with 9 digits."),
        Regexp(r'^\d{9}$', message="You must enter a DUNS number with 9 digits."),
    ])


class CompaniesHouseNumberForm(Form):
    companies_house_number = StripWhitespaceStringField('Companies house number', validators=[
        Optional(),
        Regexp(r'^([0-9]{2}|[A-Za-z]{2})[0-9]{6}$',
               message="Companies House numbers must have either 8 digits or 2 letters followed by 6 digits."
               )
    ])


class CompanyNameForm(Form):
    company_name = StripWhitespaceStringField('Company name', validators=[
        DataRequired(message="You must provide a company name."),
        Length(max=255, message="You must provide a company name under 256 characters.")
    ])


class CompanyContactDetailsForm(Form):
    contact_name = StripWhitespaceStringField('Contact name', validators=[
        DataRequired(message="You must provide a contact name."),
        Length(max=255, message="You must provide a contact name under 256 characters.")
    ])
    email_address = StripWhitespaceStringField('Contact email address', validators=[
        DataRequired(message="You must provide an email address."),
        EmailValidator(message="You must provide a valid email address."),
    ])
    phone_number = StripWhitespaceStringField('Contact phone number', validators=[
        DataRequired(message="You must provide a phone number."),
        Length(max=20, message="You must provide a phone number under 20 characters.")
    ])


class EmailAddressForm(Form):
    email_address = StripWhitespaceStringField('Email address', validators=[
        DataRequired(message="You must provide an email address."),
        EmailValidator(message="You must provide a valid email address."),
    ])


class CompanyOrganisationSizeForm(Form):
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
