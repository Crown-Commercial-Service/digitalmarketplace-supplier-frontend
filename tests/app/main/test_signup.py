import mock
from ..helpers import BaseApplicationTest
from dmutils.forms import FakeCsrf
from dmutils.email import EmailError
import pytest


def get_application(id):
    return {'application': {
        'id': 1,
        'data': {'a': 'b'},
        'user_id': 123,
        'created_at': '	2016-11-14 01:22:01.14119'
    }}


class TestSignupPage(BaseApplicationTest):
    test_applicant = {'csrf_token': FakeCsrf.valid_token, 'representative': 'matt', 'name': 'a company',
                      'abn': '123456',
                      'phone': '55555555', 'email': 'email@company.com'}

    def setup(self):
        super(TestSignupPage, self).setup()

    @mock.patch('app.main.views.signup.render_component')
    def test_signup_page_renders(self, render_component):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        res = self.client.get(self.expand_path('/signup'))

        assert res.status_code == 200

    @mock.patch('app.main.views.signup.send_email')
    def test_email_valid_applicant(self, send_email):

        res = self.client.post(
            self.expand_path('/signup'),
            data=self.test_applicant
        )

        assert res.status_code == 200
        send_email.assert_called_once_with(
            self.test_applicant['email'],
            mock.ANY,
            self.app.config['INVITE_EMAIL_SUBJECT'],
            self.app.config['INVITE_EMAIL_FROM'],
            self.app.config['INVITE_EMAIL_NAME']
        )

    @mock.patch('app.main.views.signup.start_seller_signup')
    def test_invalid_applicant(self, seller_signup):

        data = dict(self.test_applicant)
        data['representative'] = ''

        res = self.client.post(
            self.expand_path('/signup'),
            data=data
        )

        del data['csrf_token']

        seller_signup.assert_called_once_with(
            data,
            {'representative': {'required': True}}
        )

    @mock.patch('app.main.views.signup.send_email')
    def test_email_error(self, send_email):
        send_email.side_effect = EmailError("Failed")

        res = self.client.post(
            self.expand_path('/signup'),
            data=self.test_applicant
        )

        send_email.assert_called_once_with(
            self.test_applicant['email'],
            mock.ANY,
            self.app.config['INVITE_EMAIL_SUBJECT'],
            self.app.config['INVITE_EMAIL_FROM'],
            self.app.config['INVITE_EMAIL_NAME']
        )
        assert res.status_code == 503


class TestApplicationPage(BaseApplicationTest):

    def setup(self):
        super(TestApplicationPage, self).setup()

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    def test_application_page_renders(self, render_component, data_api_client):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        with self.app.test_client():
            self.login()
            data_api_client.get_application.side_effect = get_application
            res = self.client.get(self.expand_path('/application/1'))

            assert res.status_code == 200

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    def test_application_page_denies_access(self, render_component, data_api_client):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        with self.app.test_client():
            self.login_as_buyer()
            data_api_client.get_application.side_effect = get_application
            res = self.client.get(self.expand_path('/application/1'))

            assert res.status_code == 302

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    @pytest.mark.skipif(True, reason="failing due to csrf")
    def test_application_update(self, render_component, data_api_client):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        with self.app.test_client():
            self.login()
            data_api_client.get_application.side_effect = get_application
            res = self.client.post(self.expand_path('/application/1'), {'a': 'b'})

            assert res.status_code == 200

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    @pytest.mark.skipif(True, reason="failing due to csrf")
    def test_application_update_denies_access(self, render_component, data_api_client):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        with self.app.test_client():
            self.login_as_buyer()
            data_api_client.get_application.side_effect = get_application
            res = self.client.post(self.expand_path('/application/1'), {'a': 'b'})

            assert res.status_code == 302
