from flask import jsonify

from . import status
from . import utils
from .. import data_api_client


@status.route('/_status')
def status():

    api_status = data_api_client.get_status()

    if api_status['status'] == "ok":
        return jsonify(
            status="ok",
            version=utils.get_version_label(),
            api_status=api_status,
        )

    return jsonify(
        status="error",
        version=utils.get_version_label(),
        api_status=api_status,
        message="Error connecting to the (Data) API.",
    ), 500
