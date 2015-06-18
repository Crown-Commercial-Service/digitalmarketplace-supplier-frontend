from flask import render_template, abort
from flask_login import login_required, current_user

from dmutils.apiclient import APIError
from dmutils import flask_featureflags

from ...main import main
from ... import data_api_client


@main.route('/frameworks/g-cloud-7', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('FRAMEWORK_DASHBOARD')
def framework_dashboard():
    template_data = main.config['BASE_TEMPLATE_DATA']

    try:
        supplier = data_api_client.get_supplier(
            current_user.supplier_id
        )['suppliers']
    except APIError as e:
        abort(e.status_code)

    # get the framework
    # get the list of

    return render_template(
        "frameworks/dashboard.html",
        supplier=supplier,
        **template_data
    ), 200
