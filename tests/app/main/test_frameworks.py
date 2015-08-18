# -*- coding: utf-8 -*-
from nose.tools import assert_equal, assert_true, assert_in
import os
import mock
from mock import Mock
from lxml import html
from dmutils.apiclient import APIError
from dmutils.audit import AuditTypes
from dmutils.email import MandrillException
from dmutils.s3 import S3ResponseError

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
            data_api_client.find_audit_events.return_value = {
                "auditEvents": []
            }

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            assert_equal(res.status_code, 200)
            data_api_client.create_audit_event.assert_called_once_with(
                audit_type=AuditTypes.register_framework_interest,
                user="email@email.com",
                object_type="suppliers",
                object_id=1234,
                data={"frameworkSlug": "g-cloud-7"})

    def test_interest_in_framework_only_registered_once(self, data_api_client):
        with self.app.test_client():
            self.login()
            data_api_client.find_audit_events.return_value = {
                "auditEvents": [{"data": {"frameworkSlug": "g-cloud-7"}}]
            }

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            assert_equal(res.status_code, 200)
            assert not data_api_client.create_audit_event.called

    def test_declaration_status_when_complete(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_selection_answers.return_value = \
                {"selectionAnswers":
                    {"questionAnswers": FULL_G7_SUBMISSION}
                 }

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            doc = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                len(doc.xpath('//p[contains(text(), "All services marked as complete will be automatically submitted at 3pm BST, 6 October")]')),  # noqa
                1)

    def test_declaration_status_when_started(self, data_api_client):
        with self.app.test_client():
            self.login()

            submission = FULL_G7_SUBMISSION.copy()
            # User has not yet submitted page 3 of the declaration
            del submission['SQ2-1abcd']
            del submission['SQ2-1e']
            del submission['SQ2-1f']
            del submission['SQ2-1ghijklmn']
            submission.update({"status": "started"})

            data_api_client.get_selection_answers.return_value = \
                {"selectionAnswers":
                    {"questionAnswers": submission}
                 }

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            doc = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                len(doc.xpath('//p[contains(text(), "You have started making the supplier declaration, but it is not yet finished")]')),  # noqa
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
                len(doc.xpath('//p[contains(text(), "You haven\'t made the supplier declaration")]')),
                1)


FULL_G7_SUBMISSION = {
    "status": "complete",
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
    "AQA3": "true",
    "SQE2a": ["as a prime contractor, using third parties (subcontractors) to provide some services"]
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
                '/suppliers/frameworks/g-cloud-7/declaration/g_cloud_7_essentials')

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
                        "status": "started",
                        "PR1": False,
                    }
                }
            }

            res = self.client.get(
                '/suppliers/frameworks/g-cloud-7/declaration/g_cloud_7_essentials')

            assert_equal(res.status_code, 200)
            doc = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                len(doc.xpath('//input[@id="input-PR1-no"]/@checked')), 1)

    def test_post_valid_data(self, data_api_client):
        with self.app.test_client():
            self.login()
            data_api_client.get_selection_answers.return_value = {
                "selectionAnswers": {
                    "questionAnswers": {"status": "started"}
                }
            }
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration/g_cloud_7_essentials',
                data=FULL_G7_SUBMISSION)

            assert_equal(res.status_code, 302)
            data_api_client.answer_selection_questions.assert_called()

    def test_post_valid_data_with_api_failure(self, data_api_client):
        with self.app.test_client():
            self.login()
            response = Mock()
            response.status_code = 400
            data_api_client.get_selection_answers.return_value = {
                "selectionAnswers": {
                    "questionAnswers": {"status": "started"}
                }
            }
            data_api_client.answer_selection_questions.side_effect = \
                APIError(response)

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration/g_cloud_7_essentials',
                data=FULL_G7_SUBMISSION)

            assert_equal(res.status_code, 400)

    @mock.patch('app.main.views.frameworks.get_error_messages_for_page')
    def test_post_with_validation_errors(self, get_error_messages_for_page, data_api_client):
        """Test that answers are not saved if there are errors

        For unit tests of the validation see :mod:`tests.app.main.helpers.test_frameworks`
        """
        with self.app.test_client():
            self.login()

            get_error_messages_for_page.return_value = {'PR1': {'input_name': 'PR1', 'message': 'this is invalid'}}

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration/g_cloud_7_essentials',
                data=FULL_G7_SUBMISSION)

            assert_equal(res.status_code, 400)
            assert not data_api_client.answer_selection_questions.called


