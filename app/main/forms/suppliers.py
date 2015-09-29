from wtforms import IntegerField, StringField, FieldList
from wtforms.validators import DataRequired, ValidationError, Length, Optional, Regexp, Email

from . import StripWhitespaceForm, strip_whitespace


def word_length(limit=None, message=None):
    message = message or 'Must not be more than %d words'
    message = message % limit

    def _length(form, field):
        if not field.data or not limit:
            return field

        if len(field.data.split()) > limit:
            raise ValidationError(message)

    return _length


class EditSupplierForm(StripWhitespaceForm):
    description = StringField('Supplier summary', validators=[
        word_length(50, 'Your summary must not be more than %d words')
    ])
    clients = FieldList(StringField(filters=[strip_whitespace]))

    def validate_clients(form, field):
        if len(field.data) > 10:
            raise ValidationError('You must have 10 or fewer clients')


class EditContactInformationForm(StripWhitespaceForm):
    id = IntegerField()
    address1 = StringField('Business address')
    address2 = StringField('Business address')
    city = StringField('Town or city')
    country = StringField()
    postcode = StringField()
    website = StringField()
    phoneNumber = StringField('Phone number')
    email = StringField('Email address', validators=[
        DataRequired(message="Email can not be empty"),
        Email(message="Please enter a valid email address")
    ])
    contactName = StringField('Contact name', validators=[
        DataRequired(message="Contact name can not be empty"),
    ])


class DunsNumberForm(StripWhitespaceForm):
    duns_number = StringField('DUNS Number', validators=[
        DataRequired(message="You must enter a DUNS number with 9 digits."),
        Regexp(r'^\d{9}$', message="You must enter a DUNS number with 9 digits."),
    ])


class CompaniesHouseNumberForm(StripWhitespaceForm):
    companies_house_number = StringField('Companies house number', validators=[
        Optional(),
        Length(min=8, max=8, message="Companies House numbers must have 8 characters.")
    ])


class CompanyNameForm(StripWhitespaceForm):
    company_name = StringField('Company name', validators=[
        DataRequired(message="You must provide a company name."),
        Length(max=255, message="You must provide a company name under 256 characters.")
    ])


class CompanyContactDetailsForm(StripWhitespaceForm):
    contact_name = StringField('Contact name', validators=[
        DataRequired(message="You must provide a contact name."),
        Length(max=255, message="You must provide a contact name under 256 characters.")
    ])
    email_address = StringField('Email address', validators=[
        DataRequired(message="You must provide a email address."),
        Email(message="You must provide a valid email address.")
    ])
    phone_number = StringField('Phone number', validators=[
        DataRequired(message="You must provide a phone number."),
        Length(max=20, message="You must provide a phone number under 20 characters.")
    ])


class EmailAddressForm(StripWhitespaceForm):
    email_address = StringField('Email address', validators=[
        DataRequired(message="You must provide a email address."),
        Email(message="You must provide a valid email address.")
    ])
