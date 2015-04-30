import os
from requests.exceptions import ConnectionError


def get_version_label():
    try:
        path = os.path.join(os.path.dirname(__file__),
                            '..', '..', 'version_label')
        with open(path) as f:
            return f.read().strip()
    except IOError:
        return None


def return_response_from_api_status_call(api_status_call):

    try:
        return api_status_call()

    except ConnectionError:
        pass

    return None


def return_json_or_none(response):
    return None if response is None else response.json()
