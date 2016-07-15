# -*- coding: utf-8 -*-
import pytest
import mock
from nose.tools import assert_equal
from werkzeug.exceptions import HTTPException

from app.main.helpers.frameworks import get_statuses_for_lot, return_supplier_framework_info_if_on_framework_or_abort


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

    assert_equal(
        expected_result,
        get_statuses_for_lot(
            *parameters,
            lot_name='user research studios',
            unit='lab',
            unit_plural='labs'
        )
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
