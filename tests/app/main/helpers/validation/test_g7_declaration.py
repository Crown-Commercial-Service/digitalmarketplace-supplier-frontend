# -*- coding: utf-8 -*-
from app.main.helpers.validation import G7Validator, get_validator
from app.main import content_loader


FULL_G7_SUBMISSION = {
    "PR1": True,
    "PR2": True,
    "PR3": True,
    "PR4": True,
    "PR5": True,
    "SQ1-1i-i": True,
    "SQ2-1abcd": True,
    "SQ2-1e": True,
    "SQ2-1f": True,
    "SQ2-1ghijklmn": True,
    "SQ2-2a": True,
    "SQ3-1a": True,
    "SQ3-1b": True,
    "SQ3-1c": True,
    "SQ3-1d": True,
    "SQ3-1e": True,
    "SQ3-1f": True,
    "SQ3-1g": True,
    "SQ3-1h-i": True,
    "SQ3-1h-ii": True,
    "SQ3-1i-i": True,
    "SQ3-1i-ii": True,
    "SQ3-1j": True,
    "SQ3-1k": "Blah",
    "SQ4-1a": True,
    "SQ4-1b": True,
    "SQ5-2a": True,
    "SQD2b": True,
    "SQD2d": True,
    "SQ1-1a": "Blah",
    "SQ1-1b": "Blah",
    "SQ1-1cii": "Blah",
    "SQ1-1d": "Blah",
    "SQ1-1d-i": "Blah",
    "SQ1-1d-ii": "Blah",
    "SQ1-1e": "Blah",
    "SQ1-1h": "999999999",
    "SQ1-1i-ii": "Blah",
    "SQ1-1j-ii": "Blah",
    "SQ1-1p-i": "Blah",
    "SQ1-1k": "Blah",
    "SQ1-1n": "Blah",
    "SQ1-1o": "valid@email.com",
    "SQ1-2a": "Blah",
    "SQ1-2b": "valid@email.com",
    "SQ2-2b": "Blah",
    "SQ4-1c": "Blah",
    "SQD2c": "Blah",
    "SQD2e": "Blah",
    "SQ1-1ci": "public limited company",
    "SQ1-1j-i": ["licensed?"],
    "SQ1-1m": "micro",
    "SQ1-3": ["on-demand self-service. blah blah"],
    "SQ5-1a": u"Yes – your organisation has, blah blah",
    "SQC2": [
        "race?",
        "sexual orientation?",
        "disability?",
        "age equality?",
        "religion or belief?",
        "gender (sex)?",
        "gender reassignment?",
        "marriage or civil partnership?",
        "pregnancy or maternity?",
        "human rights?"
    ],
    "SQC3": True,
    "SQA2": True,
    "SQA3": True,
    "SQA4": True,
    "SQA5": True,
    "AQA3": True,
    "SQE2a": ["as a prime contractor, using third parties (subcontractors) to provide some services"]
}


def test_error_if_required_field_is_missing():
    content = content_loader.get_manifest('g-cloud-7', 'declaration')
    submission = FULL_G7_SUBMISSION.copy()
    del submission['SQ3-1i-i']
    validator = G7Validator(content, submission)

    assert validator.errors() == {'SQ3-1i-i': 'answer_required'}


def test_error_if_required_text_field_is_empty():
    content = content_loader.get_manifest('g-cloud-7', 'declaration')
    submission = FULL_G7_SUBMISSION.copy()
    submission['SQ1-2b'] = ""
    validator = G7Validator(content, submission)

    assert validator.errors() == {'SQ1-2b': 'answer_required'}


def test_no_error_if_optional_field_is_missing():
    content = content_loader.get_manifest('g-cloud-7', 'declaration')
    submission = FULL_G7_SUBMISSION.copy()
    del submission['SQ1-1p-i']
    validator = G7Validator(content, submission)

    assert validator.errors() == {}


def test_trading_status_details_error_depends_on_trading_status():
    content = content_loader.get_manifest('g-cloud-7', 'declaration')
    submission = FULL_G7_SUBMISSION.copy()
    del submission['SQ1-1cii']
    validator = G7Validator(content, submission)

    submission['SQ1-1ci'] = "something"
    validator = G7Validator(content, submission)
    assert validator.errors() == {}

    submission['SQ1-1ci'] = "other (please specify)"
    validator = G7Validator(content, submission)
    assert validator.errors() == {'SQ1-1cii': 'answer_required'}


def test_trade_registers_details_error_depends_on_trade_registers():
    content = content_loader.get_manifest('g-cloud-7', 'declaration')
    submission = FULL_G7_SUBMISSION.copy()
    del submission['SQ1-1i-ii']

    submission['SQ1-1i-i'] = False
    validator = G7Validator(content, submission)
    assert validator.errors() == {}

    submission['SQ1-1i-i'] = True
    validator = G7Validator(content, submission)
    assert validator.errors() == {'SQ1-1i-ii': 'answer_required'}


