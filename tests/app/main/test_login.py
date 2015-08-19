# coding: utf-8

from dmutils.apiclient import HTTPError
from dmutils.audit import AuditTypes
from dmutils.email import generate_token, MandrillException
from nose.tools import assert_equal, assert_true, assert_is_not_none, assert_in, assert_false
from ..helpers import BaseApplicationTest
from lxml import html
import mock

EMAIL_EMPTY_ERROR = "Email address must be provided"
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
            123, "email@email.com", 1234, 'name', 'name'
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
        assert_true("Log in to the Digital Marketplace" in res.get_data(as_text=True))

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

    _user = None

    def setup(self):
        super(TestResetPassword, self).setup()

        data_api_client_config = {'get_user.return_value': self.user(
            123, "email@email.com", 1234, 'name', 'Name'
        )}

        self._user = {
            "user": 123,
            "email": 'email@email.com',
        }

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

    @mock.patch('app.main.views.login.send_email')
    def test_redirect_to_same_page_on_success(self, send_email):
        res = self.client.post("/suppliers/reset-password", data={
            'email_address': 'email@email.com'
        })
        assert_equal(res.status_code, 302)
        assert_equal(res.location,
                     'http://localhost/suppliers/reset-password')

    def test_email_should_be_decoded_from_token(self):
        with self.app.app_context():
            token = generate_token(
                self._user,
                self.app.config['SECRET_KEY'],
                self.app.config['RESET_PASSWORD_SALT'])
            url = '/suppliers/reset-password/{}'.format(token)

        res = self.client.get(url)
        assert_equal(res.status_code, 200)
        assert_true(
            "Reset password for email@email.com" in res.get_data(as_text=True)
        )

    def test_password_should_not_be_empty(self):
        with self.app.app_context():
            token = generate_token(
                self._user,
                self.app.config['SECRET_KEY'],
                self.app.config['RESET_PASSWORD_SALT'])
            url = '/suppliers/reset-password/{}'.format(token)

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
            token = generate_token(
                self._user,
                self.app.config['SECRET_KEY'],
                self.app.config['RESET_PASSWORD_SALT'])
            url = '/suppliers/reset-password/{}'.format(token)

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
            token = generate_token(
                self._user,
                self.app.config['SECRET_KEY'],
                self.app.config['RESET_PASSWORD_SALT'])
            url = '/suppliers/reset-password/{}'.format(token)

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
            token = generate_token(
                self._user,
                self.app.config['SECRET_KEY'],
                self.app.config['RESET_PASSWORD_SALT'])
            url = '/suppliers/reset-password/{}'.format(token)

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
            token = generate_token(
                self._user,
                self.app.config['SECRET_KEY'],
                self.app.config['RESET_PASSWORD_SALT'])
            url = '/suppliers/reset-password/{}'.format(token)

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
                123, "email@email.com", 1234, 'email', 'Name', is_token_valid=False
            )
            token = generate_token(
                self._user,
                self.app.config['SECRET_KEY'],
                self.app.config['RESET_PASSWORD_SALT'])
            url = '/suppliers/reset-password/{}'.format(token)

            res = self.client.post(url, data={
                'password': '1234567890',
                'confirm_password': '1234567890'
            }, follow_redirects=True)

            assert_equal(res.status_code, 200)
            assert_true(
                TOKEN_CREATED_BEFORE_PASSWORD_LAST_CHANGED_ERROR
                in res.get_data(as_text=True)
            )

    @mock.patch('app.main.views.login.send_email')
    def test_should_call_send_email_with_correct_params(
            self, send_email
    ):
        with self.app.app_context():

            self.app.config['DM_MANDRILL_API_KEY'] = "API KEY"
            self.app.config['RESET_PASSWORD_EMAIL_SUBJECT'] = "SUBJECT"
            self.app.config['RESET_PASSWORD_EMAIL_FROM'] = "EMAIL FROM"
            self.app.config['RESET_PASSWORD_EMAIL_NAME'] = "EMAIL NAME"

            data_api_client_config = {
                'get_user.return_value': self.user(
                    123,
                    "email@email.com",
                    1234,
                    'name',
                    'name'
                )}

            res = self.client.post(
                '/suppliers/reset-password',
                data={'email_address': 'email@email.com'}
            )

            assert_equal(res.status_code, 302)

            send_email.assert_called_once_with(
                "email@email.com",
                mock.ANY,
                "API KEY",
                "SUBJECT",
                "EMAIL FROM",
                "EMAIL NAME",
                ["password-resets"]
            )

    @mock.patch('app.main.views.login.send_email')
    def test_should_be_an_error_if_send_email_fails(
            self, send_email
    ):
        with self.app.app_context():

            send_email.side_effect = MandrillException(Exception('API is down'))

            data_api_client_config = {
                'get_user.return_value': self.user(
                    123,
                    "email@email.com",
                    1234,
                    'name',
                    'name'
                )}

            res = self.client.post(
                '/suppliers/reset-password',
                data={'email_address': 'email@email.com'}
            )

            assert_equal(res.status_code, 503)


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
            "Log in to the Digital Marketplace"
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
            123, "email@email.com", 1234, 'email', 'name'
        )

        with self.app.app_context():
            token = generate_token(
                {
                    "user": 123,
                    "email": 'email@email.com',
                },
                self.app.config['SECRET_KEY'],
                self.app.config['RESET_PASSWORD_SALT'])

            url = '/suppliers/reset-password/{}'.format(token)

        self._forms_and_inputs_not_autofillable(
            url,
            "Reset password",
            "Reset password for email@email.com"
        )


