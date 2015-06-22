import mock
from mock import Mock
from nose.tools import assert_equal, assert_true, assert_false, \
    assert_in, assert_not_in
from tests.app.helpers import BaseApplicationTest
from dmutils.content_loader import ContentLoader

content = ContentLoader(
    "app/section_order.yml",
    "app/content/g6/"
)


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
            assert_true("You don't have any services"
                        in res.get_data(as_text=True))

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
                self.strip_all_whitespace('<h1>Supplier Name</h1>')
                in self.strip_all_whitespace(res.get_data(as_text=True))
            )
            assert_true(
                self.strip_all_whitespace('email@email.com')
                in self.strip_all_whitespace(res.get_data(as_text=True))
            )

    def test_should_redirect_to_login_if_not_logged_in(self):
        res = self.client.get("/suppliers/services")
        assert_equal(res.status_code, 302)
        assert_equal(res.location,
                     'http://localhost/suppliers/login'
                     '?next=%2Fsuppliers%2Fservices')


@mock.patch('app.main.services.data_api_client')
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


@mock.patch('app.main.services.request')
class TestCreateService(BaseApplicationTest):

    def setup(self):
        super(TestCreateService, self).setup()
        self._answer_required = 'Answer is required'
        self._validation_error = \
            'There was a problem with your answer to the following questions'

    @staticmethod
    def _format_for_request(phrase):
        return phrase.replace(' ', '+')

    def _test_get_create_service_page(self, if_error_expected):
        with self.app.test_client():
            self.login()

        res = self.client.get('/suppliers/submission/g-cloud-7/create')
        assert_equal(res.status_code, 200)
        assert_true("Create new service"
                    in res.get_data(as_text=True))

        lots = content.get_question('lot')

        for lot in lots['options']:
            assert_true(lot['label'] in res.get_data(as_text=True))

        if if_error_expected:
            assert_in(self._validation_error, res.get_data(as_text=True))
        else:
            assert_not_in(self._validation_error, res.get_data(as_text=True))

    def _test_post_create_service(self, if_error_expected):
        with self.app.test_client():
            self.login()

        res = self.client.post(
            '/suppliers/submission/g-cloud-7/create',
        )

        assert_equal(res.status_code, 302)

        error_message = '?error={}'.format(
            self._format_for_request(self._answer_required)
        )

        if if_error_expected:
            assert_in(error_message, res.location)
        else:
            assert_not_in(error_message, res.location)

    def test_get_create_service_page_succeeds(self, request):
        request.args.get.return_value = None
        self._test_get_create_service_page(if_error_expected=False)

    def test_get_create_service_page_fails(self, request):
        request.args.get.return_value = self._answer_required
        self._test_get_create_service_page(if_error_expected=True)

    def test_post_create_service_with_lot_selected_succeeds(self, request):
        request.form.get.return_value = "IaaS"
        self._test_post_create_service(if_error_expected=False)

    def test_post_create_service_without_lot_selected_fails(self, request):
        request.form.get.return_value = None
        self._test_post_create_service(if_error_expected=True)
