# coding: utf-8
from __future__ import unicode_literals

import mock
from dmapiclient import api_stubs, HTTPError
from dmapiclient.audit import AuditTypes
from dmutils.email import EmailError
from dmutils.forms import FakeCsrf
from ..helpers import BaseApplicationTest, FakeMail
from lxml import html


brief_form_submission = {
    'csrf_token': FakeCsrf.valid_token,
    "availability": "Next Tuesday",
    "dayRate": "£200",
    "essentialRequirements-0": 'ess0',
    "essentialRequirements-1": 'ess1',
    "essentialRequirements-2": 'ess2',
    "niceToHaveRequirements-0": 'nth0',
    "niceToHaveRequirements-1": 'nth1',
    "niceToHaveRequirements-2": 'nth2',
}

processed_brief_submission = {
    "availability": "Next Tuesday",
    "dayRate": "£200",
    "essentialRequirements": [
        'ess0',
        'ess1',
        'ess2'
    ],
    "niceToHaveRequirements": [
        'nth0',
        'nth1',
        'nth2'
    ],
}

ERROR_MESSAGE_PAGE_HEADING_APPLICATION = 'You can’t apply for this opportunity'
ERROR_MESSAGE_NO_SERVICE_ON_LOT_APPLICATION = \
    'You can’t apply for this opportunity because you didn’t say you'\
    ' could provide services in this category when you applied to the Digital Outcomes and Specialists framework.'
ERROR_MESSAGE_NO_SERVICE_ON_FRAMEWORK_APPLICATION = \
    'You can’t apply for this opportunity because you’re not a Digital Outcomes and Specialists supplier.'
ERROR_MESSAGE_NO_SERVICE_WITH_ROLE_APPLICATION = \
    'You can’t apply for this opportunity because you didn’t say you'\
    ' could provide this specialist role when you applied to the Digital Outcomes and Specialists framework.'

ERROR_MESSAGE_PAGE_HEADING_CLARIFICATION = 'You can’t ask a question about this opportunity'
ERROR_MESSAGE_NO_SERVICE_ON_LOT_CLARIFICATION = \
    'You can’t ask a question about this opportunity because you didn’t say you'\
    ' could provide services in this category when you applied to the Digital Outcomes and Specialists framework.'
ERROR_MESSAGE_NO_SERVICE_ON_FRAMEWORK_CLARIFICATION = \
    'You can’t ask a question about this opportunity because you’re not a Digital Outcomes and Specialists supplier.'
ERROR_MESSAGE_NO_SERVICE_WITH_ROLE_CLARIFICATION = \
    'You can’t ask a question about this opportunity because you didn’t say you'\
    ' could provide this specialist role when you applied to the Digital Outcomes and Specialists framework.'


