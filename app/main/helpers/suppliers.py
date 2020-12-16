import os
import json
from typing import Union
from datetime import datetime, timedelta

from flask import current_app


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


def is_g12_recovery_supplier(supplier_id: Union[str, int]) -> bool:
    supplier_ids_string = current_app.config.get('DM_G12_RECOVERY_SUPPLIER_IDS') or ''

    try:
        supplier_ids = [int(s) for s in supplier_ids_string.split(sep=',')]
    except AttributeError as e:
        current_app.logger.error("DM_G12_RECOVERY_SUPPLIER_IDS not a string", extra={'error': str(e)})
        return False
    except ValueError as e:
        current_app.logger.error("DM_G12_RECOVERY_SUPPLIER_IDS not a list of supplier IDs", extra={'error': str(e)})
        return False

    return int(supplier_id) in supplier_ids


G12_RECOVERY_DEADLINE = datetime(year=2025, month=1, day=1, hour=17)


def g12_recovery_time_remaining() -> str:
    return format_g12_recovery_time_remaining(G12_RECOVERY_DEADLINE - datetime.now())


def format_g12_recovery_time_remaining(time_to_deadline: timedelta) -> str:
    if time_to_deadline.days > 0:
        number, unit = time_to_deadline.days, 'day'
    elif time_to_deadline.seconds / 3600 >= 1:
        number, unit = int(time_to_deadline.seconds / 3600), 'hour'
    elif time_to_deadline.seconds / 60 >= 1:
        number, unit = int(time_to_deadline.seconds / 60), 'minute'
    elif time_to_deadline.seconds >= 0:
        number, unit = time_to_deadline.seconds, 'second'
    else:
        number, unit = 0, 'second'

    if number != 1:
        unit += 's'

    return f'{number} {unit}'
