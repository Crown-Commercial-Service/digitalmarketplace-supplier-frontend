import mock
from ..helpers import BaseApplicationTest
from dmutils.forms import FakeCsrf
from dmutils.email import EmailError
from app.main.views.signup import render_create_application
from dmapiclient import HTTPError
from io import BytesIO
import json


def get_application(id):
    return {'application': {
        'id': 1,
        'status': 'saved',
        'data': {'a': 'b'},
        'created_at': '2016-11-14 01:22:01.14119',
        'email': 'applicant@email.com',
        'representative': 'Ms Authorised Rep',
        'name': 'My Amazing Company'
    }}


def get_unauthorised_application(id):
    return {'application': {
        'id': 1,
        'status': 'saved',
        'data': {'a': 'b'},
        'created_at': '2016-11-14 01:22:01.14119',
        'email': 'test@email.com',
        'representative': 'Ms Authorised Rep',
        'name': 'My Amazing Company'
    }}


def get_submitted_application(id):
    return {'application': {
        'id': 1,
        'status': 'submitted',
        'data': {'a': 'b'},
        'created_at': '2016-11-14 01:22:01.14119',
    }}


def get_another_application(id):
    return {'application': {
        'id': 2,
        'status': 'saved',
        'data': {'a': 'b'},
        'created_at': '2016-11-14 01:22:01.14119',
    }}


