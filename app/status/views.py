from flask import jsonify, current_app

from . import status
from . import utils
from .. import data_api_client


@status.route('/_status')
def status():

    api_response = utils.return_response_from_api_status_call(
        data_api_client.get_status
    )

    apis_with_errors = []

    if api_response is None or api_response.status_code != 200:
        apis_with_errors.append("(Data) API")

    # if no errors found, return everything
    if not apis_with_errors:
        return jsonify(
            status="ok",
            version=utils.get_version_label(),
            api_status=api_response.json(),
        )

    message = "Error connecting to the {}.".format(
        " and the ".join(apis_with_errors)
    )

    current_app.logger.error(message)

    return jsonify(
        status="error",
        version=utils.get_version_label(),
        api_status=utils.return_json_or_none(api_response),
        message=message,
    ), 500
