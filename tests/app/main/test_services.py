# -*- coding: utf-8 -*-
try:
    from StringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO

from dmutils.apiclient import HTTPError
import copy
import mock
from lxml import html
from freezegun import freeze_time

from nose.tools import assert_equal, assert_true, assert_false, \
    assert_in, assert_not_in
from tests.app.helpers import BaseApplicationTest
from app.main import content_loader


class TestListServices(BaseApplicationTest):
    @mock.patch('app.main.views.services.data_api_client')
    def test_shows_no_services_message(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.find_services.return_value = {
                "services": []
                }

            res = self.client.get('/suppliers/services')
            assert_equal(res.status_code, 200)
            data_api_client.find_services.assert_called_once_with(
                supplier_id=1234)
            assert_in(
                "You don&#39;t have any services on the Digital Marketplace",
                res.get_data(as_text=True)
            )

    @mock.patch('app.main.views.services.data_api_client')
    def test_shows_services_list(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.find_services.return_value = {
                'services': [{
                    'serviceName': 'Service name 123',
                    'status': 'published',
                    'id': '123',
                    'lot': 'SaaS',
                    'frameworkName': 'G-Cloud 1'
                }]
            }

            res = self.client.get('/suppliers/services')
            assert_equal(res.status_code, 200)
            data_api_client.find_services.assert_called_once_with(
                supplier_id=1234)
            assert_true("Service name 123" in res.get_data(as_text=True))
            assert_true("SaaS" in res.get_data(as_text=True))
            assert_true("G-Cloud 1" in res.get_data(as_text=True))

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
            assert_equal(res.status_code, 302)
            assert_equal(res.location, 'http://localhost/suppliers/login?next=%2Fsuppliers%2Fservices')

    @mock.patch('app.main.views.services.data_api_client')
    def test_shows_services_edit_button_with_id(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.find_services.return_value = {
                'services': [{
                    'serviceName': 'Service name 123',
                    'status': 'published',
                    'id': '123'
                }]
            }

            res = self.client.get('/suppliers/services')
            assert_equal(res.status_code, 200)
            data_api_client.find_services.assert_called_once_with(
                supplier_id=1234)
            assert_true(
                "/suppliers/services/123" in res.get_data(as_text=True))


class TestListServicesLogin(BaseApplicationTest):
    @mock.patch('app.main.views.services.data_api_client')
    def test_should_show_services_list_if_logged_in(self, data_api_client):
        with self.app.test_client():
            self.login()
            data_api_client.find_services.return_value = {'services': [{
                'serviceName': 'Service name 123',
                'status': 'published',
                'id': '123'
            }]}

            res = self.client.get('/suppliers/services')

            assert_equal(res.status_code, 200)

            assert_true(
                self.strip_all_whitespace('<h1>Current services</h1>')
                in self.strip_all_whitespace(res.get_data(as_text=True))
            )

    def test_should_redirect_to_login_if_not_logged_in(self):
        res = self.client.get("/suppliers/services")
        assert_equal(res.status_code, 302)
        assert_equal(res.location,
                     'http://localhost/suppliers/login'
                     '?next=%2Fsuppliers%2Fservices')


@mock.patch('app.main.views.services.data_api_client')
class TestSupplierUpdateService(BaseApplicationTest):
    def _get_service(self,
                     data_api_client,
                     service_status="published",
                     service_belongs_to_user=True):
        data_api_client.get_service.return_value = {
            'services': {
                'serviceName': 'Service name 123',
                'status': service_status,
                'id': '123',
                'frameworkName': 'G-Cloud 6',
                'supplierId': 1234 if service_belongs_to_user else 1235
            }
        }

    def _post_status_update(
            self, status, expected_status_code):
        res = self.client.post('/suppliers/services/123', data={
            'status': status,
        })
        assert_equal(res.status_code, expected_status_code)

    def _post_status_updates(
            self,
            service_should_be_modifiable=True,
            failing_status_code=400
    ):
        expected_status_code = \
            302 if service_should_be_modifiable else failing_status_code

        # Should work if service not removed/disabled or another supplier's
        self._post_status_update('private', expected_status_code)
        self._post_status_update('public', expected_status_code)

        # Database statuses should not work
        self._post_status_update('published', failing_status_code)
        self._post_status_update('enabled', failing_status_code)

        # Removing a service should be impossible
        self._post_status_update('removed', failing_status_code)
        self._post_status_update('disabled', failing_status_code)

        # non-statuses should not work
        self._post_status_update('orange', failing_status_code)
        self._post_status_update('banana', failing_status_code)

    def test_should_view_public_service_with_correct_input_checked(
            self, data_api_client
    ):
        self.login()
        self._get_service(data_api_client, service_status='published')

        res = self.client.get('/suppliers/services/123')
        assert_equal(res.status_code, 200)

        assert_true(
            'Service name 123' in res.get_data(as_text=True)
        )

        # check that 'public' is selected.
        assert_true(
            '<input type="radio" name="status" id="input-status-1" value="Public" checked="checked"'  # noqa
            in res.get_data(as_text=True)
        )
        assert_false(
            '<input type="radio" name="status" id="input-status-2" value="Private" checked="checked"'  # noqa
            in res.get_data(as_text=True)
        )

        self._post_status_updates(
            service_should_be_modifiable=True
        )

    def test_should_view_private_service_with_correct_input_checked(
            self, data_api_client
    ):
        self.login()
        self._get_service(data_api_client, service_status='enabled')

        res = self.client.get('/suppliers/services/123')
        assert_equal(res.status_code, 200)
        assert_true(
            'Service name 123' in res.get_data(as_text=True)
        )

        # check that 'public' is not selected.
        assert_false(
            '<input type="radio" name="status" id="input-status-1" value="Public" checked="checked"'  # noqa
            in res.get_data(as_text=True)
        )
        assert_true(
            '<input type="radio" name="status" id="input-status-2" value="Private" checked="checked"'  # noqa
            in res.get_data(as_text=True)
        )

        self._post_status_updates(
            service_should_be_modifiable=True
        )

    def test_should_view_disabled_service_with_removed_message(
            self, data_api_client
    ):
        self.login()
        self._get_service(data_api_client, service_status='disabled')

        res = self.client.get('/suppliers/services/123')
        assert_equal(res.status_code, 200)
        assert_true(
            'Service name 123' in res.get_data(as_text=True)
        )

        assert_true(
            'This service has been removed'
            in res.get_data(as_text=True)
        )

        self._post_status_updates(
            service_should_be_modifiable=False
        )

    def test_should_not_view_other_suppliers_services(
            self, data_api_client
    ):
        self.login()
        self._get_service(data_api_client, service_status='published', service_belongs_to_user=False)

        res = self.client.get('/suppliers/services/123')
        assert_equal(res.status_code, 404)

        # Should all be 404 if service doesn't belong to supplier
        self._post_status_updates(
            service_should_be_modifiable=False,
            failing_status_code=404
        )

    def test_should_redirect_to_login_if_not_logged_in(self, data_api_client):
        res = self.client.get("/suppliers/services/123")
        assert_equal(res.status_code, 302)
        assert_equal(res.location,
                     'http://localhost/suppliers/login'
                     '?next=%2Fsuppliers%2Fservices%2F123')


@mock.patch('app.main.views.services.data_api_client')
class TestEditService(BaseApplicationTest):

    empty_service = {
        'services': {
            'serviceName': 'Service name 123',
            'status': 'published',
            'id': '123',
            'frameworkName': 'G-Cloud 6',
            'supplierId': 1234,
            'supplierName': 'We supply any',
            'lot': 'SCS',
        }
    }

    def setup(self):
        super(TestEditService, self).setup()
        with self.app.test_client():
            self.login()

    def test_questions_for_this_service_section_can_be_changed(self, data_api_client):
        data_api_client.get_service.return_value = self.empty_service
        res = self.client.post(
            '/suppliers/services/1/edit/description',
            data={
                'serviceName': 'The service',
                'serviceSummary': 'This is the service',
            })

        assert_equal(res.status_code, 302)
        data_api_client.update_service.assert_called_once_with(
            '1', {'serviceName': 'The service', 'serviceSummary': 'This is the service'},
            'email@email.com')

    def test_editing_readonly_section_is_not_allowed(self, data_api_client):
        data_api_client.get_service.return_value = self.empty_service

        res = self.client.get('/suppliers/services/1/edit/service_attributes')
        assert_equal(res.status_code, 404)

        data_api_client.get_draft_service.return_value = self.empty_service
        res = self.client.post(
            '/suppliers/services/1/edit/service_attributes',
            data={
                'lot': 'SCS',
            })
        assert_equal(res.status_code, 404)

    def test_only_questions_for_this_service_section_can_be_changed(self, data_api_client):
        data_api_client.get_service.return_value = self.empty_service
        res = self.client.post(
            '/suppliers/services/1/edit/description',
            data={
                'serviceFeatures': '',
            })

        assert_equal(res.status_code, 302)
        data_api_client.update_service.assert_called_one_with(
            '1', dict(), 'email@email.com')

    def test_edit_non_existent_service_returns_404(self, data_api_client):
        data_api_client.get_service.return_value = None
        res = self.client.get('/suppliers/services/1/edit/description')

        assert_equal(res.status_code, 404)

    def test_edit_non_existent_section_returns_404(self, data_api_client):
        data_api_client.get_service.return_value = self.empty_service
        res = self.client.get(
            '/suppliers/services/1/edit/invalid_section'
        )
        assert_equal(404, res.status_code)

    def test_update_with_answer_required_error(self, data_api_client):
        data_api_client.get_service.return_value = self.empty_service
        data_api_client.update_service.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'serviceSummary': 'answer_required'})
        res = self.client.post(
            '/suppliers/services/1/edit/description',
            data={})

        assert_equal(res.status_code, 200)
        document = html.fromstring(res.get_data(as_text=True))
        assert_equal(
            "You need to answer this question.",
            document.xpath('//span[@id="error-serviceSummary"]/text()')[0].strip())

    def test_update_with_under_50_words_error(self, data_api_client):
        data_api_client.get_service.return_value = self.empty_service
        data_api_client.update_service.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'serviceSummary': 'under_50_words'})
        res = self.client.post(
            '/suppliers/services/1/edit/description',
            data={})

        assert_equal(res.status_code, 200)
        document = html.fromstring(res.get_data(as_text=True))
        assert_equal(
            "Your description must not be more than 50 words.",
            document.xpath('//span[@id="error-serviceSummary"]/text()')[0].strip())

    def test_update_non_existent_service_returns_404(self, data_api_client):
        data_api_client.get_service.return_value = None
        res = self.client.post('/suppliers/services/1/edit/description')

        assert_equal(res.status_code, 404)

    def test_update_non_existent_section_returns_404(self, data_api_client):
        data_api_client.get_service.return_value = self.empty_service
        res = self.client.post(
            '/suppliers/services/1/edit/invalid_section'
        )
        assert_equal(404, res.status_code)


