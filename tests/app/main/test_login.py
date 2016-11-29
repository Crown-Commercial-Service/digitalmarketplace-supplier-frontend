# coding: utf-8
from __future__ import unicode_literals

from dmapiclient import HTTPError
from dmapiclient.audit import AuditTypes
from dmutils.email import generate_token, MandrillException
from ..helpers import BaseApplicationTest
import mock
import pytest

EMAIL_EMPTY_ERROR = "Email address must be provided"
EMAIL_INVALID_ERROR = "Please enter a valid email address"
EMAIL_SENT_MESSAGE = "If the email address you've entered belongs to a Digital Marketplace account, we'll send a link to reset the password."  # noqa
PASSWORD_EMPTY_ERROR = "Please enter your password"
PASSWORD_INVALID_ERROR = "Passwords must be between 10 and 50 characters"
PASSWORD_MISMATCH_ERROR = "The passwords you entered do not match"
NEW_PASSWORD_EMPTY_ERROR = "Please enter a new password"
NEW_PASSWORD_CONFIRM_EMPTY_ERROR = "Please confirm your new password"

TOKEN_CREATED_BEFORE_PASSWORD_LAST_CHANGED_ERROR = "This password reset link is invalid."
USER_LINK_EXPIRED_ERROR = "Check you’ve entered the correct link or ask the person who invited you to send a new invitation."  # noqa


class TestSupplierRoleRequired(BaseApplicationTest):
    def test_buyer_cannot_access_supplier_dashboard(self):
        with self.app.app_context():
            self.login_as_buyer()
            res = self.client.get('/suppliers')
            assert res.status_code == 302
            assert res.location == 'http://localhost/login?next=%2Fsuppliers'
            self.assert_flashes('supplier-role-required', expected_category='error')


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
            assert EMAIL_INVALID_ERROR in res.get_data(as_text=True)
            assert res.status_code == 400

    def test_should_be_an_error_for_missing_email(self):
        with self.app.app_context():
            self.login()
            res = self.client.post(
                '/suppliers/invite-user',
                data={}
            )
            assert EMAIL_EMPTY_ERROR in res.get_data(as_text=True)
            assert res.status_code == 400

    @mock.patch('app.main.views.login.data_api_client')
    @mock.patch('app.main.views.login.send_email')
    def test_should_redirect_to_list_users_on_success_invite(self, send_email, data_api_client):
        with self.app.app_context():
            self.login()
            res = self.client.post(
                '/suppliers/invite-user',
                data={
                    'email_address': 'this@isvalid.com'
                }
            )
            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/users'

    @mock.patch('app.main.views.login.data_api_client')
    @mock.patch('app.main.views.login.send_email')
    def test_should_strip_whitespace_surrounding_invite_user_email_address_field(self, send_email, data_api_client):
        with self.app.app_context():
            self.login()
            self.client.post(
                '/suppliers/invite-user',
                data={
                    'email_address': '  this@isvalid.com  '
                }
            )
            send_email.assert_called_once_with(
                'this@isvalid.com',
                mock.ANY,
                mock.ANY,
                mock.ANY,
                mock.ANY,
                mock.ANY,
                mock.ANY,
            )

    @mock.patch('app.main.views.login.data_api_client')
    @mock.patch('app.main.views.login.generate_token')
    @mock.patch('app.main.views.login.send_email')
    def test_should_call_generate_token_with_correct_params(self, send_email, generate_token, data_api_client):
        with self.app.app_context():

            self.app.config['SHARED_EMAIL_KEY'] = "KEY"
            self.app.config['INVITE_EMAIL_SALT'] = "SALT"

            self.login()
            res = self.client.post(
                '/suppliers/invite-user',
                data={
                    'email_address': 'this@isvalid.com'
                })
            assert res.status_code == 302
            generate_token.assert_called_once_with(
                {
                    "supplier_id": 1234,
                    "supplier_name": "Supplier NĀme",
                    "email_address": "this@isvalid.com"
                },
                'KEY',
                'SALT'
            )

    @mock.patch('app.main.views.login.send_email')
    @mock.patch('app.main.views.login.generate_token')
    def test_should_not_generate_token_or_send_email_if_invalid_email(self, send_email, generate_token):
        with self.app.app_context():

            self.login()
            res = self.client.post(
                '/suppliers/invite-user',
                data={
                    'email_address': 'total rubbish'
                })
            assert res.status_code == 400
            assert not send_email.called
            assert not generate_token.called

    @mock.patch('app.main.views.login.send_email')
    def test_should_be_an_error_if_send_invitation_email_fails(self, send_email):
        with self.app.app_context():
            self.login()

            send_email.side_effect = MandrillException(Exception('API is down'))

            res = self.client.post(
                '/suppliers/invite-user',
                data={'email_address': 'email@email.com', 'name': 'valid'}
            )

            assert res.status_code == 503

    @mock.patch('app.main.views.login.data_api_client')
    @mock.patch('app.main.views.login.send_email')
    def test_should_call_send_invitation_email_with_correct_params(self, send_email, data_api_client):
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

            assert res.status_code == 302

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
    def test_should_create_audit_event(self, send_email, data_api_client):
        with self.app.app_context():
            self.login()

            res = self.client.post(
                '/suppliers/invite-user',
                data={'email_address': 'email@example.com', 'name': 'valid'})

            assert res.status_code == 302

            data_api_client.create_audit_event.assert_called_once_with(
                audit_type=AuditTypes.invite_user,
                user='email@email.com',
                object_type='suppliers',
                object_id=1234,
                data={'invitedEmail': 'email@example.com'})


