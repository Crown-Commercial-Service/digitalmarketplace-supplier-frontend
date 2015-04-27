from nose.tools import assert_equal, assert_true, \
    assert_is_not_none
from app.model import User
from ..helpers import BaseApplicationTest
from mock import Mock
import re
from app import api_client


class TestLogin(BaseApplicationTest):
    email_head_error = '<a href="#example-textbox" class="validation-masthead-link">' \
                       '<label for="email_address">Email address</label></a>'
    email_field_error = '<p class="validation-message" ' \
                        'id="error-email-address-textbox">' \
                        'This field is required.</p>'
    invalid_email_field_error = '<p class="validation-message" ' \
                                'id="error-email-address-textbox">' \
                                'Invalid email address.</p>'
    password_head_error = '<a href="#example-textbox" class="validation-masthead-link">' \
                          '<label for="password">Password</label></a>'
    password_field_error = '<p class="validation-message" ' \
                           'id="error-password-textbox">' \
                           'This field is required.</p>'

    def test_should_show_login_page(self):
        res = self.client.get("/suppliers/login")
        assert_equal(res.status_code, 200)
        assert_true("<h1>Login</h1>" in res.get_data(as_text=True))

    def test_should_redirect_to_dashboard_on_login(self):
        api_client.users_auth = Mock(
            return_value=(self.user(123, "email@email.com", 1234, 'name')))
        res = self.client.post("/suppliers/login", data={
            'email_address': 'valid@email.com',
            'password': '1234567890'
        })
        assert_equal(res.status_code, 302)
        assert_equal(res.location, 'http://localhost/suppliers/dashboard')

    def test_should_have_cookie_on_redirect(self):
        with self.app.app_context():
            self.app.config['SESSION_COOKIE_DOMAIN'] = '127.0.0.1'
            self.app.config['SESSION_COOKIE_SECURE'] = True
            api_client.users_auth = Mock(
                return_value=(self.user(123, "email@email.com", 1234, 'name')))
            res = self.client.post("/suppliers/login", data={
                'email_address': 'valid@email.com',
                'password': '1234567890'
            })
            cookie_value = self.get_cookie_by_name(res, 'dm_session')
            assert_is_not_none(cookie_value['dm_session'])
            assert_equal(cookie_value['Secure; HttpOnly; Path'], '/')
            assert_equal(cookie_value["Domain"], "127.0.0.1")

    def test_should_redirect_to_login_on_logout(self):
        res = self.client.get('/suppliers/logout')
        assert_equal(res.status_code, 302)
        assert_equal(res.location, 'http://localhost/suppliers/login')

    def test_should_return_a_403_for_invalid_login(self):
        api_client.users_auth = Mock(
            return_value=None)
        res = self.client.post("/suppliers/login", data={
            'email_address': 'valid@email.com',
            'password': '1234567890'
        })
        assert_true(
            self.strip_all_whitespace("Sorry, we couldn&#39;t find a "
                                      "user with that username and password")
            in self.strip_all_whitespace(res.get_data(as_text=True)))
        assert_equal(res.status_code, 403)

    def test_should_be_validation_error_if_no_email_or_password(self):
        res = self.client.post("/suppliers/login", data={})
        assert_equal(res.status_code, 400)
        assert_true(
            self.strip_all_whitespace(self.email_head_error)
            in self.strip_all_whitespace(res.get_data(as_text=True)))
        assert_true(
            self.strip_all_whitespace(self.email_field_error)
            in self.strip_all_whitespace(res.get_data(as_text=True)))
        assert_true(
            self.strip_all_whitespace(self.password_head_error)
            in self.strip_all_whitespace(res.get_data(as_text=True)))
        assert_true(
            self.strip_all_whitespace(self.password_field_error)
            in self.strip_all_whitespace(res.get_data(as_text=True)))

    def test_should_be_validation_error_if_invalid_email(self):
        res = self.client.post("/suppliers/login", data={
            'email_address': 'invalid',
            'password': '1234567890'
        })
        assert_equal(res.status_code, 400)
        assert_true(
            self.strip_all_whitespace(self.email_head_error)
            in self.strip_all_whitespace(res.get_data(as_text=True)))
        assert_true(
            self.strip_all_whitespace(self.invalid_email_field_error)
            in self.strip_all_whitespace(res.get_data(as_text=True)))
