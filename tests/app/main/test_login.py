from app.main import helpers
from nose.tools import assert_equal, assert_true, assert_is_not_none, assert_in
from ..helpers import BaseApplicationTest
from lxml import html
import mock


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

TOKEN_CREATED_BEFORE_PASSWORD_LAST_CHANGED_ERROR = \
    'This password reset link is invalid.'


class TestLogin(BaseApplicationTest):

    def setup(self):
        super(TestLogin, self).setup()

        data_api_client_config = {'authenticate_user.return_value': self.user(
            123, "email@email.com", 1234, 'name'
        )}

        self._data_api_client = mock.patch(
            'app.main.views.login.data_api_client', **data_api_client_config
        )
        self._data_api_client.start()

    def teardown(self):
        self._data_api_client.stop()

    def test_should_show_login_page(self):
        res = self.client.get("/suppliers/login")
        assert_equal(res.status_code, 200)
        assert_true("<h1>Supplier login</h1>" in res.get_data(as_text=True))

    def test_should_redirect_to_dashboard_on_login(self):
        res = self.client.post("/suppliers/login", data={
            'email_address': 'valid@email.com',
            'password': '1234567890'
        })
        assert_equal(res.status_code, 302)
        assert_equal(res.location, 'http://localhost/suppliers')
        assert_in('Secure;', res.headers['Set-Cookie'])

    def test_ok_next_url_redirects_on_login(self):
        res = self.client.post("/suppliers/login?next=/suppliers/services/123",
                               data={
                                   'email_address': 'valid@email.com',
                                   'password': '1234567890'
                               })
        assert_equal(res.status_code, 302)
        assert_equal(res.location, 'http://localhost/suppliers/services/123')

    def test_bad_next_url_takes_user_to_dashboard(self):
        res = self.client.post("/suppliers/login?next=http://badness.com",
                               data={
                                   'email_address': 'valid@email.com',
                                   'password': '1234567890'
                               })
        assert_equal(res.status_code, 302)
        assert_equal(res.location, 'http://localhost/suppliers')

    def test_should_have_cookie_on_redirect(self):
        with self.app.app_context():
            self.app.config['SESSION_COOKIE_DOMAIN'] = '127.0.0.1'
            self.app.config['SESSION_COOKIE_SECURE'] = True
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

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_return_a_403_for_invalid_login(self, data_api_client):
        data_api_client.authenticate_user.return_value = None

        res = self.client.post("/suppliers/login", data={
            'email_address': 'valid@email.com',
            'password': '1234567890'
        })
        assert_in(
            self.strip_all_whitespace("Sorry, we couldn't log you in"),
            self.strip_all_whitespace(res.get_data(as_text=True)))
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


