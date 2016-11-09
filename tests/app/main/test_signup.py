import mock
from ..helpers import BaseApplicationTest
from react.render_server import RenderedComponent
from dmutils.forms import FakeCsrf
from dmutils.email import EmailError


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
