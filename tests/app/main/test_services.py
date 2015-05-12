from mock import Mock
from app import data_api_client
from nose.tools import assert_equal, assert_true
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
                    'frameworkName': 'G-Cloud 6'
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
