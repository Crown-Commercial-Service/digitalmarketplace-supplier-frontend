# coding: utf-8
from __future__ import unicode_literals

from dmapiclient.audit import AuditTypes
from dmutils.email.exceptions import EmailError

from ..helpers import BaseApplicationTest
import mock

EMAIL_EMPTY_ERROR = "Email address must be provided"
EMAIL_INVALID_ERROR = "Please enter a valid email address"


class TestCreateUser(BaseApplicationTest):
    def test_should_redirect_to_the_user_frontend_app(self):
        res = self.client.get('/suppliers/create-user/1234567890')
        assert res.status_code == 301
        assert res.location == 'http://localhost/user/create/1234567890'


class TestSupplierRoleRequired(BaseApplicationTest):
    def test_buyer_cannot_access_supplier_dashboard(self):
        with self.app.app_context():
            self.login_as_buyer()
            res = self.client.get('/suppliers')
            assert res.status_code == 302
            assert res.location == 'http://localhost/user/login?next=%2Fsuppliers'
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
    @mock.patch('app.main.views.login.InviteUser')
    def test_should_redirect_to_list_users_on_success_invite(self, InviteUser, data_api_client):
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
    @mock.patch('app.main.views.login.InviteUser')
    def test_should_strip_whitespace_surrounding_invite_user_email_address_field(self, InviteUser, data_api_client):
        with self.app.app_context():
            self.login()
            self.client.post(
                '/suppliers/invite-user',
                data={
                    'email_address': '  this@isvalid.com  '
                }
            )
            InviteUser.assert_called_once_with(
                {
                    'role': 'supplier',
                    'supplier_id': mock.ANY,
                    'supplier_name': mock.ANY,
                    'email_address': 'this@isvalid.com'
                }
            )

    @mock.patch('app.main.views.login.InviteUser')
    def test_should_not_send_email_if_invalid_email(self, InviteUser):
        with self.app.app_context():

            self.login()
            res = self.client.post(
                '/suppliers/invite-user',
                data={
                    'email_address': 'total rubbish'
                })
            assert res.status_code == 400
            assert InviteUser.send_email.called is False

    @mock.patch('dmutils.email.invite_user.DMNotifyClient')
    def test_should_be_an_error_if_send_invitation_email_fails(self, DMNotifyClient):
        notify_client_mock = mock.Mock()
        notify_client_mock.send_email.side_effect = EmailError()
        DMNotifyClient.return_value = notify_client_mock

        with self.app.app_context():
            self.login()

            res = self.client.post(
                '/suppliers/invite-user',
                data={'email_address': 'email@email.com', 'name': 'valid'}
            )

            assert res.status_code == 503

    @mock.patch('app.main.views.login.data_api_client')
    @mock.patch('app.main.views.login.InviteUser')
    def test_should_send_invitation_email_with_correct_params(self, InviteUser, data_api_client):
        user_invite_mock = mock.Mock()
        user_invite_mock.token = 'not-actually-a-token'
        InviteUser.return_value = user_invite_mock

        with self.app.app_context():
            self.login()
            res = self.client.post(
                '/suppliers/invite-user',
                data={'email_address': 'email@email.com', 'name': 'valid'}
            )

            assert res.status_code == 302

            InviteUser.assert_called_once_with(
                {
                    'role': 'supplier',
                    'supplier_id': mock.ANY,
                    'supplier_name': mock.ANY,
                    'email_address': 'email@email.com'
                }
            )

            user_invite_mock.send_invite_email.assert_called_once_with(
                'http://localhost/user/create/not-actually-a-token'
            )

    @mock.patch('app.main.views.login.data_api_client')
    @mock.patch('app.main.views.login.InviteUser')
    def test_should_create_audit_event(self, InviteUser, data_api_client):
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
