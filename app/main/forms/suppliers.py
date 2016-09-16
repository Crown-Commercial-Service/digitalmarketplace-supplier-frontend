from wtforms import IntegerField, FieldList
from wtforms.validators import DataRequired, ValidationError, Length, Optional, Regexp, Email
from dmutils.forms import DmForm, StripWhitespaceStringField


def word_length(limit=None, message=None):
    message = message or 'Must not be more than %d words'
    message = message % limit

    def _length(form, field):
        if not field.data or not limit:
            return field

        if len(field.data.split()) > limit:
            raise ValidationError(message)

    return _length


class EditSupplierForm(DmForm):
    summary = StripWhitespaceStringField('Supplier summary', validators=[
        word_length(50, 'Your summary must not be more than %d words')
    ])


class EditContactInformationForm(DmForm):
    phone = StripWhitespaceStringField('Phone number')
    email = StripWhitespaceStringField('Email address', validators=[
        DataRequired(message="You must provide an email address"),
        Email(message="Please enter a valid email address")
    ])
    name = StripWhitespaceStringField('Contact name', validators=[
        DataRequired(message="You must provide a contact name"),
    ])


class DunsNumberForm(DmForm):
    duns_number = StripWhitespaceStringField('DUNS Number', validators=[
        DataRequired(message="You must enter a DUNS number with 9 digits."),
        Regexp(r'^\d{9}$', message="You must enter a DUNS number with 9 digits."),
    ])


class CompaniesHouseNumberForm(DmForm):
    companies_house_number = StripWhitespaceStringField('Companies house number', validators=[
        Optional(),
        Length(min=8, max=8, message="Companies House numbers must have 8 characters.")
    ])


class CompanyNameForm(DmForm):
    company_name = StripWhitespaceStringField('Company name', validators=[
        DataRequired(message="You must provide a company name."),
        Length(max=255, message="You must provide a company name under 256 characters.")
    ])


class CompanyContactDetailsForm(DmForm):
    contact_name = StripWhitespaceStringField('Contact name', validators=[
        DataRequired(message="You must provide a contact name."),
        Length(max=255, message="You must provide a contact name under 256 characters.")
    ])
    email_address = StripWhitespaceStringField('Email address', validators=[
        DataRequired(message="You must provide a email address."),
        Email(message="You must provide a valid email address.")
    ])
    phone_number = StripWhitespaceStringField('Phone number', validators=[
        DataRequired(message="You must provide a phone number."),
        Length(max=20, message="You must provide a phone number under 20 characters.")
    ])


class EmailAddressForm(DmForm):
    email_address = StripWhitespaceStringField('Email address', validators=[
        DataRequired(message="You must provide a email address."),
        Email(message="You must provide a valid email address.")
    ])
