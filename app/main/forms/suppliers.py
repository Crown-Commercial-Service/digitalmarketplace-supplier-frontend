from flask.ext.wtf import Form
from wtforms import IntegerField, StringField, FieldList
from wtforms.validators import DataRequired, Email


class EditSupplierForm(Form):
    description = StringField()
    clients = FieldList(StringField(), max_entries=10)


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