@mock.patch('app.main.views.services.data_api_client')
@mock.patch('app.main.views.services.request')
class TestCreateDraftService(BaseApplicationTest):
    def setup(self):
        super(TestCreateDraftService, self).setup()
        self._answer_required = 'Answer is required'
        self._validation_error = \
            'There was a problem with your answer to the following questions'

    @staticmethod
    def _format_for_request(phrase):
        return phrase.replace(' ', '+')

    def test_get_create_draft_service_page_if_open(self, request, data_api_client):
        with self.app.test_client():
            self.login()
        data_api_client.get_framework.return_value = self.framework(status='open')

        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/create')
        assert_equal(res.status_code, 200)
        assert_in("Create new service", res.get_data(as_text=True))

        lots = content_loader.get_builder('g-cloud-7', 'edit_submission').get_question('lot')

        for lot in lots['options']:
            assert_in(lot['label'], res.get_data(as_text=True))

        assert_not_in(self._validation_error, res.get_data(as_text=True))

    def test_can_not_get_create_draft_service_page_if_not_open(self, request, data_api_client):
        with self.app.test_client():
            self.login()
        data_api_client.get_framework.return_value = self.framework(status='other')

        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/create')
        assert_equal(res.status_code, 404)

    def _test_post_create_draft_service(self, if_error_expected, data_api_client):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.create_new_draft_service.return_value = {
            'services': {
                'id': 1,
                'supplierId': 1234,
                'supplierName': "supplierName",
                'lot': "SCS",
                'status': "not-submitted",
                'frameworkName': "frameworkName",
                'links': {},
                'updatedAt': "2015-06-29T15:26:07.650368Z"
            }
        }

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/create'
        )

        if if_error_expected:
            assert_equal(res.status_code, 400)
            assert_in(self._validation_error, res.get_data(as_text=True))
        else:
            assert_equal(res.status_code, 302)

    def test_post_create_draft_service_with_lot_selected_succeeds(self, request, data_api_client):
        request.form.get.return_value = "SCS"
        self._test_post_create_draft_service(if_error_expected=False, data_api_client=data_api_client)

    def test_post_create_draft_service_without_lot_selected_fails(self, request, data_api_client):
        request.form.get.return_value = None
        self._test_post_create_draft_service(if_error_expected=True, data_api_client=data_api_client)

    def test_cannot_post_if_not_open(self, request, data_api_client):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(status='other')
        res = self.client.post(
            '/suppliers/submission/g-cloud-7/create'
        )
        assert_equal(res.status_code, 404)


