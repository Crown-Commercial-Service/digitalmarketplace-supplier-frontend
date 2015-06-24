from flask_login import login_required, current_user
from flask import render_template, request, redirect, url_for, abort

from ...main import main
from ... import data_api_client, flask_featureflags
from dmutils.apiclient import APIError, HTTPError
from dmutils.content_loader import ContentBuilder, YAMLLoader
from dmutils.presenters import Presenters

existing_service_options = [
    "app/section_order.yml",
    "app/content/g6/",
    YAMLLoader()
]
presenters = Presenters()


@main.route('/services')
@login_required
def list_services():
    template_data = main.config['BASE_TEMPLATE_DATA']
    suppliers_services = data_api_client.find_services(
        supplier_id=current_user.supplier_id
    )

    return render_template(
        "services/list_services.html",
        services=suppliers_services["services"],
        updated_service_id=request.args.get('updated_service_id'),
        updated_service_name=request.args.get('updated_service_name'),
        updated_service_status=request.args.get('updated_service_status'),
        **template_data), 200


@main.route('/services/<string:service_id>', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('EDIT_SERVICE_PAGE')
def edit_service(service_id):
    service = data_api_client.get_service(service_id).get('services')

    if not _is_service_associated_with_supplier(service):
        abort(404)

    return _update_service_status(service)


# Might have to change the route if we're generalizing this to update
@main.route('/services/<string:service_id>', methods=['POST'])
@login_required
@flask_featureflags.is_active_feature('EDIT_SERVICE_PAGE')
def update_service_status(service_id):
    service = data_api_client.get_service(service_id).get('services')

    if not _is_service_associated_with_supplier(service):
        abort(404)

    if not _is_service_modifiable(service):
        return _update_service_status(
            service,
            "Sorry, but this service isn't modifiable."
        )

    # Value should be either public or private
    status = request.form.get('status', '').lower()

    translate_frontend_to_api = {
        'public': 'published',
        'private': 'enabled'
    }

    if status in translate_frontend_to_api.keys():
        status = translate_frontend_to_api[status]
    else:
        return _update_service_status(
            service,
            "Sorry, but '{}' is not a valid status.".format(status)
        )

    try:
        updated_service = data_api_client.update_service_status(
            service.get('id'), status,
            current_user.email_address, "Status changed to '{0}'".format(
                status))

    except APIError:

        return _update_service_status(
            service,
            "Sorry, there's been a problem updating the status."
        )

    updated_service = updated_service.get("services")
    return redirect(
        url_for(".list_services",
                updated_service_id=updated_service.get("id"),
                updated_service_name=updated_service.get("serviceName"),
                updated_service_status=updated_service.get("status")
                )
    )


@main.route(
    '/services/<string:service_id>/edit/<string:section>',
    methods=['GET']
)
@login_required
@flask_featureflags.is_active_feature('EDIT_SERVICE_PAGE')
def edit_section(service_id, section):

    service = data_api_client.get_service(service_id)['services']

    if not _is_service_associated_with_supplier(service):
        abort(404)
    content = ContentBuilder(*existing_service_options)

    return render_template(
        "services/edit_section.html",
        section=content.get_section_filtered_by(section, service),
        service_data=service,
        service_id=service_id,
        **main.config['BASE_TEMPLATE_DATA']
    )


@main.route(
    '/services/<string:service_id>/edit/<string:section>',
    methods=['POST']
)
@login_required
@flask_featureflags.is_active_feature('EDIT_SERVICE_PAGE')
def update_section(service_id, section):
    service = data_api_client.get_service(service_id).get('services')

    if not _is_service_associated_with_supplier(service):
        abort(404)

    content = ContentBuilder(*existing_service_options)

    posted_data = dict(
        list(request.form.items()) + list(request.files.items())
    )

    posted_data.pop('csrf_token', None)

    # Turn responses which have multiple parts into lists
    for key in request.form:
        item_as_list = request.form.getlist(key)
        list_types = ['list', 'checkboxes', 'pricing']
        if (
            key != 'csrf_token' and
            content.get_question(key)['type'] in list_types
        ):
            posted_data[key] = item_as_list

    if posted_data:
        try:
            data_api_client.update_service(
                service_id,
                posted_data,
                "user",
                "supplier app")
        except HTTPError as e:
            return render_template(
                "services/edit_section.html",
                section=content.get_section_filtered_by(section, service),
                service_data=service,
                service_id=service_id,
                error=e.message,
                **main.config['BASE_TEMPLATE_DATA']
            )

    return redirect(url_for(".edit_service", service_id=service_id))


def _is_service_associated_with_supplier(service):

    return service.get('supplierId') == current_user.supplier_id


def _is_service_modifiable(service):

    return service.get('status') != 'disabled'


def _update_service_status(service, error_message=None):

    template_data = main.config['BASE_TEMPLATE_DATA']
    content = ContentBuilder(*existing_service_options)
    status_code = 400 if error_message else 200

    question = {
        'question': 'Choose service status',
        'hint': 'Private services don\'t appear in search results '
                'and don\'t have a URL',
        'name': 'status',
        'type': 'radio',
        'inline': True,
        'options': [
            {
                'checked': service['status'] == 'published',
                'label': 'Public'
            },
            {
                'checked': service['status'] == 'enabled',
                'label': 'Private'
            }
        ]
    }

    return render_template(
        "services/service.html",
        service_id=service.get('id'),
        service_data=presenters.present_all(service, content),
        sections=content.get_sections_filtered_by(service),
        error=error_message,
        **dict(question, **template_data)), status_code
