# -*- coding: utf-8 -*-
import copy
import re
from datetime import datetime
from functools import partial
from io import BytesIO

from freezegun import freeze_time
from lxml import html
import mock
import pytest

from dmapiclient import HTTPError
from dmtestutils.api_model_stubs import FrameworkStub, LotStub, SupplierStub, ServiceStub
from dmtestutils.fixtures import valid_pdf_bytes, valid_odt_bytes

from app.main.helpers.services import parse_document_upload_time
from tests.app.helpers import (
    BaseApplicationTest,
    empty_g7_draft_service,
    empty_g9_draft_service,
    MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin
)


@pytest.fixture(params=(
    # a tuple of framework_slug, framework_family, framework_name, framework_editable_services
    (
        "g-cloud-9",
        "g-cloud",
        "G-Cloud 9",
        True
    ),
    (
        "digital-outcomes-and-specialists-2",
        "digital-outcomes-and-specialists",
        "Digital outcomes and specialists 2",
        False
    )
))
def supplier_service_editing_fw_params(request):
    return request.param


# find a better way of organizing this than using oddly specific long names
@pytest.fixture(params=(
    # a tuple of service status, service_belongs_to_user, expect_api_call_if_data, expected_status_code
    ("published", True, True, 302,),
    ("enabled", True, False, 400,),
    ("disabled", True, False, 400,),
    ("published", False, False, 404,),
))
def supplier_remove_service__service_status__expected_results(request):
    return request.param


@pytest.fixture(params=(False, True,))
def supplier_remove_service__post_data(request):
    return request.param


