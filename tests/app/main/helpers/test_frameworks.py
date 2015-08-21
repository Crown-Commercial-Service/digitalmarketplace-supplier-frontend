# -*- coding: utf-8 -*-
from nose.tools import assert_equal

from app.main.helpers.frameworks import get_all_errors
from app.main import declaration_content


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
    "SQ1-1e": "Blah",
    "SQ1-1h": "999999999",
    "SQ1-1i-ii": "Blah",
    "SQ1-1j-ii": "Blah",
    "SQ1-1k": "Blah",
    "SQ1-1n": "Blah",
    "SQ1-1o": "Blah",
    "SQ1-2a": "Blah",
    "SQ1-2b": "Blah",
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
    content = declaration_content.get_builder()
    submission = FULL_G7_SUBMISSION.copy()
    del submission['SQ3-1i-i']

    assert_equal(get_all_errors(content, submission, 4), {'SQ3-1i-i': 'answer_required'})


def test_error_if_required_text_field_is_empty():
    content = declaration_content.get_builder()
    submission = FULL_G7_SUBMISSION.copy()
    submission['SQ1-2b'] = ""

    assert_equal(get_all_errors(content, submission, 2), {'SQ1-2b': 'answer_required'})


def test_no_error_if_optional_field_is_missing():
    content = declaration_content.get_builder()
    submission = FULL_G7_SUBMISSION.copy()
    del submission['SQ1-1e']

    assert_equal(get_all_errors(content, submission, 2), {})


def test_trading_status_details_error_depends_on_trading_status():
    content = declaration_content.get_builder()
    submission = FULL_G7_SUBMISSION.copy()
    del submission['SQ1-1cii']

    submission['SQ1-1ci'] = "something"
    assert_equal(get_all_errors(content, submission, 2), {})

    submission['SQ1-1ci'] = "other (please specify)"
    assert_equal(get_all_errors(content, submission, 2), {'SQ1-1cii': 'answer_required'})


def test_trade_registers_details_error_depends_on_trade_registers():
    content = declaration_content.get_builder()
    submission = FULL_G7_SUBMISSION.copy()
    del submission['SQ1-1i-ii']

    submission['SQ1-1i-i'] = False
    assert_equal(get_all_errors(content, submission, 2), {})

    submission['SQ1-1i-i'] = True
    assert_equal(get_all_errors(content, submission, 2), {'SQ1-1i-ii': 'answer_required'})


def test_licenced_details_error_depends_on_licenced():
    content = declaration_content.get_builder()
    submission = FULL_G7_SUBMISSION.copy()
    del submission['SQ1-1j-ii']

    del submission['SQ1-1j-i']
    assert_equal(get_all_errors(content, submission, 2), {})

    submission['SQ1-1j-i'] = ["something"]
    assert_equal(get_all_errors(content, submission, 2), {'SQ1-1j-ii': 'answer_required'})


def test_no_error_if_no_tax_issues_and_no_details():
    content = declaration_content.get_builder()
    submission = FULL_G7_SUBMISSION.copy()

    submission['SQ4-1a'] = False
    submission['SQ4-1b'] = False
    del submission['SQ4-1c']

    assert_equal(get_all_errors(content, submission, 4), {})


def test_error_if_tax_issues_and_no_details():
    content = declaration_content.get_builder()
    submission = FULL_G7_SUBMISSION.copy()

    del submission['SQ4-1c']

    submission['SQ4-1a'] = True
    submission['SQ4-1b'] = False
    assert_equal(get_all_errors(content, submission, 4), {'SQ4-1c': 'answer_required'})

    submission['SQ4-1a'] = False
    submission['SQ4-1b'] = True
    assert_equal(get_all_errors(content, submission, 4), {'SQ4-1c': 'answer_required'})


def test_error_if_mitigation_factors_not_provided_when_required():
    content = declaration_content.get_builder()
    submission = FULL_G7_SUBMISSION.copy()

    del submission['SQ3-1k']

    dependent_fields = [
        'SQ2-2a', 'SQ3-1a' 'SQ3-1b', 'SQ3-1c', 'SQ3-1d', 'SQ3-1e', 'SQ3-1f', 'SQ3-1g',
        'SQ3-1h-i', 'SQ3-1h-ii', 'SQ3-1i-i', 'SQ3-1i-ii', 'SQ3-1j'
    ]
    for field in dependent_fields:
        # Set all other fields to false to show that just this field causes the error
        for other in dependent_fields:
            submission[other] = False
        submission[field] = True

        assert_equal(get_all_errors(content, submission, 4), {'SQ3-1k': 'answer_required'})


def test_mitigation_factors_not_required():
    content = declaration_content.get_builder()
    submission = FULL_G7_SUBMISSION.copy()

    del submission['SQ3-1k']

    dependent_fields = [
        'SQ2-2a', 'SQ3-1a', 'SQ3-1b', 'SQ3-1c', 'SQ3-1d', 'SQ3-1e', 'SQ3-1f', 'SQ3-1g',
        'SQ3-1h-i', 'SQ3-1h-ii', 'SQ3-1i-i', 'SQ3-1i-ii', 'SQ3-1j'
    ]
    for field in dependent_fields:
        submission[field] = False
    assert_equal(get_all_errors(content, submission, 4), {})


def test_fields_only_relevant_to_non_uk():
    content = declaration_content.get_builder()
    submission = FULL_G7_SUBMISSION.copy()

    submission['SQ5-2a'] = False
    del submission['SQ1-1i-i']

    assert_equal(get_all_errors(content, submission, 2), {'SQ1-1i-i': 'answer_required'})


def test_invalid_vat_number_causes_error():
    content = declaration_content.get_builder()
    submission = FULL_G7_SUBMISSION.copy()

    submission['SQ1-1h'] = 'invalid'
    assert_equal(get_all_errors(content, submission, 2), {'SQ1-1h': 'invalid_format'})


def test_character_limit_errors():
    cases = [
        ("SQ1-1a", 5000, 2),
        ("SQ1-1cii", 5000, 2),
        ("SQ1-1d-i", 5000, 2),
        ("SQ1-1d-ii", 5000, 2),
        ("SQ1-1i-ii", 5000, 2),
        ("SQ3-1k", 5000, 4),
    ]
    content = declaration_content.get_builder()
    submission = FULL_G7_SUBMISSION.copy()

    for field, limit, page in cases:
        submission[field] = "a" * (limit + 1)
        assert_equal(get_all_errors(content, submission, page), {field: 'under_character_limit'})

        submission[field] = "a" * limit
        assert_equal(get_all_errors(content, submission, page), {})
