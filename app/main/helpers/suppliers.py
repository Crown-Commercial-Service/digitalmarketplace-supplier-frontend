import os
import json


def load_countries():
    helpers_path = os.path.abspath(os.path.dirname(__file__))
    countryfile = os.path.join(helpers_path, '../../static/location-autocomplete-canonical-list.json')
    with open(countryfile) as f:
        return json.load(f)


def get_country_name_from_country_code(country_code):
    if country_code and country_code == 'gb':
        # We need to support the old country code style ('gb') until after the existing country code data we have in the
        # database has been updated by a script we'll run.
        # TODO: Remove support for old country codes after migration.
        return 'United Kingdom'
    elif country_code:
        for country in COUNTRY_TUPLE:
            if country[1] == country_code:
                return country[0]
        return ''
    else:
        # In the case that a suppliers registration country isn't set we maintain existing behavior, which is for the
        # country to be returned as an empty string. 15/02/18
        return ''


COUNTRY_TUPLE = load_countries()


def supplier_company_details_are_complete(supplier_data):
    supplier_required_fields = ['dunsNumber', 'name', 'registeredName', 'registrationCountry', 'organisationSize',
                                'tradingStatus']
    contact_required_fields = ['address1', 'city', 'postcode']

    # We require one of either 'companiesHouseNumber' or 'otherCompanyRegistrationNumber'
    if 'companiesHouseNumber' in supplier_data:
        supplier_required_fields.append('companiesHouseNumber')
    else:
        supplier_required_fields.append('otherCompanyRegistrationNumber')

    return (
        all([f in supplier_data and supplier_data[f] for f in supplier_required_fields]) and
        all([f in supplier_data['contactInformation'][0] and supplier_data['contactInformation'][0][f]
             for f in
             contact_required_fields])
    )


def get_company_details_from_supplier(supplier):
    address = {"country": supplier.get("registrationCountry")}
    if supplier.get('contactInformation'):
        address.update({
            "street_address_line_1": supplier['contactInformation'][0].get('address1'),
            "locality": supplier["contactInformation"][0].get("city"),
            "postcode": supplier["contactInformation"][0].get("postcode"),
        })
    return {
        "registration_number": (
            supplier.get("companiesHouseNumber")
            or
            supplier.get("otherCompanyRegistrationNumber")
        ),
        "registered_name": supplier.get("registeredName"),
        "address": address
    }
