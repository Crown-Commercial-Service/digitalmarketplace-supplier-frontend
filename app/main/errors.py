from flask import render_template
from . import main


@main.app_errorhandler(404)
def page_not_found(e):
    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template("errors/404.html", **template_data), 404


@main.app_errorhandler(500)
def exception(e):
    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template("errors/500.html", **template_data), 500