@pytest.mark.parametrize("service_status", ("published", "enabled", "disabled",))
@pytest.mark.parametrize("framework_family", ("g-cloud", "digital-outcomes-and-specialists",))
class TestServiceHierarchyRedirection(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    @staticmethod
    def _mock_get_service_side_effect(service_status, framework_family, service_belongs_to_user, service_id):
        try:
            return {"567": {
                'services': {
                    'serviceName': 'Some name 567',
                    'status': service_status,
                    'id': '567',
                    'frameworkName': "Q-Cloud #57",
                    'frameworkSlug': "q-cloud-57",
                    'frameworkFramework': framework_family,
                    'supplierId': 1234 if service_belongs_to_user else 1235,
                },
            }}[str(service_id)]
        except KeyError:
            raise HTTPError(mock.Mock(status_code=404))

    @pytest.mark.parametrize("suffix", ("", "/blah/123",))
    def test_redirects_happy_path(self, service_status, framework_family, suffix):
        self.login()

        self.data_api_client.get_service.side_effect = partial(
            self._mock_get_service_side_effect,
            service_status,
            framework_family,
            True,
        )
        res = self.client.get('/suppliers/services/567' + suffix)

        assert res.status_code == 302
        assert res.location == "http://localhost/suppliers/frameworks/q-cloud-57/services/567" + suffix

    @pytest.mark.parametrize("suffix", ("", "/blah/123",))
    def test_fails_if_wrong_supplier(self, service_status, framework_family, suffix):
        self.login()

        self.data_api_client.get_service.side_effect = partial(
            self._mock_get_service_side_effect,
            service_status,
            framework_family,
            False,
        )
        res = self.client.get('/suppliers/services/567' + suffix)

        assert res.status_code == 404

    @pytest.mark.parametrize("suffix", ("", "/blah/123",))
    def test_fails_if_unknown_service(self, service_status, framework_family, suffix):
        self.login()

        self.data_api_client.get_service.side_effect = partial(
            self._mock_get_service_side_effect,
            service_status,
            framework_family,
            True,
        )
        res = self.client.get('/suppliers/services/31415' + suffix)

        assert res.status_code == 404

    @pytest.mark.parametrize("service_belongs_to_user", (False, True,))
    def test_trailing_slash(
            self,
            service_status,
            framework_family,
            service_belongs_to_user,
    ):
        self.login()

        self.data_api_client.get_service.side_effect = partial(
            self._mock_get_service_side_effect,
            service_status,
            framework_family,
            service_belongs_to_user,
        )
        res = self.client.get('/suppliers/services/567/')

        assert res.status_code == 301
        assert res.location == "http://localhost/suppliers/services/567"


class TestListServices(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def _mock_get_framework_side_effect(self, framework_slug):
        try:
            return {
                "g-cloud-909": self.framework(status="live", slug="g-cloud-909"),
                "g-cloud-890": self.framework(status="open", slug="g-cloud-890"),
                "g-cloud-870": self.framework(status="expired", slug="g-cloud-870"),
                "digital-outcomes-and-specialists-100":
                    self.framework(status="live", slug="digital-outcomes-and-specialists-100"),
            }[framework_slug]
        except KeyError:
            raise HTTPError(mock.Mock(status_code=404))

    def test_shows_no_services_message(self):
        self.login()

        self.data_api_client.get_framework.side_effect = self._mock_get_framework_side_effect
        self.data_api_client.find_services.return_value = {
            "services": [],
        }

        res = self.client.get('/suppliers/frameworks/g-cloud-909/services')
        assert res.status_code == 200

        document = html.fromstring(res.get_data(as_text=True))
        assert document.xpath(
            "//h1[normalize-space(string())=$t]",
            t="Your G-Cloud 909 services",
        )
        assert document.xpath(
            "//p[contains(@class, 'govuk-body')][normalize-space(string())=$t]",
            t="You don’t have any G-Cloud 909 services on the Digital Marketplace",
        )

        self.data_api_client.find_services.assert_called_once_with(
            supplier_id=1234,
            framework="g-cloud-909",
        )

    @pytest.mark.parametrize("framework_slug", (
        "g-cloud-890",
        "g-cloud-870",
        "x-cloud-123",
    ))
    def test_no_services_list_inappropriate_frameworks(self, framework_slug):
        self.login()

        self.data_api_client.get_framework.side_effect = self._mock_get_framework_side_effect
        self.data_api_client.find_services.side_effect = AssertionError("Shouldn't be called")

        res = self.client.get("/suppliers/frameworks/{}/services".format(framework_slug))
        assert res.status_code == 404

    def test_shows_services_list(self):
        self.login()

        self.data_api_client.get_framework.side_effect = self._mock_get_framework_side_effect
        self.data_api_client.find_services.return_value = {
            'services': [{
                'serviceName': 'Service name 123',
                'status': 'published',
                'id': '123',
                'lotSlug': 'saas',
                'lotName': 'Software as a Service',
                'frameworkName': 'G-Cloud 909',
                'frameworkSlug': 'g-cloud-909'
            }]
        }

        res = self.client.get("/suppliers/frameworks/g-cloud-909/services")
        assert res.status_code == 200

        document = html.fromstring(res.get_data(as_text=True))
        assert document.xpath(
            "//h1[normalize-space(string())=$t]",
            t="Your G-Cloud 909 services",
        )
        assert document.xpath(
            "//td[contains(@class, 'govuk-table__cell')][normalize-space(string())=$t]",
            t="Software as a Service",
        )
        assert document.xpath(
            "//td[contains(@class, 'govuk-table__cell')][normalize-space(string())=$t]",
            t="Service name 123",
        )

        self.data_api_client.find_services.assert_called_once_with(
            supplier_id=1234,
            framework="g-cloud-909",
        )

    def test_shows_service_for_single_service_lot(self):
        self.login()

        self.data_api_client.get_framework.side_effect = self._mock_get_framework_side_effect
        self.data_api_client.find_services.return_value = {
            'services': [{
                'status': 'published',
                'id': '123',
                'lotSlug': 'digital-outcomes',
                'lotName': 'Digital Outcomes',
                'frameworkName': "digital-outcomes-and-specialists-100",
                'frameworkSlug': "digital-outcomes-and-specialists-100",
            }]
        }

        res = self.client.get("/suppliers/frameworks/digital-outcomes-and-specialists-100/services")
        assert res.status_code == 200

        document = html.fromstring(res.get_data(as_text=True))
        assert document.xpath(
            "//td[contains(@class, 'govuk-table__cell')][normalize-space(string())=$t]//a",
            t="Digital Outcomes",
        )

    def test_should_not_be_able_to_see_page_if_user_inactive(self):
        self.login(active=False)

        res = self.client.get('/suppliers/frameworks/g-cloud-909/services')
        assert res.status_code == 302
        assert res.location == 'http://localhost/user/login?next=%2Fsuppliers%2Fframeworks%2Fg-cloud-909%2Fservices'

    def test_should_redirect_to_login_if_not_logged_in(self):
        res = self.client.get("/suppliers/frameworks/g-cloud-909/services")
        assert res.status_code == 302
        assert res.location == 'http://localhost/user/login?next=%2Fsuppliers%2Fframeworks%2Fg-cloud-909%2Fservices'

    def test_shows_service_edit_link_with_id(self):
        self.login()

        self.data_api_client.get_framework.side_effect = self._mock_get_framework_side_effect
        self.data_api_client.find_services.return_value = {
            'services': [{
                'serviceName': 'Service name 123',
                'status': 'published',
                'id': '123',
                'frameworkSlug': 'g-cloud-909'
            }]
        }

        res = self.client.get('/suppliers/frameworks/g-cloud-909/services')
        assert res.status_code == 200

        document = html.fromstring(res.get_data(as_text=True))
        assert document.xpath(
            "//td//a[normalize-space(string())=$t][@href=$u]",
            t="Service name 123",
            u="/suppliers/frameworks/g-cloud-909/services/123",
        )
        self.data_api_client.find_services.assert_called_once_with(
            supplier_id=1234,
            framework="g-cloud-909",
        )

    def test_services_without_service_name_show_lot_instead(self):
        self.login()

        self.data_api_client.get_framework.side_effect = self._mock_get_framework_side_effect
        self.data_api_client.find_services.return_value = {
            'services': [{
                'status': 'published',
                'id': '123',
                'lotName': 'Special Lot Name',
                'frameworkSlug': 'g-cloud-909',
            }]
        }

        res = self.client.get('/suppliers/frameworks/g-cloud-909/services')
        assert res.status_code == 200

        document = html.fromstring(res.get_data(as_text=True))
        assert document.xpath(
            "//td[contains(@class, 'govuk-table__cell')][normalize-space(string())=$t]",
            t="Special Lot Name",
        )
        self.data_api_client.find_services.assert_called_once_with(
            supplier_id=1234,
            framework="g-cloud-909",
        )


class _BaseTestSupplierEditRemoveService(BaseApplicationTest):
    def _setup_service(
        self,
        framework_slug,
        framework_family,
        framework_name,
        service_status="published",
        service_belongs_to_user=True,
        **kwargs
    ):
        service_data = {
            'serviceName': 'Service name 123',
            'status': service_status,
            'id': '123',
            'frameworkName': framework_name,
            'frameworkSlug': framework_slug,
            'frameworkFramework': framework_family,
            'frameworkFamily': framework_family,
            'supplierId': 1234 if service_belongs_to_user else 1235,
        }
        service_data.update(kwargs)
        self.data_api_client.get_service.return_value = {
            'services': service_data
        }
        if service_status == 'published':
            self.data_api_client.update_service_status.return_value = self.data_api_client.get_service.return_value
        else:
            self.data_api_client.get_service.return_value['serviceMadeUnavailableAuditEvent'] = {
                "createdAt": "2015-03-23T09:30:00.00001Z"
            }

        self.data_api_client.get_framework.return_value = {
            'frameworks': {
                'name': framework_name,
                'slug': framework_slug,
                'status': 'live',
            }
        }


class _BaseSupplierEditServiceTestsSharedAcrossFrameworks(_BaseTestSupplierEditRemoveService):
    """Tests shared by both DOS and GCloud frameworks for editing a service e.g. /suppliers/services/123"""

    @pytest.mark.parametrize("fwk_status,expected_code", [
        ("coming", 404),
        ("open", 404),
        ("pending", 404),
        ("standstill", 404),
        ("live", 200),
        ("expired", 404),
    ])
    def test_edit_page_only_exists_for_services_on_live_frameworks(self, fwk_status, expected_code):
        self.login()
        fwk_kwargs = self.framework_kwargs.copy()
        fwk_kwargs.update({'status': fwk_status})
        self._setup_service(service_status='published', **fwk_kwargs)
        self.data_api_client.get_framework.return_value = {
            'frameworks': {
                'slug': fwk_kwargs.get('framework_slug'),
                'status': fwk_kwargs.get('status'),
            }
        }
        res = self.client.get("/suppliers/frameworks/{}/services/123".format(self.framework_kwargs["framework_slug"]))
        assert res.status_code == expected_code, (
            "Unexpected response {} for {} framework state".format(res.status_code, fwk_status)
        )

    def test_edit_page_returns_404_if_service_not_found(self):
        self.login()
        self.data_api_client.get_service.return_value = None

        res = self.client.get("/suppliers/frameworks/{}/services/123".format(self.framework_kwargs["framework_slug"]))

        assert res.status_code == 404

    def test_should_not_view_other_suppliers_services(self):
        self.login()
        self._setup_service(service_status='published', service_belongs_to_user=False, **self.framework_kwargs)

        res = self.client.get("/suppliers/frameworks/{}/services/123".format(self.framework_kwargs["framework_slug"]))

        assert res.status_code == 404

    def test_should_redirect_to_login_if_not_logged_in(self):
        self._setup_service(service_status='published', **self.framework_kwargs)
        res = self.client.get("/suppliers/frameworks/{}/services/123".format(self.framework_kwargs["framework_slug"]))
        assert res.status_code == 302
        assert res.location == \
            'http://localhost/user/login?next=%2Fsuppliers%2Fframeworks%2F{}%2Fservices%2F123'.format(
                self.framework_kwargs["framework_slug"]
            )

    @pytest.mark.parametrize("status", ["enabled", "disabled"])
    def test_should_view_private_or_disabled_service_with_correct_message(self, status):
        self.login()
        self._setup_service(service_status=status, **self.framework_kwargs)

        res = self.client.get("/suppliers/frameworks/{}/services/123".format(self.framework_kwargs["framework_slug"]))

        assert res.status_code == 200
        assert 'Service name 123' in res.get_data(as_text=True)

        self.assert_in_strip_whitespace(
            '<h2>This service was removed on Monday 23 March 2015</h2>',
            res.get_data(as_text=True)
        )

        # this assertion should always be true for DOS, still we need to check it for g-cloud
        self.assert_not_in_strip_whitespace(
            '<h2>Remove this service</h2>',
            res.get_data(as_text=True)
        )

    @pytest.mark.parametrize("status", ["published", "enabled", "disabled"])
    def test_service_incorrect_framework(self, status):
        self.login()
        self._setup_service(service_status=status, **self.framework_kwargs)

        res = self.client.get("/suppliers/frameworks/not-a-framework/services/123")
        assert res.status_code == 404


class TestSupplierEditGCloudService(_BaseSupplierEditServiceTestsSharedAcrossFrameworks):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    framework_kwargs = {
        "framework_slug": "g-cloud-9",
        "framework_family": "g-cloud",
        "framework_name": "G-Cloud 9"
    }

    def test_should_view_public_service_with_correct_message(self):
        self.login()
        self._setup_service(service_status='published', **self.framework_kwargs)

        res = self.client.get("/suppliers/frameworks/{}/services/123".format(self.framework_kwargs["framework_slug"]))

        assert res.status_code == 200

        assert 'Service name 123' in res.get_data(as_text=True)

        # first message should be there
        self.assert_in_strip_whitespace(
            'Remove this service',
            res.get_data(as_text=True)
        )

        # removal confirmation message should not have been triggered yet
        self.assert_not_in_strip_whitespace(
            'Are you sure you want to remove your service?',
            res.get_data(as_text=True)
        )

        # service removed message should not have been triggered yet
        self.assert_not_in_strip_whitespace(
            'Service name 123 has been removed.',
            res.get_data(as_text=True)
        )

        # service removed notification banner shouldn't be there
        self.assert_not_in_strip_whitespace(
            'This service was removed',
            res.get_data(as_text=True)
        )

        # service updated message shouldn't be there either
        self.assert_not_in_strip_whitespace(
            "The changes are now live on the Digital Marketplace",
            res.get_data(as_text=True)
        )

    def test_should_view_public_service_with_update_message(self):
        self.login()
        self._setup_service(service_status='published', **self.framework_kwargs)

        # this is meant to emulate a "service updated" message
        with self.client.session_transaction() as session:
            session['_flashes'] = [
                ('message', 'Foo Bar 123 321'),
            ]

        res = self.client.get("/suppliers/frameworks/{}/services/123".format(self.framework_kwargs["framework_slug"]))

        assert res.status_code == 200

        assert 'Service name 123' in res.get_data(as_text=True)

        # first message should be there
        self.assert_in_strip_whitespace(
            'Remove this service',
            res.get_data(as_text=True)
        )

        # removal confirmation message should not have been triggered
        self.assert_not_in_strip_whitespace(
            'Are you sure you want to remove your service?',
            res.get_data(as_text=True)
        )

        # service removed message should not have been triggered
        self.assert_not_in_strip_whitespace(
            'Service name 123 has been removed.',
            res.get_data(as_text=True)
        )

        # service removed notification banner shouldn't be there
        self.assert_not_in_strip_whitespace(
            'This service was removed',
            res.get_data(as_text=True)
        )

        # dummy service updated message should be there
        self.assert_in_strip_whitespace(
            "Foo Bar 123 321",
            res.get_data(as_text=True)
        )

    def test_editable_empty_questions_are_shown(self):
        """Currently the only question that is editable but potentially empty (optional during service submission)
        is the serviceDefinitionDocumentURL for G-Cloud 9 so we test this behaviour in this class"""
        service_kwargs = {
            "serviceName": "My G-Cloud 9 service",
            "lot": "cloud-hosting",
            "lotName": "Cloud Hosting",
            "lotSlug": "cloud-hosting"
        }
        service_kwargs.update(self.framework_kwargs)
        self.login()
        self._setup_service(service_status='published', **service_kwargs)

        res = self.client.get("/suppliers/frameworks/{}/services/123".format(self.framework_kwargs["framework_slug"]))

        assert res.status_code == 200
        page = res.get_data(as_text=True)

        # There's no serviceDefinitionDocumentURL in the test service data, so a row with empty_message should be shown
        self.assert_in_strip_whitespace('Service definition document', page)
        self.assert_in_strip_whitespace('You haven’t added a service definition document', page)


class TestSupplierEditDosServices(_BaseSupplierEditServiceTestsSharedAcrossFrameworks):
    """Although the route tested is the edit service page, DOS services are not editable or removable and are only
    viewable at the moment"""
    framework_kwargs = {
        "framework_slug": "digital-outcomes-and-specialists-2",
        "framework_family": "digital-outcomes-and-specialists",
        "framework_name": "Digital outcomes and specialists 2"
    }

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_supplier_can_view_their_dos_service_details(self):
        self.login()
        self._setup_service(service_status='published', **self.framework_kwargs)
        res = self.client.get("/suppliers/frameworks/{}/services/123".format(self.framework_kwargs["framework_slug"]))

        assert res.status_code == 200
        assert 'Service name 123' in res.get_data(as_text=True)

    def test_no_link_to_public_service_page(self):
        self.login()
        self._setup_service(service_status='published', **self.framework_kwargs)
        res = self.client.get("/suppliers/frameworks/{}/services/123".format(self.framework_kwargs["framework_slug"]))
        assert res.status_code == 200
        assert 'View service page on the Digital Marketplace' not in res.get_data(as_text=True)

    def test_no_remove_service_section(self):
        self.login()
        self._setup_service(service_status='published', **self.framework_kwargs)
        res = self.client.get("/suppliers/frameworks/{}/services/123".format(self.framework_kwargs["framework_slug"]))
        assert res.status_code == 200
        self.assert_not_in_strip_whitespace(
            'Remove this service',
            res.get_data(as_text=True)
        )

    def test_no_remove_service_confirmation_prompt(self):
        self.login()
        self._setup_service(service_status='published', **self.framework_kwargs)
        res = self.client.get("/suppliers/frameworks/{}/services/123?remove_requested=True".format(
            self.framework_kwargs["framework_slug"]
        ))
        assert res.status_code == 200
        self.assert_not_in_strip_whitespace(
            'Are you sure you want to remove your service?',
            res.get_data(as_text=True)
        )

    def test_uneditable_empty_questions_are_hidden(self):
        """Although the behaviour of hiding empty question summary rows is not specific to DOS, it is currently the
        only framework with uneditable questions that can be empty so we test this behaviour in this class"""
        service_kwargs = {
            "designerLocations": ["London", "Scotland"],
            "designerPriceMin": "100",
            "designerPriceMax": "1000",
            "lot": "digital-specialists",
            "lotName": "Digital specialists",
            "lotSlug": "digital-specialists"
        }
        service_kwargs.update(self.framework_kwargs)
        self.login()
        self._setup_service(service_status='published', **service_kwargs)

        res = self.client.get("/suppliers/frameworks/{}/services/123".format(self.framework_kwargs["framework_slug"]))

        assert res.status_code == 200
        self.assert_in_strip_whitespace(
            'Designer',
            res.get_data(as_text=True)
        )
        # No developer role in data so table row should not exist
        self.assert_not_in_strip_whitespace(
            'Developer',
            res.get_data(as_text=True)
        )


class TestSupplierRemoveServiceEditInterplay(_BaseTestSupplierEditRemoveService):
    """
        These tests actually test the *interplay* between the remove view and its subsequent (redirected)
        views through using `follow_redirects` to perform both a POST to the remove view and a subsequent GET to the
        following view. Chief thing we're asserting is the flash message throw/catch.
    """

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_should_view_confirmation_message_if_first_remove_service_button_clicked(
        self, supplier_service_editing_fw_params
    ):
        framework_slug, framework_family, framework_name, framework_editable_services = \
            supplier_service_editing_fw_params
        self.login()
        self._setup_service(
            framework_slug,
            framework_family,
            framework_name,
            service_status='published'
        )

        # NOTE two http requests performed here
        res = self.client.post(
            '/suppliers/frameworks/{}/services/123/remove'.format(framework_slug),
            follow_redirects=True,
        )
        if not framework_editable_services:
            assert res.status_code == 404
            assert self.data_api_client.update_service_status.called is False
            return

        assert res.status_code == 200

        # first message should be gone
        self.assert_not_in_strip_whitespace(
            'Remove this service',
            res.get_data(as_text=True)
        )

        # confirmation message should be there
        self.assert_in_strip_whitespace(
            'Are you sure you want to remove your service?',
            res.get_data(as_text=True)
        )

        # service removed message should not have been triggered yet
        self.assert_not_in_strip_whitespace(
            'Service name 123 has been removed.',
            res.get_data(as_text=True)
        )

    def test_should_view_correct_notification_message_if_service_removed(self, supplier_service_editing_fw_params):
        framework_slug, framework_family, framework_name, framework_editable_services = \
            supplier_service_editing_fw_params
        self.login()
        self._setup_service(
            framework_slug,
            framework_family,
            framework_name,
            service_status='published'
        )

        # NOTE two http requests performed here
        res = self.client.post(
            '/suppliers/frameworks/{}/services/123/remove'.format(framework_slug),
            data={'remove_confirmed': True},
            follow_redirects=True)
        if not framework_editable_services:
            assert res.status_code == 404
            assert self.data_api_client.update_service_status.called is False
            return

        assert res.status_code == 200
        self.assert_in_strip_whitespace(
            'Service name 123 has been removed.',
            res.get_data(as_text=True)
        )

        # the "are you sure" message should be gone
        self.assert_not_in_strip_whitespace(
            'Are you sure you want to remove your service?',
            res.get_data(as_text=True)
        )


class TestSupplierRemoveService(_BaseTestSupplierEditRemoveService):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    @pytest.mark.parametrize("fwk_status,expected_code", [
        ("coming", 404),
        ("open", 404),
        ("pending", 404),
        ("standstill", 404),
        ("live", 302),
        ("expired", 404),
    ])
    def test_remove_only_works_for_services_on_live_frameworks(self, fwk_status, expected_code):
        self.login()
        self._setup_service(
            'g-cloud-9',
            'g-cloud',
            'G-Cloud 9',
            service_status='published',
            service_belongs_to_user=True,
        )
        self.data_api_client.get_framework.return_value = {
            'frameworks': {
                'slug': 'g-cloud-9',
                'status': fwk_status,
            }
        }
        response = self.client.post(
            '/suppliers/frameworks/g-cloud-9/services/123/remove',
            data={'remove_confirmed': True},
        )

        assert response.status_code == expected_code, (
            "Unexpected response {} for {} framework state".format(response.status_code, fwk_status)
        )

    def test_remove_service(
        self,
        supplier_service_editing_fw_params,
        supplier_remove_service__service_status__expected_results,
        supplier_remove_service__post_data,
    ):
        framework_slug, framework_family, framework_name, framework_editable_services = \
            supplier_service_editing_fw_params
        service_status, service_belongs_to_user, expect_api_call_if_data, expected_status_code = \
            supplier_remove_service__service_status__expected_results
        post_data = supplier_remove_service__post_data

        self.login()
        self._setup_service(
            framework_slug,
            framework_family,
            framework_name,
            service_status=service_status,
            service_belongs_to_user=service_belongs_to_user,
        )

        response = self.client.post(
            '/suppliers/frameworks/{}/services/123/remove'.format(framework_slug),
            data={'remove_confirmed': True} if post_data else {},
        )
        if not framework_editable_services:
            assert response.status_code == 404
            assert self.data_api_client.update_service_status.called is False
            return

        assert self.data_api_client.update_service_status.called is (expect_api_call_if_data and post_data)
        assert response.status_code == expected_status_code

    @pytest.mark.parametrize("confirm", (False, True,))
    def test_should_fail_if_incorrect_framework(self, supplier_service_editing_fw_params, confirm):
        framework_slug, framework_family, framework_name, framework_editable_services = \
            supplier_service_editing_fw_params
        self.login()
        self._setup_service(
            framework_slug,
            framework_family,
            framework_name,
            service_status='published'
        )

        res = self.client.post(
            '/suppliers/frameworks/{}-fake/services/123/remove'.format(framework_slug),
            data={'remove_confirmed': True} if confirm else None,
        )

        assert res.status_code == 404
        assert self.data_api_client.update_service_status.called is False


@mock.patch('dmutils.s3.S3')
class TestSupplierEditUpdateServiceSection(BaseApplicationTest):

    def _get_framework_response(self, **kwargs):
        return {
            "frameworks": {
                "framework": "g-cloud",
                "name": "G-Cloud 6",
                "slug": "g-cloud-6",
                "status": "live",
                **kwargs
            }
        }

    empty_service = {
        'services': {
            'serviceName': 'Service name 123',
            'status': 'published',
            'id': '123',
            'frameworkSlug': 'g-cloud-6',
            'frameworkName': 'G-Cloud 6',
            'supplierId': 1234,
            'supplierName': 'We supply any',
            'lot': 'scs',
            'lotSlug': 'scs',
            'lotName': "Specialist Cloud Services",
        }
    }

    def setup_method(self, method):
        super().setup_method(method)
        self.login()

        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    @pytest.mark.parametrize("fwk_status,expected_code", [
        ("coming", 404),
        ("open", 404),
        ("pending", 404),
        ("standstill", 404),
        ("live", 200),
        ("expired", 404),
    ])
    def test_edit_section_only_exists_for_live_frameworks(self, s3, fwk_status, expected_code):
        self.data_api_client.get_service.return_value = self.empty_service
        self.data_api_client.get_framework.return_value = self._get_framework_response(status=fwk_status)

        res = self.client.get('/suppliers/frameworks/g-cloud-6/services/1/edit/description')
        assert res.status_code == expected_code, (
            "Unexpected response {} for {} framework state".format(res.status_code, fwk_status)
        )

    def test_edit_page(self, s3):
        self.data_api_client.get_service.return_value = self.empty_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        res = self.client.get('/suppliers/frameworks/g-cloud-6/services/1/edit/description')

        assert res.status_code == 200
        document = html.fromstring(res.get_data(as_text=True))

        form = document.xpath(
            "//form[@method='post'][.//button[normalize-space(string())=$t]]",
            t="Save and return",
        )[0]
        assert form.xpath(
            ".//input[@name=$n][@value=$v]",
            n="serviceName",
            v="Service name 123",
        )
        assert form.xpath(
            ".//textarea[@name=$n]",
            n="serviceSummary",
        )
        assert document.xpath(
            "//a[@href=$u][normalize-space(string())]",
            u="/suppliers/frameworks/g-cloud-6/services/1",
            t="Return to service summary",
        )

        assert self.data_api_client.update_service.called is False
        self.assert_no_flashes()

        breadcrumbs = document.xpath("//div[@class='govuk-breadcrumbs']/ol/li")

        assert tuple(li.xpath("normalize-space(string())") for li in breadcrumbs) == (
            "Digital Marketplace",
            "Your account",
            "Your G-Cloud 6 services",
            "Service name 123",
            "Description",
        )
        assert tuple(li.xpath(".//a/@href") for li in breadcrumbs) == (
            ['/'],
            ['/suppliers'],
            ['/suppliers/frameworks/g-cloud-6/services'],
            ['/suppliers/frameworks/g-cloud-6/services/1'],
            [],
        )

    def test_edit_service_incorrect_framework(self, s3):
        self.data_api_client.get_service.return_value = self.empty_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        res = self.client.get('/suppliers/frameworks/g-cloud-7/services/1/edit/description')
        assert res.status_code == 404
        assert self.data_api_client.update_service.called is False
        self.assert_no_flashes()

    @pytest.mark.parametrize("fwk_status,expected_code", [
        ("coming", 404),
        ("open", 404),
        ("pending", 404),
        ("standstill", 404),
        ("live", 302),
        ("expired", 404),
    ])
    def test_update_section_only_works_for_live_frameworks(self, s3, fwk_status, expected_code):
        self.data_api_client.get_service.return_value = self.empty_service
        self.data_api_client.get_framework.return_value = self._get_framework_response(status=fwk_status)

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-6/services/1/edit/description',
            data={
                'serviceName': 'The service',
                'serviceSummary': 'This is the service',
            })

        assert res.status_code == expected_code, (
            "Unexpected response {} for {} framework state".format(res.status_code, fwk_status)
        )

    def test_questions_for_this_service_section_can_be_changed(self, s3):
        self.data_api_client.get_service.return_value = self.empty_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-6/services/1/edit/description',
            data={
                'serviceName': 'The service',
                'serviceSummary': 'This is the service',
            })

        assert res.status_code == 302
        self.data_api_client.update_service.assert_called_once_with(
            '1', {'serviceName': 'The service', 'serviceSummary': 'This is the service'},
            'email@email.com')

        assert self.get_flash_messages() == ((
            "success",
            "You’ve edited your service. The changes are now live on the Digital Marketplace.",
        ),)

    def test_editing_readonly_section_is_not_allowed(self, s3):
        self.data_api_client.get_service.return_value = self.empty_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        res = self.client.get('/suppliers/frameworks/g-cloud-6/services/1/edit/service-attributes')
        assert res.status_code == 404

        self.data_api_client.get_draft_service.return_value = self.empty_service
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-6/services/1/edit/service-attributes',
            data={
                'lotSlug': 'scs',
            })

        assert res.status_code == 404
        assert self.data_api_client.update_service.called is False
        self.assert_no_flashes()

    def test_only_questions_for_this_service_section_can_be_changed(self, s3):
        self.data_api_client.get_service.return_value = self.empty_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-6/services/1/edit/description',
            data={
                'serviceFeatures': '',
            })

        assert res.status_code == 302
        self.data_api_client.update_service.assert_called_once_with(
            '1', dict(), 'email@email.com')

        assert self.get_flash_messages() == ((
            "success",
            "You’ve edited your service. The changes are now live on the Digital Marketplace.",
        ),)

    def test_edit_non_existent_service_returns_404(self, s3):
        self.data_api_client.get_service.return_value = None
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        res = self.client.get('/suppliers/frameworks/g-cloud-6/services/1/edit/description')

        assert res.status_code == 404
        assert self.data_api_client.update_service.called is False

    def test_edit_non_existent_section_returns_404(self, s3):
        self.data_api_client.get_service.return_value = self.empty_service
        res = self.client.get(
            '/suppliers/frameworks/g-cloud-6/services/1/edit/invalid-section'
        )
        assert res.status_code == 404
        assert self.data_api_client.update_service.called is False

    def test_update_with_answer_required_error(self, s3):
        self.data_api_client.get_service.return_value = self.empty_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        self.data_api_client.update_service.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {
                'serviceSummary': 'answer_required',
                'serviceName': 'answer_required',
            },
        )
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-6/services/1/edit/description',
            data={})

        assert res.status_code == 400
        document = html.fromstring(res.get_data(as_text=True))

        form = document.xpath(
            "//form[@method='post'][.//button[normalize-space(string())=$t]]",
            t="Save and return",
        )[0]
        assert form.xpath(
            ".//input[@name=$n]",
            n="serviceName",
        )
        assert form.xpath(
            ".//textarea[@name=$n]",
            n="serviceSummary",
        )
        assert document.xpath(
            "//a[@href=$u][normalize-space(string())]",
            u="/suppliers/frameworks/g-cloud-6/services/1",
            t="Return to service summary",
        )

        assert len(document.xpath('//span[@class="validation-message"]')) == 2
        assert len(document.xpath(
            '//span[@class="validation-message"][normalize-space(string())=$t]',
            t="You need to answer this question.",
        )) == 2
        self.assert_no_flashes()

        breadcrumbs = document.xpath("//div[@class='govuk-breadcrumbs']/ol/li")

        assert tuple(li.xpath("normalize-space(string())") for li in breadcrumbs) == (
            "Digital Marketplace",
            "Your account",
            "Your G-Cloud 6 services",
            "Service name 123",
            "Description",
        )
        assert tuple(li.xpath(".//a/@href") for li in breadcrumbs) == (
            ['/'],
            ['/suppliers'],
            ['/suppliers/frameworks/g-cloud-6/services'],
            ['/suppliers/frameworks/g-cloud-6/services/1'],
            [],
        )

    def test_update_with_under_50_words_error(self, s3):
        self.data_api_client.get_service.return_value = self.empty_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        self.data_api_client.update_service.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'serviceSummary': 'under_50_words'})
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-6/services/1/edit/description',
            data={})

        assert res.status_code == 400
        document = html.fromstring(res.get_data(as_text=True))
        assert document.xpath(
            '//span[@class="validation-message"]/text()'
        )[0].strip() == "Your description must be no more than 50 words."
        self.assert_no_flashes()

    def test_update_non_existent_service_returns_404(self, s3):
        self.data_api_client.get_service.return_value = None
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        res = self.client.post('/suppliers/frameworks/g-cloud-6/services/1/edit/description')

        assert res.status_code == 404
        self.assert_no_flashes()
        assert self.data_api_client.update_service.called is False

    def test_update_non_existent_section_returns_404(self, s3):
        self.data_api_client.get_service.return_value = self.empty_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-6/services/1/edit/invalid_section'
        )
        assert res.status_code == 404
        self.assert_no_flashes()
        assert self.data_api_client.update_service.called is False

    def test_incorrect_framework_fails(self, s3):
        self.data_api_client.get_service.return_value = self.empty_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/services/1/edit/description',
            data={
                'serviceName': 'The service',
                'serviceSummary': 'This is the service',
            })

        assert res.status_code == 404
        self.assert_no_flashes()
        assert self.data_api_client.update_service.called is False