class TestResetPassword(BaseApplicationTest):

    def setup(self):
        super(TestResetPassword, self).setup()

        data_api_client_config = {'get_user.return_value': self.user(
            123, "email@email.com", 1234, 'name'
        )}

        self._data_api_client = mock.patch(
            'app.main.views.login.data_api_client', **data_api_client_config
        )
        self._data_api_client.start()

    def teardown(self):
        self._data_api_client.stop()

    def test_email_should_not_be_empty(self):
        res = self.client.post("/suppliers/reset-password", data={})
        content = self.strip_all_whitespace(res.get_data(as_text=True))
        assert_equal(res.status_code, 400)
        assert_true(
            self.strip_all_whitespace(EMAIL_EMPTY_ERROR)
            in content)

    def test_email_should_be_valid(self):
        res = self.client.post("/suppliers/reset-password", data={
            'email_address': 'invalid'
        })
        content = self.strip_all_whitespace(res.get_data(as_text=True))
        assert_equal(res.status_code, 400)
        assert_true(
            self.strip_all_whitespace(EMAIL_INVALID_ERROR)
            in content)

    def test_redirect_to_same_page_on_success(self):
        res = self.client.post("/suppliers/reset-password", data={
            'email_address': 'email@email.com'
        })
        assert_equal(res.status_code, 302)
        assert_equal(res.location,
                     'http://localhost/suppliers/reset-password')

    def test_email_should_be_decoded_from_token(self):
        with self.app.app_context():
            url = helpers.email.generate_reset_url(123, "email@email.com")
        res = self.client.get(url)
        assert_equal(res.status_code, 200)
        assert_true(
            "Reset password for email@email.com" in res.get_data(as_text=True)
        )

    def test_password_should_not_be_empty(self):
        with self.app.app_context():
            url = helpers.email.generate_reset_url(123, 'email@email.com')
            res = self.client.post(url, data={
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
        with self.app.app_context():
            url = helpers.email.generate_reset_url(123, 'email@email.com')
            res = self.client.post(url, data={
                'password': '123456789',
                'confirm_password': '123456789'
            })
            assert_equal(res.status_code, 400)
            assert_true(
                PASSWORD_INVALID_ERROR in res.get_data(as_text=True)
            )

    def test_password_should_be_under_51_chars_long(self):
        with self.app.app_context():
            url = helpers.email.generate_reset_url(123, 'email@email.com')
            res = self.client.post(url, data={
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
        with self.app.app_context():
            url = helpers.email.generate_reset_url(123, 'email@email.com')
            res = self.client.post(url, data={
                'password': '1234567890',
                'confirm_password': '0123456789'
            })
            assert_equal(res.status_code, 400)
            assert_true(
                PASSWORD_MISMATCH_ERROR in res.get_data(as_text=True)
            )

    def test_redirect_to_login_page_on_success(self):
        with self.app.app_context():
            url = helpers.email.generate_reset_url(123, 'email@email.com')
            res = self.client.post(url, data={
                'password': '1234567890',
                'confirm_password': '1234567890'
            })
            assert_equal(res.status_code, 302)
            assert_equal(res.location,
                         'http://localhost/suppliers/login')

    @mock.patch('app.main.views.login.data_api_client')
    def test_token_created_before_last_updated_password_cannot_be_used(
            self, data_api_client
    ):
        with self.app.app_context():
            data_api_client.get_user.return_value = self.user(
                123, "email@email.com", 1234, 'email', is_token_valid=False
            )
            url = helpers.email.generate_reset_url(123, 'email@email.com')
            res = self.client.post(url, data={
                'password': '1234567890',
                'confirm_password': '1234567890'
            }, follow_redirects=True)

            assert_equal(res.status_code, 200)
            assert_true(
                TOKEN_CREATED_BEFORE_PASSWORD_LAST_CHANGED_ERROR
                in res.get_data(as_text=True)
            )


class TestLoginFormsNotAutofillable(BaseApplicationTest):

    def _forms_and_inputs_not_autofillable(
            self, url, expected_title, expected_lede=None
    ):
        response = self.client.get(url)
        assert_equal(response.status_code, 200)

        document = html.fromstring(response.get_data(as_text=True))

        page_title = document.xpath(
            '//main[@id="content"]//h1/text()')[0].strip()
        assert_equal(expected_title, page_title)

        if expected_lede:
            page_lede = document.xpath(
                '//main[@id="content"]//p[@class="lede"]/text()')[0].strip()
            assert_equal(expected_lede, page_lede)

        forms = document.xpath('//main[@id="content"]//form')

        for form in forms:
            assert_equal("off", form.get('autocomplete'))
            non_hidden_inputs = form.xpath('//input[@type!="hidden"]')

            for input in non_hidden_inputs:
                assert_equal("off", input.get('autocomplete'))

    def test_login_form_and_inputs_not_autofillable(self):
        self._forms_and_inputs_not_autofillable(
            "/suppliers/login",
            "Supplier login"
        )

    def test_request_password_reset_form_and_inputs_not_autofillable(self):
        self._forms_and_inputs_not_autofillable(
            "/suppliers/reset-password",
            "Reset password"
        )

    @mock.patch('app.main.views.login.data_api_client')
    def test_reset_password_form_and_inputs_not_autofillable(
            self, data_api_client
    ):
        data_api_client.get_user.return_value = self.user(
            123, "email@email.com", 1234, 'email'
        )

        with self.app.app_context():
            url = helpers.email.generate_reset_url(123, "email@email.com")

        self._forms_and_inputs_not_autofillable(
            url,
            "Reset password",
            "Reset password for email@email.com"
        )
