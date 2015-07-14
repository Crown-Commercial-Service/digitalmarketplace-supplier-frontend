from flask import jsonify, current_app, request

from . import status
from .. import data_api_client
from dmutils.status import get_flags


@status.route('/_status')
def status():

    if 'ignore-dependencies' in request.args:
        return jsonify(
            status="ok",
        ), 200

    api_status = data_api_client.get_status()
    version = current_app.config['VERSION']

    if api_status['status'] == "ok":
        return jsonify(
            status="ok",
            version=version,
            api_status=api_status,
            flags=get_flags(current_app)
        )

    return jsonify(
        status="error",
        version=version,
        api_status=api_status,
        message="Error connecting to the (Data) API.",
        flags=get_flags(current_app)
    ), 500
