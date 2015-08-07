from flask.ext.wtf import Form
from wtforms import IntegerField, StringField, FieldList
from wtforms.validators import DataRequired, Email, ValidationError, NumberRange, Length, Optional


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
    description = StringField('Supplier summary', validators=[
        word_length(50, 'Your summary must not be more than %d words')
    ])
    clients = FieldList(StringField())

    def validate_clients(form, field):
        if len(field.data) > 10:
            raise ValidationError('You must have 10 or fewer clients')


class EditContactInformationForm(Form):
    id = IntegerField()
    address1 = StringField('Business address')
    address2 = StringField('Business address')
    city = StringField('Town or city')
    country = StringField()
    postcode = StringField(validators=[
        DataRequired(message="Postcode can not be empty"),
    ])
    website = StringField()
    phoneNumber = StringField('Phone number')
    email = StringField('Email address', validators=[
        DataRequired(message="Email can not be empty"),
        Email(message="Please enter a valid email address")
    ])
    contactName = StringField('Contact name', validators=[
        DataRequired(message="Contact name can not be empty"),
    ])


class DunsNumberForm(Form):
    duns_number = IntegerField('DUNS Number', validators=[
        DataRequired(message="DUNS Number must be 9 digits"),
        NumberRange(min=100000000, max=999999999, message="DUNS Number must be 9 digits")
    ])


class CompaniesHouseNumberForm(Form):
    companies_house_number = StringField('Companies house number', validators=[
        Optional(),
        Length(min=8, max=8, message="Companies house number must be 8 characters")
    ])


class CompanyNameForm(Form):
    company_name = StringField('Company name', validators=[
        DataRequired(message="Company name is required"),
        Length(max=255, message="Company name must be under 256 characters")
    ])


class CompanyContactDetailsForm(Form):
    contact_name = StringField('Contact name', validators=[
        DataRequired(message="Contact name can not be empty"),
        Length(max=255, message="Contact name must be under 256 characters")
    ])
    email_address = StringField('Email address', validators=[
        DataRequired(message="Email can not be empty"),
        Email(message="Please enter a valid email address")
    ])
    phone_number = StringField('Phone number', validators=[
        DataRequired(message="Phone number can not be empty"),
        Length(max=20, message="Phone number must be under 20 characters")
    ])


class EmailAddressForm(Form):
    email_address = StringField('Email address', validators=[
        DataRequired(message="Email can not be empty"),
        Email(message="Please enter a valid email address")
    ])
