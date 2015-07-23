from dmutils.apiclient import HTTPError
import mock
from lxml import html
from mock import Mock
from nose.tools import assert_equal, assert_true, assert_false, \
    assert_in, assert_not_in
from tests.app.helpers import BaseApplicationTest
from app.main import new_service_content


class TestListServices(BaseApplicationTest):
    @mock.patch('app.main.views.services.data_api_client')
    def test_shows_no_services_message(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.find_services = Mock(
                return_value={
                    "services": []
                })

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

            data_api_client.find_services = Mock(
                return_value={'services': [{
                    'serviceName': 'Service name 123',
                    'status': 'published',
                    'id': '123',
                    'lot': 'SaaS',
                    'frameworkName': 'G-Cloud 1'
                }]}
            )

            res = self.client.get('/suppliers/services')
            assert_equal(res.status_code, 200)
            data_api_client.find_services.assert_called_once_with(
                supplier_id=1234)
            assert_true("Service name 123" in res.get_data(as_text=True))
            assert_true("SaaS" in res.get_data(as_text=True))
            assert_true("G-Cloud 1" in res.get_data(as_text=True))

    @mock.patch('app.main.views.services.data_api_client')
    def test_shows_services_edit_button_with_id(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.find_services = Mock(
                return_value={'services': [{
                    'serviceName': 'Service name 123',
                    'status': 'published',
                    'id': '123'
                }]}
            )

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
            data_api_client.authenticate_user = Mock(
                return_value=(self.user(
                    123, "email@email.com", 1234, 'Supplier Name')))

            data_api_client.get_user = Mock(
                return_value=(self.user(
                    123, "email@email.com", 1234, 'Supplier Name')))

            data_api_client.find_services = Mock(
                return_value={'services': [{
                    'serviceName': 'Service name 123',
                    'status': 'published',
                    'id': '123'
                }]}
            )

            self.client.post("/suppliers/login", data={
                'email_address': 'valid@email.com',
                'password': '1234567890'
            })

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

    def _login(
            self,
            data_api_client,
            service_status="published",
            service_belongs_to_user=True
    ):

        data_api_client.authenticate_user.return_value = self.user(
            123, "email@email.com", 1234, 'name'
        )

        data_api_client.get_user.return_value = self.user(
            123, "email@email.com", 1234, 'name'
        )

        data_api_client.get_service.return_value = {
            'services': {
                'serviceName': 'Service name 123',
                'status': service_status,
                'id': '123',
                'frameworkName': 'G-Cloud 6',
                'supplierId': 1234 if service_belongs_to_user else 1235
            }
        }

        self.client.post("/suppliers/login", data={
            'email_address': 'email@email.com',
            'password': '1234567890'
        })

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
        self._login(
            data_api_client,
            service_status='published'
        )

        res = self.client.get('/suppliers/services/123')
        assert_equal(res.status_code, 200)
        assert_true(
            'Service name 123' in res.get_data(as_text=True)
        )

        # check that 'public' is selected.
        assert_true(
            '<input type="radio" name="status" id="status-1" value="Public" checked="checked"'  # noqa
            in res.get_data(as_text=True)
        )
        assert_false(
            '<input type="radio" name="status" id="status-2" value="Private" checked="checked"'  # noqa
            in res.get_data(as_text=True)
        )

        self._post_status_updates(
            service_should_be_modifiable=True
        )

    def test_should_view_private_service_with_correct_input_checked(
            self, data_api_client
    ):
        self._login(
            data_api_client,
            service_status='enabled'
        )

        res = self.client.get('/suppliers/services/123')
        assert_equal(res.status_code, 200)
        assert_true(
            'Service name 123' in res.get_data(as_text=True)
        )

        # check that 'public' is not selected.
        assert_false(
            '<input type="radio" name="status" id="status-1" value="Public" checked="checked"'  # noqa
            in res.get_data(as_text=True)
        )
        assert_true(
            '<input type="radio" name="status" id="status-2" value="Private" checked="checked"'  # noqa
            in res.get_data(as_text=True)
        )

        self._post_status_updates(
            service_should_be_modifiable=True
        )

    def test_should_view_disabled_service_with_removed_message(
            self, data_api_client
    ):
        self._login(
            data_api_client,
            service_status='disabled'
        )

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
        self._login(
            data_api_client,
            service_status='published',
            service_belongs_to_user=False
        )

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

    def test_edit_section_contains_hidden_page_questions(self):
        with mock.patch('app.main.views.services.data_api_client') as data_api_client:
            data_api_client.get_service.return_value = self.empty_service
            res = self.client.get('/suppliers/services/1/edit/description')

            assert_equal(res.status_code, 200)
            document = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                'serviceName|serviceSummary',
                document.xpath('//input[@name="page_questions"]/@value')[0])

    def test_edit_non_existent_service_returns_404(self):
        with mock.patch('app.main.views.services.data_api_client') as data_api_client:
            data_api_client.get_service.return_value = None
            res = self.client.get('/suppliers/services/1/edit/description')

            assert_equal(res.status_code, 404)

    def test_edit_non_existent_section_returns_404(self):
        with mock.patch('app.main.views.services.data_api_client') as data_api_client:
            data_api_client.get_service.return_value = self.empty_service
            res = self.client.get(
                '/suppliers/services/1/edit/invalid_section'
            )
            assert_equal(404, res.status_code)

    def test_update_with_answer_required_error(self):
        with mock.patch('app.main.views.services.data_api_client') as data_api_client:
            data_api_client.get_service.return_value = self.empty_service
            data_api_client.update_service.side_effect = HTTPError(
                mock.Mock(status_code=400),
                {'serviceSummary': 'answer_required'})
            res = self.client.post(
                '/suppliers/services/1/edit/description',
                data={
                    'page_questions': '',
                })

            assert_equal(res.status_code, 200)
            document = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                "This question requires an answer.",
                document.xpath('//span[@id="error-serviceSummary"]/text()')[0].strip())

    def test_update_with_under_50_words_error(self):
        with mock.patch('app.main.views.services.data_api_client') as data_api_client:
            data_api_client.get_service.return_value = self.empty_service
            data_api_client.update_service.side_effect = HTTPError(
                mock.Mock(status_code=400),
                {'serviceSummary': 'under_50_words'})
            res = self.client.post(
                '/suppliers/services/1/edit/description',
                data={
                    'page_questions': '',
                })

            assert_equal(res.status_code, 200)
            document = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                "Your description must not be more than 50 words.",
                document.xpath('//span[@id="error-serviceSummary"]/text()')[0].strip())

    def test_update_non_existent_service_returns_404(self):
        with mock.patch('app.main.views.services.data_api_client') as data_api_client:
            data_api_client.get_service.return_value = None
            res = self.client.post('/suppliers/services/1/edit/description')

            assert_equal(res.status_code, 404)

    def test_update_non_existent_section_returns_404(self):
        with mock.patch('app.main.views.services.data_api_client') as data_api_client:
            data_api_client.get_service.return_value = self.empty_service
            res = self.client.post(
                '/suppliers/services/1/edit/invalid_section'
            )
            assert_equal(404, res.status_code)


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

    def _test_get_create_draft_service_page(self, if_error_expected):
        with self.app.test_client():
            self.login()

        res = self.client.get('/suppliers/submission/g-cloud-7/create')
        assert_equal(res.status_code, 200 if not if_error_expected else 400)
        assert_true("Create new service"
                    in res.get_data(as_text=True))

        lots = new_service_content.get_question('lot')

        for lot in lots['options']:
            assert_true(lot['label'] in res.get_data(as_text=True))

        if if_error_expected:
            assert_in(self._validation_error, res.get_data(as_text=True))
        else:
            assert_not_in(self._validation_error, res.get_data(as_text=True))

    def _test_post_create_draft_service(self, if_error_expected):
        with self.app.test_client():
            self.login()

        with mock.patch('app.main.views.services.data_api_client') \
                as data_api_client:

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
                '/suppliers/submission/g-cloud-7/create'
            )

            assert_equal(res.status_code, 302)

            error_message = '?error={}'.format(
                self._format_for_request(self._answer_required)
            )

            if if_error_expected:
                assert_in(error_message, res.location)
            else:
                assert_not_in(error_message, res.location)

    def test_get_create_draft_service_page_succeeds(self, request):
        request.args.get.return_value = None
        self._test_get_create_draft_service_page(if_error_expected=False)

    def test_get_create_draft_service_page_fails(self, request):
        request.args.get.return_value = self._answer_required
        self._test_get_create_draft_service_page(if_error_expected=True)

    def test_post_create_draft_service_with_lot_selected_succeeds(self, request):
        request.form.get.return_value = "SCS"
        self._test_post_create_draft_service(if_error_expected=False)

    def test_post_create_draft_service_without_lot_selected_fails(self, request):
        request.form.get.return_value = None
        self._test_post_create_service(if_error_expected=True)


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

    def test_copy_draft(self, api_client):
        api_client.get_draft_service.return_value = {'services': self.draft}

        res = self.client.post('/suppliers/submission/services/1/copy')
        assert_equal(res.status_code, 302)

    def test_copy_draft_checks_supplier_id(self, api_client):
        self.draft['supplierId'] = 2
        api_client.get_draft_service.return_value = {'services': self.draft}

        res = self.client.post('/suppliers/submission/services/1/copy')
        assert_equal(res.status_code, 404)


