from mock import Mock
import mock
from app import data_api_client
from nose.tools import assert_equal, assert_true, assert_false
from tests.app.helpers import BaseApplicationTest


class TestDashboardContent(BaseApplicationTest):
    def test_shows_no_services_message(self):
        with self.app.test_client():
            self.login()

            data_api_client.find_services = Mock(
                return_value={
                    "services": []
                })

            res = self.client.get('/suppliers/')
            assert_equal(res.status_code, 200)
            data_api_client.find_services.assert_called_once_with(
                supplier_id=1234)
            assert_true("You don't have any services"
                        in res.get_data(as_text=True))

    def test_shows_services_on_dashboard(self):
        with self.app.test_client():
            self.login()

            data_api_client.find_services = Mock(
                return_value={'services': [{
                    'serviceName': 'Service name 123',
                    'status': 'published',
                    'id': '123',
                    'lot': 'SaaaaaaaS',
                    'frameworkName': 'G-Cloud 1'
                }]}
            )

            res = self.client.get('/suppliers/')
            assert_equal(res.status_code, 200)
            data_api_client.find_services.assert_called_once_with(
                supplier_id=1234)
            assert_true("Service name 123" in res.get_data(as_text=True))
            assert_true("SaaaaaaaS" in res.get_data(as_text=True))
            assert_true("G-Cloud 1" in res.get_data(as_text=True))

    def test_shows_services_edit_button_with_id_on_dashboard(self):
        with self.app.test_client():
            self.login()

            data_api_client.find_services = Mock(
                return_value={'services': [{
                    'serviceName': 'Service name 123',
                    'status': 'published',
                    'id': '123'
                }]}
            )

            res = self.client.get('/suppliers/')
            assert_equal(res.status_code, 200)
            data_api_client.find_services.assert_called_once_with(
                supplier_id=1234)
            assert_true(
                "/suppliers/services/123" in res.get_data(as_text=True))

    def login(self):
        data_api_client.authenticate_user = Mock(
            return_value=(self.user(
                123, "email@email.com", 1234, 'Supplier Name')))

        data_api_client.get_user = Mock(
            return_value=(self.user(
                123, "email@email.com", 1234, 'Supplier Name')))

        self.client.post("/suppliers/login", data={
            'email_address': 'valid@email.com',
            'password': '1234567890'
        })

        data_api_client.authenticate_user.assert_called_once_with(
            "valid@email.com", "1234567890")


class TestDashboardLogin(BaseApplicationTest):
    def test_should_show_dashboard_if_logged_in(self):
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

            res = self.client.get('/suppliers/')

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
        res = self.client.get("/suppliers/")
        assert_equal(res.status_code, 302)
        assert_equal(res.location,
                     'http://localhost/suppliers/login'
                     '?next=%2Fsuppliers%2F')


class TestServicesLogin(BaseApplicationTest):
    def test_should_show_dashboard_if_logged_in(self):
        with self.app.test_client():
            data_api_client.authenticate_user = Mock(
                return_value=(self.user(123, "email@email.com", 1234, 'name')))

            data_api_client.get_user = Mock(
                return_value=(self.user(123, "email@email.com", 1234, 'name')))

            data_api_client.get_service = Mock(
                return_value={'services': {
                    'serviceName': 'Service name 123',
                    'status': 'published',
                    'id': '123',
                    'frameworkName': 'G-Cloud 6',
                    'supplierId': 1234
                }})

            self.client.post("/suppliers/login", data={
                'email_address': 'valid@email.com',
                'password': '1234567890'
            })

            res = self.client.get('/suppliers/services/123')

            assert_equal(res.status_code, 200)

            assert_true(
                self.strip_all_whitespace('<p class="context">Edit</p>')
                in self.strip_all_whitespace(res.get_data(as_text=True))
            )
            assert_true(
                'Service name 123' in res.get_data(as_text=True)
            )

    def test_should_redirect_to_login_if_not_logged_in(self):
        res = self.client.get("/suppliers/services/123")
        assert_equal(res.status_code, 302)
        assert_equal(res.location,
                     'http://localhost/suppliers/login'
                     '?next=%2Fsuppliers%2Fservices%2F123')


@mock.patch('app.main.services.data_api_client')
class TestSupplierUpdateService(BaseApplicationTest):

    def _add_user_and_service(
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
            'service_status': status,
        })
        assert_equal(res.status_code, expected_status_code)

    def _post_status_updates(
            self,
            service_should_be_modifiable=True
    ):
        expected_status_code = 302 if service_should_be_modifiable else 400

        # Should work if service not removed/disabled or another supplier's
        self._post_status_update('private', expected_status_code)
        self._post_status_update('public', expected_status_code)

        # Database statuses should not work
        self._post_status_update('published', 400)
        self._post_status_update('enabled', 400)

        # Removing a service should be impossible
        self._post_status_update('removed', 400)
        self._post_status_update('disabled', 400)

        # non-statuses should not work
        self._post_status_update('orange', 400)
        self._post_status_update('banana', 400)

    def test_should_view_public_service_with_correct_input_checked(
            self, data_api_client
    ):
        self._add_user_and_service(
            data_api_client,
            service_status='published'
        )

        res = self.client.get('/suppliers/services/123')
        assert_equal(res.status_code, 200)

        # check that 'public' is selected.
        assert_true(
            '<input type="radio" name="service_status" id="service_status_published" value="public" checked'  # noqa
            in res.get_data(as_text=True)
        )
        assert_false(
            '<input type="radio" name="service_status" id="service_status_private" value="private" checked'  # noqa
            in res.get_data(as_text=True)
        )

        self._post_status_updates(
            service_should_be_modifiable=True
        )

    def test_should_view_private_service_with_correct_input_checked(
            self, data_api_client
    ):
        self._add_user_and_service(
            data_api_client,
            service_status='enabled'
        )

        res = self.client.get('/suppliers/services/123')
        assert_equal(res.status_code, 200)

        # check that 'public' is not selected.
        assert_false(
            '<input type="radio" name="service_status" id="service_status_published" value="public" checked'  # noqa
            in res.get_data(as_text=True)
        )
        assert_true(
            '<input type="radio" name="service_status" id="service_status_private" value="private" checked'  # noqa
            in res.get_data(as_text=True)
        )

        self._post_status_updates(
            service_should_be_modifiable=True
        )

    def test_should_view_disabled_service_with_removed_message(
            self, data_api_client
    ):
        self._add_user_and_service(
            data_api_client,
            service_status='disabled'
        )

        res = self.client.get('/suppliers/services/123')
        assert_equal(res.status_code, 200)

        assert_true(
            'This service has been removed'
            in res.get_data(as_text=True)
        )

        self._post_status_updates(
            service_should_be_modifiable=False
        )

    def test_should_not_view_other_suppliers_services(self, data_api_client):
        self._add_user_and_service(
            data_api_client,
            service_status='published',
            service_belongs_to_user=False
        )

        res = self.client.get('/suppliers/services/123')
        assert_equal(res.status_code, 404)

        # Should all be 404 if service doesn't belong to supplier
        self._post_status_update('public', 404)
        self._post_status_update('published', 404)
        self._post_status_update('watermelon', 404)
