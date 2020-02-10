# coding=utf-8
import mock
from lxml import html

from wtforms import ValidationError
from dmapiclient.errors import HTTPError

from app.main.helpers.frameworks import question_references
from .helpers import BaseApplicationTest


class TestApplication(BaseApplicationTest):
    def setup_method(self, method):
        super(TestApplication, self).setup_method(method)

    def test_response_headers(self):
        response = self.client.get('/suppliers/create/start')

        assert response.status_code == 200
        assert (
            response.headers['cache-control'] ==
            "no-cache"
        )

    def test_url_with_non_canonical_trailing_slash(self):
        response = self.client.get('/suppliers/')
        assert response.status_code == 301
        assert "http://localhost/suppliers" == response.location

    def test_404(self):
        res = self.client.get('/service/1234')
        assert res.status_code == 404
        assert "Check you’ve entered the correct web " \
               "address or start again on the Digital Marketplace homepage." in res.get_data(as_text=True)
        assert "If you can’t find what you’re looking for, contact us at " in res.get_data(as_text=True)

    @mock.patch('app.main.views.suppliers.data_api_client')
    def test_503(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_supplier.side_effect = HTTPError('API is down')
            self.app.config['DEBUG'] = False

            res = self.client.get('/suppliers')
            assert res.status_code == 503
            assert u"Sorry, we’re experiencing technical difficulties" in res.get_data(as_text=True)
            assert "Try again later." in res.get_data(as_text=True)

    def test_header_xframeoptions_set_to_deny(self):
        res = self.client.get('/suppliers/create/start')
        assert res.status_code == 200
        assert 'DENY', res.headers['X-Frame-Options']

    def test_should_use_local_cookie_page_on_cookie_message(self):
        res = self.client.get('/suppliers/create/start')
        assert res.status_code == 200
        document = html.fromstring(res.get_data(as_text=True))
        cookie_banner = document.xpath('//div[@id="dm-cookie-banner"]')
        assert cookie_banner[0].xpath('//h2//text()')[0].strip() == "Can we store analytics cookies on your device?"

    @mock.patch('flask_wtf.csrf.validate_csrf', autospec=True)
    @mock.patch('app.main.views.suppliers.data_api_client')
    def test_csrf_handler_redirects_to_login(self, data_api_client, validate_csrf):
        self.login()
        with self.app.test_client():
            self.app.config['WTF_CSRF_ENABLED'] = True
            self.client.set_cookie(
                "localhost",
                self.app.config['DM_COOKIE_PROBE_COOKIE_NAME'],
                self.app.config['DM_COOKIE_PROBE_COOKIE_VALUE'],
            )
            data_api_client.get_supplier.return_value = {'suppliers': {'contactInformation': ['something']}}

            # This will raise a CSRFError for us when the form is validated
            validate_csrf.side_effect = ValidationError('The CSRF session token is missing.')

            res = self.client.post('/suppliers/registered-address/edit', data={'anything': 'really'})

            self.assert_flashes("Your session has expired. Please log in again.", expected_category="error")
            assert res.status_code == 302

            # POST requests will not preserve the request path on redirect
            assert res.location == 'http://localhost/user/login'
            assert validate_csrf.call_args_list == [mock.call(None)]


class TestQuestionReferences(object):

    def get_question_mock(self, id):
        return {'number': 19}

    def test_string_with_with_question_references(self):
        assert question_references(
            'Please see question [[otherQuestion]] for more info',
            self.get_question_mock
        ) == 'Please see question 19 for more info'

    def test_string_with_no_question_references(self):
        assert question_references(
            'What was the name of your first pet?',
            self.get_question_mock
        ) == 'What was the name of your first pet?'

    def test_string_with_broken_question_references(self):
        assert question_references(
            'Here’s ]][[ a [[string full of ] misused square brackets]',
            self.get_question_mock
        ) == 'Here’s ]][[ a [[string full of ] misused square brackets]'
