# -*- coding: utf-8 -*-
import pytest
from nose.tools import assert_equal
from app.main.helpers.frameworks import get_statuses_for_lot


def get_lot_status_examples():
    # limit, drafts, complete, declaration, framework
    cases = [
        # Lots with limit of one service
        (
            [True, 0, 0, None, 'open'],
            [{
                'title': u'You haven’t applied to provide digital shoutcomes',
                'type': u'quiet'
            }]
        ),
        (
            [True, 1, 0, None, 'open'],
            [{
                'title': u'You’ve started your application',
                'type': u'quiet'
            }]
        ),
        (
            [True, 0, 1, None, 'open'],
            [{
                'title': u'You’ve completed this service',
                'hint': u'You can edit it until the deadline'
            }]
        ),
        (
            [True, 0, 1, 'complete', 'open'],
            [{
                'title': u'You’re submitting this service',
                'hint': u'You can edit it until the deadline',
                'type': u'happy'
            }]
        ),

        # Lots with limit of one, framework in standstill
        (
            [True, 0, 0, None, 'standstill'],
            [{
                'title': u'You didn’t apply to provide digital shoutcomes',
                'type': u'quiet'
            }]
        ),
        (
            [True, 1, 0, None, 'standstill'],
            [{
                'title': u'You started your application',
                'type': u'quiet'
            }]
        ),
        (
            [True, 0, 1, None, 'standstill'],
            [{
                'title': 'You marked this service as complete'
            }]
        ),
        (
            [True, 0, 1, 'complete', 'standstill'],
            [{
                'title': u'You submitted this service',
                'type': u'happy'
            }]
        ),

        # Multi-service lots, no declaration, framework open
        (
            [False, 0, 0, None, 'open'],
            [{
                'title': u'You haven’t applied to provide digital shoutcomes',
                'type': u'quiet'
            }]
        ),
        (
            [False, 1, 0, None, 'open'],
            [{
                'title': u'1 draft service',
                'type': u'quiet'
            }]
        ),
        (
            [False, 0, 1, None, 'open'],
            [{
                'title': u'1 complete service',
                'hint': u'You can edit it until the deadline',
                'type': None
            }]
        ),
        (
            [False, 1, 1, None, 'open'],
            [
                {
                    'title': u'1 complete service',
                    'hint': u'You can edit it until the deadline',
                    'type': None
                },
                {
                    'title': u'1 draft service',
                    'type': u'quiet'
                }
            ]
        ),
        (
            [False, 3, 3, None, 'open'],
            [
                {
                    'title': u'3 complete services',
                    'hint': u'You can edit them until the deadline',
                    'type': None
                },
                {
                    'title': u'3 draft services',
                    'type': u'quiet'
                }
            ]
        ),

        # Multi-service lots, declaration_complete, framework open
        (
            [False, 0, 0, 'complete', 'open'],
            [{
                'title': u'You haven’t applied to provide digital shoutcomes',
                'type': u'quiet'
            }]
        ),
        (
            [False, 1, 0, 'complete', 'open'],
            [{
                'title': u'1 draft service won’t be submitted',
                'type': u'quiet'
            }]
        ),
        (
            [False, 0, 1, 'complete', 'open'],
            [{
                'title': u'1 complete service will be submitted',
                'hint': u'You can edit it until the deadline',
                'type': u'happy'
            }]
        ),
        (
            [False, 1, 1, 'complete', 'open'],
            [
                {
                    'title': u'1 complete service will be submitted',
                    'hint': u'You can edit it until the deadline',
                    'type': u'happy'
                },
                {
                    'title': u'1 draft service won’t be submitted',
                    'type': u'quiet'
                }
            ]
        ),
        (
            [False, 3, 3, 'complete', 'open'],
            [
                {
                    'title': u'3 complete services will be submitted',
                    'hint': u'You can edit them until the deadline',
                    'type': u'happy'
                },
                {
                    'title': u'3 draft services won’t be submitted',
                    'type': u'quiet'
                }
            ]
        ),
        (
            [False, 3, 1, 'complete', 'open'],
            [
                {
                    'title': u'1 complete service will be submitted',
                    'hint': u'You can edit it until the deadline',
                    'type': u'happy'
                },
                {
                    'title': u'3 draft services won’t be submitted',
                    'type': u'quiet'
                }
            ]
        ),
        (
            [False, 1, 3, 'complete', 'open'],
            [
                {
                    'title': u'3 complete services will be submitted',
                    'hint': u'You can edit them until the deadline',
                    'type': u'happy'
                },
                {
                    'title': u'1 draft service won’t be submitted',
                    'type': u'quiet'
                }
            ]
        ),

        # Multi-service lots, no declaration, framework closed
        (
            [False, 0, 0, None, 'standstill'],
            [{
                'title': u'You didn’t apply to provide digital shoutcomes',
                'type': u'quiet'
            }]
        ),
        (
            [False, 1, 0, None, 'standstill'],
            [{
                'title': u'1 draft service wasn’t submitted',
                'type': u'quiet'
            }]
        ),
        (
            [False, 0, 1, None, 'standstill'],
            [{
                'title': u'1 complete service wasn’t submitted',
                'type': u'quiet'
            }]
        ),
        (
            [False, 1, 1, None, 'standstill'],
            [
                {
                    'title': u'1 complete service wasn’t submitted',
                    'type': u'quiet'
                },
                {
                    'title': u'1 draft service wasn’t submitted',
                    'type': u'quiet'
                }
            ]
        ),
        (
            [False, 3, 3, None, 'standstill'],
            [
                {
                    'title': u'3 complete services weren’t submitted',
                    'type': u'quiet'
                },
                {
                    'title': u'3 draft services weren’t submitted',
                    'type': u'quiet'
                }
            ]
        ),

        # Multi-service lots, declaration complete, framework closed
        (
            [False, 0, 0, 'complete', 'standstill'],
            [{
                'title': u'You didn’t apply to provide digital shoutcomes',
                'type': u'quiet'
            }]
        ),
        (
            [False, 1, 0, 'complete', 'standstill'],
            [{
                'title': u'1 draft service wasn’t submitted',
                'type': u'quiet'
            }]
        ),
        (
            [False, 0, 1, 'complete', 'standstill'],
            [{
                'title': u'1 complete service was submitted',
                'type': u'happy'
            }]
        ),
        (
            [False, 1, 1, 'complete', 'standstill'],
            [
                {
                    'title': u'1 complete service was submitted',
                    'type': u'happy'
                },
                {
                    'title': u'1 draft service wasn’t submitted',
                    'type': u'quiet'
                }
            ]
        ),
        (
            [False, 3, 3, 'complete', 'standstill'],
            [
                {
                    'title': u'3 complete services were submitted',
                    'type': u'happy'
                },
                {
                    'title': u'3 draft services weren’t submitted',
                    'type': u'quiet'
                }
            ]
        )
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
        get_statuses_for_lot(*parameters, lot_name='digital shoutcomes')
    )
