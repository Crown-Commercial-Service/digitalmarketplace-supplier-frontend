from flask import request, abort
from flask_login import current_user

from dmutils.config import convert_to_boolean

from ...main import new_service_content


def get_section_questions(section):
    return [question['id'] for question in section['questions']]


def is_service_associated_with_supplier(service):
    return service.get('supplierId') == current_user.supplier_id


def is_service_modifiable(service):
    return service.get('status') != 'disabled'


def get_formatted_section_data(section):
    section_data = dict(list(request.form.items()))
    section_data = _filter_keys(section_data, get_section_questions(section))
    # Turn responses which have multiple parts into lists and booleans into booleans
    for key in section_data:
        if _is_list_type(key):
            section_data[key] = request.form.getlist(key)
        elif _is_boolean_type(key):
            section_data[key] = convert_to_boolean(section_data[key])
    return section_data


def get_section_error_messages(e, lot):
    errors_map = {}
    for error in e.message.keys():
        if error == '_form':
            abort(400, "Submitted data was not in a valid format")
        else:
            message_key = e.message[error]
            if error == 'serviceTypes':
                error = 'serviceTypes{}'.format(lot)
            validation_message = get_error_message(error, message_key, new_service_content)
            question_id = new_service_content.get_question(error)['id']
            errors_map[question_id] = {
                'input_name': error,
                'question': new_service_content.get_question(error)['question'],
                'message': validation_message
            }
    return errors_map


def get_error_message(error, message_key, content):
    validations = [
        validation for validation in content.get_question(error)['validations']
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
    key_set = set(keys) & set(data.keys())
    return {key: data[key] for key in key_set}


def _is_list_type(key):
    """Return True if a given key is a list type"""
    if key == 'serviceTypes':
        return True
    return new_service_content.get_question(key)['type'] in ['list', 'checkbox', 'pricing']


def _is_boolean_type(key):
    """Return True if a given key is a boolean type"""
    return new_service_content.get_question(key)['type'] == 'boolean'
