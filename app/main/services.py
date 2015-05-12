from flask_login import login_required, current_user
from flask import render_template, request, redirect, url_for

from app.main import main
from .. import data_api_client
from dmutils.apiclient import APIError


@main.route('/')
@login_required
def dashboard():
    template_data = main.config['BASE_TEMPLATE_DATA']
    suppliers_services = data_api_client.find_services(
        supplier_id=current_user.supplier_id
    )

    return render_template(
        "services/dashboard.html",
        services=suppliers_services["services"],
        updated_service_id=request.args.get('updated_service_id'),
        updated_service_name=request.args.get('updated_service_name'),
        updated_service_status=request.args.get('updated_service_status'),
        **template_data), 200


@main.route('/services/<string:service_id>', methods=['GET'])
@login_required
def services(service_id):
    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template(
        "services/service.html",
        service_id=service_id,
        service_data=data_api_client.get_service(service_id).get('services'),
        **template_data), 200


# Might have to change the route if we're generalizing this to update
@main.route('/services/<string:service_id>', methods=['POST'])
@login_required
def update_service_status(service_id):
    template_data = main.config['BASE_TEMPLATE_DATA']

    # Value should be either public or private
    status = request.form['service_status']

    translate_frontend_to_api = {
        'public': 'published',
        'private': 'enabled'
    }

    if status in translate_frontend_to_api.keys():
        status = translate_frontend_to_api[status]

    try:
        updated_service = data_api_client.update_service_status(
            service_id, status,
            current_user.email_address, "Status changed to '{0}'".format(
                status))

    except APIError as e:

        error_message = "Sorry, there's been a problem updating the status."

        # If we try to update with a status that's not a real status
        if "400 Client Error: BAD REQUEST" in e.message:
            error_message = "Sorry, but '{}' is not a valid status.".format(
                status
            )

        return render_template(
            "services/service.html",
            service_id=service_id,
            service_data=data_api_client.get_service(
                service_id).get('services'),
            error=error_message,
            **template_data), 200

    updated_service = updated_service.get("services")
    return redirect(
        url_for(".dashboard",
                updated_service_id=updated_service.get("id"),
                updated_service_name=updated_service.get("serviceName"),
                updated_service_status=updated_service.get("status")
                )
    )
