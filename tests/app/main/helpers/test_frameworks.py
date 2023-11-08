# -*- coding: utf-8 -*-
"""Test for app/main/helpers/frameworks.py"""

import inspect
import mock
import pytest
from lxml import html
from werkzeug.exceptions import HTTPException

from dmtestutils.api_model_stubs import FrameworkStub, SupplierFrameworkStub
from dmapiclient import DataAPIClient, HTTPError
from dmcontent.errors import ContentNotFoundError

from app.main.helpers.frameworks import (
    check_agreement_is_related_to_supplier_framework_or_abort, get_framework_for_reuse, get_statuses_for_lot,
    return_supplier_framework_info_if_on_framework_or_abort, order_frameworks_for_reuse,
    get_frameworks_closed_and_open_for_applications, get_supplier_registered_name_from_declaration,
    get_framework_or_500, EnsureApplicationCompanyDetailsHaveBeenConfirmed, return_404_if_applications_closed
)

from ...helpers import BaseApplicationTest


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
class TestReturnSupplierFrameworkInfoIfOnFrameworkorAbort:

    def test_return_supplier_framework_info_if_on_framework_or_abort_aborts_if_no_supplier_framework_exists(
        self, current_user
    ):
        data_api_client = mock.Mock()
        data_api_client.get_supplier_framework_info.return_value = {'frameworkInterest': {}}
        with pytest.raises(HTTPException):
            return_supplier_framework_info_if_on_framework_or_abort(data_api_client, 'g-cloud-8')

    def test_return_supplier_framework_info_if_on_framework_or_abort_aborts_if_on_framework_false(self, current_user):
        data_api_client = mock.Mock()
        data_api_client.get_supplier_framework_info.return_value = {'frameworkInterest': {'onFramework': None}}
        with pytest.raises(HTTPException):
            return_supplier_framework_info_if_on_framework_or_abort(data_api_client, 'g-cloud-8')

    def test_return_supplier_framework_info_if_on_framework_or_abort_returns_supplier_framework_if_on_framework(
        self, current_user
    ):
        supplier_framework_response = {'frameworkInterest': {'onFramework': True}}
        data_api_client = mock.Mock()
        data_api_client.get_supplier_framework_info.return_value = supplier_framework_response
        assert return_supplier_framework_info_if_on_framework_or_abort(data_api_client, 'g-cloud-8') == \
            supplier_framework_response['frameworkInterest']


class TestCheckAgreementRelatedToSupplierFrameworkOrAbort:

    def test_check_agreement_is_related_to_supplier_framework_or_abort_does_abort_for_supplier_mismatch(self):
        supplier_framework = {"supplierId": 200, "frameworkSlug": 'g-cloud-8'}
        agreement = {"supplierId": 201, "frameworkSlug": 'g-cloud-8'}
        with pytest.raises(HTTPException):
            check_agreement_is_related_to_supplier_framework_or_abort(agreement, supplier_framework)

    def test_check_agreement_is_related_to_supplier_framework_or_abort_does_abort_for_framework_mismatch(self):
        supplier_framework = {"supplierId": 200, "frameworkSlug": 'g-cloud-8'}
        agreement = {"supplierId": 200, "frameworkSlug": 'g-cloud-7'}
        with pytest.raises(HTTPException):
            check_agreement_is_related_to_supplier_framework_or_abort(agreement, supplier_framework)

    def test_check_agreement_is_related_to_supplier_framework_or_abort_does_abort_if_supplier_ids_are_none(self):
        supplier_framework = {"supplierId": None, "frameworkSlug": 'g-cloud-8'}
        agreement = {"supplierId": None, "frameworkSlug": 'g-cloud-8'}
        with pytest.raises(HTTPException):
            check_agreement_is_related_to_supplier_framework_or_abort(agreement, supplier_framework)

    def test_check_agreement_is_related_to_supplier_framework_or_abort_does_abort_if_framework_slugs_are_none(self):
        supplier_framework = {"supplierId": 212, "frameworkSlug": None}
        agreement = {"supplierId": 212, "frameworkSlug": None}
        with pytest.raises(HTTPException):
            check_agreement_is_related_to_supplier_framework_or_abort(agreement, supplier_framework)

    def test_check_agreement_is_related_to_supplier_framework_or_abort_does_not_abort_for_match(self):
        supplier_framework = {"supplierId": 212, "frameworkSlug": 'g-cloud-8'}
        agreement = {"supplierId": 212, "frameworkSlug": 'g-cloud-8'}
        check_agreement_is_related_to_supplier_framework_or_abort(agreement, supplier_framework)


