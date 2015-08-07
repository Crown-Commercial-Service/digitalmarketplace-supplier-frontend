from flask import request, abort, current_app, url_for
from flask_login import current_user

from dmutils.config import convert_to_boolean, convert_to_number
from dmutils import s3
from dmutils.documents import filter_empty_files, validate_documents, upload_document
from dmutils.service_attribute import Attribute
from app.main import new_service_content


def get_section_questions(section):
    """Return the section question IDs as they are sent to the API"""
    return price_question_filter(get_raw_section_questions(section))


def get_raw_section_questions(section):
    """Return the section question IDs as they appear in the question manifest"""
    return [question['id'] for question in section['questions']]


def get_service_attributes(service_data, service_questions):
    return map(
        lambda section: {
            'name': section['name'],
            'rows': _get_rows(section, service_data),
            'editable': section['editable'],
            'id': section['id']
        },
        service_questions
    )


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


def get_formatted_section_data(section):
    """Validate, filter and format form data to match the section content.

    Removes any keys from the request that do not match any of the current
    section questions list.

    Converts list and boolean fields from strings to correct types.

    Removes file upload questions from the request.form: file uploads should
    only be accepted as files, since accepting URLs directly as form data
    requires additional validation.

    Packs assurance back into a dict

    """

    section_data = {}
    for key in set(request.form) & set(get_raw_section_questions(section)):

        if _is_list_type(key):
            section_data[key] = request.form.getlist(key)
        elif _is_boolean_type(key):
            section_data[key] = convert_to_boolean(request.form[key])
        elif _is_numeric_type(key):
            section_data[key] = convert_to_number(request.form[key])
        elif _is_pricing_type(key):
            section_data.update(
                expand_pricing_field(request.form.getlist(key))
            )
        elif _is_not_upload(key):
            section_data[key] = request.form[key]

        if _has_assurance(key):
            section_data[key] = {
                "value": section_data[key],
                "assurance": request.form.get(key + '--assurance')
            }

    return section_data


PRICE_FIELDS = ['priceMin', 'priceMax', 'priceUnit', 'priceInterval']


def expand_pricing_field(pricing):
    """Expand the priceString list into a dictionary"""
    return {
        field_name: pricing[i] for i, field_name in enumerate(PRICE_FIELDS)
        if len(pricing[i]) > 0
    }


def price_question_filter(questions):
    if any(map(_is_pricing_type, questions)):
        questions = [
            q for q in questions if not _is_pricing_type(q)
        ] + PRICE_FIELDS

    return questions


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

    return uploader.get_signed_url(document_path)


def upload_draft_documents(service, request_files, section):
    request_files = request_files.to_dict(flat=True)
    files = _filter_keys(request_files, get_section_questions(section))
    files = filter_empty_files(files)
    errors = validate_documents(files)

    if errors:
        return None, errors

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


def _is_not_upload(key):
    """Return True if a given key is not a file upload"""
    return new_service_content.get_question(key)['type'] != 'upload'


def _is_list_type(key):
    """Return True if a given key is a list type"""
    return key == 'serviceTypes' or _is_type(key, 'list', 'checkboxes')


def _is_boolean_type(key):
    """Return True if a given key is a boolean type"""
    return _is_type(key, 'boolean')


def _is_numeric_type(key):
    """Return True if a given key is a numeric type"""
    return _is_type(key, 'percentage')


def _is_pricing_type(key):
    """Return True if a given key is a pricing type"""
    return _is_type(key, 'pricing')


def _is_type(key, *types):
    """Return True if a given key is one of the provided types"""
    return new_service_content.get_question(key)['type'] in types


def _has_assurance(key):
    """Return True if a question has an assurance component"""
    return new_service_content.get_question(key).get('assuranceApproach', False)
