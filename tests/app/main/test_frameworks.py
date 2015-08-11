from nose.tools import assert_equal, assert_true
import mock
from mock import Mock
from lxml import html
from dmutils.apiclient import APIError
from dmutils.email import MandrillException
from flask import render_template

from ..helpers import BaseApplicationTest


@mock.patch('app.main.views.frameworks.data_api_client')
class TestFrameworksDashboard(BaseApplicationTest):
    def test_shows(self, data_api_client):
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            assert_equal(res.status_code, 200)


@mock.patch('app.main.views.frameworks.data_api_client')
class TestSupplierDeclaration(BaseApplicationTest):
    def test_get_with_no_previous_answers(self, data_api_client):
        with self.app.test_client():
            self.login()

            response = Mock()
            response.status_code = 404
            data_api_client.get_selection_answers.side_effect = \
                APIError(response)

            res = self.client.get(
                '/suppliers/frameworks/g-cloud-7/declaration')

            assert_equal(res.status_code, 200)
            doc = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                doc.xpath('//input[@id="PR-1-yes"]/@checked'), [])
            assert_equal(
                doc.xpath('//input[@id="PR-1-no"]/@checked'), [])

    def test_get_with_with_previous_answers(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_selection_answers.return_value = {
                "selectionAnswers": {
                    "questionAnswers": {
                        "PR1": False,
                    }
                }
            }

            res = self.client.get(
                '/suppliers/frameworks/g-cloud-7/declaration')

            assert_equal(res.status_code, 200)
            doc = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                len(doc.xpath('//input[@id="PR1-no"]/@checked')), 1)

    def test_post_valid_data(self, data_api_client):
        with self.app.test_client():
            self.login()
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration',
                data={
                    'PR1': True,
                    'SQ1-2a': 'Jo Bloggs',
                })

            assert_equal(res.status_code, 302)
            data_api_client.answer_selection_questions.assert_called_with(
                1234, 'g-cloud-7',
                {'PR1': True, 'SQ1-2a': 'Jo Bloggs'},
                'email@email.com'
            )

    def test_post_valid_data_with_api_failure(self, data_api_client):
        with self.app.test_client():
            self.login()

            response = Mock()
            response.status_code = 400
            data_api_client.answer_selection_questions.side_effect = \
                APIError(response)

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration',
                data={
                    'PR1': True,
                    'SQ1-2a': 'Jo Bloggs',
                })

            assert_equal(res.status_code, 400)


class TestSendClarificationQuestionEmail(BaseApplicationTest):

    def _send_email(self, clarification_question):
        with self.app.test_client():
            self.login()

            return self.client.post(
                "/suppliers/frameworks/g-cloud-7/updates",
                data={
                    'clarification_question': clarification_question,
                }
            )

    def _assert_email(self, send_email, is_called=True):

        if is_called:
            assert_equal(1, send_email.call_count)
            send_email.assert_called_once_with(
                "digitalmarketplace@mailinator.com",
                mock.ANY,
                "MANDRILL",
                "Clarification question",
                "suppliers@digitalmarketplace.service.gov.uk",
                "G-Cloud 7 Supplier",
                ["clarification-question"]
            )

        else:
            assert_equal(0, send_email.call_count)

    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_not_send_email_if_invalid_clarification_question(self, send_email):

        for invalid_clarification_question in [
            {
                'question': '',  # empty question
                'error_message': 'Question cannot be empty'
            }, {
                'question': '\t   \n\n\n',  # whitespace-only question
                'error_message': 'Question cannot be empty'
            },
            {
                'question': ('ten__chars' * 500) + '1',  # 5000+ char question
                'error_message': 'Question cannot be longer than 5000 characters'
            }
        ]:

            response = self._send_email(invalid_clarification_question['question'])
            self._assert_email(send_email, is_called=False)

            assert_equal(response.status_code, 400)
            assert_true(
                self.strip_all_whitespace('There was a problem with your submitted question')
                in self.strip_all_whitespace(response.get_data(as_text=True))
            )
            assert_true(
                self.strip_all_whitespace(invalid_clarification_question['error_message'])
                in self.strip_all_whitespace(response.get_data(as_text=True))
            )

    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_call_send_email_with_correct_params(self, send_email):

        clarification_question = 'This is a clarification question.'
        response = self._send_email(clarification_question)

        self._assert_email(send_email)

        assert_equal(response.status_code, 200)
        assert_true(
            self.strip_all_whitespace('<p class="banner-message">Message sent. Cheers.</p>')
            in self.strip_all_whitespace(response.get_data(as_text=True))
        )

    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_be_a_503_if_email_fails(self, send_email):
        send_email.side_effect = MandrillException("Arrrgh")

        clarification_question = 'This is a clarification question.'
        response = self._send_email(clarification_question)
        self._assert_email(send_email)

        assert_equal(response.status_code, 503)
