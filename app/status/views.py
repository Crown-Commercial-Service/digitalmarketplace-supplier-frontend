from flask import jsonify, current_app

from . import status
from . import utils


@status.route('/_status')
def status():
    for rule in current_app.url_map.iter_rules():
        print rule
    return jsonify(status="ok", version=utils.get_version_label())
