#!/usr/bin/env python
"""Generate JSON schemas from the frameworks questions content.

Usage:
    generate-schemas.py --output-path=<output_path>

"""

import os
import re
import json

from docopt import docopt
from dmutils.content_loader import ContentLoader


SCHEMAS = [
    ('G-Cloud 7 SCS', 'g-cloud-7', 'scs'),
    ('G-Cloud 7 IaaS', 'g-cloud-7', 'iaas'),
    ('G-Cloud 7 PaaS', 'g-cloud-7', 'paas'),
    ('G-Cloud 7 SaaS', 'g-cloud-7', 'saas'),
    ('Digital Outcomes and Specialists Digital outcomes',
     'digital-outcomes-and-specialists', 'digital-outcomes'),
    ('Digital Outcomes and Specialists Digital specialists',
     'digital-outcomes-and-specialists', 'digital-specialists'),
    ('Digital Outcomes and Specialists User research studios',
     'digital-outcomes-and-specialists', 'user-research-studios'),
    ('Digital Outcomes and Specialists User research participants',
     'digital-outcomes-and-specialists', 'user-research-participants'),
]


def load_questions(framework_slug, lot_slug):
    loader = ContentLoader('./')
    loader.load_manifest(framework_slug, 'services', 'edit_submission')

    builder = loader.get_builder(framework_slug, 'edit_submission').filter({'lot': lot_slug})
    return {q['id']: q for q in sum((s.questions for s in builder.sections), [])}


def drop_non_schema_questions(questions):
    for key in ['id', 'lot', 'lotName']:
        questions.pop(key, None)


def empty_schema(schema_name):
    return {
        "title": "{} Service Schema".format(schema_name),
        "$schema": "http://json-schema.org/schema#",
        "type": "object",
        "additionalProperties": False,
        "properties": {},
        "required": [],
    }


def text_property(question):
    data = {
        "type": "string",
        "minLength": 0 if question.get('optional') else 1,
    }

    data.update(parse_question_limits(question))

    return {question['id']: data}


def uri_property(question):
    return {question['id']: {
        "type": "string",
        "format": "uri",
    }}


def checkbox_property(question):
    return {question['id']: {
        "type": "array",
        "uniqueItems": True,
        "minItems": 0 if question.get('optional') else 1,
        "maxItems": len(question['options']),
        "items": {
            "enum": [option['label'] for option in question['options']]
        }
    }}


def radios_property(question):
    return {question['id']: {
        "enum": [option['label'] for option in question['options']]
    }}


def boolean_property(question):
    return {question['id']: {
        "type": "boolean"
    }}


def list_property(question):
    return {question['id']: {
        "type": "array",
        "minItems": 0 if question.get('optional') else 1,
        "maxItems": 10,
        "items": {
            "type": "string",
            "maxLength": 100,
            "pattern": "^(?:\\S+\\s+){0,9}\\S+$"
        }
    }}


def price_string(optional):
    pattern = r"^\d+(?:\.\d{1,5})?$"
    if optional:
        pattern = r"^$|" + pattern
    return {
        "type": "string",
        "pattern": pattern,
    }


def pricing_property(question):
    pricing = {}
    if 'minimum_price' in question.fields:
        pricing[question.fields['minimum_price']] = price_string(
            'minimum_price' in question.get('optional_fields', [])
        )
    if 'maximum_price' in question.fields:
        pricing[question.fields['maximum_price']] = price_string(
            'maximum_price' in question.get('optional_fields', [])
        )
    if 'price_unit' in question.fields:
        pricing[question.fields['price_unit']] = {
            "enum": [
                "Unit",
                "Person",
                "Licence",
                "User",
                "Device",
                "Instance",
                "Server",
                "Virtual machine",
                "Transaction",
                "Megabyte",
                "Gigabyte",
                "Terabyte"
            ]
        }
        if 'price_unit' in question.get('optional_fields', []):
            pricing[question.fields['price_unit']]['enum'].insert(0, "")
    if 'price_interval' in question.fields:
        pricing[question.fields['price_interval']] = {
            "enum": [
                "Second",
                "Minute",
                "Hour",
                "Day",
                "Week",
                "Month",
                "Quarter",
                "6 months",
                "Year"
            ]
        }
        if 'price_interval' in question.get('optional_fields', []):
            pricing[question.fields['price_interval']]['enum'].insert(0, "")

    return pricing


def percentage_property(question):
    return {question['id']: {
        "exclusiveMaximum": True,
        "maximum": 100,
        "minimum": 0,
        "type": "number"
    }}


def multiquestion(question):
    properties = {}
    for nested_question in question['questions']:
        properties.update(build_question_properties(nested_question))

    return properties


QUESTION_TYPES = {
    'text': text_property,
    'upload': uri_property,
    'textbox_large': text_property,
    'checkboxes': checkbox_property,
    'radios': radios_property,
    'boolean': boolean_property,
    'list': list_property,
    'pricing': pricing_property,
    'percentage': percentage_property,
    'multiquestion': multiquestion
}


