# coding: utf-8
from flask import current_app
import mock

from dmapiclient.audit import AuditTypes
from dmutils.email.exceptions import EmailError

from ..helpers import BaseApplicationTest

EMAIL_EMPTY_ERROR = "Email address must be provided"
EMAIL_INVALID_ERROR = "Please enter a valid email address"


class TestSupplierRoleRequired(BaseApplicationTest):
    def test_buyer_cannot_access_supplier_dashboard(self):
        self.login_as_buyer()
        res = self.client.get('/suppliers')
        assert res.status_code == 302
        assert res.location == 'http://localhost/user/login?next=%2Fsuppliers'
        self.assert_flashes('You must log in with a supplier account to see this page.', expected_category='error')


class TestInviteUser(BaseApplicationTest):
    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.login.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_should_be_an_error_for_invalid_email(self):
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
        self.login()
        res = self.client.post(
            '/suppliers/invite-user',
            data={}
        )
        assert EMAIL_EMPTY_ERROR in res.get_data(as_text=True)
        assert res.status_code == 400

    @mock.patch('app.main.views.login.send_user_account_email')
    def test_should_redirect_to_list_users_on_success_invite(self, send_user_account_email):
        self.login()
        res = self.client.post(
            '/suppliers/invite-user',
            data={
                'email_address': 'this@isvalid.com'
            }
        )
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/users'

    @mock.patch('app.main.views.login.send_user_account_email')
    def test_strip_whitespace_around_invite_user_email_address_field(self, send_user_account_email):
        with self.app.app_context():
            self.login()
            self.client.post(
                '/suppliers/invite-user',
                data={
                    'email_address': '  this@isvalid.com  '
                }
            )
            send_user_account_email.assert_called_once_with(
                'supplier',
                'this@isvalid.com',
                current_app.config['NOTIFY_TEMPLATES']['invite_contributor'],
                extra_token_data={
                    "supplier_id": 1234,
                    "supplier_name": 'Supplier NĀme'
                },
                personalisation={
                    'user': 'Năme',
                    'supplier': 'Supplier NĀme'
                }
            )

    @mock.patch('app.main.views.login.send_user_account_email')
    def test_should_not_send_email_if_invalid_email(self, send_user_account_email):
        self.login()
        res = self.client.post(
            '/suppliers/invite-user',
            data={
                'email_address': 'total rubbish'
            })
        assert res.status_code == 400
        assert send_user_account_email.send_email.called is False

    @mock.patch('dmutils.email.user_account_email.DMNotifyClient')
    def test_should_be_an_error_if_send_invitation_email_fails(self, DMNotifyClient):
        notify_client_mock = mock.Mock()
        notify_client_mock.send_email.side_effect = EmailError()
        DMNotifyClient.return_value = notify_client_mock

        self.login()

        res = self.client.post(
            '/suppliers/invite-user',
            data={'email_address': 'email@email.com', 'name': 'valid'}
        )

        assert res.status_code == 503

    @mock.patch('app.main.views.login.send_user_account_email')
    def test_should_send_invitation_email_with_correct_params(self, send_user_account_email):
        with self.app.app_context():
            self.login()
            res = self.client.post(
                '/suppliers/invite-user',
                data={'email_address': 'email@email.com', 'name': 'valid'}
            )

            assert res.status_code == 302

            send_user_account_email.assert_called_once_with(
                'supplier',
                'email@email.com',
                current_app.config['NOTIFY_TEMPLATES']['invite_contributor'],
                extra_token_data={
                    'supplier_id': 1234,
                    'supplier_name': 'Supplier NĀme'
                },
                personalisation={
                    'user': 'Năme',
                    'supplier': 'Supplier NĀme'
                }
            )

    @mock.patch('app.main.views.login.send_user_account_email')
    def test_should_create_audit_event(self, send_user_account_email):
        self.login()

        res = self.client.post(
            '/suppliers/invite-user',
            data={'email_address': 'email@example.com', 'name': 'valid'})

        assert res.status_code == 302

        self.data_api_client.create_audit_event.assert_called_once_with(
            audit_type=AuditTypes.invite_user,
            user='email@email.com',
            object_type='suppliers',
            object_id=1234,
            data={'invitedEmail': 'email@example.com'})