class TestCreateUser(BaseApplicationTest):
    def _generate_token(self, supplier_id=1234, supplier_name='Supplier Name', email_address='test@email.com'):
        return generate_token(
            {
                'supplier_id': supplier_id,
                'supplier_name': supplier_name,
                'email_address': email_address
            },
            self.app.config['SHARED_EMAIL_KEY'],
            self.app.config['INVITE_EMAIL_SALT']
        )

    def test_should_be_an_error_for_invalid_token(self):
        token = "1234"
        res = self.client.get(
            '/suppliers/create-user/{}'.format(token)
        )
        assert res.status_code == 400

    def test_should_be_an_error_for_missing_token(self):
        res = self.client.get('/suppliers/create-user')
        assert res.status_code == 404

    def test_should_be_an_error_for_missing_token_trailing_slash(self):
        res = self.client.get('/suppliers/create-user/')
        assert res.status_code == 301
        assert res.location == 'http://localhost/suppliers/create-user'

    @mock.patch('app.main.views.login.data_api_client')
    def test_invalid_token_contents_500s(self, data_api_client):
        token = generate_token(
            {
                'this_is_not_expected': 1234
            },
            self.app.config['SHARED_EMAIL_KEY'],
            self.app.config['INVITE_EMAIL_SALT']
        )

        with pytest.raises(KeyError):
            self.client.get(
                '/suppliers/create-user/{}'.format(token)
            )

    def test_should_be_a_bad_request_if_token_expired(self):
        res = self.client.get(
            '/suppliers/create-user/12345'
        )

        assert res.status_code == 400
        assert USER_LINK_EXPIRED_ERROR in res.get_data(as_text=True)

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_render_create_user_page_if_user_does_not_exist(self, data_api_client):
        data_api_client.get_user.return_value = None

        token = self._generate_token()
        res = self.client.get(
            '/suppliers/create-user/{}'.format(token)
        )

        assert res.status_code == 200
        for message in [
            "Supplier Name",
            "test@email.com",
            '<input type="submit" class="button-save"  value="Create contributor account" />',
            '<form autocomplete="off" action="/suppliers/create-user/%s" method="POST" id="createUserForm">' % token
        ]:
            assert message in res.get_data(as_text=True)

    def test_should_be_an_error_if_invalid_token_on_submit(self):
        res = self.client.post(
            '/suppliers/create-user/invalidtoken',
            data={
                'password': '123456789',
                'name': 'name',
                'email_address': 'valid@test.com'}
        )

        assert res.status_code == 400
        assert USER_LINK_EXPIRED_ERROR in res.get_data(as_text=True)
        assert (
            '<input type="submit" class="button-save"  value="Create contributor account" />'
            not in res.get_data(as_text=True)
        )

    def test_should_be_an_error_if_missing_name_and_password(self):
        token = self._generate_token()
        res = self.client.post(
            '/suppliers/create-user/{}'.format(token),
            data={}
        )

        assert res.status_code == 400
        for message in [
            "Please enter a name",
            "Please enter a password"
        ]:
            assert message in res.get_data(as_text=True)

    def test_should_be_an_error_if_too_short_name_and_password(self):
        token = self._generate_token()
        res = self.client.post(
            '/suppliers/create-user/{}'.format(token),
            data={
                'password': "123456789",
                'name': ""
            }
        )

        assert res.status_code == 400
        for message in [
            "Please enter a name",
            "Passwords must be between 10 and 50 characters"
        ]:
            assert message in res.get_data(as_text=True)

    def test_should_be_an_error_if_too_long_name_and_password(self):
        with self.app.app_context():

            token = self._generate_token()
            twofiftysix = "a" * 256
            fiftyone = "a" * 51

            res = self.client.post(
                '/suppliers/create-user/{}'.format(token),
                data={
                    'password': fiftyone,
                    'name': twofiftysix
                }
            )

            assert res.status_code == 400
            for message in [
                "Names must be between 1 and 255 characters",
                "Passwords must be between 10 and 50 characters",
                "Create contributor account for Supplier Name",
                "test@email.com"
            ]:
                assert message in res.get_data(as_text=True)

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_return_an_error_if_user_exists_and_is_a_buyer(self, data_api_client):
        data_api_client.get_user.return_value = self.user(123, 'test@email.com', None, None, 'Users name')

        token = self._generate_token()
        res = self.client.get(
            '/suppliers/create-user/{}'.format(token)
        )

        assert res.status_code == 400
        print("RESPONSE: {}".format(res.get_data(as_text=True)))
        assert "Account already exists" in res.get_data(as_text=True)

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_return_an_error_with_admin_message_if_user_is_an_admin(self, data_api_client):
        data_api_client.get_user.return_value = self.user(123, 'test@email.com', None, None, 'Users name', role='admin')

        token = self._generate_token()
        res = self.client.get(
            '/suppliers/create-user/{}'.format(token)
        )

        assert res.status_code == 400
        assert "Account already exists" in res.get_data(as_text=True)

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_return_an_error_with_locked_message_if_user_is_locked(self, data_api_client):
        data_api_client.get_user.return_value = self.user(
            123,
            'test@email.com',
            1234,
            'Supplier Name',
            'Users name',
            locked=True
        )

        token = self._generate_token()
        res = self.client.get(
            '/suppliers/create-user/{}'.format(token)
        )

        assert res.status_code == 400
        assert "Your account has been locked" in res.get_data(as_text=True)

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_return_an_error_with_inactive_message_if_user_is_not_active(self, data_api_client):
        data_api_client.get_user.return_value = self.user(
            123,
            'test@email.com',
            1234,
            'Supplier Name',
            'Users name',
            active=False
        )

        token = self._generate_token()
        res = self.client.get(
            '/suppliers/create-user/{}'.format(token)
        )

        assert res.status_code == 400
        assert "Your account has been deactivated" in res.get_data(as_text=True)

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_return_an_error_with_wrong_supplier_message_if_invited_by_wrong_supplier(self, data_api_client):  # noqa
        data_api_client.get_user.return_value = self.user(
            123,
            'test@email.com',
            1234,
            'Supplier Name',
            'Users name'
        )

        token = self._generate_token(
            supplier_id=9999,
            supplier_name='Different Supplier Name',
            email_address='different_supplier@email.com'
        )

        res = self.client.get(
            '/suppliers/create-user/{}'.format(token)
        )

        assert res.status_code == 400
        assert u"You were invited by ‘Different Supplier Name’" in res.get_data(as_text=True)
        assert u"Your account is registered with ‘Supplier Name’" in res.get_data(as_text=True)

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_return_an_error_if_user_is_already_a_supplier(self, data_api_client):
        data_api_client.get_user.return_value = self.user(
            123,
            'test@email.com',
            1234,
            'Supplier Name',
            'Users name'
        )

        token = self._generate_token()
        res = self.client.get(
            '/suppliers/create-user/{}'.format(token),
            follow_redirects=True
        )

        assert res.status_code == 400
        assert "Account already exists" in res.get_data(as_text=True)

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_return_an_error_if_logged_in_user_is_not_invited_user(self, data_api_client):
        self.login()
        data_api_client.get_user.return_value = self.user(
            999,
            'different_email@email.com',
            1234,
            'Supplier Name',
            'Different users name'
        )

        token = self._generate_token()
        res = self.client.get(
            '/suppliers/create-user/{}'.format(token)
        )

        assert res.status_code == 400
        assert "Account already exists" in res.get_data(as_text=True)

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_return_an_error_if_user_is_already_logged_in(self, data_api_client):
        self.login()
        data_api_client.get_user.return_value = self.user(
            123,
            'email@email.com',
            1234,
            'Supplier Name',
            'Users name'
        )

        token = self._generate_token()
        res = self.client.get(
            '/suppliers/create-user/{}'.format(token)
        )

        assert res.status_code == 400
        assert "Account already exists" in res.get_data(as_text=True)

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_create_user_if_user_does_not_exist(self, data_api_client):
        data_api_client.get_user.return_value = None

        token = self._generate_token()
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
            'emailAddress': 'test@email.com',
            'name': 'valid name',
            'supplierId': 1234
        })

        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers'
        self.assert_flashes('account-created', 'flag')

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_return_an_error_if_user_exists(self, data_api_client):
        data_api_client.create_user.side_effect = HTTPError(mock.Mock(status_code=409))

        token = self._generate_token()
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
            'emailAddress': 'test@email.com',
            'name': 'valid name',
            'supplierId': 1234
        })

        assert res.status_code == 400

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_strip_whitespace_surrounding_create_user_name_field(self, data_api_client):
        data_api_client.get_user.return_value = None
        token = self._generate_token()
        self.client.post(
            '/suppliers/create-user/{}'.format(token),
            data={
                'password': 'validpassword',
                'name': '  valid name  '
            }
        )

        data_api_client.create_user.assert_called_once_with({
            'role': mock.ANY,
            'password': 'validpassword',
            'emailAddress': mock.ANY,
            'name': 'valid name',
            'supplierId': mock.ANY
        })

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_not_strip_whitespace_surrounding_create_user_password_field(self, data_api_client):
        data_api_client.get_user.return_value = None
        token = self._generate_token()
        self.client.post(
            '/suppliers/create-user/{}'.format(token),
            data={
                'password': '  validpassword  ',
                'name': 'valid name  '
            }
        )

        data_api_client.create_user.assert_called_once_with({
            'role': mock.ANY,
            'password': '  validpassword  ',
            'emailAddress': mock.ANY,
            'name': 'valid name',
            'supplierId': mock.ANY
        })

    @mock.patch('app.main.views.login.data_api_client')
    def test_should_be_a_503_if_api_fails(self, data_api_client):
        with self.app.app_context():

            data_api_client.create_user.side_effect = HTTPError("bad email")

            token = self._generate_token()
            res = self.client.post(
                '/suppliers/create-user/{}'.format(token),
                data={
                    'password': 'validpassword',
                    'name': 'valid name'
                }
            )
            assert res.status_code == 503
