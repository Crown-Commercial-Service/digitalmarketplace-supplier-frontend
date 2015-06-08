from flask import jsonify, current_app

from . import status
from .. import data_api_client
from dmutils.status import get_version_label, get_flags


@status.route('/_status')
def status():

    api_status = data_api_client.get_status()

    if api_status['status'] == "ok":
        return jsonify(
            status="ok",
            version=get_version_label(),
            api_status=api_status,
            flags=get_flags(current_app)
        )

    return jsonify(
        status="error",
        version=get_version_label(),
        api_status=api_status,
        message="Error connecting to the (Data) API.",
        flags=get_flags(current_app)
    ), 500