@mock.patch('dmutils.s3.S3')
class TestSupplierEditUpdateServiceSectionG9(BaseApplicationTest):

    def _get_framework_response(self, **kwargs):
        return {
            "frameworks": {
                "framework": "g-cloud",
                "name": "G-Cloud 9",
                "slug": "g-cloud-9",
                "status": "live",
                **kwargs
            }
        }

    base_service = {
        'services': {
            'serviceName': 'Service name 321',
            'status': 'published',
            'id': '321',
            'frameworkSlug': 'g-cloud-9',
            'frameworkName': 'G-Cloud 9',
            'supplierId': 1234,
            'supplierName': 'We supply almost any',
            'lot': 'cloud-software',
            'lotSlug': 'cloud-software',
            'lotName': "Cloudy Softwares",
            'serviceFeatures': ["eight", "nine"],
            'serviceBenefits': ["ten"],
        }
    }

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()
        self.login()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_edit_page(self, s3):
        self.data_api_client.get_service.return_value = self.base_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        res = self.client.get('/suppliers/frameworks/g-cloud-9/services/321/edit/service-features-and-benefits')

        assert res.status_code == 200
        document = html.fromstring(res.get_data(as_text=True))
        assert tuple(
            (elem.attrib["name"], elem.attrib["value"],)
            for elem in document.xpath("//form//input[@name='serviceFeatures' or @name='serviceBenefits']")
            if elem.attrib.get("value")
        ) == (
            ("serviceFeatures", "eight",),
            ("serviceFeatures", "nine",),
            ("serviceBenefits", "ten",),
        )

    def test_questions_for_this_service_section_can_be_changed(self, s3):
        self.data_api_client.get_service.return_value = self.base_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-9/services/321/edit/service-features-and-benefits',
            data={
                'serviceFeatures': ["one", "two"],
                'serviceBenefits': ["three", "four"],
            })

        assert res.status_code == 302
        assert res.location == "http://localhost/suppliers/frameworks/g-cloud-9/services/321"
        self.data_api_client.update_service.assert_called_once_with(
            '321',
            {
                'serviceFeatures': ["one", "two"],
                'serviceBenefits': ["three", "four"],
            },
            'email@email.com',
        )

        assert self.get_flash_messages() == ((
            "success",
            "You’ve edited your service. The changes are now live on the Digital Marketplace.",
        ),
        )

    @pytest.mark.parametrize("file_extension,valid_bytes", (
        ('pdf', valid_pdf_bytes),
        ('odt', valid_odt_bytes)
    ))
    def test_file_upload(self, s3, file_extension, valid_bytes):
        self.data_api_client.get_service.return_value = self.base_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        with freeze_time('2017-11-12 13:14:15'):
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-9/services/321/edit/documents',
                data={
                    'serviceDefinitionDocumentURL': (BytesIO(valid_bytes
                                                             ), f"document.{file_extension}"),
                }
            )

        assert res.status_code == 302
        slug = '321-service-definition-document-2017-11-12-1314'
        self.data_api_client.update_service.assert_called_once_with(
            '321',
            {
                'serviceDefinitionDocumentURL':
                f"http://asset-host/g-cloud-9/documents/1234/{slug}.{file_extension}"
            },
            'email@email.com',
        )

        s3.return_value.save.assert_called_once_with(
            f"g-cloud-9/documents/1234/321-service-definition-document-2017-11-12-1314.{file_extension}",
            mock.ANY, acl='public-read'
        )

    def test_S3_should_not_be_called_if_there_are_no_files(self, s3):
        self.data_api_client.get_service.return_value = self.base_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-9/services/321/edit/service-features-and-benefits',
            data={
                'serviceFeatures': ["one", "two"],
                'serviceBenefits': ["three", "four"],
            })

        assert res.status_code == 302
        assert s3.return_value.save.called is False

    def test_file_upload_filters_empty_and_unknown_files(self, s3):
        self.data_api_client.get_service.return_value = self.base_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-9/services/321/edit/documents',
            data={
                'serviceDefinitionDocumentURL': (BytesIO(b''), 'document.pdf'),
                'unknownDocumentURL': (BytesIO(b'doc'), 'document.pdf'),
            })

        assert res.status_code == 302
        assert s3.return_value.save.called is False
        self.data_api_client.update_service.assert_called_once_with('321', {}, 'email@email.com')

    def test_upload_question_can_not_be_set_by_form_data(self, s3):
        self.data_api_client.get_service.return_value = self.base_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-9/services/321/edit/documents',
            data={
                'serviceDefinitionDocumentURL': 'http://example.com/document.pdf',
            })

        assert res.status_code == 302
        self.data_api_client.update_service.assert_called_once_with('321', {}, 'email@email.com')

    def test_has_session_timeout_warning(self, s3):
        self.data_api_client.get_service.return_value = self.base_service
        self.data_api_client.get_framework.return_value = self._get_framework_response()

        with freeze_time("2019-04-03 13:14:14"):
            self.login()  # need to login after freezing time

            doc = html.fromstring(
                self.client.get(
                    "/suppliers/frameworks/g-cloud-9/services/321/edit/documents",
                ).data
            )

            assert "3:14pm BST" in doc.xpath("string(.//div[@id='session-timeout-warning'])")


