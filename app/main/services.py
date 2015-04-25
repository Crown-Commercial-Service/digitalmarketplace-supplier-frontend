from flask_login import login_required, current_user
from app.main import main
from flask import render_template
from .. import api_client


@main.route('/dashboard')
@login_required
def dashboard():
    template_data = main.config['BASE_TEMPLATE_DATA']
    suppliers_services = api_client.services_by_supplier_id(current_user.supplier_id)

    return render_template(
        "services/dashboard.html",
        services=suppliers_services["services"],
        **template_data), 200


@main.route('/services')
@login_required
def services():
    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template(
        "services/services.html",
        **template_data), 200
