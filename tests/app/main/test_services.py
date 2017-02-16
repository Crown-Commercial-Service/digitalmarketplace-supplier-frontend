# -*- coding: utf-8 -*-
try:
    from StringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO

from dmapiclient import HTTPError
import copy
import mock
import pytest
from lxml import html
from freezegun import freeze_time

from tests.app.helpers import BaseApplicationTest, BaseApplicationTestLoggedIn, empty_g7_draft_service, empty_g9_draft_service


# this is mostly a workaround for pytest not being able to do parametrization with unittest-derived class methods
# otherwise it doesn't get us much over function parametrization...
@pytest.fixture(params=(
    # a tuple of framework_slug, framework_name, framework_editable_services
    ("g-cloud-6", "G-Cloud 6", True,),
    ("g-cloud-7", "G-Cloud 7", True,),
    ("digital-outcomes-and-specialists", "Digital outcomes and specialists", False,),
))
def supplier_service_editing_fw_params(request):
    return request.param


# and these fixtures really are just a workaround to not being able to use plain function parametrization in unittest-
# derived classes and should be replaced with that as soon as we're able to do so. hence the hence the oddly specific
# long names
@pytest.fixture(params=(
    # a tuple of service status, service_belongs_to_user, expect_api_call_if_data, expected_status_code
    ("published", True, True, 302,),
    ("enabled", True, False, 400,),
    ("disabled", True, False, 400,),
    ("published", False, False, 404,),\
))
def supplier_remove_service__service_status__expected_results(request):
    return request.param


@pytest.fixture(params=(False, True,))
def supplier_remove_service__post_data(request):
    return request.param


