# -*- coding: utf-8 -*-
"""Test for app/main/helpers/frameworks.py"""

from datetime import datetime

import mock
import pytest
from werkzeug.exceptions import HTTPException

from app.main.helpers.frameworks import (
    get_statuses_for_lot, return_supplier_framework_info_if_on_framework_or_abort,
    check_agreement_is_related_to_supplier_framework_or_abort,
    order_frameworks_for_reuse,
    get_reusable_declaration)


def get_lot_status_examples():
    # limit, drafts, complete, declaration, framework
    cases = [
        # Lots with limit of one service
        (
            [True, 0, 0, None, 'open'],
            []
        ),
        (
            [True, 1, 0, None, 'open'],
            [{
                'title': u'Started but not complete',
                'type': u'quiet'
            }]
        ),
        (
            [True, 0, 1, None, 'open'],
            [{
                'title': u'Marked as complete',
                'hint': u'You can edit it until the deadline'
            }]
        ),
        (
            [True, 0, 1, 'complete', 'open'],
            [{
                'title': u'This will be submitted',
                'hint': u'You can edit it until the deadline',
                'type': u'happy'
            }]
        ),

        # Lots with limit of one, framework in standstill
        (
            [True, 0, 0, None, 'standstill'],
            []
        ),
        (
            [True, 1, 0, None, 'standstill'],
            [{
                'title': u'Not completed',
                'type': u'quiet'
            }]
        ),
        (
            [True, 0, 1, None, 'standstill'],
            [{
                'title': 'Marked as complete'
            }]
        ),
        (
            [True, 0, 1, 'complete', 'standstill'],
            [{
                'title': u'Submitted',
                'type': u'happy'
            }]
        ),

        # Multi-service lots, no declaration, framework open
        (
            [False, 0, 0, None, 'open'],
            []
        ),
        (
            [False, 1, 0, None, 'open'],
            [{
                'title': u'1 draft lab',
                'hint': u'Started but not complete',
                'type': u'quiet'
            }]
        ),
        (
            [False, 0, 1, None, 'open'],
            [{
                'title': u'1 lab marked as complete',
                'hint': u'You can edit it until the deadline'
            }]
        ),
        (
            [False, 1, 1, None, 'open'],
            [
                {
                    'title': u'1 lab marked as complete',
                    'hint': u'You can edit it until the deadline'
                },
                {
                    'title': u'1 draft lab',
                    'hint': u'Started but not complete',
                    'type': u'quiet'
                }
            ]
        ),
        (
            [False, 3, 3, None, 'open'],
            [
                {
                    'title': u'3 labs marked as complete',
                    'hint': u'You can edit them until the deadline'
                },
                {
                    'title': u'3 draft labs',
                    'hint': u'Started but not complete',
                    'type': u'quiet'
                }
            ]
        ),

        # Multi-service lots, declaration_complete, framework open
        (
            [False, 0, 0, 'complete', 'open'],
            []
        ),
        (
            [False, 1, 0, 'complete', 'open'],
            [{
                'title': u'1 draft lab',
                'hint': u'Started but not complete',
                'type': u'quiet'
            }]
        ),
        (
            [False, 0, 1, 'complete', 'open'],
            [{
                'title': u'1 lab will be submitted',
                'hint': u'You can edit it until the deadline',
                'type': u'happy'
            }]
        ),
        (
            [False, 1, 1, 'complete', 'open'],
            [
                {
                    'title': u'1 lab will be submitted',
                    'hint': u'You can edit it until the deadline',
                    'type': u'happy'
                },
                {
                    'title': u'1 draft lab',
                    'hint': u'Started but not complete',
                    'type': u'quiet'
                }
            ]
        ),
        (
            [False, 3, 3, 'complete', 'open'],
            [
                {
                    'title': u'3 labs will be submitted',
                    'hint': u'You can edit them until the deadline',
                    'type': u'happy'
                },
                {
                    'title': u'3 draft labs',
                    'hint': u'Started but not complete',
                    'type': u'quiet'
                }
            ]
        ),
        (
            [False, 3, 1, 'complete', 'open'],
            [
                {
                    'title': u'1 lab will be submitted',
                    'hint': u'You can edit it until the deadline',
                    'type': u'happy'
                },
                {
                    'title': u'3 draft labs',
                    'hint': u'Started but not complete',
                    'type': u'quiet'
                }
            ]
        ),
        (
            [False, 1, 3, 'complete', 'open'],
            [
                {
                    'title': u'3 labs will be submitted',
                    'hint': u'You can edit them until the deadline',
                    'type': u'happy'
                },
                {
                    'title': u'1 draft lab',
                    'hint': u'Started but not complete',
                    'type': u'quiet'
                }
            ]
        ),

        # Multi-service lots, no declaration, framework closed
        (
            [False, 0, 0, None, 'standstill'],
            []
        ),
        (
            [False, 1, 0, None, 'standstill'],
            [{
                'title': u'No labs were marked as complete',
                'type': u'quiet'
            }]
        ),
        (
            [False, 0, 1, None, 'standstill'],
            [{
                'title': u'1 complete lab wasn’t submitted',
                'type': u'quiet'
            }]
        ),
        (
            [False, 1, 1, None, 'standstill'],
            [{
                'title': u'1 complete lab wasn’t submitted',
                'type': u'quiet'
            }]
        ),
        (
            [False, 3, 3, None, 'standstill'],
            [{
                'title': u'3 complete labs weren’t submitted',
                'type': u'quiet'
            }]
        ),

        # Multi-service lots, declaration complete, framework closed
        (
            [False, 0, 0, 'complete', 'standstill'],
            []
        ),
        (
            [False, 1, 0, 'complete', 'standstill'],
            [{
                'title': u'No labs were marked as complete',
                'type': u'quiet'
            }]
        ),
        (
            [False, 0, 1, 'complete', 'standstill'],
            [{
                'title': u'1 complete lab was submitted',
                'type': u'happy'
            }]
        ),
        (
            [False, 1, 1, 'complete', 'standstill'],
            [{
                'title': u'1 complete lab was submitted',
                'type': u'happy'
            }]
        ),
        (
            [False, 3, 3, 'complete', 'standstill'],
            [
                {
                    'title': u'3 complete labs were submitted',
                    'type': u'happy'
                }
            ]
        ),

        # Test that declaration started is treated the same way as no declaration
        (
            [True, 0, 1, 'started', 'open'],
            [{
                'title': u'Marked as complete',
                'hint': u'You can edit it until the deadline'
            }]
        ),
    ]

    def get_example():
        for parameters, result in cases:
            yield (parameters, result)

    return get_example()