class TestOrderFrameworksForReuse:

    def test_order_frameworks_for_reuse(self):
        """Test happy path. Should return 2 frameworks, closest date first."""
        t09 = '2009-03-03T01:01:01.000000Z'
        t07 = '2007-03-03T01:01:01.000000Z'
        t12 = '2012-03-03T01:01:01.000000Z'

        fake_frameworks = [
            {'allowDeclarationReuse': False, 'applicationsCloseAtUTC': t09, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t12, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t07, 'extraneousField': 'foo'},
        ]
        ordered = order_frameworks_for_reuse(fake_frameworks)
        assert len(ordered) == 2, "order_frameworks_for_reuse should only filter out inappropriate frameworks."
        assert ordered == [
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t12, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t07, 'extraneousField': 'foo'}
        ], "order_frameworks_for_reuse should return appropriate frameworks."

    def test_order_frameworks_for_reuse_none(self):
        """Test no suitable frameworks returns an empty list."""
        t09 = '2009-03-03T01:01:01.000000Z'
        t07 = '2007-03-03T01:01:01.000000Z'
        t12 = '2012-03-03T01:01:01.000000Z'

        fake_frameworks = [
            {'allowDeclarationReuse': False, 'applicationsCloseAtUTC': t12, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': False, 'applicationsCloseAtUTC': t09, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': False, 'applicationsCloseAtUTC': t07, 'extraneousField': 'foo'},
        ]
        ordered = order_frameworks_for_reuse(fake_frameworks)

        assert ordered == []

    def test_order_frameworks_for_reuse_one(self):
        """Test that the function returns a list of 1 when given a single suitable framework."""
        t09 = '2009-03-03T01:01:01.000000Z'
        t07 = '2007-03-03T01:01:01.000000Z'
        t12 = '2012-03-03T01:01:01.000000Z'

        fake_frameworks = [
            {'allowDeclarationReuse': False, 'applicationsCloseAtUTC': t12, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': False, 'applicationsCloseAtUTC': t09, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t07, 'extraneousField': 'foo'},
        ]
        ordered = order_frameworks_for_reuse(fake_frameworks)

        assert ordered == [{'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t07, 'extraneousField': 'foo'}]

    def test_order_frameworks_for_reuse_unordered(self):
        """Test crazy order passed in is ordered correctly."""
        t09 = '2009-03-03T01:01:01.000000Z'
        t07 = '2007-03-03T01:01:01.000000Z'
        t11 = '2011-03-03T01:01:01.000000Z'
        t12 = '2012-03-03T01:01:01.000000Z'
        t13 = '2013-03-03T01:01:01.000000Z'
        t14 = '2014-03-03T01:01:01.000000Z'

        fake_frameworks = [
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t07, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t13, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t09, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t14, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t12, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t11, 'extraneousField': 'foo'},
        ]
        ordered = order_frameworks_for_reuse(fake_frameworks)

        expected = [
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t14, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t13, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t12, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t11, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t09, 'extraneousField': 'foo'},
            {'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t07, 'extraneousField': 'foo'}
        ]

        assert ordered == expected


class TestGetReusableDeclaration:

    def setup_method(self, method):
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()

    def test_get_reusable_declaration(self):
        """Test happy path, should return the framework and declaration where
        framework.allowDeclarationReuse == True
        supplierFramework.allowDeclarationReuse == True
        applicationsCloseAtUTC is closest to today
        and declaration exists for that framework
        and declaration status is completed
        and supplier is 'onFramework'
        """
        t09 = '2009-03-03T01:01:01.000000Z'
        t07 = '2007-03-03T01:01:01.000000Z'
        t11 = '2011-03-03T01:01:01.000000Z'
        t12 = '2012-03-03T01:01:01.000000Z'
        t13 = '2013-03-03T01:01:01.000000Z'
        t14 = '2014-03-03T01:01:01.000000Z'
        t15 = '2015-03-03T01:01:01.000000Z'
        t16 = '2015-03-03T01:01:01.000000Z'

        frameworks = [
            {'x_field': 'foo', 'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t07, 'slug': 'ben-cloud-1'},
            {'x_field': 'foo', 'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t09, 'slug': 'ben-cloud-2'},
            {'x_field': 'foo', 'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t11, 'slug': 'ben-cloud-3'},
            {'x_field': 'foo', 'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t12, 'slug': 'ben-cloud-4'},
            {'x_field': 'foo', 'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t13, 'slug': 'ben-cloud-5'},
            {
                'x_field': 'foo',
                'allowDeclarationReuse': False,
                'applicationsCloseAtUTC': t14,
                'slug': 'ben-cloud-alpha',
            },
            {
                'x_field': 'bar',
                'allowDeclarationReuse': True,
                'applicationsCloseAtUTC': t15,
                'slug': 'bun-cloud-beta',
            },
            {
                'x_field': 'bar',
                'allowDeclarationReuse': True,
                'applicationsCloseAtUTC': t16,
                'slug': 'bean-cloud-gamma',
            },
        ]
        declarations = [
            {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-4', 'onFramework': True},
            {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-1000000', 'onFramework': True},
            {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-2', 'onFramework': True, 'allowDeclarationReuse': True},
            {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-alpha', 'onFramework': True},
            {'x_field': 'foo', 'frameworkSlug': 'bun-cloud-beta', 'onFramework': False},
            {
                'x_field': 'foo',
                'frameworkSlug': 'bean-cloud-gamma',
                'onFramework': True,
                'allowDeclarationReuse': False,
            },
        ]

        self.data_api_client.find_frameworks.return_value = {'frameworks': frameworks}
        self.data_api_client.find_supplier_declarations.return_value = {'frameworkInterest': declarations}
        framework = get_framework_for_reuse(declarations, self.data_api_client)

        assert framework['slug'] == 'ben-cloud-4'

    def test_get_reusable_declaration_none(self):
        """Test returning None.
        """
        t09 = '2009-03-03T01:01:01.000000Z'
        t11 = '2011-03-03T01:01:01.000000Z'
        t14 = '2014-03-05T01:01:01.000000Z'
        t16 = '2015-03-03T01:01:01.000000Z'

        frameworks = [
            {'x_field': 'foo', 'allowDeclarationReuse': False, 'applicationsCloseAtUTC': t09, 'slug': 'ben-cloud-2'},
            {'x_field': 'foo', 'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t11, 'slug': 'ben-cloud-3'},
            {'x_field': 'foo', 'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t14, 'slug': 'ben-cloud-5'},
            {
                'x_field': 'bar',
                'allowDeclarationReuse': True,
                'applicationsCloseAtUTC': t16,
                'slug': 'bean-cloud-gamma',
            },
        ]
        declarations = [
            {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-2', 'onFramework': True, 'allowDeclarationReuse': True},
            {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-3', 'onFramework': False, 'allowDeclarationReuse': True},
            {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-4', 'onFramework': True},
            {
                'x_field': 'foo',
                'frameworkSlug': 'bean-cloud-gamma',
                'onFramework': True,
                'allowDeclarationReuse': False,
            },
        ]

        self.data_api_client.find_frameworks.return_value = {'frameworks': frameworks}
        framework = get_framework_for_reuse(declarations, client=self.data_api_client)

        assert framework is None


def test_get_frameworks_closed_and_open_for_applications():
    cases = [
        {
            "frameworks": [
                {"framework": "g-things", "slug": "g-things-23", "status": "open"},
                {"framework": "g-things", "slug": "g-things-22", "status": "live"},
                {"framework": "g-things", "slug": "g-things-21", "status": "expired"},
                {"framework": "g-things", "slug": "g-things-20", "status": "expired"},
                {"framework": "digi-stuff", "slug": "digi-stuff-10", "status": "coming"},
                {"framework": "digi-stuff", "slug": "digi-stuff-9", "status": "live"},
                {"framework": "digi-stuff", "slug": "digi-stuff-8", "status": "expired"},
                {"framework": "paper-stuff", "slug": "paper-stuff-8", "status": "expired"},
                {"framework": "paper-stuff", "slug": "paper-stuff-7", "status": "expired"},
            ],
            "expected": (
                {"framework": "digi-stuff", "slug": "digi-stuff-10", "status": "coming"},
                {"framework": "g-things", "slug": "g-things-23", "status": "open"},
                {"framework": "paper-stuff", "slug": "paper-stuff-8", "status": "expired"},
            ),
        },
        {
            "frameworks": [
                {"framework": "g-things", "slug": "g-things-24", "status": "live"},
                {"framework": "g-things", "slug": "g-things-23", "status": "expired"},
                {"framework": "digi-stuff", "slug": "digi-stuff-11", "status": "pending"},
                {"framework": "digi-stuff", "slug": "digi-stuff-9", "status": "live"},
                {"framework": "paper-stuff", "slug": "paper-stuff-8", "status": "standstill"},
                {"framework": "paper-stuff", "slug": "paper-stuff-7", "status": "expired"},
            ],
            "expected": (
                {"framework": "digi-stuff", "slug": "digi-stuff-11", "status": "pending"},
                {"framework": "g-things", "slug": "g-things-24", "status": "live"},
                {"framework": "paper-stuff", "slug": "paper-stuff-8", "status": "standstill"},
            ),
        },
        {
            "frameworks": [
                {"framework": "g-things", "slug": "g-things-24", "status": "open"},
                {"framework": "g-things", "slug": "g-things-23", "status": "live"},
                {"framework": "digi-stuff", "slug": "digi-stuff-11", "status": "open"},
                {"framework": "digi-stuff", "slug": "digi-stuff-9", "status": "live"},
                {"framework": "paper-stuff", "slug": "paper-stuff-8", "status": "expired"},
                {"framework": "paper-stuff", "slug": "paper-stuff-7", "status": "expired"},
            ],
            "expected": (
                {"framework": "digi-stuff", "slug": "digi-stuff-11", "status": "open"},
                {"framework": "g-things", "slug": "g-things-24", "status": "open"},
                {"framework": "paper-stuff", "slug": "paper-stuff-8", "status": "expired"},
            ),
        },
    ]
    for case in cases:
        displayed_frameworks = get_frameworks_closed_and_open_for_applications(case["frameworks"])
        assert displayed_frameworks == case["expected"], "ERROR ON CASE {}".format(case)


@pytest.mark.parametrize('name_of_org, supplier_reg_name, expected_result', [
    ('G-Cloud 9 supplier', None, 'G-Cloud 9 supplier'),
    (None, 'G-Cloud 10 supplier', 'G-Cloud 10 supplier'),
    ('G-9 supplier', 'G-10 supplier', 'G-10 supplier'),  # Favour newer key, but in reality should NEVER exist with both
])
def test_get_supplier_registered_name_from_declaration(name_of_org, supplier_reg_name, expected_result):
    declaration = {}
    if name_of_org:
        declaration['nameOfOrganisation'] = name_of_org
    if supplier_reg_name:
        declaration['supplierRegisteredName'] = supplier_reg_name
    assert get_supplier_registered_name_from_declaration(declaration) == expected_result


class CustomAbortException(Exception):
    """Custom error for testing abort"""
    pass


class TestGetFrameworkOr500():
    def test_returns_framework(self):
        data_api_client_mock = mock.Mock()
        data_api_client_mock.get_framework.return_value = FrameworkStub().single_result_response()

        assert get_framework_or_500(data_api_client_mock, 'g-cloud-10')['slug'] == 'g-cloud-10'

    @mock.patch('app.main.helpers.frameworks.abort')
    def test_aborts_with_500_if_framework_not_found(self, abort):
        data_api_client_mock = mock.Mock()
        data_api_client_mock.get_framework.side_effect = HTTPError(mock.Mock(status_code=404), 'Framework not found')
        abort.side_effect = CustomAbortException()

        with pytest.raises(CustomAbortException):
            get_framework_or_500(data_api_client_mock, 'g-cloud-7')

        assert abort.call_args_list == [
            mock.call(500, 'Framework not found: g-cloud-7')
        ]

    def test_raises_original_error_if_not_404(self):
        data_api_client_mock = mock.Mock()
        data_api_client_mock.get_framework.side_effect = HTTPError(mock.Mock(status_code=400), 'Original exception')

        with pytest.raises(HTTPError) as original_exception:
            get_framework_or_500(data_api_client_mock, 'g-cloud-7')

        assert original_exception.value.message == 'Original exception'
        assert original_exception.value.status_code == 400

    @mock.patch('app.main.helpers.frameworks.abort')
    def test_calls_logger_if_provided(self, abort):
        data_api_client_mock = mock.Mock()
        logger_mock = mock.Mock()
        data_api_client_mock.get_framework.side_effect = HTTPError(mock.Mock(status_code=404), 'An error from the API')

        get_framework_or_500(data_api_client_mock, 'g-cloud-7', logger_mock)

        assert logger_mock.error.call_args_list == [
            mock.call(
                'Framework not found. Error: {error}, framework_slug: {framework_slug}',
                extra={'error': 'An error from the API (status: 404)', 'framework_slug': 'g-cloud-7'},
            )
        ]


class TestEnsureApplicationCompanyDetailsHaveBeenConfirmed(BaseApplicationTest):
    def setup_method(self, method):
        super().setup_method(method)

        from app import data_api_client
        self.data_api_client_mock = mock.Mock(spec_set=data_api_client)

    def test_validator_raises_500_if_framework_slug_missing(self):
        @EnsureApplicationCompanyDetailsHaveBeenConfirmed(self.data_api_client_mock)
        def some_func():
            pass

        with mock.patch('app.main.helpers.frameworks.current_app') as current_app_patch:
            with pytest.raises(HTTPException) as e:
                some_func()

        assert e.value.code == 500
        assert current_app_patch.logger.error.call_args_list == [
            mock.call("Required parameter `framework_slug` is undefined for the calling view.")
        ]

    def test_validator_raises_400_if_application_company_details_not_confirmed(self):
        @EnsureApplicationCompanyDetailsHaveBeenConfirmed(self.data_api_client_mock)
        def some_func(framework_slug):
            pass

        self.data_api_client_mock.get_supplier_framework_info.return_value = SupplierFrameworkStub(
            framework_slug='g-cloud-10',
            application_company_details_confirmed=False
        ).single_result_response()

        with mock.patch('app.main.helpers.frameworks.current_user') as current_user_patch:
            current_user_patch.return_value.is_authenticated = True
            current_user_patch.supplier_id.return_value = 1

            with pytest.raises(HTTPException) as e:
                some_func(framework_slug='g-cloud-10')

        assert e.value.code == 400

    def test_validator_raises_404_if_supplier_not_on_framework(self):
        @EnsureApplicationCompanyDetailsHaveBeenConfirmed(self.data_api_client_mock)
        def some_func(framework_slug):
            pass

        self.data_api_client_mock.get_supplier_framework_info.side_effect = HTTPError(
            mock.Mock(status_code=404), 'Supplier framework info not found'
        )

        with mock.patch('app.main.helpers.frameworks.current_user') as current_user_patch:
            current_user_patch.return_value.is_authenticated = True
            current_user_patch.supplier_id.return_value = 1

            with pytest.raises(HTTPError) as e:
                some_func(framework_slug='g-cloud-12')

        assert e.value.status_code == 404

    def test_validator_returns_true_if_application_company_details_are_confirmed(self):
        decorator = EnsureApplicationCompanyDetailsHaveBeenConfirmed(self.data_api_client_mock)

        self.data_api_client_mock.get_supplier_framework_info.return_value = SupplierFrameworkStub(
            framework_slug='g-cloud-10',
            application_company_details_confirmed=True
        ).single_result_response()

        with mock.patch('app.main.helpers.frameworks.current_user') as current_user_patch:
            current_user_patch.return_value.is_authenticated = True
            current_user_patch.supplier_id.return_value = 1

            assert decorator.validator(framework_slug='g-cloud-10') is True

    def test_only_known_decorated_views_are_protected(self):
        """This checks _all_ registered routes and asserts that the views listed in `decorated_views`, below, are all
        protected by the check on application company details needing confirmation. For any views not in
        `decorated_views`, it asserts that it is _not_ protected by the same check."""
        decorated_views = {
            'main.start_new_draft_service',
            'main.copy_draft_service',
            'main.complete_draft_service',
            'main.confirm_draft_service_delete',
            'main.delete_draft_service',
            'main.service_submission_document',
            'main.download_declaration_document',
            'main.view_service_submission',
            'main.edit_service_submission',
            'main.confirm_subsection_remove',
            'main.remove_subsection',
            'main.previous_services',
            'main.copy_previous_service',
            'main.confirm_copy_all_previous_services',
            'main.copy_all_previous_services',
            'main.choose_draft_service_lot',
            'main.framework_submission_lots',
            'main.framework_submission_services',
            'main.framework_start_supplier_declaration',
            'main.reuse_framework_supplier_declaration',
            'main.reuse_framework_supplier_declaration_post',
            'main.framework_supplier_declaration_overview',
            'main.framework_supplier_declaration_submit',
            'main.framework_supplier_declaration_edit',
        }

        from app.main.helpers.frameworks import EnsureApplicationCompanyDetailsHaveBeenConfirmed as decorator_class

        for view_name, view_callable in self.app.view_functions.items():
            if inspect.isfunction(view_callable):
                with mock.patch.object(decorator_class, 'validator', mock.MagicMock()) as validator_mock:
                    validator_mock.return_value = False

                    with self.app.app_context():
                        with mock.patch('app.main.helpers.require_login') as require_login_patch:
                            require_login_patch.return_value = False

                            if view_name in decorated_views:
                                with pytest.raises(HTTPException) as e:
                                    view_callable()

                                assert validator_mock.call_count == 1
                                assert e.value.code == 500
                                assert e.value.description == (
                                    "There was a problem accessing this page of your application. Please try again "
                                    "later."
                                )

                            else:
                                # If it's not decorated, we don't care what error is raised as long as it's not our 500
                                try:
                                    view_callable()

                                except Exception as e:
                                    if isinstance(e, HTTPException):
                                        assert e.value.code != 500 and e.value.description != (
                                            "There was a problem accessing this page of your application. Please try "
                                            "again later."
                                        )

                                assert validator_mock.call_count == 0


class TestReturn404IfApplicationClosed(BaseApplicationTest):
    def setup_method(self, method):
        self.data_api_client_mock = mock.Mock(spec_set=DataAPIClient)
        super().setup_method(method)

    def test_aborts_with_500_and_logs_if_framwork_slug_not_in_kwargs(self):

        @return_404_if_applications_closed(lambda: self.data_api_client_mock)
        def view_function(framework_slug):
            pass

        with mock.patch('app.main.helpers.frameworks.current_app') as current_app_mock:
            with pytest.raises(HTTPException) as e:
                view_function()

        assert e.value.code == 500
        assert current_app_mock.logger.error.call_args_list == [
            mock.call("Required parameter `framework_slug` is undefined for the calling view.")
        ]

    def test_aborts_with_404_if_framework_not_found(self):
        self.data_api_client_mock.get_framework.side_effect = HTTPError(
            mock.Mock(status_code=404), 'Framework not found'
        )

        @return_404_if_applications_closed(lambda: self.data_api_client_mock)
        def view_function(framework_slug):
            pass

        with pytest.raises(HTTPError) as e:
            view_function(framework_slug='not_a_framework')

        assert e.value.status_code == 404
        assert e.value.message == "Framework not found"

    @pytest.mark.parametrize('status', ('pending', 'standstill', 'live'))
    @mock.patch('app.main.helpers.frameworks.current_user')
    def test_returns_404_and_logs_if_framework_status_not_open(self, current_user_mock, status):
        # 'coming' and 'expired' frameworks are caught by `get_framework_or_404`
        self.data_api_client_mock.get_framework.return_value = FrameworkStub(status=status).single_result_response()
        current_user_mock.supplier_id = 123

        @return_404_if_applications_closed(lambda: self.data_api_client_mock)
        def view_function(framework_slug):
            pass

        with mock.patch('app.main.helpers.frameworks.current_app') as current_app_mock:
            with self.app.test_request_context('/suppliers'):
                response = view_function(framework_slug='g-cloud-9')

        assert current_app_mock.logger.info.call_args_list == [
            mock.call(
                'Supplier {supplier_id} requested "{method} {path}" after {framework_slug} applications closed.',
                extra={
                    'supplier_id': 123,
                    'method': 'GET',
                    'path': '/suppliers',
                    'framework_slug': 'g-cloud-9'
                }
            )
        ]
        assert response[1] == 404

    @pytest.mark.parametrize('status', ('pending', 'standstill', 'live'))
    @pytest.mark.parametrize('content_set', (True, False))
    @mock.patch('app.main.helpers.frameworks.content_loader', autospec=True)
    def test_renders_error_page_correctly_if_following_framework_content_set(
        self, content_loader_mock, content_set, status
    ):
        self.data_api_client_mock.get_framework.return_value = FrameworkStub(status=status).single_result_response()
        if content_set:
            content_loader_mock.get_metadata.return_value = {
                'name': 'Next Framework 2', 'slug': 'n-f-2', 'coming': '2042'
            }
        else:
            content_loader_mock.get_metadata.side_effect = ContentNotFoundError()

        @return_404_if_applications_closed(lambda: self.data_api_client_mock)
        def view_function(framework_slug):
            pass

        with mock.patch('app.main.helpers.frameworks.current_user'):
            with mock.patch('app.main.helpers.frameworks.current_app'):
                with self.app.test_request_context('/suppliers'):
                    response = view_function(framework_slug='g-cloud-9')

        document = html.fromstring(response[0])
        assert response[1] == 404
        assert document.xpath('//title/text()')[0].strip() == "Applications closed - Digital Marketplace"
        assert document.xpath('//h1/text()')[0] == "You can no longer apply to G-Cloud 10"
        assert "The deadline for applying was 12am GMT, Monday 3 January 2000." in \
            document.xpath('//div[@class="dmspeak"]/p/text()')[0]

        if content_set:
            assert "Next Framework 2 is expected to open in 2042." in \
                document.xpath('//div[@class="dmspeak"]/p/text()')[1]
        else:
            assert "is expected to open in" not in response[0]

    def test_returns_the_view_function_if_framework_is_open(self):
        self.data_api_client_mock.get_framework.return_value = FrameworkStub(status='open').single_result_response()

        @return_404_if_applications_closed(lambda: self.data_api_client_mock)
        def view_function(framework_slug):
            return f'{framework_slug} - OK!'

        response = view_function(framework_slug='g-cloud-7')

        assert response == 'g-cloud-7 - OK!'

    @mock.patch('app.main.views.frameworks.data_api_client')
    @mock.patch('app.main.views.services.data_api_client')
    @mock.patch('app.main.helpers.require_login')
    @mock.patch('app.main.helpers.frameworks.current_user')
    def test_only_known_application_editing_decorated_views_are_protected(
        self, current_user_mock, require_login_mock, services_data_api_client, frameworks_data_api_client,
    ):
        decorated_views = {
            'main.edit_service_submission',
            'main.confirm_subsection_remove',
            'main.remove_subsection',
            'main.delete_draft_service',
            'main.start_new_draft_service',
            'main.previous_services',
            'main.complete_draft_service',
            'main.confirm_draft_service_delete',
            'main.copy_draft_service',
            'main.copy_previous_service',
            'main.confirm_copy_all_previous_services',
            'main.copy_all_previous_services',
            'main.framework_supplier_declaration_submit',
            'main.framework_start_supplier_declaration',
            'main.reuse_framework_supplier_declaration',
            'main.reuse_framework_supplier_declaration_post',
            'main.framework_supplier_declaration_edit',
        }

        services_data_api_client.get_framework.return_value = FrameworkStub(status='pending').single_result_response()
        frameworks_data_api_client.get_framework.return_value = FrameworkStub(status='pending').single_result_response()
        current_user_mock.supplier_id = 123
        require_login_mock.return_value = False

        from app.main.helpers.frameworks import EnsureApplicationCompanyDetailsHaveBeenConfirmed as \
            company_details_decorator_class

        for view_name, view_callable in self.app.view_functions.items():
            if inspect.isfunction(view_callable):
                with mock.patch.object(
                    company_details_decorator_class, 'validator', mock.MagicMock()
                ) as validator_mock:
                    # Always validate true to bypass EnsureApplicationCompanyDetailsHaveBeenConfirmed decorator
                    validator_mock.return_value = True

                    with self.app.test_request_context('/suppliers'):
                        if view_name in decorated_views:
                            response = view_callable(framework_slug='Sausage-Cloud 6')

                            assert response[1] == 404
                            assert "Applications closed - Digital Marketplace" in response[0]

                        else:
                            # If it's not decorated, we don't care if the call is succesful or errors, as long it
                            # doesn't use our decorator. This call will ALWAYS error if the decorator is used.
                            try:
                                response = view_callable()

                            except Exception as e:
                                if isinstance(e, HTTPException):
                                    assert e.value.code != 500 and e.value.description != (
                                        "There was a problem accessing this page of your application. Please try "
                                        "again later."
                                    )
