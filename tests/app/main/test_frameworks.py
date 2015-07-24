from nose.tools import assert_equal
import mock
from mock import Mock
from lxml import html
from dmutils.apiclient import APIError

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
                doc.xpath('//input[@id="registration_number"]/@value')[0], "")

    def test_get_with_with_previous_answers(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_selection_answers.return_value = {
                "selectionAnswers": {
                    "questionAnswers": {
                        "registration_number": "12345",
                    }
                }
            }

            res = self.client.get(
                '/suppliers/frameworks/g-cloud-7/declaration')

            assert_equal(res.status_code, 200)
            doc = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                doc.xpath('//input[@id="registration_number"]/@value')[0],
                "12345")

    def test_post_valid_data(self, data_api_client):
        with self.app.test_client():
            self.login()
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration',
                data={
                    'registration_number': '12345',
                    'bankrupt': 'val-2',
                })

            assert_equal(res.status_code, 200)
            data_api_client.answer_selection_questions.assert_called_with(
                1234, 'g-cloud-7',
                {'registration_number': '12345', 'bankrupt': False},
                'email@email.com'
            )
            doc = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                doc.xpath('//input[@id="registration_number"]/@value')[0],
                "12345")
            assert_equal(
                len(doc.xpath('//input[@id="bankrupt-no"]/@checked')), 1)

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
                    'registration_number': '12345',
                    'bankrupt': 'val-2',
                })

            assert_equal(res.status_code, 400)