@mock.patch('app.main.views.services.data_api_client')
class TestCopyDraft(BaseApplicationTest):

    def setup(self):
        super(TestCopyDraft, self).setup()

        with self.app.test_client():
            self.login()

        self.draft = {
            'id': 1,
            'supplierId': 1234,
            'supplierName': "supplierName",
            'lot': "SCS",
            'status': "not-submitted",
            'frameworkName': "frameworkName",
            'links': {},
            'updatedAt': "2015-06-29T15:26:07.650368Z"
        }

    def test_copy_draft(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = {'services': self.draft}

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/1/copy')
        assert_equal(res.status_code, 302)

    def test_copy_draft_checks_supplier_id(self, data_api_client):
        self.draft['supplierId'] = 2
        data_api_client.get_draft_service.return_value = {'services': self.draft}

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/1/copy')
        assert_equal(res.status_code, 404)

    def test_cannot_copy_draft_if_not_open(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='other')

        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/1/copy')
        assert_equal(res.status_code, 404)


@mock.patch('app.main.views.services.data_api_client')
class TestCompleteDraft(BaseApplicationTest):

    def setup(self):
        super(TestCompleteDraft, self).setup()

        with self.app.test_client():
            self.login()

        self.draft = {
            'id': 1,
            'supplierId': 1234,
            'supplierName': "supplierName",
            'lot': "SCS",
            'status': "not-submitted",
            'frameworkName': "frameworkName",
            'links': {},
            'updatedAt': "2015-06-29T15:26:07.650368Z"
        }

    def test_complete_draft(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = {'services': self.draft}

        res = self.client.post('/suppliers/submission/services/1/complete')
        assert_equal(res.status_code, 302)
        assert_true('lot=scs' in res.location)
        assert_true('service_completed=1' in res.location)
        assert_true('/suppliers/frameworks/g-cloud-7/services' in res.location)

    def test_complete_draft_checks_supplier_id(self, data_api_client):
        self.draft['supplierId'] = 2
        data_api_client.get_draft_service.return_value = {'services': self.draft}

        res = self.client.post('/suppliers/submission/services/1/complete')
        assert_equal(res.status_code, 404)

    def test_cannot_complete_draft_if_not_open(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='other')

        res = self.client.post('/suppliers/submission/services/1/complete')
        assert_equal(res.status_code, 404)


@mock.patch('dmutils.s3.S3')
@mock.patch('app.main.views.services.data_api_client')
class TestEditDraftService(BaseApplicationTest):

    empty_draft = {
        'services': {
            'id': 1,
            'supplierId': 1234,
            'supplierName': "supplierName",
            'lot': "SCS",
            'status': "not-submitted",
            'frameworkSlug': 'g-slug',
            'frameworkName': "frameworkName",
            'links': {},
            'updatedAt': "2015-06-29T15:26:07.650368Z"
        }
    }

    def setup(self):
        super(TestEditDraftService, self).setup()
        with self.app.test_client():
            self.login()

    def test_questions_for_this_draft_section_can_be_changed(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_description',
            data={
                'serviceSummary': 'This is the service',
            })

        assert_equal(res.status_code, 302)
        data_api_client.update_draft_service.assert_called_once_with(
            '1',
            {'serviceSummary': 'This is the service'},
            'email@email.com',
            page_questions=['serviceSummary']
        )

    def test_update_without_changes_is_not_sent_to_the_api(self, data_api_client, s3):
        draft = self.empty_draft['services'].copy()
        draft.update({'serviceSummary': u"summary"})
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = {'services': draft}

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_description',
            data={
                'serviceSummary': u"summary",
            })

        assert_equal(res.status_code, 302)
        assert_false(data_api_client.update_draft_service.called)

    def test_S3_should_not_be_called_if_there_are_no_files(self, data_api_client, s3):
        uploader = mock.Mock()
        s3.return_value = uploader
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_description',
            data={
                'serviceSummary': 'This is the service',
            })

        assert_equal(res.status_code, 302)
        assert not uploader.save.called

    def test_editing_readonly_section_is_not_allowed(self, data_api_client, s3):
        data_api_client.get_draft_service.return_value = self.empty_draft

        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_attributes')
        assert_equal(res.status_code, 404)

        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_attributes',
            data={
                'lot': 'SCS',
            })
        assert_equal(res.status_code, 404)

    def test_draft_section_cannot_be_edited_if_not_open(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='other')
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_description',
            data={
                'serviceSummary': 'This is the service',
            })
        assert_equal(res.status_code, 404)

    def test_only_questions_for_this_draft_section_can_be_changed(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_description',
            data={
                'serviceFeatures': '',
            })

        assert_equal(res.status_code, 302)
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
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_definition'
        )
        document = html.fromstring(response.get_data(as_text=True))

        assert_equal(response.status_code, 200)
        assert_equal(len(document.cssselect('p.file-upload-existing-value')), 1)

    def test_display_file_upload_with_no_existing_file(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        response = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_definition'
        )
        document = html.fromstring(response.get_data(as_text=True))

        assert_equal(response.status_code, 200)
        assert_equal(len(document.cssselect('p.file-upload-existing-value')), 0)

    def test_file_upload(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        with freeze_time('2015-01-02 03:04:05'):
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_definition',
                data={
                    'serviceDefinitionDocumentURL': (StringIO(b'doc'), 'document.pdf'),
                }
            )

        assert_equal(res.status_code, 302)
        data_api_client.update_draft_service.assert_called_once_with(
            '1', {
                'serviceDefinitionDocumentURL': 'http://localhost/suppliers/submission/documents/g-slug/1234/1-service-definition-document-2015-01-02-0304.pdf'  # noqa
            }, 'email@email.com',
            page_questions=['serviceDefinitionDocumentURL']
        )

        s3.return_value.save.assert_called_once_with(
            'g-slug/1234/1-service-definition-document-2015-01-02-0304.pdf',
            mock.ANY, acl='private'
        )

    def test_file_upload_filters_empty_and_unknown_files(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_definition',
            data={
                'serviceDefinitionDocumentURL': (StringIO(b''), 'document.pdf'),
                'unknownDocumentURL': (StringIO(b'doc'), 'document.pdf'),
                'pricingDocumentURL': (StringIO(b'doc'), 'document.pdf'),
            })

        assert_equal(res.status_code, 302)
        data_api_client.update_draft_service.assert_called_once_with(
            '1', {}, 'email@email.com',
            page_questions=['serviceDefinitionDocumentURL']
        )

        assert_false(s3.return_value.save.called)

    def test_upload_question_not_accepted_as_form_data(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_definition',
            data={
                'serviceDefinitionDocumentURL': 'http://example.com/document.pdf',
            })

        assert_equal(res.status_code, 302)
        data_api_client.update_draft_service.assert_called_once_with(
            '1', {}, 'email@email.com',
            page_questions=['serviceDefinitionDocumentURL']
        )

    def test_pricing_fields_are_added_correctly(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/pricing',
            data={
                'priceString': ["10.10", "11.10", "Person", "Second"],
            })

        assert_equal(res.status_code, 302)
        data_api_client.update_draft_service.assert_called_once_with(
            '1',
            {
                'priceMin': "10.10", 'priceMax': "11.10", "priceUnit": "Person", 'priceInterval': 'Second',
            },
            'email@email.com',
            page_questions=[
                'vatIncluded', 'educationPricing',
                'priceMin', 'priceMax', 'priceUnit', 'priceInterval'
            ])

    def test_edit_non_existent_draft_service_returns_404(self, data_api_client, s3):
        data_api_client.get_draft_service.side_effect = HTTPError(mock.Mock(status_code=404))
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_description')

        assert_equal(res.status_code, 404)

    def test_edit_non_existent_draft_section_returns_404(self, data_api_client, s3):
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/invalid_section'
        )
        assert_equal(404, res.status_code)

    def test_update_redirects_to_next_editable_section(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        data_api_client.update_draft_service.return_value = None

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_description',
            data={
                'continue_to_next_section': 'Save and continue'
            })

        assert_equal(302, res.status_code)
        assert_equal('http://localhost/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_type',
                     res.headers['Location'])

    def test_update_redirects_to_edit_submission_if_no_next_editable_section(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        data_api_client.update_draft_service.return_value = None

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/sfia_rate_card',
            data={})

        assert_equal(302, res.status_code)
        assert_equal('http://localhost/suppliers/frameworks/g-cloud-7/submissions/1',
                     res.headers['Location'])

    def test_update_redirects_to_edit_submission_if_return_to_summary(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        data_api_client.update_draft_service.return_value = None

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_description?return_to_summary=1',
            data={})

        assert_equal(302, res.status_code)
        assert_equal('http://localhost/suppliers/frameworks/g-cloud-7/submissions/1',
                     res.headers['Location'])

    def test_update_redirects_to_edit_submission_if_grey_button_clicked(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        data_api_client.update_draft_service.return_value = None

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_description',
            data={})

        assert_equal(302, res.status_code)
        assert_equal('http://localhost/suppliers/frameworks/g-cloud-7/submissions/1',
                     res.headers['Location'])

    def test_update_with_answer_required_error(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        data_api_client.update_draft_service.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'serviceSummary': 'answer_required'})
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_description',
            data={})

        assert_equal(res.status_code, 200)
        document = html.fromstring(res.get_data(as_text=True))
        assert_equal(
            "You need to answer this question.",
            document.xpath('//span[@id="error-serviceSummary"]/text()')[0].strip())

    def test_update_with_under_50_words_error(self, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.empty_draft
        data_api_client.update_draft_service.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'serviceSummary': 'under_50_words'})
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_description',
            data={})

        assert_equal(res.status_code, 200)
        document = html.fromstring(res.get_data(as_text=True))
        assert_equal(
            "Your description must not be more than 50 words.",
            document.xpath('//span[@id="error-serviceSummary"]/text()')[0].strip())

    def test_update_with_pricing_errors(self, data_api_client, s3):
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
                '/suppliers/frameworks/g-cloud-7/submissions/1/edit/pricing',
                data={})

            assert_equal(res.status_code, 200)
            document = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                message, document.xpath('//span[@id="error-priceString"]/text()')[0].strip())

    def test_update_non_existent_draft_service_returns_404(self, data_api_client, s3):
        data_api_client.get_draft_service.side_effect = HTTPError(mock.Mock(status_code=404))
        res = self.client.post('/suppliers/frameworks/g-cloud-7/submissions/1/edit/service_description')

        assert_equal(res.status_code, 404)

    def test_update_non_existent_draft_section_returns_404(self, data_api_client, s3):
        data_api_client.get_draft_service.return_value = self.empty_draft
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/submissions/1/edit/invalid_section'
        )
        assert_equal(404, res.status_code)