class TestListServices(BaseApplicationTest):
    @mock.patch('app.main.views.services.data_api_client')
    def test_shows_no_services_message(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.find_services.return_value = {
                "services": []
                }

            res = self.client.get('/suppliers/services')
            assert res.status_code == 200
            data_api_client.find_services.assert_called_once_with(
                supplier_id=1234)
            assert "You don&#39;t have any services on the Digital Marketplace" in res.get_data(as_text=True)

    @mock.patch('app.main.views.services.data_api_client')
    def test_shows_services_list(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.find_services.return_value = {
                'services': [{
                    'serviceName': 'Service name 123',
                    'status': 'published',
                    'id': '123',
                    'lotSlug': 'saas',
                    'lotName': 'Software as a Service',
                    'frameworkName': 'G-Cloud 1',
                    'frameworkSlug': 'g-cloud-1'
                }]
            }

            res = self.client.get('/suppliers/services')
            assert res.status_code == 200
            data_api_client.find_services.assert_called_once_with(
                supplier_id=1234)
            assert "Service name 123" in res.get_data(as_text=True)
            assert "Software as a Service" in res.get_data(as_text=True)
            assert "G-Cloud 1" in res.get_data(as_text=True)

    @mock.patch('app.data_api_client')
    def test_should_not_be_able_to_see_page_if_made_inactive(self, services_data_api_client):
        with self.app.test_client():
            self.login()

            services_data_api_client.get_user.return_value = self.user(
                123,
                "email@email.com",
                1234,
                'Supplier Name',
                'User name',
                active=False
            )

            res = self.client.get('/suppliers/services')
            assert res.status_code == 302
            assert res.location == 'http://localhost/login?next=%2Fsuppliers%2Fservices'

    @mock.patch('app.main.views.services.data_api_client')
    def test_shows_service_edit_link_with_id(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.find_services.return_value = {
                'services': [{
                    'serviceName': 'Service name 123',
                    'status': 'published',
                    'id': '123',
                    'frameworkSlug': 'g-cloud-1'
                }]
            }

            res = self.client.get('/suppliers/services')
            assert res.status_code == 200
            data_api_client.find_services.assert_called_once_with(
                supplier_id=1234)
            assert "/suppliers/services/123" in res.get_data(as_text=True)

    @mock.patch('app.main.views.services.data_api_client')
    def test_services_without_service_name_show_lot_instead(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.find_services.return_value = {
                'services': [{
                    'status': 'published',
                    'id': '123',
                    'lotName': 'Special Lot Name',
                    'frameworkSlug': 'digital-outcomes-and-specialists'
                }]
            }

            res = self.client.get('/suppliers/services')
            assert res.status_code == 200
            data_api_client.find_services.assert_called_once_with(supplier_id=1234)

            assert "Special Lot Name" in res.get_data(as_text=True)

    @mock.patch('app.main.views.services.data_api_client')
    def test_shows_dos_service_name_without_edit_link(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.find_services.return_value = {
                'services': [{
                    'serviceName': 'Service name 123',
                    'lotName': 'Special Lot Name',
                    'status': 'published',
                    'id': '123',
                    'frameworkSlug': 'digital-outcomes-and-specialists-2',
                    'frameworkFramework': 'digital-outcomes-and-specialists',
                }]
            }

            res = self.client.get('/suppliers/services')
            assert res.status_code == 200
            data_api_client.find_services.assert_called_once_with(supplier_id=1234)

            assert "Service name 123" in res.get_data(as_text=True)
            assert "/suppliers/services/123" not in res.get_data(as_text=True)


class TestListServicesLogin(BaseApplicationTest):
    @mock.patch('app.main.views.services.data_api_client')
    def test_should_show_services_list_if_logged_in(self, data_api_client):
        with self.app.test_client():
            self.login()
            data_api_client.find_services.return_value = {'services': [{
                'serviceName': 'Service name 123',
                'status': 'published',
                'id': '123',
                'frameworkSlug': 'g-cloud-1'
            }]}

            res = self.client.get('/suppliers/services')

            assert res.status_code == 200

            assert self.strip_all_whitespace('<h1>Current services</h1>') in \
                self.strip_all_whitespace(res.get_data(as_text=True))

    def test_should_redirect_to_login_if_not_logged_in(self):
        res = self.client.get("/suppliers/services")
        assert res.status_code == 302
        assert res.location == 'http://localhost/login?next=%2Fsuppliers%2Fservices'


class _BaseTestSupplierEditRemoveService(BaseApplicationTest):
    def _setup_service(
            self,
            data_api_client,
            framework_slug,
            framework_name,
            service_status="published",
            service_belongs_to_user=True,
            ):

        data_api_client.get_service.return_value = {
            'services': {
                'serviceName': 'Service name 123',
                'status': service_status,
                'id': '123',
                'frameworkName': framework_name,
                'frameworkSlug': framework_slug,
                'supplierId': 1234 if service_belongs_to_user else 1235,
            }
        }
        if service_status == 'published':
            data_api_client.update_service_status.return_value = data_api_client.get_service.return_value
        else:
            data_api_client.get_service.return_value['serviceMadeUnavailableAuditEvent'] = {
                "createdAt": "2015-03-23T09:30:00.00001Z"
            }

        data_api_client.get_framework.return_value = {
            'frameworks': {
                'name': framework_name,
                'slug': framework_slug,
                'status': 'live',
            }
        }


@mock.patch('app.main.views.services.data_api_client')
class TestSupplierEditService(_BaseTestSupplierEditRemoveService):
    def test_should_view_public_service_with_correct_message(
            self, data_api_client, supplier_service_editing_fw_params
    ):
        framework_slug, framework_name, framework_editable_services = supplier_service_editing_fw_params
        self.login()
        self._setup_service(data_api_client, framework_slug, framework_name, service_status='published')

        res = self.client.get('/suppliers/services/123')
        if not framework_editable_services:
            assert res.status_code == 404
            return

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

    def test_should_view_public_service_with_update_message(
            self, data_api_client, supplier_service_editing_fw_params
    ):
        framework_slug, framework_name, framework_editable_services = supplier_service_editing_fw_params
        self.login()
        self._setup_service(data_api_client, framework_slug, framework_name, service_status='published')

        # this is meant to emulate a "service updated" message
        with self.client.session_transaction() as session:
            session['_flashes'] = [
                ('message', 'Foo Bar 123 321'),
            ]

        res = self.client.get('/suppliers/services/123')
        if not framework_editable_services:
            assert res.status_code == 404
            return

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

    def test_should_view_private_service_with_correct_message(
            self, data_api_client, supplier_service_editing_fw_params
    ):
        framework_slug, framework_name, framework_editable_services = supplier_service_editing_fw_params
        self.login()
        self._setup_service(data_api_client, framework_slug, framework_name, service_status='enabled')

        res = self.client.get('/suppliers/services/123')
        if not framework_editable_services:
            assert res.status_code == 404
            return

        assert res.status_code == 200
        assert 'Service name 123' in res.get_data(as_text=True)

        self.assert_in_strip_whitespace(
            '<h2>This service was removed on Monday 23 March 2015</h2>',
            res.get_data(as_text=True)
        )

        self.assert_not_in_strip_whitespace(
            '<h2>Remove this service</h2>',
            res.get_data(as_text=True)
        )

    def test_should_view_disabled_service_with_removed_message(
            self, data_api_client, supplier_service_editing_fw_params
    ):
        framework_slug, framework_name, framework_editable_services = supplier_service_editing_fw_params
        self.login()
        self._setup_service(data_api_client, framework_slug, framework_name, service_status='disabled')

        res = self.client.get('/suppliers/services/123')
        if not framework_editable_services:
            assert res.status_code == 404
            return

        assert res.status_code == 200
        self.assert_in_strip_whitespace(
            'Service name 123',
            res.get_data(as_text=True)
        )

        self.assert_in_strip_whitespace(
            '<h2>This service was removed on Monday 23 March 2015</h2>',
            res.get_data(as_text=True)
        )

    def test_should_not_view_other_suppliers_services(
            self, data_api_client, supplier_service_editing_fw_params
    ):
        framework_slug, framework_name, framework_editable_services = supplier_service_editing_fw_params
        self.login()
        self._setup_service(
            data_api_client, framework_slug, framework_name, service_status='published', service_belongs_to_user=False)

        res = self.client.get('/suppliers/services/123')

        assert res.status_code == 404

    def test_should_redirect_to_login_if_not_logged_in(self, data_api_client):
        res = self.client.get("/suppliers/services/123")
        assert res.status_code == 302
        assert res.location == 'http://localhost/login?next=%2Fsuppliers%2Fservices%2F123'


@mock.patch('app.main.views.services.data_api_client')
class TestSupplierRemoveServiceEditInterplay(_BaseTestSupplierEditRemoveService):
    """
        These tests actually test the *interplay* between the remove view and its subsequent (redirected)
        views through using `follow_redirects` to perform both a POST to the remove view and a subsequent GET to the
        following view. Chief thing we're asserting is the flash message throw/catch.
    """
    def test_should_view_confirmation_message_if_first_remove_service_button_clicked(
            self, data_api_client, supplier_service_editing_fw_params
    ):
        framework_slug, framework_name, framework_editable_services = supplier_service_editing_fw_params
        self.login()
        self._setup_service(data_api_client, framework_slug, framework_name, service_status='published')

        # NOTE two http requests performed here
        res = self.client.post('/suppliers/services/123/remove', follow_redirects=True)
        if not framework_editable_services:
            assert res.status_code == 404
            assert data_api_client.update_service_status.called is False
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

    def test_should_view_correct_notification_message_if_service_removed(
            self, data_api_client, supplier_service_editing_fw_params
    ):
        framework_slug, framework_name, framework_editable_services = supplier_service_editing_fw_params
        self.login()
        self._setup_service(data_api_client, framework_slug, framework_name, service_status='published')

        # NOTE two http requests performed here
        res = self.client.post(
            '/suppliers/services/123/remove',
            data={'remove_confirmed': True},
            follow_redirects=True)
        if not framework_editable_services:
            assert res.status_code == 404
            assert data_api_client.update_service_status.called is False
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


@mock.patch('app.main.views.services.data_api_client')
class TestSupplierRemoveService(_BaseTestSupplierEditRemoveService):
    def test_remove_service(
            self,
            data_api_client,
            supplier_service_editing_fw_params,
            supplier_remove_service__service_status__expected_results,
            supplier_remove_service__post_data,
            ):
        framework_slug, framework_name, framework_editable_services = supplier_service_editing_fw_params
        service_status, service_belongs_to_user, expect_api_call_if_data, expected_status_code = \
            supplier_remove_service__service_status__expected_results
        post_data = supplier_remove_service__post_data

        self.login()
        self._setup_service(
            data_api_client,
            framework_slug,
            framework_name,
            service_status=service_status,
            service_belongs_to_user=service_belongs_to_user,
        )

        response = self.client.post(
            '/suppliers/services/123/remove',
            data={'remove_confirmed': True} if post_data else {},
        )
        if not framework_editable_services:
            assert response.status_code == 404
            assert data_api_client.update_service_status.called is False
            return

        assert data_api_client.update_service_status.called is (expect_api_call_if_data and post_data)
        assert response.status_code == expected_status_code


@mock.patch('app.main.views.services.data_api_client')
class TestSupplierEditUpdateServiceSection(BaseApplicationTestLoggedIn):

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

    def test_return_to_service_summary_link_present(self, data_api_client):
        data_api_client.get_service.return_value = self.empty_service
        res = self.client.get('/suppliers/services/1/edit/description')
        assert res.status_code == 200
        assert self.strip_all_whitespace('<a href="/suppliers/services/1">Return to service summary</a>') in \
            self.strip_all_whitespace(res.get_data(as_text=True))

    def test_questions_for_this_service_section_can_be_changed(self, data_api_client):
        data_api_client.get_service.return_value = self.empty_service
        res = self.client.post(
            '/suppliers/services/1/edit/description',
            data={
                'serviceName': 'The service',
                'serviceSummary': 'This is the service',
            })

        assert res.status_code == 302
        data_api_client.update_service.assert_called_once_with(
            '1', {'serviceName': 'The service', 'serviceSummary': 'This is the service'},
            'email@email.com')

        self.assert_flashes(
            {"updated_service_name": "The service"},
            "service_updated",
        )

    def test_editing_readonly_section_is_not_allowed(self, data_api_client):
        data_api_client.get_service.return_value = self.empty_service

        res = self.client.get('/suppliers/services/1/edit/service-attributes')
        assert res.status_code == 404

        data_api_client.get_draft_service.return_value = self.empty_service
        res = self.client.post(
            '/suppliers/services/1/edit/service-attributes',
            data={
                'lotSlug': 'scs',
            })

        assert res.status_code == 404
        self.assert_no_flashes()

    def test_only_questions_for_this_service_section_can_be_changed(self, data_api_client):
        data_api_client.get_service.return_value = self.empty_service
        res = self.client.post(
            '/suppliers/services/1/edit/description',
            data={
                'serviceFeatures': '',
            })

        assert res.status_code == 302
        data_api_client.update_service.assert_called_once_with(
            '1', dict(), 'email@email.com')

        self.assert_flashes(
            {"updated_service_name": "Service name 123"},
            "service_updated",
        )

    def test_edit_non_existent_service_returns_404(self, data_api_client):
        data_api_client.get_service.return_value = None
        res = self.client.get('/suppliers/services/1/edit/description')

        assert res.status_code == 404

    def test_edit_non_existent_section_returns_404(self, data_api_client):
        data_api_client.get_service.return_value = self.empty_service
        res = self.client.get(
            '/suppliers/services/1/edit/invalid-section'
        )
        assert res.status_code == 404

    def test_update_with_answer_required_error(self, data_api_client):
        data_api_client.get_service.return_value = self.empty_service
        data_api_client.update_service.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'serviceSummary': 'answer_required'})
        res = self.client.post(
            '/suppliers/services/1/edit/description',
            data={})

        assert res.status_code == 200
        document = html.fromstring(res.get_data(as_text=True))
        assert document.xpath(
            '//span[@class="validation-message"]/text()'
        )[0].strip() == "You need to answer this question."
        self.assert_no_flashes()

    def test_update_with_under_50_words_error(self, data_api_client):
        data_api_client.get_service.return_value = self.empty_service
        data_api_client.update_service.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'serviceSummary': 'under_50_words'})
        res = self.client.post(
            '/suppliers/services/1/edit/description',
            data={})

        assert res.status_code == 200
        document = html.fromstring(res.get_data(as_text=True))
        assert document.xpath(
            '//span[@class="validation-message"]/text()'
        )[0].strip() == "Your description must be no more than 50 words."
        self.assert_no_flashes()

    def test_update_non_existent_service_returns_404(self, data_api_client):
        data_api_client.get_service.return_value = None
        res = self.client.post('/suppliers/services/1/edit/description')

        assert res.status_code == 404
        self.assert_no_flashes()

    def test_update_non_existent_section_returns_404(self, data_api_client):
        data_api_client.get_service.return_value = self.empty_service
        res = self.client.post(
            '/suppliers/services/1/edit/invalid_section'
        )
        assert res.status_code == 404
        self.assert_no_flashes()


@mock.patch('app.main.views.services.data_api_client', autospec=True)
class TestCreateDraftService(BaseApplicationTestLoggedIn):
    def setup_method(self, method):
        super(TestCreateDraftService, self).setup_method(method)
        self._answer_required = 'Answer is required'
        self._validation_error = 'There was a problem with your answer to:'

    def test_get_create_draft_service_page_if_open(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='open')

        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/create')
        assert res.status_code == 200
        assert u'Service name' in res.get_data(as_text=True)

        assert self._validation_error not in res.get_data(as_text=True)

    def test_can_not_get_create_draft_service_page_if_not_open(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='other')

        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/create')
        assert res.status_code == 404

    def _test_post_create_draft_service(self, data, if_error_expected, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.create_new_draft_service.return_value = {"services": empty_g7_draft_service()}

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/create',
            data=data
        )

        if if_error_expected:
            assert res.status_code == 400
            assert self._validation_error in res.get_data(as_text=True)
        else:
            assert res.status_code == 302

    def test_post_create_draft_service_succeeds(self, data_api_client):
        self._test_post_create_draft_service(
            {'serviceName': "Service Name"},
            if_error_expected=False, data_api_client=data_api_client
        )

    def test_post_create_draft_service_with_api_error_fails(self, data_api_client):
        data_api_client.create_new_draft_service.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'serviceName': 'answer_required'}
        )

        self._test_post_create_draft_service(
            {},
            if_error_expected=True, data_api_client=data_api_client
        )

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/create',
            data={}
        )

        assert res.status_code == 400
        assert self._validation_error in res.get_data(as_text=True)

    def test_cannot_post_if_not_open(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='other')
        res = self.client.post(
            '/suppliers/submission/g-cloud-7/submissions/scs/create'
        )
        assert res.status_code == 404