@pytest.mark.parametrize(("parameters", "expected_result"), get_lot_status_examples())
def test_get_status_for_lot(parameters, expected_result):

    # This print statement makes it easier to debug failing tests
    for index, label in enumerate([
        'has_one_service_limit...',
        'drafts_count............',
        'complete_drafts_count...',
        'declaration_status......',
        'framework_status........'
    ]):
        print(label, parameters[index])

    assert expected_result == get_statuses_for_lot(
        *parameters,
        lot_name='user research studios',
        unit='lab',
        unit_plural='labs'
    )


@mock.patch("app.main.helpers.frameworks.current_user")
def test_return_supplier_framework_info_if_on_framework_or_abort_aborts_if_no_supplier_framework_exists(current_user):
    data_api_client = mock.Mock()
    data_api_client.get_supplier_framework_info.return_value = {'frameworkInterest': {}}
    with pytest.raises(HTTPException):
        return_supplier_framework_info_if_on_framework_or_abort(data_api_client, 'g-cloud-8')


@mock.patch("app.main.helpers.frameworks.current_user")
def test_return_supplier_framework_info_if_on_framework_or_abort_aborts_if_on_framework_false(current_user):
    data_api_client = mock.Mock()
    data_api_client.get_supplier_framework_info.return_value = {'frameworkInterest': {'onFramework': None}}
    with pytest.raises(HTTPException):
        return_supplier_framework_info_if_on_framework_or_abort(data_api_client, 'g-cloud-8')


@mock.patch("app.main.helpers.frameworks.current_user")
def test_return_supplier_framework_info_if_on_framework_or_abort_returns_supplier_framework_if_on_framework(
        current_user
):
    supplier_framework_response = {'frameworkInterest': {'onFramework': True}}
    data_api_client = mock.Mock()
    data_api_client.get_supplier_framework_info.return_value = supplier_framework_response
    assert return_supplier_framework_info_if_on_framework_or_abort(data_api_client, 'g-cloud-8') == \
        supplier_framework_response['frameworkInterest']


def test_check_agreement_is_related_to_supplier_framework_or_abort_does_abort_for_supplier_mismatch():
    supplier_framework = {"supplierId": 200, "frameworkSlug": 'g-cloud-8'}
    agreement = {"supplierId": 201, "frameworkSlug": 'g-cloud-8'}
    with pytest.raises(HTTPException):
        check_agreement_is_related_to_supplier_framework_or_abort(agreement, supplier_framework)


