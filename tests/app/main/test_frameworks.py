# -*- coding: utf-8 -*-
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

    def test_interest_registered_in_framework(self, data_api_client):
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            assert_equal(res.status_code, 200)
            data_api_client.create_audit_event.assert_called_once_with(
                audit_type="register_framework_interest",
                user="email@email.com",
                object_type="suppliers",
                object_id=1234,
                data={"frameworkSlug": "g-cloud-7"})

    def test_declaration_status_when_complete(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_selection_answers.return_value = True

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            doc = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                len(doc.xpath('//p[contains(text(), "You have made the declaration")]')),
                1)

    def test_declaration_status_when_not_complete(self, data_api_client):
        with self.app.test_client():
            self.login()

            response = Mock()
            response.status_code = 404
            data_api_client.get_selection_answers.side_effect = APIError(response)

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            doc = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                len(doc.xpath('//p[contains(text(), "You have made the declaration")]')),
                0)


FULL_G7_SUBMISSION = {
    "PR1": "true",
    "PR2": "true",
    "PR3": "true",
    "PR4": "true",
    "PR5": "true",
    "SQ1-1i-i": "true",
    "SQ2-1abcd": "true",
    "SQ2-1e": "true",
    "SQ2-1f": "true",
    "SQ2-1ghijklmn": "true",
    "SQ2-2a": "true",
    "SQ3-1a": "true",
    "SQ3-1b": "true",
    "SQ3-1c": "true",
    "SQ3-1d": "true",
    "SQ3-1e": "true",
    "SQ3-1f": "true",
    "SQ3-1g": "true",
    "SQ3-1h-i": "true",
    "SQ3-1h-ii": "true",
    "SQ3-1i-i": "true",
    "SQ3-1i-ii": "true",
    "SQ3-1j": "true",
    "SQ3-1k": "Blah",
    "SQ4-1a": "true",
    "SQ4-1b": "true",
    "SQ5-2a": "true",
    "SQD2b": "true",
    "SQD2d": "true",
    "SQ1-1a": "Blah",
    "SQ1-1b": "Blah",
    "SQ1-1cii": "Blah",
    "SQ1-1d": "Blah",
    "SQ1-1e": "Blah",
    "SQ1-1f": "Blah",
    "SQ1-1g": "999999999",
    "SQ1-1h": "999999999",
    "SQ1-1i-ii": "Blah",
    "SQ1-1j-ii": "Blah",
    "SQ1-1k": "Blah",
    "SQ1-1n": "Blah",
    "SQ1-1o": "Blah",
    "SQ1-2a": "Blah",
    "SQ1-2b": "Blah",
    "SQ2-2b": "Blah",
    "SQ4-1c": "Blah",
    "SQD2c": "Blah",
    "SQD2e": "Blah",
    "SQ1-1ci": "public limited company",
    "SQ1-1j-i": "licensed?",
    "SQ1-1l": "voluntary community social enterprise (VCSE)?",
    "SQ1-1m": "micro",
    "SQ1-3": "on-demand self-service. blah blah",
    "SQ5-1a": u"Yes – your organisation has, blah blah",
    "SQC2": [
        "race?",
        "sexual orientation?",
        "disability?",
        "age equality?",
        "religion or belief?",
        "gender (sex)?",
        "gender reassignment?",
        "marriage or civil partnership?",
        "pregnancy or maternity?",
        "human rights?"
    ],
    "SQC3": "true",
    "SQA2": "true",
    "SQA3": "true",
    "SQA4": "true",
    "SQA5": "true",
    "AQA3": "true"
}


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
                data=FULL_G7_SUBMISSION)

            assert_equal(res.status_code, 302)
            data_api_client.answer_selection_questions.assert_called()

    def test_post_valid_data_with_api_failure(self, data_api_client):
        with self.app.test_client():
            self.login()

            response = Mock()
            response.status_code = 400
            data_api_client.answer_selection_questions.side_effect = \
                APIError(response)

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration',
                data=FULL_G7_SUBMISSION)

            assert_equal(res.status_code, 400)

    @mock.patch('app.main.views.frameworks.get_error_messages')
    def test_post_with_validation_errors(self, get_error_messages, data_api_client):
        """Test that answers are not saved if there are errors

        For unit tests of the validation see :mod:`tests.app.main.helpers.test_frameworks`
        """
        with self.app.test_client():
            self.login()

            get_error_messages.return_value = {'PR1': {'input_name': 'PR1', 'message': 'this is invalid'}}

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration',
                data=FULL_G7_SUBMISSION)

            assert_equal(res.status_code, 400)
            assert not data_api_client.answer_selection_questions.called


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
            self.strip_all_whitespace('<p class="banner-message">Your clarification message has been sent.</p>')
            in self.strip_all_whitespace(response.get_data(as_text=True))
        )

    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_be_a_503_if_email_fails(self, send_email):
        send_email.side_effect = MandrillException("Arrrgh")

        clarification_question = 'This is a clarification question.'
        response = self._send_email(clarification_question)
        self._assert_email(send_email)

        assert_equal(response.status_code, 503)
