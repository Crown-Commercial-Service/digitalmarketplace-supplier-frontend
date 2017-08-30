from flask import Blueprint

external = Blueprint('external', __name__)


@external.route('/suppliers/opportunities/<int:brief_id>/responses/result')
def view_response_result(brief_id):
    raise NotImplementedError()


@external.route('/suppliers/opportunities/frameworks/<framework_slug>')
def opportunities_dashboard(framework_slug):
    raise NotImplementedError()


@external.route('/user/create/<encoded_token>')
def create_user(encoded_token):
    raise NotImplementedError()