class TestCreateDraftService(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):
    def setup_method(self, method):
        super().setup_method(method)
        self._answer_required = 'Answer is required'
        self._validation_error = 'There is a problem'
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()
        self.login()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_get_create_draft_service_page_if_open(self):
        self.data_api_client.get_framework.return_value = self.framework(status='open')

        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/create')
        assert res.status_code == 200
        assert 'Service name' in res.get_data(as_text=True)

        assert self._validation_error not in res.get_data(as_text=True)

    def test_can_not_get_create_draft_service_page_if_not_open(self):
        self.data_api_client.get_framework.return_value = self.framework(status='other')

        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/create')
        assert res.status_code == 404

    def _test_post_create_draft_service(self, data, if_error_expected):
        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.create_new_draft_service.return_value = {"services": empty_g7_draft_service()}

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/create',
            data=data
        )

        if if_error_expected:
            assert res.status_code == 400
            assert self._validation_error in res.get_data(as_text=True)
        else:
            assert res.status_code == 302

    def test_post_create_draft_service_succeeds(self):
        self._test_post_create_draft_service({'serviceName': "Service Name"}, if_error_expected=False)

    def test_post_create_draft_service_with_api_error_fails(self):
        self.data_api_client.create_new_draft_service.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'serviceName': 'answer_required'}
        )

        self._test_post_create_draft_service({}, if_error_expected=True)

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/create',
            data={}
        )

        assert res.status_code == 400
        assert self._validation_error in res.get_data(as_text=True)

    def test_cannot_post_if_not_open(self):
        self.data_api_client.get_framework.return_value = self.framework(status='other')
        res = self.client.post(
            '/suppliers/submission/g-cloud-7/submissions/scs/create'
        )
        assert res.status_code == 404


class TestCopyDraft(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):

    def setup_method(self, method):
        super().setup_method(method)
        self.login()

        self.g7_draft = empty_g7_draft_service()
        self.g9_draft = empty_g9_draft_service()

        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()
        self.data_api_client.get_framework.return_value = self.framework(status='open')

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_copy_draft_with_editable_sections(self):
        # G7 drafts use editable=True, edit_questions=False on every section, which should emit a URL without
        # a question-slug parameter.
        self.data_api_client.get_draft_service.return_value = {'services': self.g7_draft}

        copy_of_draft = empty_g7_draft_service()
        copy_of_draft.update({'id': 2})
        self.data_api_client.copy_draft_service.return_value = {'services': copy_of_draft}

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/copy')
        assert res.status_code == 302
        assert '/suppliers/frameworks/g-cloud-7/submissions/scs/2/edit/service-name?force_continue_button=1' \
            in res.location

    def test_copy_draft_with_edit_questions_sections(self):
        # G9 drafts use editable=False, edit_questions=True on every section, which means a different URL
        # needs to be emitted by the draft service copy.
        self.data_api_client.get_framework.return_value = self.framework(slug='g-cloud-9', status='open')
        self.data_api_client.get_draft_service.return_value = {'services': self.g9_draft}

        copy_of_draft = empty_g9_draft_service()
        copy_of_draft.update({'id': 2})
        self.data_api_client.copy_draft_service.return_value = {'services': copy_of_draft}

        res = self.client.post('/suppliers/frameworks/g-cloud-9/submissions/cloud-hosting/1/copy')
        assert res.status_code == 302
        assert '/suppliers/frameworks/g-cloud-9/submissions/cloud-hosting/2/edit/service-name/' \
               'service-name?force_continue_button=1' in res.location

    def test_copy_draft_checks_supplier_id(self):
        self.g7_draft['supplierId'] = 2
        self.data_api_client.get_draft_service.return_value = {'services': self.g7_draft}

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/copy')
        assert res.status_code == 404

    def test_cannot_copy_draft_if_not_open(self):
        self.data_api_client.get_framework.return_value = self.framework(status='other')

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/copy')
        assert res.status_code == 404

    def test_cannot_copy_draft_if_no_supplier_framework(self):
        self.data_api_client.get_supplier_framework_info.return_value = {'frameworkInterest': {}}

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/copy')
        assert res.status_code == 404


