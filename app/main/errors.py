try:
    from urllib import quote_plus
except ImportError:
    from urllib.parse import quote_plus
from flask import redirect, render_template, request
from app.main import main
from dmapiclient import APIError
from dmutils.s3 import S3ResponseError
from dmutils.content_loader import QuestionNotFoundError


@main.app_errorhandler(APIError)
def api_error_handler(e):
    return _render_error_page(e.status_code)


@main.app_errorhandler(S3ResponseError)
def s3_response_error_handler(e):
    return _render_error_page(503)


@main.app_errorhandler(QuestionNotFoundError)
def content_loader_error_handler(e):
    return _render_error_page(400)


@main.app_errorhandler(401)
def page_unauthorized(e):
    if request.method == 'GET':
        return redirect('/login?next={}'.format(quote_plus(request.path)))
    else:
        return redirect('/login')


@main.app_errorhandler(404)
def page_not_found(e):
    return _render_error_page(404)


@main.app_errorhandler(500)
def internal_server_error(e):
    return _render_error_page(500)


@main.app_errorhandler(503)
def service_unavailable(e):
    return _render_error_page(503)


def _render_error_page(status_code):
    template_map = {
        400: "errors/500.html",
        404: "errors/404.html",
        500: "errors/500.html",
        503: "errors/500.html",
    }
    if status_code not in template_map:
        status_code = 500
    return render_template(template_map[status_code]), status_code