class TestSignupPage(BaseApplicationTest):
    test_application = {'csrf_token': FakeCsrf.valid_token, 'representative': 'matt', 'name': 'a company',
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
    def test_email_valid_application(self, send_email):

        res = self.client.post(
            self.expand_path('/signup'),
            data=self.test_application
        )

        assert res.status_code == 200
        send_email.assert_called_once_with(
            self.test_application['email'],
            mock.ANY,
            self.app.config['INVITE_EMAIL_SUBJECT'],
            self.app.config['INVITE_EMAIL_FROM'],
            self.app.config['INVITE_EMAIL_NAME']
        )

    @mock.patch('app.main.views.signup.start_seller_signup')
    def test_invalid_application(self, seller_signup):

        seller_signup.return_value = 'test'
        data = dict(self.test_application)
        data['name'] = ''

        self.client.post(
            self.expand_path('/signup'),
            data=data
        )

        del data['csrf_token']

        seller_signup.assert_called_once_with(
            data,
            {'name': {'required': True}}
        )

    @mock.patch('app.main.views.signup.send_email')
    def test_email_error(self, send_email):
        send_email.side_effect = EmailError("Failed")

        res = self.client.post(
            self.expand_path('/signup'),
            data=self.test_application
        )

        send_email.assert_called_once_with(
            self.test_application['email'],
            mock.ANY,
            self.app.config['INVITE_EMAIL_SUBJECT'],
            self.app.config['INVITE_EMAIL_FROM'],
            self.app.config['INVITE_EMAIL_NAME']
        )
        assert res.status_code == 503


class TestCreateApplicationPage(BaseApplicationTest):
    def setup(self):
        super(TestCreateApplicationPage, self).setup()

    @mock.patch('app.main.views.signup.decode_user_token')
    def test_invalid_token_data(self, decode_user_token):
        decode_user_token.return_value = {}

        res = self.client.get(
            self.url_for('main.render_create_application', token='test')
        )
        assert res.status_code == 503

    @mock.patch('app.main.views.signup.data_api_client')
    @mock.patch('app.main.views.signup.decode_user_token')
    def test_existing_user(self, decode_user_token, data_api_client):
        decode_user_token.return_value = {'email': 'test@company.com'}
        data_api_client.get_user.return_value = self.user(123, 'test@email.com', None, None, 'Users name')

        res = self.client.get(
            self.url_for('main.render_create_application', token='test')
        )
        assert res.status_code == 400

    @mock.patch('app.main.views.signup.render_component')
    @mock.patch('app.main.views.signup.data_api_client')
    @mock.patch('app.main.views.signup.decode_user_token')
    def test_render_create_application(self, decode_user_token, data_api_client, render_component):
        token_data = {'email': 'test@company.com'}
        decode_user_token.return_value = token_data
        data_api_client.get_user.return_value = None
        render_component.return_value.get_props.return_value = {}

        res = self.client.get(
            self.url_for('main.render_create_application', token='test')
        )

        assert res.status_code == 200
        render_component.assert_called_once_with(
            'bundles/SellerRegistration/EnterPasswordWidget.js', {
                'form_options': {
                    'errors': None
                },
                'enterPasswordForm': token_data
            }
        )

    @mock.patch('app.main.views.signup.render_component')
    @mock.patch('app.main.views.signup.data_api_client')
    @mock.patch('app.main.views.signup.decode_user_token')
    def test_render_create_application_with_errors(self, decode_user_token, data_api_client, render_component):
        with self.app.test_request_context():
            error = {'error': 'reason'}
            decode_user_token.return_value = {'email': 'test@company.com', 'name': 'a company'}
            data_api_client.get_user.return_value = None
            render_component.return_value.get_props.return_value = {}

            render_create_application('token', {'key': 'value'}, error)
            render_component.assert_called_once_with(
                'bundles/SellerRegistration/EnterPasswordWidget.js', {
                    'form_options': {
                        'errors': error
                    },
                    'enterPasswordForm': {'key': 'value', 'email': 'test@company.com', 'name': 'a company'}
                }
            )

    @mock.patch('app.main.views.signup.render_create_application')
    @mock.patch('app.main.views.signup.decode_user_token')
    def test_missing_password(self, decode_user_token, render_create_application):
        decode_user_token.return_value = {}
        render_create_application.return_value = 'abc'

        self.client.post(
            self.url_for('main.create_application', token='test'),
            data={'csrf_token': FakeCsrf.valid_token}
        )

        render_create_application.assert_called_once_with('test', {}, {'password': {'required': True}})

    @mock.patch('app.main.views.signup.render_create_application')
    @mock.patch('app.main.views.signup.decode_user_token')
    def test_short_password(self, decode_user_token, render_create_application):
        decode_user_token.return_value = {}
        render_create_application.return_value = 'abc'

        self.client.post(
            self.url_for('main.create_application', token='test'),
            data={'csrf_token': FakeCsrf.valid_token, 'password': '12345'}
        )

        render_create_application.assert_called_once_with('test', {'password': u'12345'}, {'password': {'min': True}})

    @mock.patch('app.main.views.signup.data_api_client')
    @mock.patch('app.main.views.signup.decode_user_token')
    def test_create_user_fails(self, decode_user_token, data_api_client):
        decode_user_token.return_value = {'name': 'joe', 'email': 'test@company.com'}
        data_api_client.create_user.side_effect = HTTPError('fail')

        res = self.client.post(
            self.url_for('main.create_application', token='test'),
            data={'csrf_token': FakeCsrf.valid_token, 'password': '12345678901'}
        )

        assert res.status_code == 503

    @mock.patch('app.main.views.signup.data_api_client')
    @mock.patch('app.main.views.signup.decode_user_token')
    def test_create_application_fails(self, decode_user_token, data_api_client):
        decode_user_token.return_value = {'name': 'joe', 'email': 'test@company.com'}
        data_api_client.create_user.return_value = self.user(123, 'test@email.com', None, None, 'Users name')
        data_api_client.create_user.side_effect = HTTPError('fail')

        res = self.client.post(
            self.url_for('main.create_application', token='test'),
            data={'csrf_token': FakeCsrf.valid_token, 'password': '12345678901'}
        )

        assert res.status_code == 503

    @mock.patch('app.main.views.signup.data_api_client')
    @mock.patch('app.main.views.signup.decode_user_token')
    def test_create_application_success(self, decode_user_token, data_api_client):
        decode_user_token.return_value = {'name': 'joe', 'email': 'test@company.com'}
        data_api_client.create_user.return_value = self.user(123, 'test@email.com', None, None, 'Users name')
        data_api_client.create_application.return_value = {'application': {'id': 999}}

        res = self.client.post(
            self.url_for('main.create_application', token='test'),
            data={'csrf_token': FakeCsrf.valid_token, 'password': '12345678901'}
        )

        assert res.status_code == 302
        assert res.location == self.url_for('main.render_application', id=999, step='start', _external=True)
        data_api_client.create_application.assert_called_once_with(
            {'status': 'saved'}
        )


class TestApplicationPage(BaseApplicationTest):

    def setup(self):
        super(TestApplicationPage, self).setup()

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    def test_application_entrypoint_redirects(self, render_component, data_api_client):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        with self.app.test_client():
            self.login_as_applicant()
            data_api_client.get_application.side_effect = get_application
            res = self.client.get(self.expand_path('/application'))

            assert res.status_code == 302

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    def test_application_entrypoint_redirects_for_supplier(self, render_component, data_api_client):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        with self.app.test_client():
            self.login()
            data_api_client.get_application.side_effect = get_application
            res = self.client.get(self.expand_path('/application'))

            assert res.status_code == 302

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    def test_application_page_renders(self, render_component, data_api_client):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        with self.app.test_client():
            self.login_as_applicant()
            data_api_client.get_application.side_effect = get_application
            res = self.client.get(self.expand_path('/application/1'))

            assert res.status_code == 200

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    def test_application_page_denies_role_access(self, render_component, data_api_client):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        with self.app.test_client():
            self.login_as_buyer()
            data_api_client.get_application.side_effect = get_application
            res = self.client.get(self.expand_path('/application/1'))

            assert res.status_code == 302

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    def test_application_page_denies_other_applicants_access(self, render_component, data_api_client):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        with self.app.test_client():
            self.login_as_applicant()
            data_api_client.get_application.side_effect = get_another_application
            res = self.client.get(self.expand_path('/application/1'))

            assert res.status_code == 403

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    def test_application_update(self, render_component, data_api_client):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        with self.app.test_client():
            self.login_as_applicant()
            data_api_client.get_application.side_effect = get_application
            res = self.client.post(
                self.expand_path('/application/1'),
                data={'a': 'b', 'next_step_slug': 'slug', 'csrf_token': FakeCsrf.valid_token}
            )

            assert res.status_code == 302
            assert res.location == self.url_for('main.render_application', id=1, step='slug', _external=True)

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    def test_application_update_json(self, render_component, data_api_client):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        csrf = 'abc123'

        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = csrf

        with self.app.test_client():
            self.login_as_applicant()
            data_api_client.get_application.side_effect = get_application

            data_api_client.update_application.return_value = {
                'application': {
                    'links': {
                        'self': 'http://self'
                    }
                }
            }

            res = self.client.post(
                self.expand_path('/application/1'),
                data=json.dumps({'application': {'phone': '123'}, 'next_step_slug': 'slug'}),
                headers={'X-CSRFToken': csrf},
                content_type='application/json'
            )

            assert res.status_code == 200

            data = json.loads(res.get_data(as_text=True))
            assert 'links' not in data['application']

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    def test_application_update_denies_access(self, render_component, data_api_client):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        with self.app.test_client():
            self.login_as_buyer()
            data_api_client.get_application.side_effect = get_application
            res = self.client.post(
                self.expand_path('/application/1'),
                data={'csrf_token': FakeCsrf.valid_token},
            )

            assert res.status_code == 302

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    def test_application_update_denies_edit_after_submit(self, render_component, data_api_client):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        with self.app.test_client():
            self.login_as_applicant()
            data_api_client.get_application.side_effect = get_submitted_application
            res = self.client.post(
                self.expand_path('/application/1'),
                data={'csrf_token': FakeCsrf.valid_token},
            )

            assert res.status_code == 302

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    def test_application_submit(self, render_component, data_api_client):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        with self.app.test_client():
            self.login_as_applicant()
            data_api_client.get_application.side_effect = get_application
            res = self.client.post(self.expand_path('/application/submit/1'), data={'csrf_token': FakeCsrf.valid_token})

            assert res.status_code == 200

            args, kwargs = data_api_client.req.applications().submit().post.call_args
            assert kwargs['data']['user_id'] == 234

    @mock.patch('app.main.views.signup.render_template')
    @mock.patch('app.main.views.signup.send_email')
    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    def test_application_authorise_has_account(self, render_component, data_api_client, send_email, render_template):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'
        render_template.return_value = ''

        with self.app.test_client():
            self.login_as_applicant()
            data_api_client.get_application.side_effect = get_application
            res = self.client.post(self.expand_path('/application/1/authorise'),
                                   data={'csrf_token': FakeCsrf.valid_token})

            assert res.status_code == 200

            render_template.called_with(
                'emails/create_authorise_email_has_account.html',
                business_name='My Amazing Company',
                name='Ms Authorised Rep',
                url='http://localhost/sellers/application/1/submit'
            )

            send_email.assert_called_once_with(
                'applicant@email.com',
                mock.ANY,
                self.app.config['INVITE_EMAIL_SUBJECT'],
                self.app.config['INVITE_EMAIL_FROM'],
                self.app.config['INVITE_EMAIL_NAME']
            )

    @mock.patch('app.main.views.signup.render_template')
    @mock.patch('app.main.views.signup.send_email')
    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.render_component')
    def test_application_authorise_no_account(self, render_component, data_api_client, send_email, render_template):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'
        render_template.return_value = ''

        with self.app.test_client():
            self.login_as_applicant()
            data_api_client.get_application.side_effect = get_unauthorised_application
            res = self.client.post(self.expand_path('/application/1/authorise'),
                                   data={'csrf_token': FakeCsrf.valid_token})

            assert res.status_code == 200

            render_template.called_with(
                'emails/create_authorise_email_no_account.html',
                business_name='My Amazing Company',
                name='Ms Authorised Rep',
                url='http://localhost/sellers/application/1/submit'
            )

            send_email.assert_called_once_with(
                'test@email.com',
                mock.ANY,
                self.app.config['INVITE_EMAIL_SUBJECT'],
                self.app.config['INVITE_EMAIL_FROM'],
                self.app.config['INVITE_EMAIL_NAME']
            )


class TestDocuments(BaseApplicationTest):

    def setup(self):
        super(TestDocuments, self).setup()

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.s3_download_file')
    def test_document_download(self, download_file, data_api_client):
        output = BytesIO()
        output.write('test file contents')
        download_file.return_value = output.getvalue()

        with self.app.test_client():
            self.login_as_applicant()
            data_api_client.get_application.side_effect = get_application
            res = self.client.get(self.expand_path('/application/1/documents/test.pdf'))

            assert res.status_code == 200
            assert res.mimetype == 'application/pdf'
            assert res.data == 'test file contents'
            download_file.assert_called_once_with('test.pdf', 'applications/1')

    @mock.patch("app.main.views.signup.data_api_client")
    @mock.patch('app.main.views.signup.s3_upload_file_from_request')
    def test_document_upload(self, upload_file, data_api_client):
        upload_file.return_value = 'test.pdf'

        with self.app.test_request_context():
            self.login_as_applicant()
            data_api_client.get_application.side_effect = get_application
            res = self.client.post(
                self.expand_path('/application/1/documents/test'),
                data={'csrf_token': FakeCsrf.valid_token}
            )

            assert res.status_code == 200
            assert res.data == 'test.pdf'
            upload_file.assert_called_once_with(mock.ANY, 'test', 'applications/1')