def test_licenced_details_error_depends_on_licenced():
    content = content_loader.get_manifest('g-cloud-7', 'declaration')
    submission = FULL_G7_SUBMISSION.copy()
    del submission['SQ1-1j-ii']

    del submission['SQ1-1j-i']
    validator = G7Validator(content, submission)
    assert validator.errors() == {}

    submission['SQ1-1j-i'] = ["licensed"]
    validator = G7Validator(content, submission)
    assert validator.errors() == {'SQ1-1j-ii': 'answer_required'}


def test_no_error_if_no_tax_issues_and_no_details():
    content = content_loader.get_manifest('g-cloud-7', 'declaration')
    submission = FULL_G7_SUBMISSION.copy()

    submission['SQ4-1a'] = False
    submission['SQ4-1b'] = False
    del submission['SQ4-1c']

    validator = G7Validator(content, submission)
    assert validator.errors() == {}


def test_error_if_tax_issues_and_no_details():
    content = content_loader.get_manifest('g-cloud-7', 'declaration')
    submission = FULL_G7_SUBMISSION.copy()

    del submission['SQ4-1c']

    submission['SQ4-1a'] = True
    submission['SQ4-1b'] = False
    validator = G7Validator(content, submission)
    assert validator.errors() == {'SQ4-1c': 'answer_required'}

    submission['SQ4-1a'] = False
    submission['SQ4-1b'] = True
    validator = G7Validator(content, submission)
    assert validator.errors() == {'SQ4-1c': 'answer_required'}


def test_error_if_mitigation_factors_not_provided_when_required():
    content = content_loader.get_manifest('g-cloud-7', 'declaration')
    submission = FULL_G7_SUBMISSION.copy()

    del submission['SQ3-1k']

    dependent_fields = [
        'SQ2-2a', 'SQ3-1a', 'SQ3-1b', 'SQ3-1c', 'SQ3-1d', 'SQ3-1e', 'SQ3-1f', 'SQ3-1g',
        'SQ3-1h-i', 'SQ3-1h-ii', 'SQ3-1i-i', 'SQ3-1i-ii', 'SQ3-1j'
    ]
    for field in dependent_fields:
        # Set all other fields to false to show that just this field causes the error
        for other in dependent_fields:
            submission[other] = False
        submission[field] = True

        validator = G7Validator(content, submission)
        assert validator.errors() == {'SQ3-1k': 'answer_required'}


def test_mitigation_factors_not_required():
    content = content_loader.get_manifest('g-cloud-7', 'declaration')
    submission = FULL_G7_SUBMISSION.copy()

    del submission['SQ3-1k']

    dependent_fields = [
        'SQ2-2a', 'SQ3-1a', 'SQ3-1b', 'SQ3-1c', 'SQ3-1d', 'SQ3-1e', 'SQ3-1f', 'SQ3-1g',
        'SQ3-1h-i', 'SQ3-1h-ii', 'SQ3-1i-i', 'SQ3-1i-ii', 'SQ3-1j'
    ]
    for field in dependent_fields:
        submission[field] = False
    validator = G7Validator(content, submission)
    assert validator.errors() == {}


def test_fields_only_relevant_to_non_uk():
    content = content_loader.get_manifest('g-cloud-7', 'declaration')
    submission = FULL_G7_SUBMISSION.copy()

    submission['SQ5-2a'] = False
    del submission['SQ1-1i-i']

    validator = G7Validator(content, submission)
    assert validator.errors() == {'SQ1-1i-i': 'answer_required'}


def test_invalid_email_addresses_cause_errors():
    content = content_loader.get_manifest('g-cloud-7', 'declaration')
    submission = FULL_G7_SUBMISSION.copy()

    submission['SQ1-1o'] = '@invalid.com'
    submission['SQ1-2b'] = 'some.user.missed.their.at.com'

    validator = G7Validator(content, submission)
    assert validator.errors() == {
        'SQ1-1o': 'invalid_format',
        'SQ1-2b': 'invalid_format',
    }


def test_character_limit_errors():
    cases = [
        ("SQ1-1a", 5000),
        ("SQ1-1cii", 5000),
        ("SQ1-1d-i", 5000),
        ("SQ1-1d-ii", 5000),
        ("SQ1-1i-ii", 5000),
        ("SQ3-1k", 5000),
    ]
    content = content_loader.get_manifest('g-cloud-7', 'declaration')
    submission = FULL_G7_SUBMISSION.copy()

    for field, limit in cases:
        submission[field] = "a" * (limit + 1)
        validator = G7Validator(content, submission)
        assert validator.errors() == {field: 'under_character_limit'}

        submission[field] = "a" * limit
        validator = G7Validator(content, submission)
        assert validator.errors() == {}


def test_get_validator():
    validator = get_validator({"slug": "g-cloud-7"}, None, None)
    assert type(validator) is G7Validator
