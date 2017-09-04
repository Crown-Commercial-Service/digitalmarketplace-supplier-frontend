from flask.ext.wtf import Form
from wtforms import IntegerField
from wtforms.validators import DataRequired, ValidationError, Length, Optional, Regexp
from dmutils.forms import StripWhitespaceStringField


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
    email = StripWhitespaceStringField('Contact email', validators=[
        DataRequired(message="You must provide an email address"),
        Regexp("^[^@^\s]+@[^@^\.^\s]+(\.[^@^\.^\s]+)+$",
               message="Please enter a valid email address")
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
        Regexp("^[^@^\s]+@[^@^\.^\s]+(\.[^@^\.^\s]+)+$",
               message="You must provide a valid email address.")
    ])
    phone_number = StripWhitespaceStringField('Contact phone number', validators=[
        DataRequired(message="You must provide a phone number."),
        Length(max=20, message="You must provide a phone number under 20 characters.")
    ])


class EmailAddressForm(Form):
    email_address = StripWhitespaceStringField('Email address', validators=[
        DataRequired(message="You must provide an email address."),
        Regexp("^[^@^\s]+@[^@^\.^\s]+(\.[^@^\.^\s]+)+$",
               message="You must provide a valid email address.")
    ])