@mock.patch('dmutils.s3.S3')
class TestFrameworkUpdatesPage(BaseApplicationTest):

    def _assert_page_title_and_table_headings(self, doc, tables_exist=True):

        assert_true(
            self.strip_all_whitespace('G-Cloud 7 updates')
            in self.strip_all_whitespace(doc.xpath('//h1')[0].text)
        )

        section_names = [
            'G-Cloud 7 communications',
            'G-Cloud 7 clarification questions and answers',
        ]

        headers = doc.xpath('//div[contains(@class, "updates-document-tables")]/h2[@class="summary-item-heading"]')
        assert_equal(len(headers), 2)
        for index, section_name in enumerate(section_names):
            assert_true(
                self.strip_all_whitespace(section_name)
                in self.strip_all_whitespace(headers[index].text)
            )

        if tables_exist:
            table_captions = doc.xpath('//div[contains(@class, "updates-document-tables")]/table/caption')
            assert_equal(len(table_captions), 2)
            for index, section_name in enumerate(section_names):
                assert_true(
                    self.strip_all_whitespace(section_name)
                    in self.strip_all_whitespace(table_captions[index].text)
                )

    @staticmethod
    def _return_fake_s3_file_dict(directory, file, last_modified=None, size=None):

        filename, ext = os.path.splitext(file)

        return {
            'path': 'g-cloud-7-updates/{}/{}'.format(directory, file),
            'filename': filename,
            'ext': ext[:1],
            'last_modified': last_modified or '2015-08-17T14:00:00.000Z',
            'size': size if size is not None else 1
        }

    def test_should_be_a_503_if_connecting_to_amazon_fails(self, s3):
        # if s3 throws a 500-level error
        s3.side_effect = S3ResponseError(500, 'Amazon has collapsed. The internet is over.')

        with self.app.test_client():
            self.login()

            response = self.client.get(
                '/suppliers/frameworks/g-cloud-7/updates'
            )

            assert_equal(response.status_code, 503)
            assert_true(
                self.strip_all_whitespace("<h1>Sorry, we're experiencing technical difficulties</h1>")
                in self.strip_all_whitespace(response.get_data(as_text=True))
            )

    def test_empty_messages_exist_if_no_files_returned(self, s3):

        with self.app.test_client():
            self.login()

            response = self.client.get(
                '/suppliers/frameworks/g-cloud-7/updates'
            )

            assert_equal(response.status_code, 200)
            doc = html.fromstring(response.get_data(as_text=True))
            self._assert_page_title_and_table_headings(doc, tables_exist=False)

            for empty_message in [
                '<p class="summary-item-no-content">No communications have been sent out</p>',
                '<p class="summary-item-no-content">No clarification questions exist</p>',
            ]:
                assert_true(
                    self.strip_all_whitespace(empty_message)
                    in self.strip_all_whitespace(response.get_data(as_text=True))
                )

    def test_the_tables_should_be_displayed_correctly(self, s3):

        filenames = [
            ('communications', 'file 1', 'odt'),
            ('communications', 'file 2', 'odt'),
            ('clarifications', 'file 3', 'odt'),
            ('clarifications', 'file 4', 'odt'),
        ]

        # the communications table is always before the clarifications table
        s3.return_value.list.return_value = [
            self._return_fake_s3_file_dict(section, "{}.{}".format(filename, ext))
            for section, filename, ext in filenames
        ]

        with self.app.test_client():
            self.login()

            response = self.client.get(
                '/suppliers/frameworks/g-cloud-7/updates'
            )
            doc = html.fromstring(response.get_data(as_text=True))
            self._assert_page_title_and_table_headings(doc)

            tables = doc.xpath('//div[contains(@class, "updates-document-tables")]/table')

            # test that for each table, we have the right number of rows
            for table in tables:
                item_rows = table.findall('.//tr[@class="summary-item-row"]')
                assert_equal(len(item_rows), 2)

                # test that the file names and urls are right
                for row in item_rows:
                    section, filename, ext = filenames.pop(0)
                    filename_link = row.find('.//a[@class="document-link-with-icon"]')

                    assert_true(filename in filename_link.text_content())
                    assert_equal(
                        filename_link.get('href'),
                        '/suppliers/frameworks/g-cloud-7/g-cloud-7-updates/{}/{}.{}'.format(
                            section, filename.replace(' ', '%20'), ext
                        )
                    )

    def test_names_with_the_section_name_in_them_will_display_correctly(self, s3):

        # for example: 'g-cloud-7-updates/clarifications/communications.odf'
        filenames = [
            ('communications', 'clarifications file', 'odt'),
            ('clarifications', 'communications file', 'odt')
        ]

        s3.return_value.list.return_value = [
            self._return_fake_s3_file_dict(section, "{}.{}".format(filename, ext))
            for section, filename, ext in filenames
        ]

        with self.app.test_client():
            self.login()

            response = self.client.get(
                '/suppliers/frameworks/g-cloud-7/updates'
            )
            doc = html.fromstring(response.get_data(as_text=True))
            self._assert_page_title_and_table_headings(doc)

            tables = doc.xpath('//div[contains(@class, "updates-document-tables")]/table')

            # test that for each table, we have the right number of rows
            for table in tables:
                item_rows = table.findall('.//tr[@class="summary-item-row"]')
                assert_equal(len(item_rows), 1)

                # test that the file names and urls are right
                for row in item_rows:
                    section, filename, ext = filenames.pop(0)
                    filename_link = row.find('.//a[@class="document-link-with-icon"]')

                    assert_true(filename in filename_link.text_content())
                    assert_equal(
                        filename_link.get('href'),
                        '/suppliers/frameworks/g-cloud-7/g-cloud-7-updates/{}/{}.{}'.format(
                            section, filename.replace(' ', '%20'), ext
                        )
                    )


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

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_not_send_email_if_invalid_clarification_question(self, send_email, s3):

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

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.data_api_client')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_call_send_email_with_correct_params(self, send_email, data_api_client, s3):

        clarification_question = 'This is a clarification question.'
        response = self._send_email(clarification_question)

        self._assert_email(send_email)

        assert_equal(response.status_code, 200)
        assert_true(
            self.strip_all_whitespace('<p class="banner-message">Your clarification message has been sent.</p>')
            in self.strip_all_whitespace(response.get_data(as_text=True))
        )

    @mock.patch('app.main.views.frameworks.data_api_client')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_create_audit_event(self, send_email, data_api_client):
        clarification_question = 'This is a clarification question'
        response = self._send_email(clarification_question)

        self._assert_email(send_email)

        assert_equal(response.status_code, 200)
        data_api_client.create_audit_event.assert_called_with(
            audit_type=AuditTypes.send_clarification_question,
            user="email@email.com",
            object_type="suppliers",
            object_id=1234,
            data={"question": clarification_question})

    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_be_a_503_if_email_fails(self, send_email):
        send_email.side_effect = MandrillException("Arrrgh")

        clarification_question = 'This is a clarification question.'
        response = self._send_email(clarification_question)
        self._assert_email(send_email)

        assert_equal(response.status_code, 503)