class TestCompleteDraft(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):

    def setup_method(self, method):
        super().setup_method(method)
        self.login()

        self.draft = empty_g7_draft_service()
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()
        self.data_api_client.get_framework.return_value = self.framework(status='open')

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_complete_draft(self):
        self.data_api_client.get_draft_service.return_value = {'services': self.draft}
        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/complete')
        assert res.status_code == 302
        assert 'lot=scs' in res.location
        assert '/suppliers/frameworks/g-cloud-7/submissions' in res.location

    def test_complete_draft_checks_supplier_id(self):
        self.draft['supplierId'] = 2
        self.data_api_client.get_draft_service.return_value = {'services': self.draft}

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/complete')
        assert res.status_code == 404

    def test_cannot_complete_draft_if_not_open(self):
        self.data_api_client.get_framework.return_value = self.framework(status='other')

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/complete')
        assert res.status_code == 404

    def test_cannot_complete_draft_if_no_supplier_framework(self):
        self.data_api_client.get_supplier_framework_info.return_value = {'frameworkInterest': {}}

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/complete')
        assert res.status_code == 404


@mock.patch('dmutils.s3.S3')
class TestEditDraftService(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):

    def setup_method(self, method):
        super().setup_method(method)
        self.login()

        self.empty_draft = {'services': empty_g7_draft_service()}
        self.empty_g9_draft = {'services': empty_g9_draft_service()}

        self.multiquestion_draft = {
            'services': {
                'id': 1,
                'supplierId': 1234,
                'supplierName': 'supplierName',
                'lot': 'digital-specialists',
                'lotSlug': 'digital-specialists',
                'frameworkSlug': 'digital-outcomes-and-specialists',
                'lotName': 'Digital specialists',
                'agileCoachLocations': ['Wales'],
                'agileCoachPriceMax': '200',
                'agileCoachPriceMin': '100',
                'developerLocations': ['Wales'],
                'developerPriceMax': '250',
                'developerPriceMin': '150',
                'status': 'not-submitted',
            },
            'auditEvents': {
                'createdAt': '2015-06-29T15:26:07.650368Z',
                'userName': 'Supplier User',
            },
            'validationErrors': {}
        }
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()
        self.data_api_client.get_framework.return_value = self.framework(status='open')

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_questions_for_this_draft_section_can_be_changed(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description',
            data={
                'serviceSummary': 'This is the service',
            })

        assert res.status_code == 302
        self.data_api_client.update_draft_service.assert_called_once_with(
            '1',
            {'serviceSummary': 'This is the service'},
            'email@email.com',
            page_questions=['serviceSummary']
        )

    def test_update_without_changes_is_not_sent_to_the_api(self, s3):
        draft = self.empty_draft['services'].copy()
        draft.update({'serviceSummary': "summary"})
        self.data_api_client.get_draft_service.return_value = {'services': draft}

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description',
            data={
                'serviceSummary': "summary",
            })

        assert res.status_code == 302
        assert self.data_api_client.update_draft_service.called is False

    def test_S3_should_not_be_called_if_there_are_no_files(self, s3):
        uploader = mock.Mock()
        s3.return_value = uploader
        self.data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description',
            data={
                'serviceSummary': 'This is the service',
            })

        assert res.status_code == 302
        assert uploader.save.called is False

    def test_editing_readonly_section_is_not_allowed(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft

        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-attributes')
        assert res.status_code == 404

        self.data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-attributes',
            data={
                'lotSlug': 'scs',
            })
        assert res.status_code == 404

    def test_draft_section_cannot_be_edited_if_not_open(self, s3):
        self.data_api_client.get_framework.return_value = self.framework(status='other')
        self.data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description',
            data={
                'serviceSummary': 'This is the service',
            })
        assert res.status_code == 404

    def test_draft_section_cannot_be_edited_if_no_supplier_framework(self, s3):
        self.data_api_client.get_supplier_framework_info.return_value = {'frameworkInterest': {}}
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description',
            data={
                'serviceSummary': 'This is the service',
            })
        assert res.status_code == 404

    def test_only_questions_for_this_draft_section_can_be_changed(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description',
            data={
                'serviceFeatures': '',
            })

        assert res.status_code == 302
        self.data_api_client.update_draft_service.assert_called_once_with(
            '1', {}, 'email@email.com',
            page_questions=['serviceSummary']
        )

    def test_display_file_upload_with_existing_file(self, s3):
        draft = copy.deepcopy(self.empty_draft)
        draft['services']['serviceDefinitionDocumentURL'] = 'http://localhost/fooo-2012-12-12-1212.pdf'
        self.data_api_client.get_draft_service.return_value = draft
        response = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-definition'
        )
        document = html.fromstring(response.get_data(as_text=True))

        assert response.status_code == 200
        assert len(document.cssselect('p.file-upload-existing-value')) == 1

    def test_display_file_upload_with_no_existing_file(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft
        response = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-definition'
        )
        document = html.fromstring(response.get_data(as_text=True))

        assert response.status_code == 200
        assert len(document.cssselect('p.file-upload-existing-value')) == 0

    def test_file_upload(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft
        with freeze_time('2015-01-02 03:04:05'):
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-definition',
                data={
                    'serviceDefinitionDocumentURL': (BytesIO(valid_pdf_bytes), 'document.pdf'),
                }
            )

        assert res.status_code == 302
        self.data_api_client.update_draft_service.assert_called_once_with(
            '1', {
                'serviceDefinitionDocumentURL': 'http://localhost/suppliers/assets/g-cloud-7/submissions/1234/1-service-definition-document-2015-01-02-0304.pdf'  # noqa
            }, 'email@email.com',
            page_questions=['serviceDefinitionDocumentURL']
        )

        s3.return_value.save.assert_called_once_with(
            'g-cloud-7/submissions/1234/1-service-definition-document-2015-01-02-0304.pdf',
            mock.ANY, acl='bucket-owner-full-control'
        )

    def test_file_upload_filters_empty_and_unknown_files(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-definition',
            data={
                'serviceDefinitionDocumentURL': (BytesIO(b''), 'document.pdf'),
                'unknownDocumentURL': (BytesIO(b'doc'), 'document.pdf'),
                'pricingDocumentURL': (BytesIO(b'doc'), 'document.pdf'),
            })

        assert res.status_code == 302
        self.data_api_client.update_draft_service.assert_called_once_with(
            '1', {}, 'email@email.com',
            page_questions=['serviceDefinitionDocumentURL']
        )

        assert s3.return_value.save.called is False

    def test_upload_question_not_accepted_as_form_data(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-definition',
            data={
                'serviceDefinitionDocumentURL': 'http://example.com/document.pdf',
            })

        assert res.status_code == 302
        self.data_api_client.update_draft_service.assert_called_once_with(
            '1', {}, 'email@email.com',
            page_questions=['serviceDefinitionDocumentURL']
        )

    def test_pricing_fields_are_added_correctly(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/pricing',
            data={
                'priceMin': "10.10",
                'priceMax': "11.10",
                'priceUnit': "Person",
                'priceInterval': "Second",
            })

        assert res.status_code == 302
        self.data_api_client.update_draft_service.assert_called_once_with(
            '1',
            {
                'priceMin': "10.10", 'priceMax': "11.10", "priceUnit": "Person", 'priceInterval': 'Second',
            },
            'email@email.com',
            page_questions=[
                'priceInterval', 'priceMax', 'priceMin', 'priceUnit',
                'vatIncluded', 'educationPricing',
            ])

    def test_edit_non_existent_draft_service_returns_404(self, s3):
        self.data_api_client.get_draft_service.side_effect = HTTPError(mock.Mock(status_code=404))
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description')

        assert res.status_code == 404

    def test_edit_non_existent_draft_section_returns_404(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/invalid_section'
        )
        assert res.status_code == 404

    def test_update_in_section_with_more_questions_redirects_to_next_question_in_section(self, s3):
        self.data_api_client.get_framework.return_value = self.framework(slug='g-cloud-9', status='open')
        self.data_api_client.get_draft_service.return_value = self.empty_g9_draft
        self.data_api_client.update_draft_service.return_value = None

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-9/submissions/cloud-hosting/1/edit/pricing/price',
            data={
                'continue_to_next_section': 'Save and continue'
            })

        assert res.status_code == 302
        assert res.headers['Location'] == \
            'http://localhost/suppliers/frameworks/g-cloud-9/submissions/cloud-hosting/1/edit/pricing/education-pricing'

    def test_update_at_end_of_section_redirects_to_summary(self, s3):
        self.data_api_client.get_framework.return_value = self.framework(slug='g-cloud-9', status='open')
        self.data_api_client.get_draft_service.return_value = self.empty_g9_draft
        self.data_api_client.update_draft_service.return_value = None

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-9/submissions/cloud-hosting/1/edit/pricing/free-or-trial-versions',
            data={
                'continue_to_next_section': 'Save and continue'
            })

        assert res.status_code == 302
        assert res.headers['Location'] == \
            'http://localhost/suppliers/frameworks/g-cloud-9/submissions/cloud-hosting/1#pricing'

    def test_update_refuses_to_redirect_to_next_editable_section_if_dos(self, s3):
        self.data_api_client.get_framework.return_value = self.framework(
            status='open', slug='digital-outcomes-and-specialists'
        )
        self.data_api_client.get_draft_service.return_value = self.multiquestion_draft
        self.data_api_client.update_draft_service.return_value = None

        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/digital-specialists/1/'
            'edit/individual-specialist-roles/product-manager',
            data={
                'continue_to_next_section': 'Save and continue'
            })

        assert res.status_code == 302
        assert 'http://localhost/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' \
            'digital-specialists/1#individual-specialist-roles' == res.headers['Location']

    def test_page_doesnt_offer_continue_to_next_editable_section_if_dos(self, s3):
        self.data_api_client.get_framework.return_value = self.framework(
            status='open', slug='digital-outcomes-and-specialists'
        )
        self.data_api_client.get_draft_service.return_value = self.multiquestion_draft

        res = self.client.get(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/digital-specialists/1/'
            'edit/individual-specialist-roles/product-manager',
        )

        assert res.status_code == 200
        document = html.fromstring(res.get_data(as_text=True))
        assert len(document.xpath("//input[@type='submit'][@name='save_and_continue']")) == 0

    def test_update_redirects_to_edit_submission_if_no_next_editable_section(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft
        self.data_api_client.update_draft_service.return_value = None

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/sfia-rate-card',
            data={})

        assert res.status_code == 302
        assert 'http://localhost/suppliers/frameworks/g-cloud-7/submissions/scs/1#sfia-rate-card' == \
            res.headers['Location']

    def test_update_doesnt_offer_continue_to_next_editable_section_if_no_next_editable_section(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft

        res = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/sfia-rate-card',
        )

        assert res.status_code == 200
        document = html.fromstring(res.get_data(as_text=True))
        assert len(document.xpath("//input[@type='submit'][@name='save_and_continue']")) == 0

    def test_update_offers_continue_to_next_editable_section_if_force_continue_button(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft

        res = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description?force_continue_button=1',
        )

        assert res.status_code == 200
        document = html.fromstring(res.get_data(as_text=True))
        assert len(document.xpath(
            "//form[@method='post']//button[@name=$n][normalize-space(string())=$t]",
            n="save_and_continue",
            t="Save and continue",
        )) == 1

    def test_update_redirects_to_edit_submission_if_save_and_return_grey_button_clicked(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft
        self.data_api_client.update_draft_service.return_value = None

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description',
            data={})

        assert res.status_code == 302
        assert 'http://localhost/suppliers/frameworks/g-cloud-7/submissions/scs/1#service-description' == \
            res.headers['Location']

    def test_update_with_answer_required_error(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft
        self.data_api_client.update_draft_service.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'serviceSummary': 'answer_required'})
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description',
            data={})

        assert res.status_code == 200
        document = html.fromstring(res.get_data(as_text=True))
        assert "You need to answer this question." == document.xpath(
            '//span[@class="validation-message"]/text()'
        )[0].strip()

    def test_update_with_under_50_words_error(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft
        self.data_api_client.update_draft_service.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'serviceSummary': 'under_50_words'})
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description',
            data={})

        assert res.status_code == 200
        document = html.fromstring(res.get_data(as_text=True))
        assert "Your description must be no more than 50 words." == document.xpath(
            '//span[@class="validation-message"]/text()'
        )[0].strip()

    @pytest.mark.parametrize("field,error,expected_message", (
        ('priceMin', 'answer_required', 'Minimum price requires an answer.',),
        ('priceUnit', 'answer_required',
            "Pricing unit requires an answer. If none of the provided units apply, please choose ‘Unit’."),
        ('priceMin', 'not_money_format', 'Minimum price must be a number, without units, eg 99.95',),
        ('priceMax', 'not_money_format', 'Maximum price must be a number, without units, eg 99.95',),
        ('priceMax', 'max_less_than_min', 'Minimum price must be less than maximum price.',),
    ))
    def test_update_with_pricing_errors(self, s3, field, error, expected_message):
        self.data_api_client.get_framework.return_value = self.framework(slug='g-cloud-9', status='open')
        self.data_api_client.get_draft_service.return_value = self.empty_g9_draft
        self.data_api_client.update_draft_service.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {field: error})
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-9/submissions/cloud-hosting/1/edit/pricing/price',
            data={})

        assert res.status_code == 200
        document = html.fromstring(res.get_data(as_text=True))
        assert document.xpath(
            "normalize-space(string(//*[@class='govuk-error-message']))") == f"Error: {expected_message}"
        assert document.xpath("normalize-space(string(//*[@class='govuk-error-summary']//a))") == expected_message

    def test_update_non_existent_draft_service_returns_404(self, s3):
        self.data_api_client.get_draft_service.side_effect = HTTPError(mock.Mock(status_code=404))
        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description')

        assert res.status_code == 404

    def test_update_non_existent_draft_section_returns_404(self, s3):
        self.data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/invalid-section'
        )
        assert res.status_code == 404

    def test_update_multiquestion(self, s3):
        self.data_api_client.get_framework.return_value = self.framework(
            status='open', slug='digital-outcomes-and-specialists'
        )
        draft = self.empty_draft.copy()
        draft['services']['lot'] = 'digital-specialists'
        draft['services']['lotSlug'] = 'digital-specialists'
        draft['services']['frameworkSlug'] = 'digital-outcomes-and-specialists'
        self.data_api_client.get_draft_service.return_value = draft

        res = self.client.get(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' +
            'digital-specialists/1/edit/individual-specialist-roles/agile-coach'
        )

        assert res.status_code == 200

        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' +
            'digital-specialists/1/edit/individual-specialist-roles/agile-coach',
            data={
                'agileCoachLocations': ['Scotland'],
            })

        assert res.status_code == 302
        self.data_api_client.update_draft_service.assert_called_once_with(
            '1',
            {'agileCoachLocations': ['Scotland']},
            'email@email.com',
            page_questions=['agileCoachLocations', 'agileCoachPriceMax', 'agileCoachPriceMin']
        )

    def test_service_submission_page_remove_subsection_button_gets_confirmation_page(self, s3):
        self.data_api_client.get_framework.return_value = self.framework(
            status='open', slug='digital-outcomes-and-specialists'
        )

        self.data_api_client.get_draft_service.return_value = self.multiquestion_draft

        res = self.client.get(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' +
            'digital-specialists/1/remove/individual-specialist-roles/agile-coach'
        )

        self.data_api_client.update_draft_service.return_value.assert_not_called()
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))

        page_title = doc.xpath('//h1')[0].text_content()
        assert page_title == "Are you sure you want to remove agile coach?"

    def test_remove_subsection(self, s3):
        self.data_api_client.get_framework.return_value = self.framework(
            status='open', slug='digital-outcomes-and-specialists'
        )

        self.data_api_client.get_draft_service.return_value = self.multiquestion_draft

        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' +
            'digital-specialists/1/remove/individual-specialist-roles/agile-coach',
            data={"remove_confirmed": "true"}
        )

        assert res.status_code == 302
        assert res.location.endswith(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/digital-specialists/1'
        )

        self.data_api_client.update_draft_service.assert_called_once_with(
            '1',
            {
                'agileCoachLocations': None,
                'agileCoachPriceMax': None,
                'agileCoachPriceMin': None,
            },
            'email@email.com'
        )

    def test_can_not_remove_last_subsection_from_submitted_draft(self, s3):
        self.data_api_client.get_framework.return_value = self.framework(
            status='open', slug='digital-outcomes-and-specialists'
        )

        draft_service = copy.deepcopy(self.multiquestion_draft)
        draft_service['services'].pop('developerLocations', None)
        draft_service['services'].pop('developerPriceMax', None)
        draft_service['services'].pop('developerPriceMin', None)
        draft_service['services']['status'] = 'submitted'

        self.data_api_client.get_draft_service.return_value = draft_service

        res = self.client.get(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' +
            'digital-specialists/1/remove/individual-specialist-roles/agile-coach'
        )

        assert res.status_code == 302
        assert res.location.endswith(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/digital-specialists/1'
        )

        res2 = self.client.get(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/digital-specialists/1'
        )
        assert res2.status_code == 200
        assert "You must offer one of the individual specialist roles to be eligible." in res2.get_data(as_text=True)

        assert self.data_api_client.update_draft_service.called is False

    def test_can_not_remove_other_suppliers_subsection(self, s3):
        draft_service = copy.deepcopy(self.multiquestion_draft)
        draft_service['services']['supplierId'] = 12345
        self.data_api_client.get_draft_service.return_value = draft_service
        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' +
            'digital-specialists/1/remove/individual-specialist-roles/agile-coach?confirm=True')

        assert res.status_code == 404
        assert self.data_api_client.update_draft_service.called is False

    def test_fails_if_api_get_fails(self, s3):
        self.data_api_client.get_draft_service.side_effect = HTTPError(mock.Mock(status_code=504))
        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' +
            'digital-specialists/1/remove/individual-specialist-roles/agile-coach',
            data={'remove_confirmed': 'true'})
        assert res.status_code == 504

    def test_fails_if_api_update_fails(self, s3):
        self.data_api_client.get_draft_service.return_value = self.multiquestion_draft
        self.data_api_client.update_draft_service.side_effect = HTTPError(mock.Mock(status_code=504))
        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' +
            'digital-specialists/1/remove/individual-specialist-roles/agile-coach',
            data={'remove_confirmed': 'true'})
        assert res.status_code == 504

    @pytest.mark.parametrize(
        "page",
        (
            "1/edit/about-your-service/service-categories",
            "create",
        )
    )
    def test_has_session_timeout_warning(self, s3, page):
        self.data_api_client.get_framework.return_value = self.framework(slug='g-cloud-9', status='open')
        self.data_api_client.get_draft_service.return_value = self.empty_g9_draft

        with freeze_time("2019-04-03 13:14:14"):
            self.login()  # need to login after freezing time

            doc = html.fromstring(
                self.client.get(
                    f"/suppliers/frameworks/g-cloud-9/submissions/cloud-hosting/{page}"
                ).data
            )

            assert "3:14pm BST" in doc.xpath("string(.//div[@id='session-timeout-warning'])")


