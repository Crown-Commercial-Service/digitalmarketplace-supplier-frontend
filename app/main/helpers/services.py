from flask import abort, current_app, url_for
from flask_login import current_user

from dmutils import s3
from dmutils.apiclient import APIError
from dmutils.documents import filter_empty_files, validate_documents, upload_document
from dmutils.service_attribute import Attribute
from dmutils.content_loader import PRICE_FIELDS

from ...main import new_service_content

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


def get_drafts(apiclient, supplier_id, framework_slug):
    try:
        drafts = apiclient.find_draft_services(
            current_user.supplier_id,
            framework='g-cloud-7'
        )['services']

    except APIError as e:
        abort(e.status_code)

    # Hide drafts without service name
    drafts = [draft for draft in drafts if draft.get('serviceName')]

    complete_drafts = [draft for draft in drafts if draft['status'] == 'submitted']
    drafts = [draft for draft in drafts if draft['status'] == 'not-submitted']

    return drafts, complete_drafts


def count_unanswered_questions(service_attributes):
    unanswered_required, unanswered_optional = (0, 0)
    for section in service_attributes:
        for question in section['rows']:
            if question.answer_required:
                unanswered_required += 1
            elif question.value in ['', [], None]:
                unanswered_optional += 1

    return unanswered_required, unanswered_optional


def get_service_attributes(service_data, service_questions):
    return list(map(
        lambda section: {
            'name': section['name'],
            'rows': _get_rows(section, service_data),
            'editable': section['editable'],
            'id': section['id']
        },
        service_questions
    ))


def _get_rows(section, service_data):
    return list(
        map(
            lambda question: Attribute(
                value=service_data.get(question['id'], None),
                question_type=question['type'],
                label=question['question'],
                optional=question.get('optional', False)
            ),
            section['questions']
        )
    )


def is_service_associated_with_supplier(service):
    return service.get('supplierId') == current_user.supplier_id


def is_service_modifiable(service):
    return service.get('status') != 'disabled'


def unformat_section_data(section_data):
    """Unpacks assurance questions
    """
    unformatted_section_data = {}
    for key in section_data:
        if _has_assurance(key):
            unformatted_section_data[key + '--assurance'] = section_data[key].get('assurance', '')
            unformatted_section_data[key] = section_data[key]['value']
    section_data.update(unformatted_section_data)


def get_draft_document_url(document_path):
    uploader = s3.S3(current_app.config['DM_G7_DRAFT_DOCUMENTS_BUCKET'])

    url = uploader.get_signed_url(document_path)
    if url is not None:
        url = urlparse.urlparse(url)
        base_url = urlparse.urlparse(current_app.config['DM_G7_DRAFT_DOCUMENTS_URL'])
        return url._replace(netloc=base_url.netloc, scheme=base_url.scheme).geturl()


def upload_draft_documents(service, request_files, section):
    request_files = request_files.to_dict(flat=True)
    files = _filter_keys(request_files, section.get_field_names())
    files = filter_empty_files(files)
    errors = validate_documents(files)

    if errors:
        return None, errors

    if len(files) == 0:
        return {}, {}

    uploader = s3.S3(current_app.config['DM_G7_DRAFT_DOCUMENTS_BUCKET'])

    for field, contents in files.items():
        url = upload_document(
            uploader, url_for('.dashboard', _external=True) + '/submission/documents/',
            service, field, contents,
            public=False
        )

        if not url:
            errors[field] = 'file_can_be_saved',
        else:
            files[field] = url

    return files, errors


def get_section_error_messages(errors, lot):
    errors_map = {}
    for error, message_key in errors.items():
        if error == '_form':
            abort(400, "Submitted data was not in a valid format")
        else:
            if error == 'serviceTypes':
                error = 'serviceTypes{}'.format(lot)
            elif error in PRICE_FIELDS:
                message_key = _rewrite_pricing_error_key(error, message_key)
                error = 'priceString'
            validation_message = get_error_message(error, message_key, new_service_content)
            question_id = new_service_content.get_question(error)['id']
            errors_map[question_id] = {
                'input_name': error,
                'question': new_service_content.get_question(error)['question'],
                'message': validation_message
            }
    return errors_map


def _rewrite_pricing_error_key(error, message_key):
    """Return a rewritten error message_key for a pricing error"""
    if message_key == 'answer_required':
        if error == 'priceMin':
            return 'no_min_price_specified'
        elif error == 'priceUnit':
            return 'no_unit_specified'
    elif message_key == 'not_money_format':
        if error == 'priceMin':
            return 'min_price_not_a_number'
        elif error == 'priceMax':
            return 'max_price_not_a_number'
    return message_key


def get_error_message(field, message_key, content):
    validations = [
        validation for validation in content.get_question(field)['validations']
        if validation['name'] == message_key]

    if len(validations):
        return validations[0]['message']
    else:
        return 'There was a problem with the answer to this question'


def _filter_keys(data, keys):
    """Return a dictionary filtered by a list of keys

    >>> _filter_keys({'a': 1, 'b': 2}, ['a'])
    {'a': 1}
    """
    key_set = set(keys) & set(data)
    return {key: data[key] for key in key_set}


def _is_pricing_type(key):
    # TODO: move into dmutils.content_loader
    """Return True if a given key is a pricing type"""
    return _is_type(key, 'pricing')


def _is_type(key, *types):
    # TODO: move into dmutils.content_loader
    """Return True if a given key is one of the provided types"""
    return new_service_content.get_question(key).get('type') in types


def _has_assurance(key):
    # TODO: move into dmutils.content_loader
    """Return True if a question has an assurance component"""
    return new_service_content.get_question(key).get('assuranceApproach', False)