def test_check_agreement_is_related_to_supplier_framework_or_abort_does_abort_for_framework_mismatch():
    supplier_framework = {"supplierId": 200, "frameworkSlug": 'g-cloud-8'}
    agreement = {"supplierId": 200, "frameworkSlug": 'g-cloud-7'}
    with pytest.raises(HTTPException):
        check_agreement_is_related_to_supplier_framework_or_abort(agreement, supplier_framework)


def test_check_agreement_is_related_to_supplier_framework_or_abort_does_abort_if_supplier_ids_are_none():
    supplier_framework = {"supplierId": None, "frameworkSlug": 'g-cloud-8'}
    agreement = {"supplierId": None, "frameworkSlug": 'g-cloud-8'}
    with pytest.raises(HTTPException):
        check_agreement_is_related_to_supplier_framework_or_abort(agreement, supplier_framework)


def test_check_agreement_is_related_to_supplier_framework_or_abort_does_abort_if_framework_slugs_are_none():
    supplier_framework = {"supplierId": 212, "frameworkSlug": None}
    agreement = {"supplierId": 212, "frameworkSlug": None}
    with pytest.raises(HTTPException):
        check_agreement_is_related_to_supplier_framework_or_abort(agreement, supplier_framework)


def test_check_agreement_is_related_to_supplier_framework_or_abort_does_not_abort_for_match():
    supplier_framework = {"supplierId": 212, "frameworkSlug": 'g-cloud-8'}
    agreement = {"supplierId": 212, "frameworkSlug": 'g-cloud-8'}
    check_agreement_is_related_to_supplier_framework_or_abort(agreement, supplier_framework)


def test_order_frameworks_for_reuse():
    """Test happy path. Should return 2 frameworks, closest date first."""
    t09 = datetime(2009, 03, 03, 01, 01, 01)
    t07 = datetime(2007, 12, 03, 01, 01, 01)
    t12 = datetime(2012, 05, 03, 01, 01, 01)

    fake_frameworks = [
        {'allow_declaration_reuse': True, 'application_close_date': t12, 'extraneous_field': 'foo'},
        {'allow_declaration_reuse': False, 'application_close_date': t09, 'extraneous_field': 'foo'},
        {'allow_declaration_reuse': True, 'application_close_date': t07, 'extraneous_field': 'foo'},
    ]
    ordered = order_frameworks_for_reuse(fake_frameworks)

    assert ordered == [
        {'allow_declaration_reuse': True, 'application_close_date': t12, 'extraneous_field': 'foo'},
        {'allow_declaration_reuse': True, 'application_close_date': t07, 'extraneous_field': 'foo'}
    ]


def test_order_frameworks_for_reuse_filters():
    """Test that this filters out anything with `allow_declaration_reuse == False`."""
    t09 = datetime(2009, 03, 03, 01, 01, 01)
    t07 = datetime(2007, 12, 03, 01, 01, 01)
    t12 = datetime(2012, 05, 03, 01, 01, 01)

    fake_frameworks = [
        {'allow_declaration_reuse': True, 'application_close_date': t12, 'extraneous_field': 'foo'},
        {'allow_declaration_reuse': False, 'application_close_date': t09, 'extraneous_field': 'foo'},
        {'allow_declaration_reuse': True, 'application_close_date': t07, 'extraneous_field': 'foo'},
    ]
    ordered = order_frameworks_for_reuse(fake_frameworks)

    assert len(ordered) == 2


def test_order_frameworks_for_reuse_none():
    """Test no suitable frameworks returns an empty list."""
    t09 = datetime(2009, 03, 03, 01, 01, 01)
    t07 = datetime(2007, 12, 03, 01, 01, 01)
    t12 = datetime(2012, 05, 03, 01, 01, 01)

    fake_frameworks = [
        {'allow_declaration_reuse': False, 'application_close_date': t12, 'extraneous_field': 'foo'},
        {'allow_declaration_reuse': False, 'application_close_date': t09, 'extraneous_field': 'foo'},
        {'allow_declaration_reuse': False, 'application_close_date': t07, 'extraneous_field': 'foo'},
    ]
    ordered = order_frameworks_for_reuse(fake_frameworks)

    assert ordered == []


