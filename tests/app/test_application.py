# coding=utf-8

import mock
from .helpers import BaseApplicationTest
from dmapiclient.errors import HTTPError
from app.main.helpers.frameworks import question_references


class TestApplication(BaseApplicationTest):

    def test_response_headers(self):
        response = self.client.get('/suppliers/create')

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
        assert u"Check you’ve entered the correct web " \
            u"address or start again on the Digital Marketplace homepage." in res.get_data(as_text=True)
        assert u"If you can’t find what you’re looking for, contact us at " \
            u"<a href=\"mailto:enquiries@digitalmarketplace.service.gov.uk?" \
            u"subject=Digital%20Marketplace%20feedback\" title=\"Please " \
            u"send feedback to enquiries@digitalmarketplace.service.gov.uk\">" \
            u"enquiries@digitalmarketplace.service.gov.uk</a>" in res.get_data(as_text=True)

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
        res = self.client.get('/suppliers/create')
        assert res.status_code == 200
        assert 'DENY', res.headers['X-Frame-Options']

    def test_should_use_local_cookie_page_on_cookie_message(self):
        res = self.client.get('/suppliers/create')
        assert res.status_code == 200
        assert '<p>GOV.UK uses cookies to make the site simpler. <a href="/cookies">Find ' \
            'out more about cookies</a></p>' in res.get_data(as_text=True)


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
