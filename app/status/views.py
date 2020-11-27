from flask import request

from . import status
from .. import data_api_client
from dmutils.status import get_app_status


@status.route('/_status')
def show_status():
    return get_app_status(data_api_client=data_api_client,
                          search_api_client=None,
                          ignore_dependencies='ignore-dependencies' in request.args)
