# coding=utf-8

import mock
from nose.tools import assert_equal, assert_true
from .helpers import BaseApplicationTest

from dmapiclient.errors import HTTPError
from dmutils.forms import FakeCsrf

from app.main.helpers.frameworks import question_references


class TestApplication(BaseApplicationTest):
    def setup(self):
        super(TestApplication, self).setup()

    def test_response_headers(self):
        response = self.client.get(self.url_for('main.create_new_supplier'))

        assert 200 == response.status_code

    def test_url_with_non_canonical_trailing_slash(self):
        response = self.client.get(self.url_for('main.create_new_supplier') + '/')
        assert 301 == response.status_code
        assert self.url_for('main.create_new_supplier', _external=True) == response.location

    @mock.patch('app.main.views.suppliers.data_api_client')
    def test_503(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_supplier.side_effect = HTTPError('API is down')
            self.app.config['DEBUG'] = False

            res = self.client.get(self.url_for('main.dashboard'))
            assert_equal(503, res.status_code)
            assert_true(
                u"Sorry, we’re experiencing technical difficulties"
                in res.get_data(as_text=True))
            assert_true(
                "Try again later."
                in res.get_data(as_text=True))

    def test_header_xframeoptions_set_to_deny(self):
        response = self.client.get(self.url_for('main.create_new_supplier'))
        assert 200 == response.status_code
        assert 'DENY', respose.headers['X-Frame-Options']

    @mock.patch('app.main.views.login.send_email')
    @mock.patch('app.main.views.login.data_api_client')
    def test_csrf_protection(self, data_api_client, send_email):
        response = self.client.post(
            self.url_for('main.send_invite_user'),
            data={
                'email_address': 'me@example.com',
                'csrf_token': FakeCsrf.valid_token,
            }
        )
        assert response.status_code < 400
        response = self.client.post(
            self.url_for('main.send_invite_user'),
            data={'email_address': 'evil@example.com'}
        )
        assert 400 == response.status_code


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
