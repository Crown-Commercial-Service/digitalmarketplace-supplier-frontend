from flask import render_template, request, redirect, url_for, abort
from flask_login import login_required, current_user

from dmutils.apiclient import APIError

from ...main import main
from ... import data_api_client


@main.route('')
@login_required
def dashboard():
    template_data = main.config['BASE_TEMPLATE_DATA']

    try:
        supplier = data_api_client.get_supplier(
            current_user.supplier_id
        )['suppliers']
        supplier['contact'] = supplier['contactInformation'][0]
    except APIError as e:
        abort(e.status_code)

    return render_template(
        "suppliers/dashboard.html",
        supplier=supplier,
        **template_data
    ), 200