class TestShowDraftService(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):

    draft_service_data = empty_g7_draft_service()
    draft_service_data.update({
        'priceMin': '12.50',
        'priceMax': '15',
        'priceUnit': 'Person',
        'priceInterval': 'Second',
    })

    draft_service = {
        'services': draft_service_data,
        'auditEvents': {
            'createdAt': '2015-06-29T15:26:07.650368Z',
            'userName': 'Supplier User',
        },
        'validationErrors': {}
    }

    complete_service = copy.deepcopy(draft_service)
    complete_service['services']['status'] = 'submitted'
    complete_service['services']['id'] = 2

    def setup_method(self, method):
        super().setup_method(method)
        self.login()
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_service_price_is_correctly_formatted(self):
        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_draft_service.return_value = self.draft_service
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1')
        document = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 200
        service_price_row_xpath = '//tr[contains(.//span/text(), "Service price")]'
        service_price_xpath = service_price_row_xpath + '/td[@class="summary-item-field"]/span/text()'
        assert document.xpath(service_price_xpath)[0].strip() == "£12.50 to £15 a person a second"

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_unanswered_questions_count(self, count_unanswered):
        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_draft_service.return_value = self.draft_service
        count_unanswered.return_value = 1, 2
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1')

        assert '3 unanswered questions' in res.get_data(as_text=True), \
            "'3 unanswered questions' not found in html"

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_move_to_complete_button(self, count_unanswered):
        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_draft_service.return_value = self.draft_service
        count_unanswered.return_value = 0, 1
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1')

        assert '1 optional question unanswered' in res.get_data(as_text=True)

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath("//form//button[normalize-space(string())=$t]", t="Mark as complete")

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_no_move_to_complete_button_if_not_open(self, count_unanswered):
        self.data_api_client.get_framework.return_value = self.framework(status='other')
        self.data_api_client.get_draft_service.return_value = self.draft_service
        count_unanswered.return_value = 0, 1
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1')

        doc = html.fromstring(res.get_data(as_text=True))
        assert not doc.xpath("//form//button[normalize-space(string())=$t]", t="Mark as complete")

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_no_move_to_complete_button_if_validation_errors(self, count_unanswered):
        draft_service = copy.deepcopy(self.draft_service)
        draft_service['validationErrors'] = {'_errors': "Everything's busted"}

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_draft_service.return_value = draft_service
        count_unanswered.return_value = 0, 1

        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1')

        doc = html.fromstring(res.get_data(as_text=True))
        assert not doc.xpath("//form//button[normalize-space(string())=$t]", t="Mark as complete")

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_shows_g7_message_if_pending_and_service_is_in_draft(self, count_unanswered):
        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.get_draft_service.return_value = self.draft_service
        count_unanswered.return_value = 3, 1
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1')

        doc = html.fromstring(res.get_data(as_text=True))
        message = doc.xpath('//section[@class="dm-banner"]')

        assert len(message) > 0
        assert "This service was not submitted" in message[0].xpath(
            'h2[contains(@class, "dm-banner__title")]/text()'
        )[0]
        assert "It wasn't marked as complete at the deadline." in message[0].xpath(
            'div[@class="dm-banner__body"]/text()'
        )[0]

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_shows_g7_message_if_pending_and_service_is_complete(self, count_unanswered):
        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.get_draft_service.return_value = self.complete_service
        count_unanswered.return_value = 0, 1
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/2')

        doc = html.fromstring(res.get_data(as_text=True))
        message = doc.xpath('//section[@class="dm-banner"]')

        assert len(message) > 0
        assert "This service was submitted" in message[0].xpath('h2[contains(@class, "dm-banner__title")]/text()')[0]
        assert "If your application is successful, it will be available on the Digital Marketplace when " \
            "G-Cloud 7 goes live." in message[0].xpath('div[@class="dm-banner__body"]/text()')[0]