def parse_question_limits(question):
    limits = {}
    word_length_validator = next(
        iter(filter(None, (
            re.match('under_(\d+)_words', validator['name'])
            for validator in question.get('validations', [])
        ))),
        None
    )
    char_length_validator = next(
        iter(filter(None, (
            re.search('(\d+)', validator['message'])
            for validator in question.get('validations', [])
            if validator['name'] == 'under_character_limit'
        ))),
        None
    )

    char_length = question.get('max_length') or (char_length_validator and char_length_validator.group(1))
    word_length = question.get('max_length_in_words') or (word_length_validator and word_length_validator.group(1))

    if char_length:
        limits['maxLength'] = int(char_length)

    if word_length:
        if question.get('optional'):
            limits['pattern'] = r"^$|(^(?:\S+\s+){0,%s}\S+$)" % (int(word_length) - 1)
        else:
            limits['pattern'] = r"^(?:\S+\s+){0,%s}\S+$" % (int(word_length) - 1)

    return limits


def add_assurance(value_schema, assurance_approach):
    assurance_options = {
        '2answers-type1': [
            'Service provider assertion', 'Independent validation of assertion'
        ],
        '3answers-type1': [
            'Service provider assertion', 'Contractual commitment', 'Independent validation of assertion'
        ],
        '3answers-type2': [
            'Service provider assertion', 'Independent validation of assertion',
            'Independent testing of implementation'
        ],
        '3answers-type3': [
            'Service provider assertion', 'Independent testing of implementation', 'CESG-assured components'
        ],
        '3answers-type4': [
            'Service provider assertion', 'Independent validation of assertion',
            'Independent testing of implementation'
        ],
        '4answers-type1': [
            'Service provider assertion', 'Independent validation of assertion',
            'Independent testing of implementation', 'CESG-assured components'
        ],
        '4answers-type2': [
            'Service provider assertion', 'Contractual commitment',
            'Independent validation of assertion', 'CESG-assured components'
        ],
        '4answers-type3': [
            'Service provider assertion', 'Independent testing of implementation',
            'Assurance of service design', 'CESG-assured components'
        ],
        '5answers-type1': [
            'Service provider assertion', 'Contractual commitment', 'Independent validation of assertion',
            'Independent testing of implementation', 'CESG-assured components'
        ]
    }

    return {
        "type": "object",
        "properties": {
            "assurance": {
                "enum": assurance_options[assurance_approach]
            },
            "value": value_schema,
        },
        "required": [
            "value",
            "assurance"
        ]
    }


def build_question_properties(question):
    question_data = QUESTION_TYPES[question['type']](question)
    if question.get('assuranceApproach'):
        for key, value_schema in question_data.items():
            question_data[key] = add_assurance(value_schema, question['assuranceApproach'])
    return question_data


def build_any_of(any_of, fields):
    return {
        'required': [field for field in sorted(fields)],
        'title': any_of
    }


def build_schema_properties(schema, questions):
    for key, question in questions.items():
        schema['properties'].update(build_question_properties(question))
        schema['required'].extend(question.required_form_fields)

    schema['required'].sort()

    return schema


def add_multiquestion_anyof(schema, questions):
    any_ofs = {}

    for key, question in questions.items():
        if question.get('any_of'):
            question_fields = []
            for q in question.questions:
                if q.get('fields'):
                    question_fields.extend(val for val in q.get('fields').values())
                else:
                    question_fields.append(q.id)
            any_ofs[question.id] = build_any_of(question.get('any_of'), question_fields)

    if any_ofs:
        schema['anyOf'] = [any_ofs[key] for key in sorted(any_ofs.keys())]


def add_multiquestion_dependencies(schema, questions):
    dependencies = {}
    for key, question in questions.items():
        if question.type == 'multiquestion':
            dependencies.update({
                field: sorted(set(question.form_fields) - set([field]))
                for field in question.form_fields
                if len(question.form_fields) > 1
            })

    if dependencies:
        schema['dependencies'] = dependencies


def generate_schema(path, schema_name, framework_slug, lot_slug):
    questions = load_questions(framework_slug, lot_slug)
    drop_non_schema_questions(questions)
    schema = empty_schema(schema_name)

    build_schema_properties(schema, questions)
    add_multiquestion_anyof(schema, questions)
    add_multiquestion_dependencies(schema, questions)

    with open(os.path.join(path, 'services-{}-{}.json'.format(framework_slug, lot_slug)), 'w') as f:
        json.dump(schema, f, sort_keys=True, indent=2, separators=(',', ': '))
        f.write('\n')


if __name__ == '__main__':
    arguments = docopt(__doc__)
    for schema in SCHEMAS:
        generate_schema(arguments['--output-path'], *schema)
