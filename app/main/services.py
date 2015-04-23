from . import main
from flask import render_template


@main.route('/dashboard')
def dashboard():
    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template(
        "services/dashboard.html",
        **template_data), 200


@main.route('/services')
def services():
    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template(
        "services/services.html",
        **template_data), 200
