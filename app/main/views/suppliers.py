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


@main.route('/edit', methods=['GET'])
@login_required
def edit_supplier(error=None):
    template_data = main.config['BASE_TEMPLATE_DATA']

    try:
        supplier = data_api_client.get_supplier(
            current_user.supplier_id
        )['suppliers']
        supplier['contact'] = supplier['contactInformation'][0]
    except APIError as e:
        abort(e.status_code)

    return render_template(
        "suppliers/edit_supplier.html",
        supplier=supplier,
        error=error,
        **template_data
    ), 200


@main.route('/edit', methods=['POST'])
@login_required
def update_supplier():
    try:
        data_api_client.update_supplier(
            current_user.supplier_id,
            {
                "description": request.form['description'],
                "clients": request.form.getlist('clients'),
            },
            current_user.email_address,
            "Update supplier info"
        )

        data_api_client.update_contact_information(
            current_user.supplier_id,
            request.form['contactId'],
            {k: request.form[k] for k in [
                "address1", "address2", "city", "country", "postcode",
                "website", "phoneNumber", "email", "contactName",
            ]},
            current_user.email_address,
            "Update supplier info"
        )
    except APIError as e:
        return edit_supplier(error=e.message)

    return redirect(url_for(".dashboard"))
