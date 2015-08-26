from dmutils.apiclient import APIError
from flask import abort
from flask_login import current_user
from dmutils.audit import AuditTypes
import re
from operator import add
from functools import reduce
import six
from werkzeug.datastructures import ImmutableOrderedMultiDict


def has_registered_interest_in_framework(client, framework_slug):
    audits = client.find_audit_events(
        audit_type=AuditTypes.register_framework_interest,
        object_type='suppliers',
        object_id=current_user.supplier_id)
    for audit in audits['auditEvents']:
        if audit['data'].get('frameworkSlug') == framework_slug:
            return True
    return False


def register_interest_in_framework(client, framework_slug):
    if not has_registered_interest_in_framework(client, framework_slug):
        client.create_audit_event(
            audit_type=AuditTypes.register_framework_interest,
            user=current_user.email_address,
            object_type='suppliers',
            object_id=current_user.supplier_id,
            data={'frameworkSlug': framework_slug})


def get_last_modified_from_first_matching_file(key_list, path_starts_with):
    """
    Takes a list of file keys and a string.
    Returns the 'last_modified' timestamp for first file whose path starts with the passed-in string,
    or None if no matching file is found.

    :param key_list: list of file keys (from an s3 bucket)
    :param path_starts_with: check for file paths which start with this string
    :return: the timestamp of the first matching file key or None
    """
    return next((key for key in key_list if key.get('path').startswith(path_starts_with)), {}).get('last_modified')


def get_required_fields(all_fields, answers):
    required_fields = set(all_fields)
    #  Remove optional fields
    optional_fields = set([
        "SQ1-1d-i", "SQ1-1d-ii",
        "SQ1-1e", "SQ1-1p-i", "SQ1-1p-ii", "SQ1-1p-iii", "SQ1-1p-iv",
        "SQ1-1q-i", "SQ1-1q-ii", "SQ1-1q-iii", "SQ1-1q-iv", "SQ1-1cii", "SQ1-1i-ii",
        "SQ1-1j-i", "SQ1-1j-ii", "SQ1-3", "SQ4-1c", "SQ3-1k", "SQC3", "SQ1-1i-i",
    ])
    required_fields -= optional_fields
    #  If you answered other to question 19 (trading status)
    if answers.get('SQ1-1ci') == 'other (please specify)':
        required_fields.add('SQ1-1cii')

    #  If you answered yes to question 27 (non-UK business registered in EU)
    if answers.get('SQ1-1i-i', False):
        required_fields.add('SQ1-1i-ii')

    #  If you answered 'licensed' or 'a member of a relevant organisation' in question 29
    if len(answers.get('SQ1-1j-i', [])) > 0:
        required_fields.add('SQ1-1j-ii')

    # If you answered yes to either question 53 or 54 (tax returns)
    if answers.get('SQ4-1a', False) or answers.get('SQ4-1b', False):
        required_fields.add('SQ4-1c')

    # If you answered Yes to questions 39 - 51 (discretionary exclusion)
    dependent_fields = [
        'SQ2-2a', 'SQ3-1a', 'SQ3-1b', 'SQ3-1c', 'SQ3-1d', 'SQ3-1e', 'SQ3-1f', 'SQ3-1g',
        'SQ3-1h-i', 'SQ3-1h-ii', 'SQ3-1i-i', 'SQ3-1i-ii', 'SQ3-1j'
    ]
    if any(answers.get(field) for field in dependent_fields):
        required_fields.add('SQ3-1k')

    # If you answered No to question 26 (established in the UK)
    if not answers.get('SQ5-2a'):
        required_fields.add('SQ1-1i-i')
        required_fields.add('SQ1-1j-i')

    return required_fields


def get_all_fields(content):
    return reduce(add, (section.get_question_ids() for section in content))


def get_fields_with_values(answers):
    return set(key for key, value in answers.items()
               # empty list types will not be included so only string types need to be considered
               if not isinstance(value, six.string_types) or len(value) > 0)


def get_answer_required_errors(content, answers):
    required_fields = get_required_fields(content, answers)
    fields_with_values = get_fields_with_values(answers)
    errors_map = {}

    for field in required_fields - fields_with_values:
        errors_map[field] = 'answer_required'

    return errors_map


def get_character_limit_errors(content, answers):
    TEXT_FIELD_CHARACTER_LIMIT = 5000
    errors_map = {}
    for question_id in get_all_fields(content):
        if content.get_question(question_id).get('type') in ['text', 'textbox_large']:
            if len(answers.get(question_id, "")) > TEXT_FIELD_CHARACTER_LIMIT:
                errors_map[question_id] = "under_character_limit"

    return errors_map


def get_formatting_errors(answers):
    errors_map = {}
    if not re.match(r'^(\S{9}|\S{12})$', answers.get('SQ1-1h', '')):
        errors_map['SQ1-1h'] = 'invalid_format'

    return errors_map


def get_error_message(content, question_id, message_key):
    for validation in content.get_question(question_id).get('validations', []):
        if validation['name'] == message_key:
            return validation['message']
    default_messages = {
        'answer_required': 'Answer required'
    }
    return default_messages.get(
        message_key, 'There was a problem with the answer to this question')


def get_all_errors(content, answers):
    all_fields = set(get_all_fields(content))
    errors_map = {}

    errors_map.update(get_answer_required_errors(all_fields, answers))
    errors_map.update(get_character_limit_errors(content, answers))
    errors_map.update(get_formatting_errors(answers))

    return errors_map


def get_error_messages(content, answers):
    raw_errors_map = get_all_errors(content, answers)
    errors_map = list()
    for question_number, question_id in enumerate(get_all_fields(content)):
        if question_id in raw_errors_map:
            validation_message = get_error_message(content, question_id, raw_errors_map[question_id])
            errors_map.append((question_id, {
                'input_name': question_id,
                'question': "Question {}".format(question_number + 1),
                'message': validation_message,
            }))

    return errors_map


def get_error_messages_for_page(content, answers, section):
    all_errors = get_error_messages(content, answers)
    page_ids = section.get_question_ids()
    page_errors = ImmutableOrderedMultiDict(filter(lambda err: err[0] in page_ids, all_errors))
    return page_errors


def get_first_question_index(content, section):
    questions_so_far = 0
    ind = content.sections.index(section)
    for i in range(0, ind):
        questions_so_far += len(content.sections[i].get_question_ids())
    return questions_so_far


def get_declaration_status(data_api_client):
    try:
        answers = data_api_client.get_selection_answers(
            current_user.supplier_id, 'g-cloud-7'
        )['selectionAnswers']['questionAnswers']
    except APIError as e:
        if e.status_code == 404:
            return 'unstarted'
        else:
            abort(e.status_code)

    if not answers:
        return 'unstarted'
    else:
        return answers.get('status', 'unstarted')