class TestDeleteDraftService(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):

    draft_service_data = empty_g7_draft_service()
    draft_service_data.update({
        'serviceName': 'My rubbish draft',
        'serviceSummary': 'This is the worst service ever',
    })
    draft_to_delete = {
        'services': draft_service_data,
        'auditEvents': {
            'createdAt': "2015-06-29T15:26:07.650368Z",
            'userName': "Supplier User",
        },
        'validationErrors': {}
    }

    def setup_method(self, method):
        super().setup_method(method)
        self.login()
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()
        self.data_api_client.get_framework.return_value = self.framework(status='open')

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_cannot_delete_if_not_open(self):
        self.data_api_client.get_framework.return_value = self.framework(status='other')
        self.data_api_client.get_draft_service.return_value = self.draft_to_delete

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/delete',
            data={})
        assert res.status_code == 404

    def test_cannot_delete_draft_if_no_supplier_framework(self):
        self.data_api_client.get_supplier_framework_info.return_value = {'frameworkInterest': {}}

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/delete')
        assert res.status_code == 404

    def test_service_submission_page_delete_button_gets_confirmation_page(self):
        self.data_api_client.get_draft_service.return_value = self.draft_to_delete
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1/delete')

        self.data_api_client.delete_draft_service.assert_not_called()
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))

        page_title = doc.xpath('//h1')[0].text_content()
        assert page_title == "Are you sure you want to remove this service?"

    def test_confirm_delete_button_deletes_and_redirects_to_dashboard(self):
        self.data_api_client.get_draft_service.return_value = self.draft_to_delete
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/delete',
            data={'delete_confirmed': 'true'})

        self.data_api_client.delete_draft_service.assert_called_with('1', 'email@email.com')
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-7/submissions/scs'

    def test_cannot_delete_other_suppliers_draft(self):
        other_draft = copy.deepcopy(self.draft_to_delete)
        other_draft['services']['supplierId'] = 12345
        self.data_api_client.get_draft_service.return_value = other_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/delete',
            data={'delete_confirmed': 'true'})

        assert res.status_code == 404


@mock.patch('dmutils.s3.S3')
class TestSubmissionDocuments(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):
    def setup_method(self, method):
        super().setup_method(method)
        self.login()
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_document_url(self, s3):
        s3.return_value.get_signed_url.return_value = 'http://example.com/document.pdf'

        res = self.client.get(
            '/suppliers/assets/g-cloud-7/submissions/1234/document.pdf'
        )

        assert res.status_code == 302
        assert res.headers['Location'] == 'http://asset-host/document.pdf'

    def test_missing_document_url(self, s3):
        s3.return_value.get_signed_url.return_value = None

        res = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/documents/1234/document.pdf'
        )

        assert res.status_code == 404

    def test_document_url_not_matching_user_supplier(self, s3):
        res = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/documents/999/document.pdf'
        )

        assert res.status_code == 404


class TestParseDocumentUploadTime(BaseApplicationTest):
    def test_parses_document_upload_time(self):
        file_url = "http://www.address.com/g-cloud-9/submissions/92352/70419-terms-and-conditions-2018-01-23-1103.pdf"
        assert parse_document_upload_time(file_url) == datetime(2018, 1, 23, 11, 3)


@mock.patch('app.main.views.services.content_loader.get_metadata')
class TestGetListPreviousServices(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):
    def setup_method(self, method):
        super().setup_method(method)
        self.login()
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_lists_correct_services_for_previous_framework_and_lot(self, get_metadata):
        self.data_api_client.get_framework.side_effect = lambda slug: self.framework(slug=slug)
        self.data_api_client.find_services.return_value = {
            'services': [
                ServiceStub(
                    service_id="12",
                    service_name="One",
                    lot="cloud-hosting",
                    copied_to_following_framework=False,
                ).response(),
                ServiceStub(
                    service_id="34",
                    service_name="Two",
                    lot="cloud-hosting",
                    copied_to_following_framework=False,
                ).response(),
                ServiceStub(
                    service_id="56",
                    service_name="Three",
                    lot="cloud-hosting",
                    copied_to_following_framework=False,
                ).response(),
            ],
        }
        get_metadata.return_value = 'g-cloud-9'

        res = self.client.get('/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting/previous-services')
        assert res.status_code == 200

        assert self.data_api_client.find_services.call_args_list == [
            mock.call(
                supplier_id=1234,
                framework='g-cloud-9',
                lot='cloud-hosting',
                status='published',
            )
        ]

        doc = html.fromstring(res.get_data(as_text=True))

        assert doc.xpath("//h1[normalize-space()='Previous cloud hosting services']")
        assert doc.xpath("//table/caption[normalize-space()='Your services from G-Cloud 9']")

        add_all_link = doc.xpath("//a[@data-name='add-all-services'][normalize-space()='Add all your services']")[0]
        assert add_all_link.attrib['href'] == \
            '/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting/copy-all-previous-framework-services'

        service_links = doc.xpath("//td//a")
        assert [service.text for service in service_links] == ['One', 'Two', 'Three']

        add_service_forms = doc.xpath(
            "//table//form[@method='post']"
        )
        assert len(add_service_forms) == 3
        assert all(
            re.match(
                r"/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting/copy-previous-framework-service/\d+",
                form.attrib["action"],
            ) for form in add_service_forms
        )

    @pytest.mark.parametrize(
        ('lot_slug', 'lot_name', 'question_advice'),
        (
            (
                'digital-outcomes',
                'digital outcomes',
                'You still have to review your service and answer any new questions.'
            ),
            (
                'digital-specialists',
                'digital specialists',
                'You’ll need to review your previous answers. Roles won’t be copied if they have new questions.'
            ),
            (
                'user-research-participants',
                'user research participants',
                'You still have to review your service and answer any new questions.'
            ),
        )
    )
    def test_shows_boolean_question_for_single_service_lots(self, get_metadata, lot_slug, lot_name, question_advice):
        self.data_api_client.get_framework.side_effect = [
            self.framework(slug='digital-outcomes-and-specialists-3'),
            self.framework(slug='digital-outcomes-and-specialists-3'),
            self.framework(slug='digital-outcomes-and-specialists-2'),
        ]
        get_metadata.return_value = 'digital-outcomes-and-specialists-2'
        self.data_api_client.find_services.return_value = {
            'services': [{'serviceName': 'Service one', 'copiedToFollowingFramework': False}],
        }

        res = self.client.get(
            f'/suppliers/frameworks/digital-outcomes-and-specialists-3/submissions/{lot_slug}/previous-services'
        )
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 200
        assert doc.xpath(f"//h1[normalize-space()='Do you want to reuse your previous {lot_name} service?']")
        assert doc.xpath(f"//span[@class='govuk-hint'][normalize-space()='{question_advice}']")
        assert [
            re.sub(r"\W", "", label.text) for label in doc.xpath("//div[@class='govuk-radios']//label")
        ] == ["Yes", "No"]
        assert doc.xpath("//form//button[normalize-space(string())=$t]", t="Save and continue")

    def test_returns_404_if_framework_not_found(self, get_metadata):

        res = self.client.get('/suppliers/frameworks/x-cloud-z/submissions/cloud-hosting/previous-services')
        assert res.status_code == 404

    def test_returns_404_if_lot_not_found(self, get_metadata):
        self.data_api_client.get_framework.return_value = self.framework(slug='g-cloud-10')

        res = self.client.get('/suppliers/frameworks/g-cloud-10/submissions/not-a-lot/previous-services')
        assert res.status_code == 404

    def test_returns_500_if_source_framework_not_found(self, get_metadata):
        self.data_api_client.get_framework.side_effect = [
            self.framework(slug='g-cloud-10'),
            self.framework(slug='g-cloud-10'),
            HTTPError(mock.Mock(status_code=404)),
        ]

        res = self.client.get('/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting/previous-services')
        assert res.status_code == 500

    @pytest.mark.parametrize(
        'services',
        (
            [
                {'serviceName': 'Service one', 'copiedToFollowingFramework': True},
                {'serviceName': 'Service two', 'copiedToFollowingFramework': True},
                {'serviceName': 'Service three', 'copiedToFollowingFramework': True},
            ],
            [],
        )
    )
    def test_redirects_to_draft_service_page_if_no_services_to_copy(self, get_metadata, services):
        self.data_api_client.get_framework.side_effect = [
            self.framework(slug='g-cloud-10'),
            self.framework(slug='g-cloud-10'),
            self.framework(slug='g-cloud-9'),
        ]
        self.data_api_client.find_services.return_value = {
            'services': services,
        }

        res = self.client.get('/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting/previous-services')

        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting'

    def test_services_page_copy_all_button_gets_confirmation_page(self, get_metadata):
        self.data_api_client.get_framework.side_effect = [
            self.framework(slug='g-cloud-12'),
            self.framework(slug='g-cloud-12'),
            self.framework(slug='g-cloud-11'),
        ]
        self.data_api_client.find_services.return_value = {
            'services': [
                {'serviceName': 'Service one', 'copiedToFollowingFramework': False},
                {'serviceName': 'Service two', 'copiedToFollowingFramework': False},
                {'serviceName': 'Service three', 'copiedToFollowingFramework': False},
            ],
        }
        get_metadata.return_value = 'g-cloud-11'

        res = self.client.get(
            '/suppliers/frameworks/g-cloud-12/submissions/cloud-hosting/copy-all-previous-framework-services'
        )
        assert res.status_code == 200

        self.data_api_client.update_draft_service.return_value.assert_not_called()
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))

        page_title = doc.xpath('//h1')[0].text_content()
        assert page_title == "Are you sure you want to copy all your G-Cloud 11 cloud hosting services to G-Cloud 12?"

    @pytest.mark.parametrize('declaration_status,banner_present', (('complete', False), ('incomplete', True)))
    def test_shows_service_warning_in_correct_conditions(
        self, get_metadata, declaration_status, banner_present
    ):
        self.data_api_client.get_framework.side_effect = [
            self.framework(slug='g-cloud-10'),
            self.framework(slug='g-cloud-10'),
            self.framework(slug='g-cloud-9'),
        ]
        self.data_api_client.find_services.return_value = {
            'services': [{'serviceName': 'Service one', 'copiedToFollowingFramework': False}]
        }
        get_metadata.return_value = 'g-cloud-9'
        self.data_api_client.get_supplier_declaration.return_value = {'declaration': {'status': declaration_status}}
        self.data_api_client.get_supplier.return_value = SupplierStub().single_result_response()

        res = self.client.get(
            '/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting/previous-services'
        )
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))

        banner = doc.xpath(
            "//section[@class='dm-banner']/h2[normalize-space()='Your application is not complete']"
        )
        declaration = doc.xpath(
            "//section[@class='dm-banner']//a[normalize-space()='make your supplier declaration']"
        )

        if banner_present:
            assert banner
            assert declaration
        else:
            assert not banner
            assert not declaration


