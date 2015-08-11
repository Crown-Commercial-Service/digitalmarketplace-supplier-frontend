import re
from operator import add
from functools import reduce
import six


def get_required_fields(all_fields, answers):
    required_fields = set(all_fields)
    #  Remove optional fields
    optional_fields = [
        "SQ1-1e", "SQ1-1f", "SQ1-1p-i", "SQ1-1p-ii", "SQ1-1p-iii", "SQ1-1p-iv",
        "SQ1-1q-i", "SQ1-1q-ii", "SQ1-1q-iii", "SQ1-1q-iv"
    ]
    required_fields -= set(optional_fields)
    #  If you answered other to question 12
    if answers.get('SQ1-1ci') != 'other (please specify)':
        required_fields.remove('SQ1-1cii')
    #  If you answered yes to question 20
    if not answers.get('SQ1-1i-i', False):
        required_fields.remove('SQ1-1i-ii')
    #  If you answered 'licensed' or 'a member of a relevant organisation' in question 22
    if len(answers.get('SQ1-1j-i', [])) == 0:
        required_fields.remove('SQ1-1j-ii')

    # If you answered yes to either question 54 or 55
    if not answers.get('SQ4-1a', False) and not answers.get('SQ4-1b', False):
        required_fields.remove('SQ4-1c')

    # If you answered Yes to questions 41 - 53
    dependent_fields = [
        'SQ2-2a', 'SQ3-1a' 'SQ3-1b', 'SQ3-1c', 'SQ3-1d', 'SQ3-1e', 'SQ3-1f', 'SQ3-1g',
        'SQ3-1h-i', 'SQ3-1h-ii', 'SQ3-1i-i', 'SQ3-1i-ii', 'SQ3-1j'
    ]
    if all(not answers.get(field) for field in dependent_fields):
        required_fields.remove('SQ3-1k')

    return required_fields


def get_all_fields(content):
    return set(reduce(add, (section.get_question_ids() for section in content)))


def get_question_numbers(content):
    numbers = {}
    for section in content:
        for question_id in section.get_question_ids():
            numbers[question_id] = len(numbers) + 1
    return numbers


def get_fields_with_values(answers):
    return set(key for key, value in answers.items() if not isinstance(value, six.string_types) or len(value) > 0)


def get_answer_required_errors(content, answers):
    required_fields = get_required_fields(content, answers)
    fields_with_values = get_fields_with_values(answers)
    errors_map = {}

    for field in required_fields - fields_with_values:
        errors_map[field] = 'answer_required'

    return errors_map


def get_character_limit_errors(answers):
    length_limits = {
        "SQ1-1a": 5000,
        "SQ1-1cii": 5000,
        "SQ1-1d": 5000,
        "SQ1-1i-ii": 5000,
        "SQ3-1k": 5000,
    }
    errors_map = {}
    for field, limit in length_limits.items():
        if len(answers.get(field, "")) > limit:
            errors_map[field] = "under_character_limit"

    return errors_map


def get_formatting_errors(answers):
    errors_map = {}
    if not re.match(r'^\d{9}$', answers.get('SQ1-1g', '')):
        errors_map['SQ1-1g'] = 'invalid_format'
    if not re.match(r'^(\S{9}|\S{12})$', answers.get('SQ1-1h', '')):
        errors_map['SQ1-1h'] = 'invalid_format'

    return errors_map


def get_error_message(content, question_id, message_key):
    for validation in content.get_question(question_id).get('validations', []):
        if validation['name'] == message_key:
            return validation['message']
    default_messages = {
        'answer_required': 'This question is required'
    }
    return default_messages.get(
        message_key, 'There was a problem with the answer to this question')


def get_all_errors(content, answers):
    all_fields = get_all_fields(content)
    errors_map = {}

    errors_map.update(get_answer_required_errors(all_fields, answers))
    errors_map.update(get_character_limit_errors(answers))
    errors_map.update(get_formatting_errors(answers))

    return errors_map


def get_error_messages(content, answers):
    raw_errors_map = get_all_errors(content, answers)
    question_numbers = get_question_numbers(content)
    errors_map = {}
    for question_id, message_key in raw_errors_map.items():
        validation_message = get_error_message(content, question_id, message_key)
        errors_map[question_id] = {
            'input_name': question_id,
            'question': "Question {}".format(question_numbers[question_id]),
            'message': validation_message,
        }

    return errors_map
