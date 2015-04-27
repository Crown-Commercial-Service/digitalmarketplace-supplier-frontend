from mock import Mock
from nose.tools import assert_equal, assert_true
from app import api_client
from tests.app.helpers import BaseApplicationTest


class TestDashboard(BaseApplicationTest):
    def test_should_show_dashboard_if_logged_in(self):
        with self.app.test_client() as c:
            api_client.users_auth = Mock(
                return_value=(self.user(123, "email@email.com")))

            api_client.user_by_id = Mock(
                return_value=(self.user(123, "email@email.com")))

            self.client.post("/suppliers/login", data={
                'email_address': 'valid@email.com',
                'password': '1234567890'
            })

            res = self.client.get('/suppliers/dashboard')

            assert_equal(res.status_code, 200)

            assert_true(
                self.strip_all_whitespace('<h1>Dashboard</h1>')
                in self.strip_all_whitespace(res.get_data(as_text=True))
            )

    def test_should_redirect_to_login_if_not_logged_in(self):
        res = self.client.get("/suppliers/dashboard")
        assert_equal(res.status_code, 302)
        assert_equal(res.location,
                     'http://localhost/suppliers/login'
                     '?next=%2Fsuppliers%2Fdashboard')


class TestServices(BaseApplicationTest):
    def test_should_show_dashboard_if_logged_in(self):
        with self.app.test_client() as c:
            api_client.users_auth = Mock(
                return_value=(self.user(123, "email@email.com")))

            api_client.user_by_id = Mock(
                return_value=(self.user(123, "email@email.com")))

            self.client.post("/suppliers/login", data={
                'email_address': 'valid@email.com',
                'password': '1234567890'
            })

            res = self.client.get('/suppliers/services')

            assert_equal(res.status_code, 200)

            assert_true(
                self.strip_all_whitespace('<h1>Service</h1>')
                in self.strip_all_whitespace(res.get_data(as_text=True))
            )

    def test_should_redirect_to_login_if_not_logged_in(self):
        res = self.client.get("/suppliers/services")
        assert_equal(res.status_code, 302)
        assert_equal(res.location,
                     'http://localhost/suppliers/login'
                     '?next=%2Fsuppliers%2Fservices')
