# -*- coding: utf-8 -*-
"""Test for app/main/helpers/frameworks.py"""

import mock
import pytest
from werkzeug.exceptions import HTTPException

from dmutils.api_stubs import framework
from dmapiclient import HTTPError

from app.main.helpers.frameworks import (
    check_agreement_is_related_to_supplier_framework_or_abort, get_framework_for_reuse, get_statuses_for_lot,
    return_supplier_framework_info_if_on_framework_or_abort, order_frameworks_for_reuse,
    get_frameworks_closed_and_open_for_applications, get_supplier_registered_name_from_declaration,
    get_framework_or_500
)


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
        allowDeclarationReuse == True
        applicationsCloseAtUTC is closest to today
        and declaration exists for that framework
        and declaration status is completed
        """
        t09 = '2009-03-03T01:01:01.000000Z'
        t07 = '2007-03-03T01:01:01.000000Z'
        t11 = '2011-03-03T01:01:01.000000Z'
        t12 = '2012-03-03T01:01:01.000000Z'
        t13 = '2013-03-03T01:01:01.000000Z'
        t14 = '2014-03-03T01:01:01.000000Z'

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
                'slug': 'ben-cloud-alpha'
            },
        ]
        declarations = [
            {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-4', 'onFramework': True},
            {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-1000000', 'onFramework': True},
            {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-2', 'onFramework': True},
            {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-alpha', 'onFramework': True},
        ]

        self.data_api_client.find_frameworks.return_value = {'frameworks': frameworks}
        self.data_api_client.find_supplier_declarations.return_value = {'frameworkInterest': declarations}
        framework = get_framework_for_reuse(declarations, self.data_api_client)

        assert framework['slug'] == 'ben-cloud-4'

    def test_get_reusable_declaration_none(self):
        """Test returning None.
        """
        t14 = '2014-03-05T01:01:01.000000Z'

        frameworks = [
            {'x_field': 'foo', 'allowDeclarationReuse': True, 'applicationsCloseAtUTC': t14, 'slug': 'ben-cloud-5'},
        ]
        declarations = [
            {'x_field': 'foo', 'frameworkSlug': 'ben-cloud-4', 'onFramework': True},
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
        data_api_client_mock.get_framework.return_value = framework()

        assert get_framework_or_500(data_api_client_mock, 'g-cloud-7')['slug'] == 'g-cloud-7'

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