@mock.patch('app.main.views.frameworks.data_api_client')
@mock.patch('app.main.views.frameworks.count_unanswered_questions')
class TestG7ServicesList(BaseApplicationTest):

    def test_drafts_list_progress_count(self, count_unanswered, apiclient):
        with self.app.test_client():
            self.login()

        count_unanswered.return_value = 3, 1

        apiclient.find_draft_services.return_value = {
            'services': [
                {'serviceName': 'draft', 'lot': 'SCS', 'status': 'not-submitted'},
            ]
        }

        res = self.client.get('/suppliers/frameworks/g-cloud-7/services')

        assert_true(u'Service can be moved to complete' not in res.get_data(as_text=True))
        assert_in(u'4 questions unanswered', res.get_data(as_text=True))

    def test_drafts_list_can_be_completed(self, count_unanswered, apiclient):
        with self.app.test_client():
            self.login()

        count_unanswered.return_value = 0, 1

        apiclient.find_draft_services.return_value = {
            'services': [
                {'serviceName': 'draft', 'lot': 'SCS', 'status': 'not-submitted'},
            ]
        }

        res = self.client.get('/suppliers/frameworks/g-cloud-7/services')

        assert_in(u'Service can be moved to complete', res.get_data(as_text=True))
        assert_in(u'1 optional question unanswered', res.get_data(as_text=True))

    def test_drafts_list_completed(self, count_unanswered, apiclient):
        with self.app.test_client():
            self.login()

        count_unanswered.return_value = 0, 1

        apiclient.find_draft_services.return_value = {
            'services': [
                {'serviceName': 'draft', 'lot': 'SCS', 'status': 'submitted'},
            ]
        }

        res = self.client.get('/suppliers/frameworks/g-cloud-7/services')

        assert_true(u'Service can be moved to complete' not in res.get_data(as_text=True))
        assert_in(u'1 optional question unanswered', res.get_data(as_text=True))