class TestInviteUser(BaseApplicationTest):

    def test_should_be_an_error_for_invalid_email(self):
        with self.app.app_context():
            self.login()
            res = self.client.post(
                '/suppliers/invite-user',
                data={
                    'email_address': 'invalid'
                }
            )
            assert_true("Please enter a valid email address" in res.get_data(as_text=True))
            assert_equal(res.status_code, 400)

    def test_should_be_an_error_for_missing_email(self):
        with self.app.app_context():
            self.login()
            res = self.client.post(
                '/suppliers/invite-user',
                data={}
            )
            assert_true("Email address must be provided" in res.get_data(as_text=True))
            assert_equal(res.status_code, 400)

    @mock.patch('app.main.views.login.data_api_client')
    @mock.patch('app.main.views.login.send_email')
    def test_should_redirect_to_list_users_on_success_invite(self,
                                                             send_email,
                                                             data_api_client):
        with self.app.app_context():
            self.login()
            res = self.client.post(
                '/suppliers/invite-user',
                data={
                    'email_address': 'this@isvalid.com'
                }
            )
            assert_equal(res.status_code, 302)
            assert_equal(res.location, 'http://localhost/suppliers/users')

    @mock.patch('app.main.views.login.data_api_client')
    @mock.patch('app.main.views.login.generate_token')
    @mock.patch('app.main.views.login.send_email')
    def test_should_call_generate_token_with_correct_params(self,
                                                            send_email,
                                                            generate_token,
                                                            data_api_client):
        with self.app.app_context():

            self.app.config['SHARED_EMAIL_KEY'] = "KEY"
            self.app.config['INVITE_EMAIL_SALT'] = "SALT"

            self.login()
            res = self.client.post(
                '/suppliers/invite-user',
                data={
                    'email_address': 'this@isvalid.com'
                })
            assert_equal(res.status_code, 302)
            generate_token.assert_called_once_with(
                {
                    "supplier_id": 1234,
                    "supplier_name": "Supplier Name",
                    "email_address": "this@isvalid.com"
                },
                'KEY',
                'SALT'
            )

    @mock.patch('app.main.views.login.send_email')
    @mock.patch('app.main.views.login.generate_token')
    def test_should_not_generate_token_or_send_email_if_invalid_email(self,
                                                                      send_email,
                                                                      generate_token):
        with self.app.app_context():

            self.login()
            res = self.client.post(
                '/suppliers/invite-user',
                data={
                    'email_address': 'total rubbish'
                })
            assert_equal(res.status_code, 400)
            assert not send_email.called
            assert not generate_token.called

    @mock.patch('app.main.views.login.send_email')
    def test_should_be_an_error_if_send_invitation_email_fails(
            self, send_email
    ):
        with self.app.app_context():
            self.login()

            send_email.side_effect = MandrillException(Exception('API is down'))

            res = self.client.post(
                '/suppliers/invite-user',
                data={'email_address': 'email@email.com', 'name': 'valid'}
            )

            assert_equal(res.status_code, 503)

    @mock.patch('app.main.views.login.data_api_client')
    @mock.patch('app.main.views.login.send_email')
    def test_should_call_send_invitation_email_with_correct_params(self,
                                                                   send_email,
                                                                   data_api_client):
        with self.app.app_context():

            self.login()

            self.app.config['DM_MANDRILL_API_KEY'] = "API KEY"
            self.app.config['INVITE_EMAIL_SUBJECT'] = "SUBJECT"
            self.app.config['INVITE_EMAIL_FROM'] = "EMAIL FROM"
            self.app.config['INVITE_EMAIL_NAME'] = "EMAIL NAME"

            res = self.client.post(
                '/suppliers/invite-user',
                data={'email_address': 'email@email.com', 'name': 'valid'}
            )

            assert_equal(res.status_code, 302)

            send_email.assert_called_once_with(
                "email@email.com",
                mock.ANY,
                "API KEY",
                "SUBJECT",
                "EMAIL FROM",
                "EMAIL NAME",
                ["user-invite"]
            )

    @mock.patch('app.main.views.login.data_api_client')
    @mock.patch('app.main.views.login.send_email')
    def test_should_create_audit_event(self,
                                       send_email,
                                       data_api_client):
        with self.app.app_context():
            self.login()

            res = self.client.post(
                '/suppliers/invite-user',
                data={'email_address': 'email@example.com', 'name': 'valid'})

            assert_equal(res.status_code, 302)

            data_api_client.create_audit_event.assert_called_once_with(
                audit_type=AuditTypes.invite_user.value,
                user='email@email.com',
                object_type='suppliers',
                object_id=1234,
                data={'invitedEmail': 'email@example.com'})

    def test_should_be_an_error_for_invalid_token(self):
        with self.app.app_context():
            token = "1234"
            res = self.client.get(
                '/suppliers/create-user/{}'.format(token)
            )
            assert_equal(res.status_code, 400)

    def test_should_be_an_error_for_missing_token(self):
        with self.app.app_context():
            res = self.client.get(
                '/suppliers/create-user'
            )
            assert_equal(res.status_code, 404)

    def test_should_be_an_error_for_missing_token_trailing_slash(self):
        with self.app.app_context():
            res = self.client.get(
                '/suppliers/create-user/'
            )
            assert_equal(res.status_code, 301)
            assert_equal(res.location, 'http://localhost/suppliers/create-user')

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_be_an_error_for_invalid_token_contents(self, data_api_client):
        with self.app.app_context():

            token = generate_token(
                {
                    'this_is_not_expected': 1234
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            res = self.client.get(
                '/suppliers/create-user/{}'.format(token)
            )
            assert_equal(res.status_code, 400)
            assert_equal(data_api_client.get_user.called, False)
            assert_equal(data_api_client.get_supplier.called, False)

    def test_should_be_a_bad_request_if_token_expired(self):
        with self.app.app_context():

            res = self.client.get(
                '/suppliers/create-user/12345'
            )

            assert_equal(res.status_code, 400)
            assert_true(
                u"Check you’ve entered the correct link or ask the person who invited you to send a new invitation."  # noqa
                in res.get_data(as_text=True)
            )

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_render_create_user_page_if_user_does_not_exist(self, data_api_client):
        with self.app.app_context():

            data_api_client.get_user.return_value = None

            token = generate_token(
                {
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier Name',
                    'email_address': 'testme@email.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            res = self.client.get(
                '/suppliers/create-user/{}'.format(token)
            )

            assert_equal(res.status_code, 200)
            assert_true(
                "Supplier Name"
                in res.get_data(as_text=True)
            )
            assert_true(
                "testme@email.com"
                in res.get_data(as_text=True)
            )
            assert_true(
                '<button class="button-save">Create contributor account</button>'
                in res.get_data(as_text=True)
            )
            assert_true(
                '<form autocomplete="off" action="/suppliers/create-user/{}" method="POST" id="createUserForm">'.format(token)  # noqa
                in res.get_data(as_text=True)
            )

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_render_update_user_page_if_user_does_exist(self, data_api_client):
        with self.app.app_context():

            data_api_client.get_user.return_value = self.user(
                123,
                'testme@email.com',
                None,
                None,
                'Users name'
            )

            token = generate_token(
                {
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier Name',
                    'email_address': 'testme@email.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            res = self.client.get(
                '/suppliers/create-user/{}'.format(token)
            )

            assert_equal(res.status_code, 200)
            assert_true(
                "Supplier Name"
                in res.get_data(as_text=True)
            )
            assert_true(
                '<button class="button-save">Create contributor account</button>'
                in res.get_data(as_text=True)
            )
            assert_true(
                '<form autocomplete="off" action="/suppliers/update-user/{}" method="POST" id="updateUserForm">'.format(token)  # noqa
                in res.get_data(as_text=True)
            )

    def test_should_be_an_error_if_invalid_token_on_submit(self):
        with self.app.app_context():
            res = self.client.post(
                '/suppliers/create-user/invalidtoken',
                data={
                    'password': '123456789',
                    'name': 'name',
                    'email_address': 'valid@test.com'}
            )

            assert_equal(res.status_code, 400)
            assert_true(
                u"Check you’ve entered the correct link or ask the person who invited you to send a new invitation." in res.get_data(as_text=True)  # noqa
            )
            assert_false(
                '<button class="button-save">Create contributor account</button>' in res.get_data(as_text=True)
            )

    def test_should_be_an_error_if_invalid_token_on_update(self):
        with self.app.app_context():
            res = self.client.post(
                '/suppliers/update-user/invalidtoken'
            )

            assert_equal(res.status_code, 400)
            assert_true(
                u"Check you’ve entered the correct link or ask the person who invited you to send a new invitation." in res.get_data(as_text=True)  # noqa
            )
            assert_false(
                '<button class="button-save">Update user</button>' in res.get_data(as_text=True)  # noqa
            )

    def test_should_be_an_error_if_missing_name_and_password(self):
        with self.app.app_context():

            token = generate_token(
                {
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier Name',
                    'email_address': 'testme@email.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            res = self.client.post(
                '/suppliers/create-user/{}'.format(token),
                data={}
            )

            assert_equal(res.status_code, 400)
            assert_true(
                "Please enter a password" in res.get_data(as_text=True)
            )
            assert_true(
                "Please enter a name" in res.get_data(as_text=True)
            )

    def test_should_be_an_error_if_too_short_name_and_password(self):
        with self.app.app_context():

            token = generate_token(
                {
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier Name',
                    'email_address': 'testme@email.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            res = self.client.post(
                '/suppliers/create-user/{}'.format(token),
                data={
                    'password': "123456789",
                    'name': ""
                }
            )

            assert_equal(res.status_code, 400)
            assert_true(
                "Please enter a name" in res.get_data(as_text=True)
            )
            assert_true(
                "Passwords must be between 10 and 50 characters" in res.get_data(as_text=True)
            )

    def test_should_be_an_error_if_too_long_name_and_password(self):
        with self.app.app_context():

            token = generate_token(
                {
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier Name',
                    'email_address': 'testme@email.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            twofiftysix = "a" * 256
            fiftyone = "a" * 51

            res = self.client.post(
                '/suppliers/create-user/{}'.format(token),
                data={
                    'password': fiftyone,
                    'name': twofiftysix
                }
            )

            assert_equal(res.status_code, 400)
            assert_true(
                "Names must be between 1 and 255 characters" in res.get_data(as_text=True)
            )
            assert_true(
                "Passwords must be between 10 and 50 characters" in res.get_data(as_text=True)
            )

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_create_user_if_user_does_not_exist(self, data_api_client):
        with self.app.app_context():

            data_api_client.get_user.return_value = None

            token = generate_token(
                {
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier Name',
                    'email_address': 'testme@email.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            res = self.client.post(
                '/suppliers/create-user/{}'.format(token),
                data={
                    'password': 'validpassword',
                    'name': 'valid name'
                }
            )

            data_api_client.create_user.assert_called_once_with({
                'role': 'supplier',
                'password': 'validpassword',
                'emailAddress': 'testme@email.com',
                'name': 'valid name',
                'supplierId': 1234
            })

            assert_equal(res.status_code, 302)
            assert_equal(res.location, 'http://localhost/suppliers')

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_update_user_if_user_does_exist(self, data_api_client):
        with self.app.app_context():

            data_api_client.get_user.return_value = self.user(
                123,
                'testme@email.com',
                None,
                None,
                'Users name'
            )

            token = generate_token(
                {
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier Name',
                    'email_address': 'testme@email.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            res = self.client.post(
                '/suppliers/update-user/{}'.format(token)
            )

            data_api_client.update_user.assert_called_once_with(
                user_id=123,
                supplier_id=1234,
                role='supplier'
            )

            assert_equal(res.status_code, 302)
            assert_equal(res.location, 'http://localhost/suppliers')

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_render_update_user_page_if_user_is_locked(self, data_api_client):
        with self.app.app_context():

            data_api_client.get_user.return_value = self.user(
                123,
                'testme@email.com',
                1234,
                'Supplier Name',
                'Users name',
                locked=True
            )

            token = generate_token(
                {
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier Name',
                    'email_address': 'testme@email.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            res = self.client.get(
                '/suppliers/create-user/{}'.format(token)
            )

            assert_equal(res.status_code, 200)
            assert_in(
                "The account associated with this email address is inactive, "
                "locked, or already registered with a different supplier",
                res.get_data(as_text=True)
            )
            assert_in(
                'Please email <a href="mailto:enquiries@digitalmarketplace.service.gov.uk">'
                'enquiries@digitalmarketplace.service.gov.uk</a> for help with setting up a new contributor account.',
                res.get_data(as_text=True)
            )

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_render_update_user_page_if_user_is_not_active(self, data_api_client):
        with self.app.app_context():

            data_api_client.get_user.return_value = self.user(
                123,
                'testme@email.com',
                1234,
                'Supplier Name',
                'Users name',
                active=False
            )

            token = generate_token(
                {
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier Name',
                    'email_address': 'testme@email.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            res = self.client.get(
                '/suppliers/create-user/{}'.format(token)
            )

            assert_equal(res.status_code, 200)
            assert_in(
                "The account associated with this email address is inactive, "
                "locked, or already registered with a different supplier",
                res.get_data(as_text=True)
            )
            assert_in(
                'Please email <a href="mailto:enquiries@digitalmarketplace.service.gov.uk">'
                'enquiries@digitalmarketplace.service.gov.uk</a> for help with setting up a new contributor account.',
                res.get_data(as_text=True)
            )

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_render_update_user_page_if_user_is_already_a_supplier(self, data_api_client):
        with self.app.app_context():

            data_api_client.get_user.return_value = self.user(
                123,
                'testme@email.com',
                1234,
                'Supplier Name',
                'Users name',
                active=True,
                locked=False
            )

            token = generate_token(
                {
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier Name',
                    'email_address': 'testme@email.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            res = self.client.get(
                '/suppliers/create-user/{}'.format(token)
            )
            assert_equal(res.status_code, 200)
            assert_in(
                "The account associated with this email address is inactive, "
                "locked, or already registered with a different supplier",
                res.get_data(as_text=True)
            )
            assert_in(
                'Please email <a href="mailto:enquiries@digitalmarketplace.service.gov.uk">'
                'enquiries@digitalmarketplace.service.gov.uk</a> for help with setting up a new contributor account.',
                res.get_data(as_text=True)
            )

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_not_update_a_supplier_account(self, data_api_client):
        with self.app.app_context():

            data_api_client.get_user.return_value = self.user(
                123,
                'testme@email.com',
                1234,
                'Supplier Name',
                'Users name',
                active=True
            )

            token = generate_token(
                {
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier Name',
                    'email_address': 'testme@email.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            res = self.client.post(
                '/suppliers/create-user/{}'.format(token)
            )

            assert_equal(res.status_code, 400)

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_not_update_an_admin_account(self, data_api_client):
        with self.app.app_context():

            data_api_client.get_user.return_value = self.user(
                123,
                'testme@email.com',
                None,
                None,
                'Users name',
                active=True,
                role='admin'
            )

            token = generate_token(
                {
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier Name',
                    'email_address': 'testme@email.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            res = self.client.post(
                '/suppliers/create-user/{}'.format(token)
            )

            assert_equal(res.status_code, 400)

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_not_update_a_locked_account(self, data_api_client):
        with self.app.app_context():

            data_api_client.get_user.return_value = self.user(
                123,
                'testme@email.com',
                None,
                None,
                'Users name',
                active=True,
                locked=True
            )

            token = generate_token(
                {
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier Name',
                    'email_address': 'testme@email.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            res = self.client.post(
                '/suppliers/create-user/{}'.format(token)
            )

            assert_equal(res.status_code, 400)

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_not_update_an_inactive_account(self, data_api_client):
        with self.app.app_context():

            data_api_client.get_user.return_value = self.user(
                123,
                'testme@email.com',
                None,
                None,
                'Users name',
                active=False,
                locked=False
            )

            token = generate_token(
                {
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier Name',
                    'email_address': 'testme@email.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            res = self.client.post(
                '/suppliers/create-user/{}'.format(token)
            )

            assert_equal(res.status_code, 400)

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_be_a_503_if_api_fails(self, data_api_client):
        with self.app.app_context():

            data_api_client.create_user.side_effect = HTTPError("bad email")

            token = generate_token(
                {
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier Name',
                    'email_address': 'testme@email.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

            res = self.client.post(
                '/suppliers/create-user/{}'.format(token),
                data={
                    'password': 'validpassword',
                    'name': 'valid name'
                }
            )
            assert_equal(res.status_code, 503)
