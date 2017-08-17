from flask import Blueprint

external = Blueprint('external', __name__)


@external.route('/suppliers/opportunities/<int:brief_id>/responses/result')
def view_response_result(brief_id):
    raise NotImplementedError()