class TestPostListPreviousService(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):
    def setup_method(self, method):
        super().setup_method(method)
        self.login()

        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()
        self.data_api_client.get_framework.return_value = self.framework(slug='digital-outcomes-and-specialists-3')
        self.data_api_client.find_services.return_value = {
            "services": [{'copiedToFollowingFramework': False, 'id': '0001'}]
        }
        self.data_api_client.find_draft_services_iter.return_value = []

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    @mock.patch('app.main.views.services.content_loader')
    @mock.patch('app.main.views.services.copy_service_from_previous_framework')
    def test_copies_service_for_one_service_lot_if_copy_true(
        self, copy_service_from_previous_framework, content_loader
    ):
        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists-3/'
            'submissions/digital-outcomes/previous-services',
            data={'copy_service': 'yes'},
        )

        assert res.status_code == 302
        assert (
            '/suppliers/frameworks/digital-outcomes-and-specialists-3/submissions/digital-outcomes'
        ) in res.location
        assert copy_service_from_previous_framework.call_args_list == [
            mock.call(
                self.data_api_client,
                content_loader,
                'digital-outcomes-and-specialists-3',
                'digital-outcomes',
                '0001'
            )
        ]
        self.assert_flashes(
            "You've added your service to Digital Outcomes and Specialists 3 as a draft. "
            "You'll need to review it before it can be completed.",
            expected_category='success',
        )

    @mock.patch('app.main.views.services.copy_service_from_previous_framework')
    def test_creates_new_draft_for_one_service_lot_if_copy_false(self, copy_service_from_previous_framework):
        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists-3/submissions/digital-outcomes/previous-services',
            data={'copy_service': 'no'},
        )

        assert res.status_code == 302
        assert '/suppliers/frameworks/digital-outcomes-and-specialists-3/submissions/digital-outcomes' in res.location
        assert copy_service_from_previous_framework.call_args_list == []
        assert self.data_api_client.create_new_draft_service.call_args_list == [
            mock.call('digital-outcomes-and-specialists-3', 'digital-outcomes', 1234, {}, 'email@email.com')
        ]

    def test_400s_if_lot_does_not_have_one_service_limit(self):
        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists-3/'
            'submissions/user-research-studios/previous-services',
            data={'copy_service': 'no'},
        )

        assert res.status_code == 400

    @pytest.mark.parametrize(
        ('lot_name', 'lot_slug'),
        (
            ('Digital outcomes', 'digital-outcomes'),
            ('Digital Specialists', 'digital-specialists'),
            ('User research participants', 'user-research-participants'),
        ),
    )
    def test_400s_if_draft_already_exists(self, lot_name, lot_slug):
        self.data_api_client.get_framework.return_value = FrameworkStub(
            slug='digital-outcomes-and-specialists-3',
            lots=[LotStub(name=lot_name, slug=lot_slug, one_service_limit=True).response()]
        ).single_result_response()
        self.data_api_client.find_draft_services_iter.return_value = [
            {'status': 'not-submitted', 'lotSlug': lot_slug},
        ]

        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists-3/'
            f'submissions/{lot_slug}/previous-services',
            data={'copy_service': True},
        )
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 400
        assert doc.xpath(
            "//div//p[normalize-space(string())=$t]",
            t=f"You already have a draft {lot_name.lower()} service.",
        )

    @mock.patch('app.main.views.services.copy_service_from_previous_framework')
    def test_form_validation_rejects_a_blank_answer(self, copy_service_from_previous_framework):
        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists-3/'
            'submissions/digital-outcomes/previous-services',
            data={},
        )

        assert res.status_code == 400
        assert copy_service_from_previous_framework.call_args_list == []


class CopyingPreviousServicesSetup(BaseApplicationTest):
    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client')
        self.data_api_client = self.data_api_client_patch.start()

        self.get_metadata_patch = mock.patch('app.main.views.services.content_loader.get_metadata')
        self.get_metadata = self.get_metadata_patch.start()

        self.data_api_client.get_framework.return_value = self.framework(slug='g-cloud-10')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
        self.data_api_client.get_service.return_value = {
            'services': {
                'lotSlug': 'cloud-hosting',
                'frameworkSlug': 'g-cloud-9',
                'copiedToFollowingFramework': False,
                'id': '2000000000',
                'supplierId': 1234,
            },
        }
        self.get_metadata.side_effect = [
            None,
            ('serviceName', 'serviceSummary'),
            'g-cloud-9'
        ]

        self.login()

    def teardown_method(self, method):
        super().teardown_method(method)
        self.data_api_client_patch.stop()
        self.get_metadata_patch.stop()


class TestCopyPreviousService(CopyingPreviousServicesSetup, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):
    def test_copies_existing_service_to_new_framework_with_questions_to_copy(self):
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting/copy-previous-framework-service/2000000000'
        )

        assert res.status_code == 302
        assert res.location == (
            "http://localhost/suppliers/frameworks/"
            "g-cloud-10/submissions/cloud-hosting/previous-services"
        )

        assert self.data_api_client.copy_draft_service_from_existing_service.call_args_list == [
            mock.call(
                '2000000000',
                'email@email.com',
                {
                    'targetFramework': 'g-cloud-10',
                    'status': 'not-submitted',
                    'questionsToCopy': ('serviceName', 'serviceSummary')
                }
            )
        ]

    @pytest.mark.parametrize('questions_to_copy', (None, ['serviceName', 'serviceSummary']))
    def test_copies_existing_service_to_new_framework_with_questions_to_exclude(self, questions_to_copy):
        self.get_metadata.side_effect = [
            ('termsAndConditionsDocumentURL', 'serviceDefinitionDocumentURL'),
            questions_to_copy,
            'g-cloud-9'
        ]

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting/copy-previous-framework-service/2000000000'
        )

        assert res.status_code == 302
        assert res.location == (
            "http://localhost/suppliers/frameworks/"
            "g-cloud-10/submissions/cloud-hosting/previous-services"
        )

        assert self.data_api_client.copy_draft_service_from_existing_service.call_args_list == [
            mock.call(
                '2000000000',
                'email@email.com',
                {
                    'targetFramework': 'g-cloud-10',
                    'status': 'not-submitted',
                    'questionsToExclude': ('termsAndConditionsDocumentURL', 'serviceDefinitionDocumentURL')
                }
            )
        ]

    def test_returns_404_if_framework_not_found(self):
        self.data_api_client.get_framework.side_effect = HTTPError(mock.Mock(status_code=404))

        res = self.client.post(
            '/suppliers/frameworks/x-cloud-z/submissions/cloud-hosting/copy-previous-framework-service/2000000000'
        )

        assert res.status_code == 404

    def test_returns_404_if_lot_not_found(self):
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-10/submissions/sausages/copy-previous-framework-service/2000000000'
        )

        assert res.status_code == 404

    def test_returns_404_if_no_supplier_framework_interest(self):
        self.data_api_client.get_supplier_framework_info.return_value = {'frameworkInterest': {}}

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting/copy-previous-framework-service/2000000000'
        )

        assert res.status_code == 404

    def test_returns_404_if_service_does_not_match_lot(self):
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-10/submissions/cloud-support/copy-previous-framework-service/2000000000'
        )

        assert res.status_code == 404

    def test_returns_404_if_service_does_not_match_source_framework(self):
        self.get_metadata.side_effect = [
            None,
            ['serviceName', 'serviceSummary'],
            'a-different-framework'
        ]

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting/copy-previous-framework-service/2000000000'
        )

        assert res.status_code == 404

    def test_returns_404_if_service_has_already_been_copied(self):
        self.data_api_client.get_service.return_value = {
            'services': {
                'lotSlug': 'cloud-hosting',
                'frameworkSlug': 'g-cloud-9',
                'copiedToFollowingFramework': True,
                'id': '2000000000',
                'supplierId': 1234,
            },
        }
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting/copy-previous-framework-service/2000000000'
        )

        assert res.status_code == 404

    @mock.patch('app.main.views.services.flash')
    def test_the_correct_flash_message_should_be_set(self, flash):
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting/copy-previous-framework-service/2000000000'
        )

        assert res.status_code == 302

        from app.main.views.services import MULTI_SERVICE_LOT_SINGLE_SERVICE_ADDED_MESSAGE as message
        assert flash.call_args_list == [
            mock.call(
                message.format(framework_name='G-Cloud 10'), "success"
            )
        ]


class TestCopyAllPreviousServices(CopyingPreviousServicesSetup,
                                  MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):
    def test_copies_all_services_with_questions_to_copy(self):
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting/copy-all-previous-framework-services'
        )

        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting'

        assert self.data_api_client.copy_published_from_framework.call_args_list == [
            mock.call(
                'g-cloud-10',
                'cloud-hosting',
                'email@email.com',
                data={
                    "sourceFrameworkSlug": 'g-cloud-9',
                    "supplierId": 1234,
                    "questionsToCopy": ('serviceName', 'serviceSummary'),
                }
            )
        ]

    @pytest.mark.parametrize('questions_to_copy', (None, ['serviceName', 'serviceSummary']))
    def test_copies_all_services_with_questions_to_exclude(self, questions_to_copy):
        self.get_metadata.side_effect = [
            ['termsAndConditionsDocumentURL', 'serviceDefinitionDocumentURL'],
            questions_to_copy,
            'g-cloud-9'
        ]

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting/copy-all-previous-framework-services'
        )

        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting'

        assert self.data_api_client.copy_published_from_framework.call_args_list == [
            mock.call(
                'g-cloud-10',
                'cloud-hosting',
                'email@email.com',
                data={
                    "sourceFrameworkSlug": 'g-cloud-9',
                    "supplierId": 1234,
                    "questionsToExclude": ['termsAndConditionsDocumentURL', 'serviceDefinitionDocumentURL']
                }
            )
        ]

    def test_returns_404_if_framework_not_found(self):
        self.data_api_client.get_framework.side_effect = HTTPError(mock.Mock(status_code=404))

        res = self.client.post(
            '/suppliers/frameworks/not-a-framework/submissions/cloud-hosting/copy-all-previous-framework-services'
        )

        assert res.status_code == 404

    def test_returns_404_if_lot_not_found(self):
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-10/submissions/sausage/copy-all-previous-framework-services'
        )

        assert res.status_code == 404

    @mock.patch('app.main.views.services.flash')
    def test_the_correct_flash_message_should_be_set(self, flash):
        self.data_api_client.copy_published_from_framework.return_value = {
            'services': {
                'draftsCreatedCount': 3
            }
        }
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting/copy-all-previous-framework-services'
        )

        assert res.status_code == 302

        from app.main.views.services import ALL_SERVICES_ADDED_MESSAGE as message
        assert flash.call_args_list == [
            mock.call(
                message.format(draft_count='3', framework_name='G-Cloud 10'), "success"
            )
        ]
