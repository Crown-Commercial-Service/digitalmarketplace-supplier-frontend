from mock import Mock
from nose.tools import assert_equal, assert_true
from app import api_client
from tests.app.helpers import BaseApplicationTest


class TestDashboardContent(BaseApplicationTest):
    def test_shows_no_services_message(self):
        with self.app.test_client():
            self.login()

            api_client.services_by_supplier_id = Mock(
                return_value={
                    "services": []
                })

            res = self.client.get('/suppliers/dashboard')
            assert_equal(res.status_code, 200)
            assert_true("You haven't submitted any services yet."
                        in res.get_data(as_text=True))

    def test_shows_services_on_dashboard(self):
        with self.app.test_client():
            self.login()

            api_client.services_by_supplier_id = Mock(
                return_value=self.services()
            )

            res = self.client.get('/suppliers/dashboard')
            assert_equal(res.status_code, 200)
            assert_true("serviceName" in res.get_data(as_text=True))
            assert_true("lot" in res.get_data(as_text=True))
            assert_true("frameworkName" in res.get_data(as_text=True))

    def test_shows_services_edit_button_with_id_on_dashboard(self):
        with self.app.test_client():
            self.login()

            api_client.services_by_supplier_id = Mock(
                return_value=self.services()
            )

            res = self.client.get('/suppliers/dashboard')
            assert_equal(res.status_code, 200)
            assert_true("/suppliers/services/id" in res.get_data(as_text=True))

    def login(self):
        api_client.users_auth = Mock(
            return_value=(self.user(
                123, "email@email.com", 1234, 'Supplier Name')))

        api_client.user_by_id = Mock(
            return_value=(self.user(
                123, "email@email.com", 1234, 'Supplier Name')))

        self.client.post("/suppliers/login", data={
            'email_address': 'valid@email.com',
            'password': '1234567890'
        })


class TestDashboardLogin(BaseApplicationTest):
    def test_should_show_dashboard_if_logged_in(self):
        with self.app.test_client():
            api_client.users_auth = Mock(
                return_value=(self.user(
                    123, "email@email.com", 1234, 'Supplier Name')))

            api_client.user_by_id = Mock(
                return_value=(self.user(
                    123, "email@email.com", 1234, 'Supplier Name')))

            api_client.services_by_supplier_id = Mock(
                return_value=self.services())

            self.client.post("/suppliers/login", data={
                'email_address': 'valid@email.com',
                'password': '1234567890'
            })

            res = self.client.get('/suppliers/dashboard')

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
        res = self.client.get("/suppliers/dashboard")
        assert_equal(res.status_code, 302)
        assert_equal(res.location,
                     'http://localhost/suppliers/login'
                     '?next=%2Fsuppliers%2Fdashboard')


class TestServicesLogin(BaseApplicationTest):
    def test_should_show_dashboard_if_logged_in(self):
        with self.app.test_client() as c:
            api_client.users_auth = Mock(
                return_value=(self.user(123, "email@email.com", 1234, 'name')))

            api_client.user_by_id = Mock(
                return_value=(self.user(123, "email@email.com", 1234, 'name')))

            self.client.post("/suppliers/login", data={
                'email_address': 'valid@email.com',
                'password': '1234567890'
            })

            res = self.client.get('/suppliers/services/123')

            assert_equal(res.status_code, 200)

            assert_true(
                self.strip_all_whitespace('<h1>Service</h1>')
                in self.strip_all_whitespace(res.get_data(as_text=True))
            )
            assert_true(
                'Service Details for 123' in res.get_data(as_text=True)
            )

    def test_should_redirect_to_login_if_not_logged_in(self):
        res = self.client.get("/suppliers/services/123")
        assert_equal(res.status_code, 302)
        assert_equal(res.location,
                     'http://localhost/suppliers/login'
                     '?next=%2Fsuppliers%2Fservices%2F123')
