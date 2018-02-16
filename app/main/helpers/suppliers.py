import os
import json


def load_countries():
    helpers_path = os.path.abspath(os.path.dirname(__file__))
    countryfile = os.path.join(helpers_path, '../../static/location-autocomplete-canonical-list.json')
    with open(countryfile) as f:
        return (json.load(f))


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
