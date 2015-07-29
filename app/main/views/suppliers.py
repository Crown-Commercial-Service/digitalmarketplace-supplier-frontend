from flask import render_template, request, redirect, url_for, abort
from flask_login import login_required, current_user

from dmutils.apiclient import HTTPError
from dmutils import flask_featureflags

from ...main import main
from ... import data_api_client
from ..forms.suppliers import EditSupplierForm, EditContactInformationForm


@main.route('')
@login_required
@flask_featureflags.is_active_feature('SUPPLIER_DASHBOARD',
                                      redirect='.list_services')
def dashboard():
    template_data = main.config['BASE_TEMPLATE_DATA']

    try:
        supplier = data_api_client.get_supplier(
            current_user.supplier_id
        )['suppliers']
        supplier['contact'] = supplier['contactInformation'][0]
    except HTTPError as e:
        abort(e.status_code)

    return render_template(
        "suppliers/dashboard.html",
        supplier=supplier,
        **template_data
    ), 200


@main.route('/edit', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('EDIT_SUPPLIER_PAGE')
def edit_supplier(supplier_form=None, contact_form=None, error=None):
    template_data = main.config['BASE_TEMPLATE_DATA']

    try:
        supplier = data_api_client.get_supplier(
            current_user.supplier_id
        )['suppliers']
    except APIError as e:
        abort(e.status_code)

    if supplier_form is None:
        supplier_form = EditSupplierForm(
            description=supplier['description'],
            clients=supplier['clients']
        )
        contact_form = EditContactInformationForm(
            prefix='contact_',
            **supplier['contactInformation'][0]
        )

    return render_template(
        "suppliers/edit_supplier.html",
        error=error,
        supplier_form=supplier_form,
        contact_form=contact_form,
        **template_data
    ), 200


@main.route('/edit', methods=['POST'])
@login_required
@flask_featureflags.is_active_feature('EDIT_SUPPLIER_PAGE')
def update_supplier():
    # FieldList expects post parameter keys to have number suffixes
    # (eg client-0, client-1 ...), which is incompatible with how
    # JS list-entry plugin generates input names. So instead of letting
    # the form search for request keys we pass in the values directly as data
    supplier_form = EditSupplierForm(
        formdata=None,
        description=request.form['description'],
        clients=filter(None, request.form.getlist('clients'))
    )

    contact_form = EditContactInformationForm(prefix='contact_')

    if not (supplier_form.validate_on_submit() and
            contact_form.validate_on_submit()):
        return edit_supplier(supplier_form=supplier_form,
                             contact_form=contact_form)

    try:
        data_api_client.update_supplier(
            current_user.supplier_id,
            supplier_form.data,
            current_user.email_address
        )

        data_api_client.update_contact_information(
            current_user.supplier_id,
            contact_form.id.data,
            contact_form.data,
            current_user.email_address
        )
    except APIError as e:
        return edit_supplier(supplier_form=supplier_form,
                             contact_form=contact_form,
                             error=e.message)

    return redirect(url_for(".dashboard"))
