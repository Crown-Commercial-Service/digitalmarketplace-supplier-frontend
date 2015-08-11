from flask import render_template
from app.main import main
from dmutils.apiclient import APIError


@main.app_errorhandler(APIError)
def api_error_handler(e):
    return _render_error_page(e.status_code)


@main.app_errorhandler(404)
def page_not_found(e):
    return _render_error_page(404)


@main.app_errorhandler(500)
def exception(e):
    return _render_error_page(500)


@main.app_errorhandler(503)
def service_unavailable(e):
    return _render_error_page(503)


def _render_error_page(status_code):
    template_map = {
        404: "errors/404.html",
        500: "errors/500.html",
        503: "errors/500.html",
    }
    if status_code not in template_map:
        status_code = 500
    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template(template_map[status_code], **template_data), status_code