class TestEditDraftService(BaseApplicationTest):

    empty_draft = {
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

    def setup(self):
        super(TestEditDraftService, self).setup()
        with self.app.test_client():
            self.login()

    def test_edit_draft_section_contains_hidden_page_questions(self):
        with mock.patch('app.main.views.services.data_api_client') as data_api_client:
            data_api_client.get_draft_service.return_value = self.empty_draft
            res = self.client.get('/suppliers/submission/services/1/edit/service_description')

            assert_equal(res.status_code, 200)
            document = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                'serviceName|serviceSummary',
                document.xpath('//input[@name="page_questions"]/@value')[0])

    def test_edit_non_existent_draft_service_returns_404(self):
        with mock.patch('app.main.views.services.data_api_client') as data_api_client:
            data_api_client.get_draft_service.side_effect = HTTPError(mock.Mock(status_code=404))
            res = self.client.get('/suppliers/submission/services/1/edit/service_description')

            assert_equal(res.status_code, 404)

    def test_edit_non_existent_draft_section_returns_404(self):
        with mock.patch('app.main.views.services.data_api_client') as data_api_client:
            data_api_client.get_draft_service.return_value = self.empty_draft
            res = self.client.get(
                '/suppliers/submission/services/1/edit/invalid_section'
            )
            assert_equal(404, res.status_code)

    def test_update_with_answer_required_error(self):
        with mock.patch('app.main.views.services.data_api_client') as data_api_client:
            data_api_client.get_draft_service.return_value = self.empty_draft
            data_api_client.update_draft_service.side_effect = HTTPError(
                mock.Mock(status_code=400),
                {'serviceSummary': 'answer_required'})
            res = self.client.post(
                '/suppliers/submission/services/1/edit/service_description',
                data={
                    'page_questions': '',
                })

            assert_equal(res.status_code, 200)
            document = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                "This question requires an answer.",
                document.xpath('//span[@id="error-serviceSummary"]/text()')[0].strip())

    def test_update_with_under_50_words_error(self):
        with mock.patch('app.main.views.services.data_api_client') as data_api_client:
            data_api_client.get_draft_service.return_value = self.empty_draft
            data_api_client.update_draft_service.side_effect = HTTPError(
                mock.Mock(status_code=400),
                {'serviceSummary': 'under_50_words'})
            res = self.client.post(
                '/suppliers/submission/services/1/edit/service_description',
                data={
                    'page_questions': '',
                })

            assert_equal(res.status_code, 200)
            document = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                "Your description must not be more than 50 words.",
                document.xpath('//span[@id="error-serviceSummary"]/text()')[0].strip())

    def test_update_non_existent_draft_service_returns_404(self):
        with mock.patch('app.main.views.services.data_api_client') as data_api_client:
            data_api_client.get_draft_service.side_effect = HTTPError(mock.Mock(status_code=404))
            res = self.client.post('/suppliers/submission/services/1/edit/service_description')

            assert_equal(res.status_code, 404)

    def test_update_non_existent_draft_section_returns_404(self):
        with mock.patch('app.main.views.services.data_api_client') as data_api_client:
            data_api_client.get_draft_service.return_value = self.empty_draft
            res = self.client.post(
                '/suppliers/submission/services/1/edit/invalid_section'
            )
            assert_equal(404, res.status_code)