def test_order_frameworks_for_reuse_one():
    """Test that the function returns a list of 1 when given a single suitable framework."""
    t09 = datetime(2009, 03, 03, 01, 01, 01)
    t07 = datetime(2007, 12, 03, 01, 01, 01)
    t12 = datetime(2012, 05, 03, 01, 01, 01)

    fake_frameworks = [
        {'allow_declaration_reuse': False, 'application_close_date': t12, 'extraneous_field': 'foo'},
        {'allow_declaration_reuse': False, 'application_close_date': t09, 'extraneous_field': 'foo'},
        {'allow_declaration_reuse': True, 'application_close_date': t07, 'extraneous_field': 'foo'},
    ]
    ordered = order_frameworks_for_reuse(fake_frameworks)

    assert ordered == [{'allow_declaration_reuse': True, 'application_close_date': t07, 'extraneous_field': 'foo'}]


def test_order_frameworks_for_reuse_unordered():
    """Test crazy order passed in is ordered correctly."""
    t09 = datetime(2009, 03, 03, 01, 01, 01)
    t07 = datetime(2007, 12, 03, 01, 01, 01)
    t11 = datetime(2012, 05, 03, 01, 01, 01)
    t12 = datetime(2012, 05, 03, 01, 01, 01)
    t13 = datetime(2012, 05, 03, 01, 01, 01)
    t14 = datetime(2012, 05, 03, 01, 01, 01)

    fake_frameworks = [
        {'allow_declaration_reuse': True, 'application_close_date': t07, 'extraneous_field': 'foo'},
        {'allow_declaration_reuse': True, 'application_close_date': t13, 'extraneous_field': 'foo'},
        {'allow_declaration_reuse': True, 'application_close_date': t09, 'extraneous_field': 'foo'},
        {'allow_declaration_reuse': True, 'application_close_date': t14, 'extraneous_field': 'foo'},
        {'allow_declaration_reuse': True, 'application_close_date': t12, 'extraneous_field': 'foo'},
        {'allow_declaration_reuse': True, 'application_close_date': t11, 'extraneous_field': 'foo'},
    ]
    ordered = order_frameworks_for_reuse(fake_frameworks)

    assert ordered[0] == {'allow_declaration_reuse': True, 'application_close_date': t14, 'extraneous_field': 'foo'}
    assert ordered[-1] == {'allow_declaration_reuse': True, 'application_close_date': t07, 'extraneous_field': 'foo'}


def test_get_reusable_declaration(data_api_client):
    """Test happy path, should return the framework and declaration where
    allow_declaration_reuse == True
    application_close_date is closest to today
    and declaration exists for that framework
    """

    t09 = datetime(2009, 03, 03, 01, 01, 01)
    t07 = datetime(2007, 12, 03, 01, 01, 01)
    t11 = datetime(2012, 05, 03, 01, 01, 01)
    t12 = datetime(2012, 05, 03, 01, 01, 01)
    t13 = datetime(2012, 05, 03, 01, 01, 01)
    t14 = datetime(2012, 05, 03, 01, 01, 01)

    frameworks = [
        {'x_field': 'foo', 'allow_declaration_reuse': True, 'application_close_date': t07, 'slug': 'ben-cloud-1'},
        {'x_field': 'foo', 'allow_declaration_reuse': True, 'application_close_date': t09, 'slug': 'ben-cloud-2'},
        {'x_field': 'foo', 'allow_declaration_reuse': True, 'application_close_date': t11, 'slug': 'ben-cloud-3'},
        {'x_field': 'foo', 'allow_declaration_reuse': True, 'application_close_date': t12, 'slug': 'ben-cloud-4'},
        {'x_field': 'foo', 'allow_declaration_reuse': True, 'application_close_date': t13, 'slug': 'ben-cloud-5'},
        {'x_field': 'foo', 'allow_declaration_reuse': False, 'application_close_date': t14, 'slug': 'ben-cloud-alpha'},
    ]
    declarations = [
        {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-4'},
        {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-1000000'},
        {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-2'},
        {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-alpha'}
    ]

    data_api_client.find_frameworks.return_value = {'frameworks': frameworks}
    declaration = get_reusable_declaration(declarations, client=data_api_client)

    assert declaration == {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-4'}


def test_get_reusable_declaration_none(data_api_client):
    """Test returning None.
    """
    t14 = datetime(2012, 05, 03, 01, 01, 01)

    frameworks = [
        {'x_field': 'foo', 'allow_declaration_reuse': True, 'application_close_date': t14, 'slug': 'ben-cloud-5'},
    ]
    declarations = [
        {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-4'},
    ]

    data_api_client.find_frameworks.return_value = {'frameworks': frameworks}
    declaration = get_reusable_declaration(declarations, client=data_api_client)

    assert declaration is None
