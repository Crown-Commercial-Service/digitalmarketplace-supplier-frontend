from flask_login import login_required, current_user
from flask import render_template, request, redirect, url_for, abort

from ...main import main, existing_service_content, new_service_content
from ... import data_api_client, flask_featureflags, convert_to_boolean
from dmutils.apiclient import APIError, HTTPError
from dmutils.presenters import Presenters

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


#  #######################  EDITING LIVE SERVICES #############################


@main.route('/services/<string:service_id>', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('EDIT_SERVICE_PAGE')
def edit_service(service_id):
    service = data_api_client.get_service(service_id).get('services')

    if not _is_service_associated_with_supplier(service):
        abort(404)

    return _update_service_status(service)


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
                updated_service_status=updated_service.get("status"))
    )


@main.route('/services/<string:service_id>/edit/<string:section_id>', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('EDIT_SERVICE_PAGE')
def edit_section(service_id, section_id):
    service = data_api_client.get_service(service_id)
    if service is None:
        abort(404)
    service = service['services']

    if not _is_service_associated_with_supplier(service):
        abort(404)

    content = existing_service_content.get_builder().filter(service)
    section = content.get_section(section_id)
    if section is None:
        abort(404)

    return render_template(
        "services/edit_section.html",
        section=section,
        service_data=service,
        service_id=service_id,
        **main.config['BASE_TEMPLATE_DATA']
    )


def get_section_questions(section):
    return [question['id'] for question in section['questions']]


@main.route('/services/<string:service_id>/edit/<string:section_id>', methods=['POST'])
@login_required
@flask_featureflags.is_active_feature('EDIT_SERVICE_PAGE')
def update_section(service_id, section_id):
    service = data_api_client.get_service(service_id)
    if service is None:
        abort(404)
    service = service['services']

    if not _is_service_associated_with_supplier(service):
        abort(404)

    content = existing_service_content.get_builder().filter(service)
    section = content.get_section(section_id)
    if section is None:
        abort(404)

    posted_data = _get_formatted_section_data(section)

    try:
        data_api_client.update_service(
            service_id,
            posted_data,
            current_user.email_address,
            "supplier app")
    except HTTPError as e:
        errors_map = _get_section_error_messages(e, service['lot'])
        if not posted_data.get('serviceName', None):
            posted_data['serviceName'] = service.get('serviceName', '')
        return render_template(
            "services/edit_section.html",
            section=section,
            service_data=posted_data,
            service_id=service_id,
            errors=errors_map,
            **main.config['BASE_TEMPLATE_DATA']
        )

    return redirect(url_for(".edit_service", service_id=service_id))


#  ####################  CREATING NEW DRAFT SERVICES ##########################


@main.route('/submission/g-cloud-7/create', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def start_new_draft_service():
    """
    Page to kick off creation of a new (G7) service.
    """
    template_data = main.config['BASE_TEMPLATE_DATA']
    breadcrumbs = [
        {
            "link": "/",
            "label": "Digital Marketplace"
        },
        {
            "link": url_for(".dashboard"),
            "label": "Your account"
        },
        {
            "link": url_for(".framework_dashboard"),
            "label": "Apply to G-Cloud 7"
        }
    ]

    lots = new_service_content.get_question('lot')
    lots['type'] = 'radio'
    lots['name'] = 'lot'
    lots.pop('error', None)

    # errors if they exist
    error, errors = request.args.get('error', None), []
    if error:
        lots['error'] = error
        errors.append({
            "input_name": lots['name'],
            "question": lots['question']
        })

    return render_template(
        "services/create_new_draft_service.html",
        errors=errors,
        breadcrumbs=breadcrumbs,
        **dict(template_data, **lots)
    ), 200 if not errors else 400


@main.route('/submission/g-cloud-7/create', methods=['POST'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def create_new_draft_service():
    """
    Hits up the data API to create a new draft (G7) service.
    """
    lot = request.form.get('lot', None)

    if not lot:
        return redirect(
            url_for(".start_new_draft_service", error="Answer is required")
        )

    supplier_id = current_user.supplier_id
    user = current_user.email_address

    try:
        draft_service = data_api_client.create_new_draft_service(
            'g-cloud-7', supplier_id, user, lot
        )

    except APIError as e:
        abort(e.status_code)

    draft_service = draft_service.get('services')
    content = new_service_content.get_builder().filter(
        {'lot': draft_service.get('lot')}
    )

    return redirect(
        url_for(
            ".edit_service_submission",
            service_id=draft_service.get('id'),
            section_id=content.get_next_editable_section_id()
        )
    )


@main.route('/submission/services/<string:service_id>/copy', methods=['POST'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def copy_draft_service(service_id):
    draft = data_api_client.get_draft_service(service_id).get('services')

    if not _is_service_associated_with_supplier(draft):
        abort(404)

    try:
        data_api_client.copy_draft_service(
            service_id,
            current_user.email_address
        )

    except APIError as e:
        abort(e.status_code)

    return redirect(url_for(".framework_dashboard"))


@main.route('/submission/services/<string:service_id>', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def view_service_submission(service_id):
    try:
        draft = data_api_client.get_draft_service(service_id)['services']
    except HTTPError as e:
        abort(e.status_code)

    if not _is_service_associated_with_supplier(draft):
        abort(404)

    content = new_service_content.get_builder().filter(draft)

    return render_template(
        "services/service_submission.html",
        service_id=service_id,
        service_data=presenters.present_all(draft, new_service_content),
        sections=content,
        **main.config['BASE_TEMPLATE_DATA']), 200


@main.route('/submission/services/<string:service_id>/edit/<string:section_id>', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def edit_service_submission(service_id, section_id):
    try:
        draft = data_api_client.get_draft_service(service_id)['services']
    except HTTPError as e:
        abort(e.status_code)

    if not _is_service_associated_with_supplier(draft):
        abort(404)

    content = new_service_content.get_builder().filter(draft)
    section = content.get_section(section_id)
    if section is None:
        abort(404)

    return render_template(
        "services/edit_submission_section.html",
        section=section,
        service_data=draft,
        service_id=service_id,
        **main.config['BASE_TEMPLATE_DATA']
    )


@main.route('/submission/services/<string:service_id>/edit/<string:section_id>', methods=['POST'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def update_section_submission(service_id, section_id):
    try:
        draft = data_api_client.get_draft_service(service_id)['services']
    except HTTPError as e:
        abort(e.status_code)

    if not _is_service_associated_with_supplier(draft):
        abort(404)

    content = new_service_content.get_builder().filter(draft)
    section = content.get_section(section_id)
    if section is None:
        abort(404)

    posted_data = _get_formatted_section_data(section, with_page_questions=True)

    try:
        data_api_client.update_draft_service(
            service_id,
            posted_data,
            current_user.email_address)
    except HTTPError as e:
        errors_map = _get_section_error_messages(e, draft['lot'])
        if not posted_data.get('serviceName', None):
            posted_data['serviceName'] = draft.get('serviceName', '')
        return render_template(
            "services/edit_submission_section.html",
            section=section,
            service_data=posted_data,
            service_id=service_id,
            errors=errors_map,
            **main.config['BASE_TEMPLATE_DATA']
            )

    return_to_summary = bool(request.args.get('return_to_summary'))
    next_section = content.get_next_editable_section_id(section_id)

    if next_section and not return_to_summary:
        return redirect(url_for(".edit_service_submission", service_id=service_id, section_id=next_section))
    else:
        return redirect(url_for(".view_service_submission", service_id=service_id))


def _is_service_associated_with_supplier(service):
    return service.get('supplierId') == current_user.supplier_id


def _is_service_modifiable(service):
    return service.get('status') != 'disabled'


def _get_error_message(error, message_key, content):
    validations = [
        validation for validation in content.get_question(error)['validations']
        if validation['name'] == message_key]

    if len(validations):
        return validations[0]['message']
    else:
        return 'There was a problem with the answer to this question'


def _is_list_type(key):
    """Return True if a given key is a list type"""
    return key == 'serviceTypes' or _is_type(key, ['list', 'checkbox'])


def _is_boolean_type(key):
    """Return True if a given key is a boolean type"""
    return _is_type(key, ['boolean'])


def _is_type(key, types):
    """Return True if a given key is one of the provided types"""
    return new_service_content.get_question(key)['type'] in types


def _get_formatted_section_data(section, with_page_questions=False):
    section_data = dict(list(request.form.items()))
    section_questions = get_section_questions(section)
    section_data = _filter_keys(section_data, section_questions)
    # Turn responses which have multiple parts into lists and booleans into booleans
    for key in list(section_data.keys()):
        if _is_list_type(key):
            section_data[key] = request.form.getlist(key)
        elif _is_boolean_type(key):
            section_data[key] = convert_to_boolean(section_data[key])
        elif _is_type(key, ['pricing']):
            pricing_field = request.form.getlist(key)
            field_names = ['priceMin', 'priceMax', 'priceUnit', 'priceInterval']

            pricing_data = {
                field_name: pricing_field[i] for i, field_name in enumerate(field_names)
                if len(pricing_field[i]) > 0
            }
            section_data.update(pricing_data)
            section_questions += field_names

            del section_data['priceString']
            section_questions.remove('priceString')
    if with_page_questions:
        section_data['page_questions'] = section_questions
    return section_data


def _filter_keys(data, keys):
    """Return a dictionary filtered by a list of keys

    >>> _filter_keys({'a': 1, 'b': 2}, ['a'])
    {'a': 1}
    """
    key_set = set(keys) & set(data.keys())
    return {key: data[key] for key in key_set}


def _update_service_status(service, error_message=None):

    template_data = main.config['BASE_TEMPLATE_DATA']
    status_code = 400 if error_message else 200

    content = existing_service_content.get_builder().filter(service)

    question = {
        'question': 'Choose service status',
        'hint': 'Private services don\'t appear in search results '
                'and don\'t have a URL',
        'name': 'status',
        'type': 'radio',
        'inline': True,
        'value': "Public" if service['status'] == 'published' else "Private",
        'options': [
            {
                'label': 'Public'
            },
            {
                'label': 'Private'
            }
        ]
    }

    return render_template(
        "services/service.html",
        service_id=service.get('id'),
        service_data=presenters.present_all(service, existing_service_content),
        sections=content,
        error=error_message,
        **dict(question, **template_data)), status_code


def _get_section_error_messages(e, lot):
    errors_map = {}
    for error in e.message.keys():
        if error == '_form':
            abort(400, "Submitted data was not in a valid format")
        else:
            message_key = e.message[error]
            if error == 'serviceTypes':
                error = 'serviceTypes{}'.format(lot)
            elif error in ['priceMin', 'priceMax', 'priceUnit', 'priceInterval']:
                message_key = _rewrite_pricing_message_key(error, message_key)
                error = 'priceString'
            validation_message = _get_error_message(error,
                                                    message_key,
                                                    new_service_content)
            question_id = new_service_content.get_question(error)['id']
            errors_map[question_id] = {
                'input_name': error,
                'question': new_service_content.get_question(error)['question'],
                'message': validation_message
            }
    return errors_map


def _rewrite_pricing_message_key(error, message_key):
    if message_key == 'answer_required':
        if error == 'priceMin':
            return 'no_min_price_specified'
        elif error == 'priceUnit':
            return 'no_unit_specified'
    elif message_key == 'not_a_number':
        if error == 'priceMin':
            return 'min_price_not_a_number'
        elif error == 'priceMax':
            return 'max_price_not_a_number'
    return message_key
