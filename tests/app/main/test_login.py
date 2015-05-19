from app.main import helpers
from nose.tools import assert_equal, assert_true, assert_is_not_none
from ..helpers import BaseApplicationTest
from mock import Mock
from app import data_api_client


EMAIL_EMPTY_ERROR = "Email can not be empty"
EMAIL_INVALID_ERROR = "Please enter a valid email address"
EMAIL_SENT_MESSAGE = "If that Digital Marketplace supplier account exists, " \
                     "you will be sent an email containing a link to reset " \
                     "your password."
PASSWORD_EMPTY_ERROR = "Please enter your password"
PASSWORD_INVALID_ERROR = "Passwords must be between 10 and 50 characters"
PASSWORD_MISMATCH_ERROR = "The passwords you entered do not match"
NEW_PASSWORD_EMPTY_ERROR = "Please enter a new password"
NEW_PASSWORD_CONFIRM_EMPTY_ERROR = "Please confirm your new password"


class TestLogin(BaseApplicationTest):

    def test_should_show_login_page(self):
        res = self.client.get("/suppliers/login")
        assert_equal(res.status_code, 200)
        assert_true("<h1>Supplier login</h1>" in res.get_data(as_text=True))

    def test_should_redirect_to_dashboard_on_login(self):
        data_api_client.authenticate_user = Mock(
            return_value=(self.user(123, "email@email.com", 1234, 'name')))
        res = self.client.post("/suppliers/login", data={
            'email_address': 'valid@email.com',
            'password': '1234567890'
        })
        assert_equal(res.status_code, 302)
        assert_equal(res.location, 'http://localhost/suppliers')

    def test_should_have_cookie_on_redirect(self):
        with self.app.app_context():
            self.app.config['SESSION_COOKIE_DOMAIN'] = '127.0.0.1'
            self.app.config['SESSION_COOKIE_SECURE'] = True
            data_api_client.authenticate_user = Mock(
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
        data_api_client.authenticate_user = Mock(
            return_value=None)
        res = self.client.post("/suppliers/login", data={
            'email_address': 'valid@email.com',
            'password': '1234567890'
        })
        assert_true(
            self.strip_all_whitespace(
                "Sorry, we couldn't find a supplier account with that username"
                "and password."
            )
            in self.strip_all_whitespace(res.get_data(as_text=True)))
        assert_equal(res.status_code, 403)

    def test_should_be_validation_error_if_no_email_or_password(self):
        res = self.client.post("/suppliers/login", data={})
        content = self.strip_all_whitespace(res.get_data(as_text=True))
        assert_equal(res.status_code, 400)
        assert_true(
            self.strip_all_whitespace(EMAIL_EMPTY_ERROR)
            in content)
        assert_true(
            self.strip_all_whitespace(PASSWORD_EMPTY_ERROR)
            in content)

    def test_should_be_validation_error_if_invalid_email(self):
        res = self.client.post("/suppliers/login", data={
            'email_address': 'invalid',
            'password': '1234567890'
        })
        content = self.strip_all_whitespace(res.get_data(as_text=True))
        assert_equal(res.status_code, 400)
        assert_true(
            self.strip_all_whitespace(EMAIL_INVALID_ERROR)
            in content)


class TestForgottenPassword(BaseApplicationTest):

    def test_email_should_not_be_empty(self):
        res = self.client.post("/suppliers/forgotten-password", data={})
        content = self.strip_all_whitespace(res.get_data(as_text=True))
        assert_equal(res.status_code, 400)
        assert_true(
            self.strip_all_whitespace(EMAIL_EMPTY_ERROR)
            in content)

    def test_email_should_be_valid(self):
        res = self.client.post("/suppliers/forgotten-password", data={
            'email_address': 'invalid'
        })
        content = self.strip_all_whitespace(res.get_data(as_text=True))
        assert_equal(res.status_code, 400)
        assert_true(
            self.strip_all_whitespace(EMAIL_INVALID_ERROR)
            in content)

    def test_redirect_to_same_page_on_success(self):
        data_api_client.get_user = Mock(
            return_value=(self.user(123, "email@email.com", 1234, 'name')))
        res = self.client.post("/suppliers/forgotten-password", data={
            'email_address': 'email@email.com'
        })
        assert_equal(res.status_code, 302)
        assert_equal(res.location,
                     'http://localhost/suppliers/forgotten-password')


class TestChangePassword(BaseApplicationTest):

    def test_email_should_be_decoded_from_token(self):
        with self.app.app_context():
            url = helpers.email.generate_reset_url(123, "email@email.com")
        res = self.client.get(url)
        assert_equal(res.status_code, 200)
        assert_true(
            "New password for email@email.com" in res.get_data(as_text=True)
        )

    def test_password_should_not_be_empty(self):
        res = self.client.post("/suppliers/change-password", data={
            'user_id': 123,
            'email_address': 'email@email.com',
            'password': '',
            'confirm_password': ''
        })
        assert_equal(res.status_code, 400)
        assert_true(
            NEW_PASSWORD_EMPTY_ERROR in res.get_data(as_text=True)
        )
        assert_true(
            NEW_PASSWORD_CONFIRM_EMPTY_ERROR in res.get_data(as_text=True)
        )

    def test_password_should_be_over_ten_chars_long(self):
        res = self.client.post("/suppliers/change-password", data={
            'user_id': 123,
            'email_address': 'email@email.com',
            'password': '123456789',
            'confirm_password': '123456789'
        })
        assert_equal(res.status_code, 400)
        assert_true(
            PASSWORD_INVALID_ERROR in res.get_data(as_text=True)
        )

    def test_password_should_be_under_51_chars_long(self):
        res = self.client.post("/suppliers/change-password", data={
            'user_id': 123,
            'email_address': 'email@email.com',
            'password':
                '123456789012345678901234567890123456789012345678901',
            'confirm_password':
                '123456789012345678901234567890123456789012345678901'
        })
        assert_equal(res.status_code, 400)
        assert_true(
            PASSWORD_INVALID_ERROR in res.get_data(as_text=True)
        )

    def test_passwords_should_match(self):
        res = self.client.post("/suppliers/change-password", data={
            'user_id': 123,
            'email_address': 'email@email.com',
            'password': '1234567890',
            'confirm_password': '0123456789'
        })
        assert_equal(res.status_code, 400)
        assert_true(
            PASSWORD_MISMATCH_ERROR in res.get_data(as_text=True)
        )

    def test_redirect_to_login_page_on_success(self):
        data_api_client.update_user_password = Mock()
        res = self.client.post("/suppliers/change-password", data={
            'user_id': 123,
            'email_address': 'email@email.com',
            'password': '1234567890',
            'confirm_password': '1234567890'
        })
        assert_equal(res.status_code, 302)
        assert_equal(res.location,
                     'http://localhost/suppliers/login')