@mock.patch('app.main.views.briefs.data_api_client', autospec=True)
class TestBriefQuestionAndAnswerSession(BaseApplicationTest):
    def test_q_and_a_session_details_requires_login(self, data_api_client):
        res = self.client.get(self.url_for('main.question_and_answer_session', brief_id=1))
        assert res.status_code == 302
        assert '/login' in res.headers['Location']

    def test_q_and_a_session_details(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live')
        data_api_client.get_brief.return_value['briefs']['questionAndAnswerSessionDetails'] = 'SESSION DETAILS'

        res = self.client.get(self.url_for('main.question_and_answer_session', brief_id=1))
        assert res.status_code == 200
        assert 'SESSION DETAILS' in res.get_data(as_text=True)

    def test_q_and_a_session_details_requires_existing_brief_id(self, data_api_client):
        self.login()
        data_api_client.get_brief.side_effect = HTTPError(mock.Mock(status_code=404))

        res = self.client.get(self.url_for('main.question_and_answer_session', brief_id=1))
        assert res.status_code == 404

    def test_q_and_a_session_details_requires_live_brief(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='expired')

        res = self.client.get(self.url_for('main.question_and_answer_session', brief_id=1))
        assert res.status_code == 404

    def test_q_and_a_session_details_requires_selected_supplier(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live')
        data_api_client.get_brief.return_value['briefs']['sellerSelector'] = 'someSellers'
        data_api_client.get_brief.return_value['briefs']['sellerEmailList'] = ['notyou@notyou.com']

        res = self.client.get(self.url_for('main.question_and_answer_session', brief_id=1))

        assert res.status_code == 400

    def test_q_and_a_session_details_requires_questions_to_be_open(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', clarification_questions_closed=True)

        res = self.client.get(self.url_for('main.question_and_answer_session', brief_id=1))
        assert res.status_code == 404


@mock.patch('app.main.views.briefs.data_api_client', autospec=True)
class TestBriefClarificationQuestions(BaseApplicationTest):
    def test_clarification_question_form_requires_login(self, data_api_client):
        res = self.client.get(self.url_for('main.ask_brief_clarification_question', brief_id=1))
        assert res.status_code == 302
        assert '/login' in res.headers['Location']

    def test_clarification_question_form(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live')

        res = self.client.get(self.url_for('main.ask_brief_clarification_question', brief_id=1))
        assert res.status_code == 200

    def test_clarification_question_form_requires_selected_supplier(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live')
        data_api_client.get_brief.return_value['briefs']['sellerSelector'] = 'someSellers'
        data_api_client.get_brief.return_value['briefs']['sellerEmailList'] = ['notyou@notyou.com']

        res = self.client.get(self.url_for('main.ask_brief_clarification_question', brief_id=1))
        assert res.status_code == 400

    def test_clarification_question_form_requires_existing_brief_id(self, data_api_client):
        self.login()
        data_api_client.get_brief.side_effect = HTTPError(mock.Mock(status_code=404))

        res = self.client.get(self.url_for('main.ask_brief_clarification_question', brief_id=1))
        assert res.status_code == 404

    def test_clarification_question_form_requires_live_brief(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='expired')

        res = self.client.get(self.url_for('main.ask_brief_clarification_question', brief_id=1))
        assert res.status_code == 404

    def test_clarification_question_form_requires_questions_to_be_open(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', clarification_questions_closed=True)

        res = self.client.get(self.url_for('main.ask_brief_clarification_question', brief_id=1))
        assert res.status_code == 404


@mock.patch('app.main.views.briefs.data_api_client', autospec=True)
class TestSubmitClarificationQuestions(BaseApplicationTest):
    def test_submit_clarification_question_requires_login(self, data_api_client):
        res = self.client.post(
            self.url_for('main.ask_brief_clarification_question', brief_id=1),
            data={'csrf_token': FakeCsrf.valid_token}
        )
        assert res.status_code == 302
        assert '/login' in res.headers['Location']

    @mock.patch('app.main.helpers.briefs.send_email')
    def test_submit_clarification_question(self, send_email, data_api_client):
        self.login()
        brief = api_stubs.brief(status="live")
        brief['briefs']['frameworkName'] = 'Brief Framework Name'
        brief['briefs']['clarificationQuestionsPublishedBy'] = '2016-03-29T10:11:13.000000Z'
        data_api_client.get_brief.return_value = brief

        res = self.client.post(self.url_for('main.ask_brief_clarification_question', brief_id=1234), data={
            'csrf_token': FakeCsrf.valid_token,
            'clarification-question': "important question",
        })
        assert res.status_code == 200

        send_email.assert_has_calls([
            mock.call(
                from_name='Brief Framework Name Supplier',
                email_body=FakeMail("important question"),
                from_email=self.app.config['CLARIFICATION_EMAIL_FROM'],
                to_email_addresses=['buyer@email.com'],
                subject=u"You\u2019ve received a new supplier question about \u2018I need a thing to do a thing\u2019"
            ),
            mock.call(
                from_name='Digital Marketplace Admin',
                email_body=FakeMail("important question"),
                from_email=self.app.config['CLARIFICATION_EMAIL_FROM'],
                to_email_addresses=['email@email.com'],
                subject=u"Your question about \u2018I need a thing to do a thing\u2019"
            ),
        ])

        data_api_client.create_audit_event.assert_called_with(
            audit_type=AuditTypes.send_clarification_question,
            object_type='briefs',
            data={'briefId': 1234, 'question': u'important question'},
            user='email@email.com',
            object_id=1234
        )

    @mock.patch('app.main.helpers.briefs.send_email')
    def test_submit_clarification_question_fails_on_email_backend_error(self, send_email, data_api_client):
        self.login()
        brief = api_stubs.brief(status="live")
        brief['briefs']['frameworkName'] = 'Framework Name'
        brief['briefs']['clarificationQuestionsPublishedBy'] = '2016-03-29T10:11:13.000000Z'
        data_api_client.get_brief.return_value = brief

        send_email.side_effect = EmailError

        res = self.client.post(self.url_for('main.ask_brief_clarification_question', brief_id=1234), data={
            'csrf_token': FakeCsrf.valid_token,
            'clarification-question': "important question",
        })
        assert res.status_code == 503

    def test_submit_clarification_question_requires_existing_brief_id(self, data_api_client):
        self.login()
        data_api_client.get_brief.side_effect = HTTPError(mock.Mock(status_code=404))

        res = self.client.post(self.url_for('main.ask_brief_clarification_question', brief_id=1), data={
            'csrf_token': FakeCsrf.valid_token,
        })
        assert res.status_code == 404

    def test_submit_clarification_question_requires_live_brief(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='expired')

        res = self.client.post(self.url_for('main.ask_brief_clarification_question', brief_id=1), data={
            'csrf_token': FakeCsrf.valid_token,
        })
        assert res.status_code == 404

    def test_submit_empty_clarification_question_returns_validation_error(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live')

        res = self.client.post(self.url_for('main.ask_brief_clarification_question', brief_id=1), data={
            'csrf_token': FakeCsrf.valid_token,
            'clarification-question': "",
        })
        assert res.status_code == 400
        assert "cannot be empty" in res.get_data(as_text=True)

    def test_clarification_question_has_max_length_limit(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live')

        res = self.client.post(self.url_for('main.ask_brief_clarification_question', brief_id=1), data={
            'csrf_token': FakeCsrf.valid_token,
            'clarification-question': "a" * 5100,
        })
        assert res.status_code == 400
        assert "cannot be longer than" in res.get_data(as_text=True)

    @mock.patch('app.main.helpers.briefs.send_email')
    def test_clarification_question_has_max_word_limit(self, send_email, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live')

        res = self.client.post(self.url_for('main.ask_brief_clarification_question', brief_id=1), data={
            'csrf_token': FakeCsrf.valid_token,
            'clarification-question': "a " * 101,
        })
        assert res.status_code == 400
        assert "must be no more than 100 words" in res.get_data(as_text=True)


@mock.patch("app.main.views.briefs.data_api_client")
class TestRespondToBrief(BaseApplicationTest):

    def setup(self):
        super(TestRespondToBrief, self).setup()

        self.brief = api_stubs.brief(status='live', lot_slug='digital-specialists')
        self.brief['briefs']['essentialRequirements'] = ['Essential one', 'Essential two', 'Essential three']
        self.brief['briefs']['niceToHaveRequirements'] = ['Nice one', 'Top one', 'Get sorted']
        self.brief['briefs']['dates'] = {}
        self.brief['briefs']['dates']['closing_time'] = '2016-11-23T07:00:00+00:00'

        lots = [api_stubs.lot(slug="digital-specialists", allows_brief=True)]
        self.framework = api_stubs.framework(status="live", slug="digital-outcomes-and-specialists",
                                             clarification_questions_open=False, lots=lots)

        with self.app.test_client():
            self.login()

    # def _test_breadcrumbs_on_brief_response_page(self, response):
    #     breadcrumbs = html.fromstring(response.get_data(as_text=True)).xpath(
    #         '//*[@class="global-breadcrumb"]/nav/div/ul/li'
    #     )
    #     brief = self.brief['briefs']

    #     breadcrumbs_we_expect = [
    #         ('Home', '/marketplace'),
    #         ('Opportunities', '/digital-outcomes-and-specialists/opportunities')
    #     ]

    #     # +1 is for the static current page
    #     assert len(breadcrumbs) == len(breadcrumbs_we_expect) + 1

    #     for index, link in enumerate(breadcrumbs_we_expect):
    #         assert breadcrumbs[index].find('a').text_content().strip() == link[0]
    #         assert breadcrumbs[index].find('a').get('href').strip() == link[1]

    def test_get_brief_response_page(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        res = self.client.get(self.url_for('main.brief_response', brief_id=1234))
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 200
        data_api_client.get_brief.assert_called_once_with(1234)
        assert len(doc.xpath('//h1[contains(text(), "Apply for ‘I need a thing to do a thing’")]')) == 1
        assert len(doc.xpath('//h2[contains(text(), "Do you have the essential skills and experience?")]')) == 1
        assert len(doc.xpath(
            '//h2[contains(text(), "Do you have any of the nice-to-have skills and experience?")]')) == 1
        # self._test_breadcrumbs_on_brief_response_page(res)

    def test_get_select_brief_response_page(self, data_api_client):
        brief = self.brief.copy()
        brief['briefs']['sellerSelector'] = 'oneSeller'
        brief['briefs']['sellerEmail'] = 'email@email.com'
        data_api_client.get_brief.return_value = brief
        data_api_client.get_framework.return_value = self.framework
        res = self.client.get(self.url_for('main.brief_response', brief_id=1234))
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 200
        data_api_client.get_brief.assert_called_once_with(1234)

    def test_get_select_brief_response_page_similar_email(self, data_api_client):
        brief = self.brief.copy()
        brief['briefs']['sellerSelector'] = 'oneSeller'
        brief['briefs']['sellerEmail'] = 'differentemail@email.com'
        data_api_client.get_brief.return_value = brief
        data_api_client.get_framework.return_value = self.framework
        res = self.client.get(self.url_for('main.brief_response', brief_id=1234))
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 200
        data_api_client.get_brief.assert_called_once_with(1234)

    def test_get_brief_response_returns_400_for_select_brief(self, data_api_client):
        brief = self.brief.copy()
        brief['briefs']['sellerSelector'] = 'someSellers'
        brief['briefs']['sellerEmailList'] = ['notyou@notyou.com']
        data_api_client.get_brief.return_value = brief
        data_api_client.get_framework.return_value = self.framework
        res = self.client.get(self.url_for('main.brief_response', brief_id=1234))

        assert res.status_code == 400

    def test_get_brief_response_returns_404_for_not_live_brief(self, data_api_client):
        brief = self.brief.copy()
        brief['briefs']['status'] = 'draft'
        data_api_client.get_brief.return_value = brief
        data_api_client.get_framework.return_value = self.framework
        res = self.client.get(self.url_for('main.brief_response', brief_id=1234))

        assert res.status_code == 404

    def test_get_brief_response_returns_404_for_not_live_framework(self, data_api_client):
        framework = self.framework.copy()
        framework['frameworks']['status'] = 'standstill'
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = framework
        res = self.client.get(self.url_for('main.brief_response', brief_id=1234))

        assert res.status_code == 404

    def test_get_brief_response_flashes_error_on_result_page_if_response_already_exists(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': [{
                'briefId': self.brief['briefs']['id'],
                'supplierCode': 1234
            }]
        }

        res = self.client.get(self.url_for('main.brief_response', brief_id=1234))
        assert res.status_code == 302
        assert res.location == self.url_for('main.view_response_result', brief_id=1234, _external=True)
        self.assert_flashes("already_applied", "error")

    def test_get_brief_response_page_includes_essential_requirements(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        res = self.client.get(self.url_for('main.brief_response', brief_id=1234))
        doc = html.fromstring(res.get_data(as_text=True))

        assert len(doc.xpath('//span[contains(text(), "Essential one")]')) == 1
        assert len(doc.xpath('//span[contains(text(), "Essential two")]')) == 1
        assert len(doc.xpath('//span[contains(text(), "Essential three")]')) == 1

    def test_get_brief_response_page_includes_nice_to_have_requirements(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        res = self.client.get(self.url_for('main.brief_response', brief_id=1234))
        doc = html.fromstring(res.get_data(as_text=True))

        assert len(doc.xpath('//span[contains(text(), "Top one")]')) == 1
        assert len(doc.xpath('//span[contains(text(), "Nice one")]')) == 1
        assert len(doc.xpath('//span[contains(text(), "Get sorted")]')) == 1

    def test_get_brief_response_page_redirects_to_login_for_buyer(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        self.login_as_buyer()
        create_url = self.url_for('main.brief_response', brief_id=1234)
        res = self.client.get(create_url)

        assert res.status_code == 302
        assert res.location == self.get_login_redirect_url(create_url)
        self.assert_flashes("supplier-role-required", "error")

    def test_create_new_brief_response(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.create_brief_response.return_value = {
            'briefResponses': {
                "essentialRequirements": [True, True, True],
                'respondToEmailAddress': 'example@example.com'}
        }

        res = self.client.post(
            self.url_for('main.brief_response', brief_id=1234),
            data=brief_form_submission
        )
        expected_location = self.url_for('main.view_response_result', brief_id=1234, result='success', _external=True)
        assert res.status_code == 302
        assert res.location == expected_location
        data_api_client.create_brief_response.assert_called_once_with(
            1234, 1234, processed_brief_submission, 'email@email.com')

    def test_create_new_brief_response_shows_result_page_for_not_all_essentials(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.create_brief_response.return_value = {
            'briefResponses': {
                "essentialRequirements": [True, False, True],
                'respondToEmailAddress': 'example@example.com'
            }
        }

        res = self.client.post(
            self.url_for('main.brief_response', brief_id=1234),
            data=brief_form_submission
        )
        assert res.status_code == 302
        assert res.location == self.url_for(
            'main.view_response_result',
            brief_id=1234,
            result='success',
            _external=True)

        data_api_client.create_brief_response.assert_called_once_with(
            1234, 1234, processed_brief_submission, 'email@email.com')

    def test_create_new_brief_response_error_message_for_boolean_list_question_empty(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.create_brief_response.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'essentialRequirements': 'answer_required'}
        )
        incomplete_brief_form_submission = brief_form_submission.copy()
        incomplete_brief_form_submission.pop('essentialRequirements-2')

        res = self.client.post(
            self.url_for('main.brief_response', brief_id=1234),
            data=incomplete_brief_form_submission,
            follow_redirects=True
        )
        assert res.status_code == 400
        doc = html.fromstring(res.get_data(as_text=True))

        assert len(doc.xpath(
            '//*[@id="validation-masthead-heading"]'
            '[contains(text(), "There was a problem with your answer to")]')) == 1
        assert doc.xpath(
            '//*[@id="content"]//a[@href="#essentialRequirements-2"]')[0].text_content() == 'Essential three'
        assert len(doc.xpath('//h1[contains(text(), "Apply for ‘I need a thing to do a thing’")]')) == 1
        assert len(doc.xpath('//h2[contains(text(), "Do you have the essential skills and experience?")]')) == 1
        assert len(doc.xpath(
            '//h2[contains(text(), "Do you have any of the nice-to-have skills and experience?")]')) == 1
        # self._test_breadcrumbs_on_brief_response_page(res)

    def test_create_new_brief_response_error_message_for_normal_question_empty(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.create_brief_response.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'availability': 'answer_required'}
        )
        incomplete_brief_form_submission = brief_form_submission.copy()
        incomplete_brief_form_submission.pop('availability')

        res = self.client.post(
            self.url_for('main.brief_response', brief_id=1234),
            data=incomplete_brief_form_submission,
            follow_redirects=True
        )
        doc = html.fromstring(res.get_data(as_text=True))

        assert len(doc.xpath(
            '//*[@id="validation-masthead-heading"]'
            '[contains(text(), "There was a problem with your answer to:")]')) == 1
        assert doc.xpath(
            '//*[@id="content"]//a[@href="#availability"]')[0].text_content() == 'Date the specialist can start work'
        assert len(doc.xpath('//h1[contains(text(), "Apply for ‘I need a thing to do a thing’")]')) == 1
        assert len(doc.xpath('//h2[contains(text(), "Do you have the essential skills and experience?")]')) == 1
        assert len(doc.xpath(
            '//h2[contains(text(), "Do you have any of the nice-to-have skills and experience?")]')) == 1
        # self._test_breadcrumbs_on_brief_response_page(res)

    def test_create_new_brief_response_404_if_not_live_brief(self, data_api_client):
        brief = self.brief.copy()
        brief['briefs']['status'] = 'draft'
        data_api_client.get_brief.return_value = brief
        data_api_client.get_framework.return_value = self.framework

        res = self.client.post(
            self.url_for('main.brief_response', brief_id=1234),
            data=brief_form_submission
        )
        assert res.status_code == 404
        assert not data_api_client.create_brief_response.called

    def test_create_new_brief_response_404_if_not_live_framework(self, data_api_client):
        framework = self.framework.copy()
        framework['frameworks']['status'] = 'standstill'
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = framework

        res = self.client.post(
            self.url_for('main.brief_response', brief_id=1234),
            data=brief_form_submission
        )
        assert res.status_code == 404
        assert not data_api_client.create_brief_response.called

    def test_create_new_brief_response_flashes_error_on_result_page_if_response_already_exists(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': [{
                'briefId': self.brief['briefs']['id'],
                'supplierCode': 1234
            }]
        }

        res = self.client.post(
            self.url_for('main.brief_response', brief_id=1234),
            data=brief_form_submission
        )
        assert res.status_code == 302
        assert res.location == self.url_for('main.view_response_result', brief_id=1234, _external=True)
        self.assert_flashes("already_applied", "error")
        assert not data_api_client.create_brief_response.called

    def test_create_new_brief_response_with_api_error_fails(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.create_brief_response.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'availability': 'answer_required'}
        )

        res = self.client.post(
            self.url_for('main.brief_response', brief_id=1234),
            data=brief_form_submission
        )

        assert res.status_code == 400
        assert "You need to answer this question." in res.get_data(as_text=True)
        data_api_client.create_brief_response.assert_called_once_with(
            1234, 1234, processed_brief_submission, 'email@email.com')

    def test_create_new_brief_response_redirects_to_login_for_buyer(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        self.login_as_buyer()
        res = self.client.post(
            self.url_for('main.brief_response', brief_id=1234),
            data=brief_form_submission
        )
        assert res.status_code == 302
        assert res.location == self.get_login_redirect_url()
        self.assert_flashes("supplier-role-required", "error")
        assert not data_api_client.get_brief.called


@mock.patch("app.main.views.briefs.data_api_client")
class TestResponseResultPage(BaseApplicationTest):

    def setup(self):
        super(TestResponseResultPage, self).setup()
        lots = [api_stubs.lot(slug="digital-specialists", allows_brief=True)]
        self.framework = api_stubs.framework(status="live", slug="digital-outcomes-and-specialists",
                                             clarification_questions_open=False, lots=lots)
        self.brief = api_stubs.brief(status='live')
        self.brief['briefs']['essentialRequirements'] = ['Must one', 'Must two', 'Must three']
        self.brief['briefs']['evaluationType'] = ['Interview', 'Scenario or test', 'Presentation', 'Written proposal',
                                                  'Work history']
        with self.app.test_client():
            self.login()

    def test_view_response_result_submitted_ok(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {
            "briefResponses": [
                {"essentialRequirements": [True, True, True]}
            ]
        }
        res = self.client.get(self.url_for('main.view_response_result', brief_id=1234))

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath('//h1')[0].text.strip() == \
            "Thanks for your application. You've now applied for ‘I need a thing to do a thing’"

    def test_view_response_result_submitted_unsuccessful(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {
            "briefResponses": [
                {"essentialRequirements": [True, False, True]}
            ]
        }
        res = self.client.get(self.url_for('main.view_response_result', brief_id=1234))

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath('//h1')[0].text.strip() == "You don’t meet all the essential requirements"

    def test_view_response_result_not_submitted_redirect_to_submit_page(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {"briefResponses": []}
        res = self.client.get(self.url_for('main.view_response_result', brief_id=1234))

        assert res.status_code == 302
        assert res.location == self.url_for('main.brief_response', brief_id=1234, _external=True)

    def test_nice_to_haves_heading_not_shown_when_there_are_none(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {
            "briefResponses": [
                {"essentialRequirements": [True, True, True]}
            ]
        }
        res = self.client.get(self.url_for('main.view_response_result', brief_id=1234))

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(
            doc.xpath('//h2[contains(normalize-space(text()), "Your nice-to-have skills and experience")]')
        ) == 0

    def test_evaluation_methods_load_default_value(self, data_api_client):
        no_extra_eval_brief = self.brief.copy()
        no_extra_eval_brief['briefs'].pop('evaluationType')
        data_api_client.get_brief.return_value = no_extra_eval_brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {
            "briefResponses": [
                {"essentialRequirements": [True, True, True]}
            ]
        }
        res = self.client.get(self.url_for('main.view_response_result', brief_id=1234))

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//li[contains(normalize-space(text()), "work history")]')) == 1

    def test_evaluation_methods_shown_with_a_or_an(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {
            "briefResponses": [
                {"essentialRequirements": [True, True, True]}
            ]
        }
        res = self.client.get(self.url_for('main.view_response_result', brief_id=1234))

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//li[contains(normalize-space(text()), "a meeting")]')) == 1

    def test_evaluation_methods_grouped_into_meeting(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {
            "briefResponses": [
                {"essentialRequirements": [True, True, True]}
            ]
        }
        res = self.client.get(self.url_for('main.view_response_result', brief_id=1234))

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//li[contains(normalize-space(text()), "a meeting")]')) == 1
        # Following items should be grouped as 'a meeting'
        assert len(doc.xpath('//li[contains(normalize-space(text()), "interview")]')) == 0
        assert len(doc.xpath('//li[contains(normalize-space(text()), "scenario or test")]')) == 0
        assert len(doc.xpath('//li[contains(normalize-space(text()), "presentation")]')) == 0
        assert len(doc.xpath('//li[contains(normalize-space(text()), "written proposal")]')) == 0