@mock.patch('app.main.views.services.data_api_client')
class TestShowDraftService(BaseApplicationTest):

    draft_service = {
        'services': {
            'id': 1,
            'supplierId': 1234,
            'supplierName': "supplierName",
            'lot': "SCS",
            'status': "not-submitted",
            'frameworkName': "frameworkName",
            'priceMin': '12.50',
            'priceMax': '15',
            'priceUnit': 'Person',
            'priceInterval': 'Second',
            'links': {},
            'updatedAt': "2015-06-29T15:26:07.650368Z"
        },
        'auditEvents': {
            'createdAt': "2015-06-29T15:26:07.650368Z",
            'userName': "Supplier User",

        }
    }

    complete_service = copy.deepcopy(draft_service)
    complete_service['services']['status'] = 'submitted'
    complete_service['services']['id'] = 2

    def setup(self):
        super(TestShowDraftService, self).setup()
        with self.app.test_client():
            self.login()

    def test_service_price_is_correctly_formatted(self, data_api_client):
        data_api_client.get_draft_service.return_value = self.draft_service
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/1')
        document = html.fromstring(res.get_data(as_text=True))

        assert_equal(res.status_code, 200)
        service_price_row_xpath = '//tr[contains(.//span/text(), "Service price")]'
        service_price_xpath = service_price_row_xpath + '/td[@class="summary-item-field"]/span/text()'
        assert_equal(
            document.xpath(service_price_xpath)[0].strip(),
            u"£12.50 to £15 per person per second")

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_unanswered_questions_count(self, count_unanswered, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.draft_service
        count_unanswered.return_value = 1, 2
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/1')

        assert_true(u'3 unanswered questions' in res.get_data(as_text=True),
                    "'3 unanswered questions' not found in html")

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_move_to_complete_button(self, count_unanswered, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.draft_service
        count_unanswered.return_value = 0, 1
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/1')

        assert_in(u'1 optional question unanswered', res.get_data(as_text=True))
        assert_in(u'<input type="submit" class="button-save"  value="Mark as complete" />',
                  res.get_data(as_text=True))

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_no_move_to_complete_button_if_not_open(self, count_unanswered, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='other')
        data_api_client.get_draft_service.return_value = self.draft_service
        count_unanswered.return_value = 0, 1
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/1')

        assert_not_in(u'<input type="submit" class="button-save"  value="Mark as complete" />',
                      res.get_data(as_text=True))

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_shows_g7_message_if_pending_and_service_is_in_draft(self, count_unanswered, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='pending')
        data_api_client.get_draft_service.return_value = self.draft_service
        count_unanswered.return_value = 3, 1
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/1')

        doc = html.fromstring(res.get_data(as_text=True))
        message = doc.xpath('//aside[@class="temporary-message"]')

        assert_true(len(message) > 0)
        assert_in(u"This service was not submitted",
                  message[0].xpath('h2[@class="temporary-message-heading"]/text()')[0])
        assert_in(u"It wasn't marked as complete at the deadline.",
                  message[0].xpath('p[@class="temporary-message-message"]/text()')[0])

    @mock.patch('app.main.views.services.count_unanswered_questions')
    def test_shows_g7_message_if_pending_and_service_is_complete(self, count_unanswered, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='pending')
        data_api_client.get_draft_service.return_value = self.complete_service
        count_unanswered.return_value = 0, 1
        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/2')

        doc = html.fromstring(res.get_data(as_text=True))
        message = doc.xpath('//aside[@class="temporary-message"]')

        assert_true(len(message) > 0)
        assert_in(u"This service was submitted",
                  message[0].xpath('h2[@class="temporary-message-heading"]/text()')[0])
        assert_in(u"If your application is successful, it will be available on the Digital Marketplace when G-Cloud 7 goes live.",  # noqa
                  message[0].xpath('p[@class="temporary-message-message"]/text()')[0])


@mock.patch('app.main.views.services.data_api_client')
class TestDeleteDraftService(BaseApplicationTest):

    draft_to_delete = {
        'services': {
            'id': 1,
            'supplierId': 1234,
            'supplierName': "supplierName",
            'lot': "SCS",
            'status': "not-submitted",
            'frameworkSlug': 'g-slug',
            'frameworkName': "frameworkName",
            'links': {},
            'serviceName': 'My rubbish draft',
            'serviceSummary': 'This is the worst service ever',
            'updatedAt': "2015-06-29T15:26:07.650368Z"
        },
        'auditEvents': {
            'createdAt': "2015-06-29T15:26:07.650368Z",
            'userName': "Supplier User",
        }
    }

    def setup(self):
        super(TestDeleteDraftService, self).setup()
        with self.app.test_client():
            self.login()

    def test_delete_button_redirects_with_are_you_sure(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.draft_to_delete
        res = self.client.post(
            '/suppliers/submission/services/1/delete',
            data={})
        assert_equal(res.status_code, 302)
        assert_equal(
            res.location,
            'http://localhost/suppliers/frameworks/g-cloud-7/submissions/1?delete_requested=True'
        )
        res2 = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/1?delete_requested=True')
        assert_in(
            b"Are you sure you want to delete this service?", res2.get_data()
        )

    def test_cannot_delete_if_not_open(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='other')
        data_api_client.get_draft_service.return_value = self.draft_to_delete
        res = self.client.post(
            '/suppliers/submission/services/1/delete',
            data={})
        assert_equal(res.status_code, 404)

    def test_confirm_delete_button_deletes_and_redirects_to_dashboard(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_draft_service.return_value = self.draft_to_delete
        res = self.client.post(
            '/suppliers/submission/services/1/delete',
            data={'delete_confirmed': 'true'})

        data_api_client.delete_draft_service.assert_called_with('1', 'email@email.com')
        assert_equal(res.status_code, 302)
        assert_equal(
            res.location,
            'http://localhost/suppliers/frameworks/g-cloud-7/services'
        )

    def test_cannot_delete_other_suppliers_draft(self, data_api_client):
        other_draft = copy.deepcopy(self.draft_to_delete)
        other_draft['services']['supplierId'] = 12345
        data_api_client.get_draft_service.return_value = other_draft
        res = self.client.post(
            '/suppliers/submission/services/1/delete',
            data={'delete_confirmed': 'true'})

        assert_equal(res.status_code, 404)


@mock.patch('dmutils.s3.S3')
class TestSubmissionDocuments(BaseApplicationTest):
    def setup(self):
        super(TestSubmissionDocuments, self).setup()
        with self.app.test_client():
            self.login()

    def test_document_url(self, s3):
        s3.return_value.get_signed_url.return_value = 'http://example.com/document.pdf'

        res = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/documents/1234/document.pdf'
        )

        assert_equal(res.status_code, 302)
        assert_equal(res.headers['Location'], 'http://localhost/document.pdf')

    def test_missing_document_url(self, s3):
        s3.return_value.get_signed_url.return_value = None

        res = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/documents/1234/document.pdf'
        )

        assert_equal(res.status_code, 404)

    def test_document_url_not_matching_user_supplier(self, s3):
        res = self.client.get(
            '/suppliers/frameworks/g-cloud-7/submissions/documents/999/document.pdf'
        )

        assert_equal(res.status_code, 404)
