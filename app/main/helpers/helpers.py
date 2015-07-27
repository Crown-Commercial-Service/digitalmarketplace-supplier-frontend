from flask import abort
from dmutils.apiclient import APIError

from ... import data_api_client


def call_data_api_client(method_name, **kwargs):
    """
    Generalises calls to the DataAPIClient so that we don't have to
    worry about try/except blocks.

    :param method_name: an APIClient method name as a string
    :param kwargs:      any keyword arguments accepted by said method
    :return:            either the response from the api or an error
    """
    try:
        return getattr(data_api_client, method_name)(**kwargs)

    except APIError as e:
        abort(e.status_code)