@mock.patch('app.main.views.services.data_api_client')
class TestCopyDraft(BaseApplicationTestLoggedIn):

    def setup_method(self, method):
        super(TestCopyDraft, self).setup_method(method)
        self.draft = empty_g7_draft_service()

    def test_copy_draft(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = {'services': self.draft}

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/copy')
        assert res.status_code == 302

    def test_copy_draft_checks_supplier_id(self, data_api_client):
        self.draft['supplierId'] = 2
        data_api_client.get_draft_service.return_value = {'services': self.draft}

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/copy')
        assert res.status_code == 404

    def test_cannot_copy_draft_if_not_open(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='other')

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/copy')
        assert res.status_code == 404


@mock.patch('app.main.views.services.data_api_client')
class TestCompleteDraft(BaseApplicationTestLoggedIn):

    def setup_method(self, method):
        super(TestCompleteDraft, self).setup_method(method)
        self.draft = empty_g7_draft_service()

    def test_complete_draft(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = {'services': self.draft}
        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/complete')
        assert res.status_code == 302
        assert 'lot=scs' in res.location
        assert '/suppliers/frameworks/g-cloud-7/submissions' in res.location

    def test_complete_draft_checks_supplier_id(self, data_api_client):
        self.draft['supplierId'] = 2
        data_api_client.get_draft_service.return_value = {'services': self.draft}

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/complete')
        assert res.status_code == 404

    def test_cannot_complete_draft_if_not_open(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='other')

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/complete')
        assert res.status_code == 404


@mock.patch('dmutils.s3.S3')
@mock.patch('app.main.views.services.data_api_client')
class TestEditDraftService(BaseApplicationTestLoggedIn):

    def setup_method(self, method):
        super(TestEditDraftService, self).setup_method(method)

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

    def test_questions_for_this_draft_section_can_be_changed(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description',
            data={
                'serviceSummary': 'This is the service',
            })

        assert res.status_code == 302
        data_api_client.update_draft_service.assert_called_once_with(
            '1',
            {'serviceSummary': 'This is the service'},
            'email@email.com',
            page_questions=['serviceSummary']
        )

    def test_update_without_changes_is_not_sent_to_the_api(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        draft = self.empty_draft['services'].copy()
        draft.update({'serviceSummary': u"summary"})
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = {'services': draft}

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description',
            data={
                'serviceSummary': u"summary",
            })

        assert res.status_code == 302
        assert data_api_client.update_draft_service.called is False

    def test_S3_should_not_be_called_if_there_are_no_files(self, data_api_client, s3):
        uploader = mock.Mock()
        s3.return_value = uploader
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description',
            data={
                'serviceSummary': 'This is the service',
            })

        assert res.status_code == 302
        assert uploader.save.called is False

    def test_editing_readonly_section_is_not_allowed(self, data_api_client, s3):
        data_api_client.get_draft_service.return_value = self.empty_draft

        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-attributes')
        assert res.status_code == 404

        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-attributes',
            data={
                'lotSlug': 'scs',
            })
        assert res.status_code == 404

    def test_draft_section_cannot_be_edited_if_not_open(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='other')
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description',
            data={
                'serviceSummary': 'This is the service',
            })
        assert res.status_code == 404

    def test_only_questions_for_this_draft_section_can_be_changed(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description',
            data={
                'serviceFeatures': '',
            })

        assert res.status_code == 302
        data_api_client.update_draft_service.assert_called_once_with(
            '1', {}, 'email@email.com',
            page_questions=['serviceSummary']
        )

    def test_display_file_upload_with_existing_file(self, data_api_client, s3):
        draft = copy.deepcopy(self.empty_draft)
        draft['services']['serviceDefinitionDocumentURL'] = 'http://localhost/fooo-2012-12-12-1212.pdf'
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = draft
        response = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-definition'
        )
        document = html.fromstring(response.get_data(as_text=True))

        assert response.status_code == 200
        assert len(document.cssselect('p.file-upload-existing-value')) == 1

    def test_display_file_upload_with_no_existing_file(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        response = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-definition'
        )
        document = html.fromstring(response.get_data(as_text=True))

        assert response.status_code == 200
        assert len(document.cssselect('p.file-upload-existing-value')) == 0

    def test_file_upload(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        with freeze_time('2015-01-02 03:04:05'):
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-definition',
                data={
                    'serviceDefinitionDocumentURL': (StringIO(b'doc'), 'document.pdf'),
                }
            )

        assert res.status_code == 302
        data_api_client.update_draft_service.assert_called_once_with(
            '1', {
                'serviceDefinitionDocumentURL': 'http://localhost/suppliers/assets/g-cloud-7/submissions/1234/1-service-definition-document-2015-01-02-0304.pdf'  # noqa
            }, 'email@email.com',
            page_questions=['serviceDefinitionDocumentURL']
        )

        s3.return_value.save.assert_called_once_with(
            'g-cloud-7/submissions/1234/1-service-definition-document-2015-01-02-0304.pdf',
            mock.ANY, acl='private'
        )

    def test_file_upload_filters_empty_and_unknown_files(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-definition',
            data={
                'serviceDefinitionDocumentURL': (StringIO(b''), 'document.pdf'),
                'unknownDocumentURL': (StringIO(b'doc'), 'document.pdf'),
                'pricingDocumentURL': (StringIO(b'doc'), 'document.pdf'),
            })

        assert res.status_code == 302
        data_api_client.update_draft_service.assert_called_once_with(
            '1', {}, 'email@email.com',
            page_questions=['serviceDefinitionDocumentURL']
        )

        assert s3.return_value.save.called is False

    def test_upload_question_not_accepted_as_form_data(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-definition',
            data={
                'serviceDefinitionDocumentURL': 'http://example.com/document.pdf',
            })

        assert res.status_code == 302
        data_api_client.update_draft_service.assert_called_once_with(
            '1', {}, 'email@email.com',
            page_questions=['serviceDefinitionDocumentURL']
        )

    def test_pricing_fields_are_added_correctly(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/pricing',
            data={
                'priceMin': "10.10",
                'priceMax': "11.10",
                'priceUnit': "Person",
                'priceInterval': "Second",
            })

        assert res.status_code == 302
        data_api_client.update_draft_service.assert_called_once_with(
            '1',
            {
                'priceMin': "10.10", 'priceMax': "11.10", "priceUnit": "Person", 'priceInterval': 'Second',
            },
            'email@email.com',
            page_questions=[
                'priceInterval', 'priceMax', 'priceMin', 'priceUnit',
                'vatIncluded', 'educationPricing',
            ])

    def test_edit_non_existent_draft_service_returns_404(self, data_api_client, s3):
        data_api_client.get_draft_service.side_effect = HTTPError(mock.Mock(status_code=404))
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description')

        assert res.status_code == 404

    def test_edit_non_existent_draft_section_returns_404(self, data_api_client, s3):
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/invalid_section'
        )
        assert res.status_code == 404

    def test_update_in_section_with_more_questions_redirects_to_next_question_in_section(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(slug='g-cloud-9', status='open')
        data_api_client.get_draft_service.return_value = self.empty_g9_draft
        data_api_client.update_draft_service.return_value = None

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-9/submissions/cloud-hosting/1/edit/pricing/price',
            data={
                'continue_to_next_section': 'Save and continue'
            })

        assert res.status_code == 302
        assert res.headers['Location'] == \
            'http://localhost/suppliers/frameworks/g-cloud-9/submissions/cloud-hosting/1/edit/pricing/education-pricing'

    def test_update_at_end_of_section_redirects_to_summary(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(slug='g-cloud-9', status='open')
        data_api_client.get_draft_service.return_value = self.empty_g9_draft
        data_api_client.update_draft_service.return_value = None

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-9/submissions/cloud-hosting/1/edit/pricing/free-or-trial-versions',
            data={
                'continue_to_next_section': 'Save and continue'
            })

        assert res.status_code == 302
        assert res.headers['Location'] == \
            'http://localhost/suppliers/frameworks/g-cloud-9/submissions/cloud-hosting/1#pricing'

    def test_update_refuses_to_redirect_to_next_editable_section_if_dos(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(
            status='open',
            slug='digital-outcomes-and-specialists',
            name='Digital Outcomes and Specialists',
        )
        data_api_client.get_draft_service.return_value = self.multiquestion_draft
        data_api_client.update_draft_service.return_value = None

        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/digital-specialists/1/'
            'edit/individual-specialist-roles/product-manager',
            data={
                'continue_to_next_section': 'Save and continue'
            })

        assert res.status_code == 302
        assert 'http://localhost/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' \
            'digital-specialists/1#individual-specialist-roles' == res.headers['Location']

    def test_page_doesnt_offer_continue_to_next_editable_section_if_dos(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(
            status='open',
            slug='digital-outcomes-and-specialists',
            name='Digital Outcomes and Specialists',
        )
        data_api_client.get_draft_service.return_value = self.multiquestion_draft

        res = self.client.get(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/digital-specialists/1/'
            'edit/individual-specialist-roles/product-manager',
        )

        assert res.status_code == 200
        document = html.fromstring(res.get_data(as_text=True))
        assert len(document.xpath("//input[@type='submit'][@name='continue_to_next_section']")) == 0

    def test_update_redirects_to_edit_submission_if_no_next_editable_section(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        data_api_client.update_draft_service.return_value = None

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/sfia-rate-card',
            data={})

        assert res.status_code == 302
        assert 'http://localhost/suppliers/frameworks/g-cloud-7/submissions/scs/1#sfia-rate-card' == \
            res.headers['Location']

    def test_update_doesnt_offer_continue_to_next_editable_section_if_no_next_editable_section(self,
                                                                                               data_api_client,
                                                                                               s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft

        res = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/sfia-rate-card',
        )

        assert res.status_code == 200
        document = html.fromstring(res.get_data(as_text=True))
        assert len(document.xpath("//input[@type='submit'][@name='continue_to_next_section']")) == 0

    def test_update_redirects_to_edit_submission_if_return_to_summary(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        data_api_client.update_draft_service.return_value = None

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description?return_to_summary=1',
            data={})

        assert res.status_code == 302
        assert 'http://localhost/suppliers/frameworks/g-cloud-7/submissions/scs/1#service-description' == \
            res.headers['Location']

    def test_update_doesnt_offer_continue_to_next_editable_section_if_return_to_summary(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft

        res = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description?return_to_summary=1',
        )

        assert res.status_code == 200
        document = html.fromstring(res.get_data(as_text=True))
        assert len(document.xpath("//input[@type='submit'][@name='continue_to_next_section']")) == 0

    def test_update_redirects_to_edit_submission_if_save_and_return_grey_button_clicked(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        data_api_client.update_draft_service.return_value = None

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description',
            data={})

        assert res.status_code == 302
        assert 'http://localhost/suppliers/frameworks/g-cloud-7/submissions/scs/1#service-description' == \
            res.headers['Location']

    def test_update_with_answer_required_error(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        data_api_client.update_draft_service.side_effect = HTTPError(
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

    def test_update_with_under_50_words_error(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        data_api_client.update_draft_service.side_effect = HTTPError(
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

    def test_update_with_pricing_errors(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        cases = [
            ('priceMin', 'answer_required', 'Minimum price requires an answer.'),
            ('priceUnit', 'answer_required', "Pricing unit requires an answer. If none of the provided units apply, please choose 'Unit'."),  # noqa
            ('priceMin', 'not_money_format', 'Minimum price must be a number, without units, eg 99.95'),
            ('priceMax', 'not_money_format', 'Maximum price must be a number, without units, eg 99.95'),
            ('priceMax', 'max_less_than_min', 'Minimum price must be less than maximum price'),
        ]

        for field, error, message in cases:
            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_draft_service.return_value = self.empty_draft
            data_api_client.update_draft_service.side_effect = HTTPError(
                mock.Mock(status_code=400),
                {field: error})
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/pricing',
                data={})

            assert res.status_code == 200
            document = html.fromstring(res.get_data(as_text=True))
            assert message == document.xpath('//span[@class="validation-message"]/text()')[0].strip()

    def test_update_non_existent_draft_service_returns_404(self, data_api_client, s3):
        data_api_client.get_draft_service.side_effect = HTTPError(mock.Mock(status_code=404))
        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/service-description')

        assert res.status_code == 404

    def test_update_non_existent_draft_section_returns_404(self, data_api_client, s3):
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/edit/invalid-section'
        )
        assert res.status_code == 404

    def test_update_multiquestion(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(
            status='open', slug='digital-outcomes-and-specialists'
        )
        draft = self.empty_draft.copy()
        draft['services']['lot'] = 'digital-specialists'
        draft['services']['lotSlug'] = 'digital-specialists'
        draft['services']['frameworkSlug'] = 'digital-outcomes-and-specialists'
        data_api_client.get_draft_service.return_value = draft

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
        data_api_client.update_draft_service.assert_called_once_with(
            '1',
            {'agileCoachLocations': ['Scotland']},
            'email@email.com',
            page_questions=['agileCoachLocations', 'agileCoachPriceMax', 'agileCoachPriceMin']
        )

    def test_remove_subsection(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(
            status='open', slug='digital-outcomes-and-specialists'
        )

        data_api_client.get_draft_service.return_value = self.multiquestion_draft

        res = self.client.get(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' +
            'digital-specialists/1/remove/individual-specialist-roles/agile-coach'
        )

        assert res.status_code == 302
        assert(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/digital-specialists/1?' in res.location
        )
        assert('section_id=individual-specialist-roles' in res.location)
        assert('confirm_remove=agile-coach' in res.location)

        res2 = self.client.get(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' +
            'digital-specialists/1?section_id=specialists&confirm_remove=agile-coach'
        )
        assert res2.status_code == 200
        assert u'Are you sure you want to remove agile coach?' in res2.get_data(as_text=True)

        res3 = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' +
            'digital-specialists/1/remove/individual-specialist-roles/agile-coach?confirm=True')

        assert res3.status_code == 302
        assert(res3.location.endswith(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/digital-specialists/1')
        )
        data_api_client.update_draft_service.assert_called_once_with(
            '1',
            {
                'agileCoachLocations': None,
                'agileCoachPriceMax': None,
                'agileCoachPriceMin': None,
            },
            'email@email.com'
        )

    def test_can_not_remove_last_subsection_from_submitted_draft(self, data_api_client, s3):
        s3.return_value.bucket_short_name = 'submissions'
        data_api_client.get_framework.return_value = self.framework(
            status='open', slug='digital-outcomes-and-specialists'
        )

        draft_service = copy.deepcopy(self.multiquestion_draft)
        draft_service['services'].pop('developerLocations', None)
        draft_service['services'].pop('developerPriceMax', None)
        draft_service['services'].pop('developerPriceMin', None)
        draft_service['services']['status'] = 'submitted'

        data_api_client.get_draft_service.return_value = draft_service

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

        assert data_api_client.update_draft_service.called is False

    def test_can_not_remove_other_suppliers_subsection(self, data_api_client, s3):
        draft_service = copy.deepcopy(self.multiquestion_draft)
        draft_service['services']['supplierId'] = 12345
        data_api_client.get_draft_service.return_value = draft_service
        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' +
            'digital-specialists/1/remove/individual-specialist-roles/agile-coach?confirm=True')

        assert res.status_code == 404
        assert data_api_client.update_draft_service.called is False

    def test_fails_if_api_get_fails(self, data_api_client, s3):
        data_api_client.get_draft_service.side_effect = HTTPError(mock.Mock(status_code=504))
        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' +
            'digital-specialists/1/remove/individual-specialist-roles/agile-coach?confirm=True')
        assert res.status_code == 504

    def test_fails_if_api_update_fails(self, data_api_client, s3):
        data_api_client.get_draft_service.return_value = self.multiquestion_draft
        data_api_client.update_draft_service.side_effect = HTTPError(mock.Mock(status_code=504))
        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/' +
            'digital-specialists/1/remove/individual-specialist-roles/agile-coach?confirm=True')
        assert res.status_code == 504


@mock.patch('app.main.views.services.data_api_client')
class TestShowDraftService(BaseApplicationTestLoggedIn):

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

    def test_service_price_is_correctly_formatted(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework('open')
        data_api_client.get_draft_service.return_value = self.draft_service
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1')
        document = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 200
        service_price_row_xpath = '//tr[contains(.//span/text(), "Service price")]'
        service_price_xpath = service_price_row_xpath + '/td[@class="summary-item-field"]/span/text()'
        assert document.xpath(service_price_xpath)[0].strip() == u"£12.50 to £15 per person per second"

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_unanswered_questions_count(self, count_unanswered, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.draft_service
        count_unanswered.return_value = 1, 2
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1')

        assert u'3 unanswered questions' in res.get_data(as_text=True), \
            "'3 unanswered questions' not found in html"

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_move_to_complete_button(self, count_unanswered, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.draft_service
        count_unanswered.return_value = 0, 1
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1')

        assert u'1 optional question unanswered' in res.get_data(as_text=True)
        assert u'<input type="submit" class="button-save"  value="Mark as complete" />' in res.get_data(as_text=True)

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_no_move_to_complete_button_if_not_open(self, count_unanswered, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='other')
        data_api_client.get_draft_service.return_value = self.draft_service
        count_unanswered.return_value = 0, 1
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1')

        assert u'<input type="submit" class="button-save"  value="Mark as complete" />' not in \
            res.get_data(as_text=True)

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_no_move_to_complete_button_if_validation_errors(self, count_unanswered, data_api_client):
        draft_service = copy.deepcopy(self.draft_service)
        draft_service['validationErrors'] = {'_errors': "Everything's busted"}

        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = draft_service
        count_unanswered.return_value = 0, 1

        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1')

        assert u'<input type="submit" class="button-save"  value="Mark as complete" />' not in \
            res.get_data(as_text=True)

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_shows_g7_message_if_pending_and_service_is_in_draft(self, count_unanswered, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='pending')
        data_api_client.get_draft_service.return_value = self.draft_service
        count_unanswered.return_value = 3, 1
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1')

        doc = html.fromstring(res.get_data(as_text=True))
        message = doc.xpath('//aside[@class="temporary-message"]')

        assert len(message) > 0
        assert u"This service was not submitted" in message[0].xpath(
            'h2[@class="temporary-message-heading"]/text()'
        )[0]
        assert u"It wasn't marked as complete at the deadline." in message[0].xpath(
            'p[@class="temporary-message-message"]/text()'
        )[0]

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_shows_g7_message_if_pending_and_service_is_complete(self, count_unanswered, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='pending')
        data_api_client.get_draft_service.return_value = self.complete_service
        count_unanswered.return_value = 0, 1
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/2')

        doc = html.fromstring(res.get_data(as_text=True))
        message = doc.xpath('//aside[@class="temporary-message"]')

        assert len(message) > 0
        assert u"This service was submitted" in message[0].xpath('h2[@class="temporary-message-heading"]/text()')[0]
        assert u"If your application is successful, it will be available on the Digital Marketplace when " \
            u"G-Cloud 7 goes live." in message[0].xpath('p[@class="temporary-message-message"]/text()')[0]


@mock.patch('app.main.views.services.data_api_client')
class TestDeleteDraftService(BaseApplicationTestLoggedIn):

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

    def test_delete_button_redirects_with_are_you_sure(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.draft_to_delete
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/delete',
            data={})
        assert res.status_code == 302
        assert '/frameworks/g-cloud-7/submissions/scs/1?delete_requested=True' in res.location
        res2 = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs/1?delete_requested=True')
        assert b"Are you sure you want to delete this service?" in res2.get_data()

    def test_cannot_delete_if_not_open(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='other')
        data_api_client.get_draft_service.return_value = self.draft_to_delete
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/delete',
            data={})
        assert res.status_code == 404

    def test_confirm_delete_button_deletes_and_redirects_to_dashboard(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.draft_to_delete
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/delete',
            data={'delete_confirmed': 'true'})

        data_api_client.delete_draft_service.assert_called_with('1', 'email@email.com')
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-7/submissions/scs'

    def test_cannot_delete_other_suppliers_draft(self, data_api_client):
        other_draft = copy.deepcopy(self.draft_to_delete)
        other_draft['services']['supplierId'] = 12345
        data_api_client.get_draft_service.return_value = other_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/scs/1/delete',
            data={'delete_confirmed': 'true'})

        assert res.status_code == 404


@mock.patch('dmutils.s3.S3')
class TestSubmissionDocuments(BaseApplicationTestLoggedIn):

    def test_document_url(self, s3):
        s3.return_value.bucket_short_name = 'submissions'
        s3.return_value.get_signed_url.return_value = 'http://example.com/document.pdf'

        res = self.client.get(
            '/suppliers/assets/g-cloud-7/submissions/1234/document.pdf'
        )

        assert res.status_code == 302
        assert res.headers['Location'] == 'http://asset-host/document.pdf'

    def test_missing_document_url(self, s3):
        s3.return_value.bucket_short_name = 'submissions'
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
