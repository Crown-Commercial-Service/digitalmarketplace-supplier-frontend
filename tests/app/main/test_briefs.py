# coding: utf-8
from __future__ import unicode_literals

import mock
from dmapiclient import api_stubs, HTTPError
from dmapiclient.audit import AuditTypes
from dmutils.email import MandrillException
from ..helpers import BaseApplicationTest, FakeMail
from lxml import html


brief_form_submission = {
    "availability": "Next Tuesday",
    "dayRate": "£200",
    "essentialRequirements-0": True,
    "essentialRequirements-1": False,
    "essentialRequirements-2": True,
    "niceToHaveRequirements-0": False,
    "niceToHaveRequirements-1": True,
    "niceToHaveRequirements-2": False,
}

processed_brief_submission = {
    "availability": "Next Tuesday",
    "dayRate": "£200",
    "essentialRequirements": [
        True,
        False,
        True
    ],
    "niceToHaveRequirements": [
        False,
        True,
        False
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
        res = self.client.get('/suppliers/opportunities/1/question-and-answer-session')
        assert res.status_code == 302
        assert '/login' in res.headers['Location']

    def test_q_and_a_session_details(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live')
        data_api_client.get_brief.return_value['briefs']['questionAndAnswerSessionDetails'] = 'SESSION DETAILS'

        res = self.client.get('/suppliers/opportunities/1/question-and-answer-session')
        assert res.status_code == 200
        assert 'SESSION DETAILS' in res.get_data(as_text=True)

    def test_q_and_a_session_details_checks_supplier_is_eligible(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', lot_slug='digital-specialists')
        data_api_client.get_brief.return_value['briefs']['frameworkName'] = 'Digital Outcomes and Specialists'
        data_api_client.is_supplier_eligible_for_brief.return_value = False

        res = self.client.get('/suppliers/opportunities/1/question-and-answer-session')
        assert res.status_code == 400

    def test_q_and_a_session_details_requires_existing_brief_id(self, data_api_client):
        self.login()
        data_api_client.get_brief.side_effect = HTTPError(mock.Mock(status_code=404))

        res = self.client.get('/suppliers/opportunities/1/question-and-answer-session')
        assert res.status_code == 404

    def test_q_and_a_session_details_requires_live_brief(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='expired')

        res = self.client.get('/suppliers/opportunities/1/question-and-answer-session')
        assert res.status_code == 404

    def test_q_and_a_session_details_requires_questions_to_be_open(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', clarification_questions_closed=True)

        res = self.client.get('/suppliers/opportunities/1/question-and-answer-session')
        assert res.status_code == 404


@mock.patch('app.main.views.briefs.data_api_client', autospec=True)
class TestBriefClarificationQuestions(BaseApplicationTest):
    def test_clarification_question_form_requires_login(self, data_api_client):
        res = self.client.get('/suppliers/opportunities/1/ask-a-question')
        assert res.status_code == 302
        assert '/login' in res.headers['Location']

    def test_clarification_question_form(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live')

        res = self.client.get('/suppliers/opportunities/1/ask-a-question')
        assert res.status_code == 200

    def test_clarification_question_form_escapes_brief_name(self, data_api_client):
        self.login()
        xss_brief = api_stubs.brief(status='live')
        xss_brief['briefs']['title'] = '<script>alert(1)</script>'
        data_api_client.get_brief.return_value = xss_brief

        res = self.client.get('/suppliers/opportunities/1/ask-a-question')
        html_string = res.get_data(as_text=True)
        doc = html.fromstring(html_string)

        assert '<script>alert(1)</script>' not in html_string
        assert '<script>alert(1)</script>' in doc.xpath('//header/h1/text()')[0].strip()

    def test_clarification_question_form_requires_existing_brief_id(self, data_api_client):
        self.login()
        data_api_client.get_brief.side_effect = HTTPError(mock.Mock(status_code=404))

        res = self.client.get('/suppliers/opportunities/1/ask-a-question')
        assert res.status_code == 404

    def test_clarification_question_checks_supplier_is_eligible(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', lot_slug='digital-specialists')
        data_api_client.get_brief.return_value['briefs']['frameworkName'] = 'Digital Outcomes and Specialists'
        data_api_client.is_supplier_eligible_for_brief.return_value = False

        res = self.client.get('/suppliers/opportunities/1/ask-a-question')
        assert res.status_code == 400

    def test_clarification_question_form_requires_live_brief(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='expired')

        res = self.client.get('/suppliers/opportunities/1/ask-a-question')
        assert res.status_code == 404

    def test_clarification_question_form_requires_questions_to_be_open(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', clarification_questions_closed=True)

        res = self.client.get('/suppliers/opportunities/1/ask-a-question')
        assert res.status_code == 404


@mock.patch('app.main.views.briefs.data_api_client', autospec=True)
class TestSubmitClarificationQuestions(BaseApplicationTest):
    def test_submit_clarification_question_requires_login(self, data_api_client):
        res = self.client.post('/suppliers/opportunities/1/ask-a-question')
        assert res.status_code == 302
        assert '/login' in res.headers['Location']

    @mock.patch('app.main.helpers.briefs.send_email')
    def test_submit_clarification_question(self, send_email, data_api_client):
        self.login()
        brief = api_stubs.brief(status="live")
        brief['briefs']['frameworkName'] = 'Brief Framework Name'
        brief['briefs']['clarificationQuestionsPublishedBy'] = '2016-03-29T10:11:13.000000Z'
        data_api_client.get_brief.return_value = brief

        res = self.client.post('/suppliers/opportunities/1234/ask-a-question', data={
            'clarification-question': "important question",
        })
        assert res.status_code == 200

        send_email.assert_has_calls([
            mock.call(
                from_name='Brief Framework Name Supplier',
                tags=['brief-clarification-question'],
                email_body=FakeMail("important question"),
                from_email='do-not-reply@digitalmarketplace.service.gov.uk',
                api_key='MANDRILL',
                to_email_addresses=['buyer@email.com'],
                subject=u"You\u2019ve received a new supplier question about \u2018I need a thing to do a thing\u2019"
            ),
            mock.call(
                from_name='Digital Marketplace Admin',
                tags=['brief-clarification-question-confirmation'],
                email_body=FakeMail("important question"),
                from_email='do-not-reply@digitalmarketplace.service.gov.uk',
                api_key='MANDRILL',
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
    def test_submit_clarification_question_fails_on_mandrill_error(self, send_email, data_api_client):
        self.login()
        brief = api_stubs.brief(status="live")
        brief['briefs']['frameworkName'] = 'Framework Name'
        brief['briefs']['clarificationQuestionsPublishedBy'] = '2016-03-29T10:11:13.000000Z'
        data_api_client.get_brief.return_value = brief

        send_email.side_effect = MandrillException

        res = self.client.post('/suppliers/opportunities/1234/ask-a-question', data={
            'clarification-question': "important question",
        })
        assert res.status_code == 503

    def test_submit_clarification_question_requires_existing_brief_id(self, data_api_client):
        self.login()
        data_api_client.get_brief.side_effect = HTTPError(mock.Mock(status_code=404))

        res = self.client.post('/suppliers/opportunities/1/ask-a-question')
        assert res.status_code == 404

    def test_submit_clarification_question_requires_live_brief(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='expired')

        res = self.client.post('/suppliers/opportunities/1/ask-a-question')
        assert res.status_code == 404

    @mock.patch('app.main.helpers.briefs.send_email')
    def test_submit_clarification_question_returns_error_page_if_supplier_has_no_services_on_lot(
            self, send_email, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', lot_slug='digital-specialists')
        data_api_client.get_brief.return_value['briefs']['frameworkName'] = 'Digital Outcomes and Specialists'
        data_api_client.is_supplier_eligible_for_brief.return_value = False
        data_api_client.find_services.side_effect = lambda *args, **kwargs: (
            {"services": [{"something": "nonempty"}]} if kwargs.get("lot") is None else {"services": []}
        )

        res = self.client.post('/suppliers/opportunities/1/ask-a-question', data={
            'clarification-question': "important question",
        })
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 400
        assert doc.xpath('normalize-space(//h1/text())') == ERROR_MESSAGE_PAGE_HEADING_CLARIFICATION
        assert len(doc.xpath(
            '//*[contains(normalize-space(text()), normalize-space("{}"))]'.format(
                ERROR_MESSAGE_NO_SERVICE_ON_LOT_CLARIFICATION
            )
        )) == 1
        assert not data_api_client.create_audit_event.called

    @mock.patch('app.main.helpers.briefs.send_email')
    def test_submit_clarification_question_returns_error_page_if_supplier_has_no_services_on_framework(
            self, send_email, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', lot_slug='digital-specialists')
        data_api_client.get_brief.return_value['briefs']['frameworkFramework'] = 'dos'
        data_api_client.is_supplier_eligible_for_brief.return_value = False
        data_api_client.find_services.return_value = {"services": []}

        res = self.client.post('/suppliers/opportunities/1/ask-a-question', data={
            'clarification-question': "important question",
        })
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 400
        assert doc.xpath('normalize-space(//h1/text())') == ERROR_MESSAGE_PAGE_HEADING_CLARIFICATION
        assert len(doc.xpath(
            '//*[contains(normalize-space(text()), normalize-space("{}"))]'.format(
                ERROR_MESSAGE_NO_SERVICE_ON_FRAMEWORK_CLARIFICATION
            )
        )) == 1
        assert not data_api_client.create_audit_event.called

    @mock.patch('app.main.helpers.briefs.send_email')
    def test_submit_clarification_question_returns_error_page_if_supplier_has_no_services_with_role(
            self, send_email, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', lot_slug='digital-specialists')
        data_api_client.get_brief.return_value['briefs']['frameworkName'] = 'Digital Outcomes and Specialists'
        data_api_client.is_supplier_eligible_for_brief.return_value = False
        data_api_client.find_services.return_value = {"services": [{"something": "nonempty"}]}

        res = self.client.post('/suppliers/opportunities/1/ask-a-question', data={
            'clarification-question': "important question",
        })
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 400
        assert doc.xpath('normalize-space(//h1/text())') == ERROR_MESSAGE_PAGE_HEADING_CLARIFICATION
        assert len(doc.xpath(
            '//*[contains(normalize-space(text()), normalize-space("{}"))]'.format(
                ERROR_MESSAGE_NO_SERVICE_WITH_ROLE_CLARIFICATION
            )
        )) == 1
        assert not data_api_client.create_audit_event.called

    def test_submit_empty_clarification_question_returns_validation_error(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live')

        res = self.client.post('/suppliers/opportunities/1/ask-a-question', data={
            'clarification-question': "",
        })
        assert res.status_code == 400
        assert "cannot be empty" in res.get_data(as_text=True)

    def test_clarification_question_has_max_length_limit(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live')

        res = self.client.post('/suppliers/opportunities/1/ask-a-question', data={
            'clarification-question': "a" * 5100,
        })
        assert res.status_code == 400
        assert "cannot be longer than" in res.get_data(as_text=True)

    @mock.patch('app.main.helpers.briefs.send_email')
    def test_clarification_question_has_max_word_limit(self, send_email, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live')

        res = self.client.post('/suppliers/opportunities/1/ask-a-question', data={
            'clarification-question': "a " * 101,
        })
        assert res.status_code == 400
        assert "must be no more than 100 words" in res.get_data(as_text=True)

    @mock.patch('app.main.helpers.briefs.send_email')
    def test_submit_clarification_question_escapes_html(self, send_email, data_api_client):
        self.login()
        brief = api_stubs.brief(status="live")
        data_api_client.get_brief.return_value = brief
        brief['briefs']['frameworkName'] = 'Brief Framework Name'
        brief['briefs']['clarificationQuestionsPublishedBy'] = '2016-03-29T10:11:13.000000Z'

        res = self.client.post('/suppliers/opportunities/1234/ask-a-question', data={
            'clarification-question': '<a href="malicious">friendly.url</a>',
        })
        assert res.status_code == 200

        escaped_string = '&lt;a href=&#34;malicious&#34;&gt;friendly.url&lt;/a&gt;'
        assert escaped_string in send_email.mock_calls[0][2]['email_body']
        assert escaped_string in send_email.mock_calls[1][2]['email_body']


class TestApplyToBrief(BaseApplicationTest):
    """Tests requests for the new multipage flow for applying for a brief"""

    def setup(self):
        super(TestApplyToBrief, self).setup()

        self.brief = api_stubs.brief(status='live', lot_slug='digital-specialists')
        self.brief['briefs']['essentialRequirements'] = ['Essential one', 'Essential two', 'Essential three']
        self.brief['briefs']['niceToHaveRequirements'] = ['Nice one', 'Top one', 'Get sorted']

        lots = [api_stubs.lot(slug="digital-specialists", allows_brief=True)]
        self.framework = api_stubs.framework(
            status="live", slug="digital-outcomes-and-specialists", clarification_questions_open=False, lots=lots
        )

        self.data_api_client_patch = mock.patch('app.main.views.briefs.data_api_client')
        self.data_api_client = self.data_api_client_patch.start()
        self.data_api_client.get_brief.return_value = self.brief
        self.data_api_client.get_framework.return_value = self.framework
        self.data_api_client.get_brief_response.return_value = self.brief_response()

        with self.app.test_client():
            self.login()

    def teardown(self):
        super(TestApplyToBrief, self).teardown()
        self.data_api_client_patch.stop()

    @mock.patch("app.main.views.briefs.content_loader")
    def test_will_redirect_from_generic_brief_response_url_to_first_section(self, content_loader):
        content_loader.get_manifest.return_value.filter.return_value.get_next_editable_section_id.return_value = 'first'

        res = self.client.get('/suppliers/opportunities/1234/responses/5')
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/5/first'

    def test_404_if_brief_response_does_not_exist(self):
        for method in ('get', 'post'):
            self.data_api_client.get_brief_response = mock.MagicMock(side_effect=HTTPError(mock.Mock(status_code=404)))

            res = self.client.open('/suppliers/opportunities/1234/responses/250/section-name', method=method)

            assert res.status_code == 404
            self.data_api_client.get_brief_response.assert_called_once_with(250)

    def test_404_if_brief_response_does_not_relate_to_brief(self):
        for method in ('get', 'post'):
            self.data_api_client.get_brief_response.return_value = {
                "briefResponses": {
                    "briefId": 234,
                    "supplierId": 1234
                }
            }

            res = self.client.open('/suppliers/opportunities/1234/responses/5/section-name', method=method)
            assert res.status_code == 404

    @mock.patch("app.main.views.briefs.current_user")
    def test_404_if_brief_response_does_not_relate_to_current_user(self, current_user):
        for method in ('get', 'post'):
            current_user.supplier_id = 789

            res = self.client.open('/suppliers/opportunities/1234/responses/5/section-name', method=method)
            assert res.status_code == 404

    def test_404_for_not_live_brief(self):
        for method in ('get', 'post'):
            self.data_api_client.get_brief.return_value = api_stubs.brief(
                status='closed', lot_slug='digital-specialists'
            )

            res = self.client.open('/suppliers/opportunities/1234/responses/5/section-name', method=method)
            assert res.status_code == 404

    def test_404_for_not_live_framework(self):
        for method in ('get', 'post'):
            self.data_api_client.get_framework.return_value = api_stubs.framework(
                status="expired", slug="digital-outcomes-and-specialists", clarification_questions_open=False
            )

            res = self.client.open('/suppliers/opportunities/1234/responses/5/section-name', method=method)
            assert res.status_code == 404

    @mock.patch("app.main.views.briefs.is_supplier_eligible_for_brief")
    def test_show_not_eligible_page_if_supplier_not_eligible_to_apply_for_brief(self, is_supplier_eligible_for_brief):
        for method in ('get', 'post'):
            is_supplier_eligible_for_brief.return_value = False

            res = self.client.open('/suppliers/opportunities/1234/responses/5/section-name', method=method)
            assert res.status_code == 400

            doc = html.fromstring(res.get_data(as_text=True))
            assert doc.xpath('//title')[0].text == 'Not eligible for opportunity – Digital Marketplace'

    @mock.patch("app.main.views.briefs.supplier_has_a_brief_response")
    def test_redirect_to_show_brief_response_if_already_applied_for_brief(self, supplier_has_a_brief_response):
        for method in ('get', 'post'):
            supplier_has_a_brief_response.return_value = True

            res = self.client.open('/suppliers/opportunities/1234/responses/5/section-name', method=method)
            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/result'
            self.assert_flashes("already_applied", "error")

    @mock.patch("app.main.views.briefs.content_loader")
    def test_should_404_for_non_existent_content_section(self, content_loader):
        for method in ('get', 'post'):
            content_loader.get_manifest.return_value.filter.return_value.get_section.return_value = None

            res = self.client.open('/suppliers/opportunities/1234/responses/5/section-name', method=method)
            assert res.status_code == 404

    @mock.patch("app.main.views.briefs.content_loader")
    def test_should_404_for_non_editable_content_section(self, content_loader):
        for method in ('get', 'post'):
            content_loader.get_manifest.return_value.filter.return_value.get_section.return_value.editable = False

            res = self.client.open('/suppliers/opportunities/1234/responses/5/section-name', method=method)
            assert res.status_code == 404

    @mock.patch("app.main.views.briefs.content_loader")
    def test_non_final_editable_section_shows_continue_button(self, content_loader):
        content_loader.get_manifest.return_value.filter.return_value.sections = [
            {'id': 'section-one'},
            {'id': 'section-two'},
            {'id': 'section-three'}
        ]

        res = self.client.get('/suppliers/opportunities/1234/responses/5/section-two')
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath("//input[@class='button-save']/@value")[0] == 'Continue'

    @mock.patch("app.main.views.briefs.content_loader")
    def test_final_editable_section_shows_submit_application_button(self, content_loader):
        content_loader.get_manifest.return_value.filter.return_value.sections = [
            {'id': 'section-one'},
            {'id': 'section-two'},
            {'id': 'section-three'}
        ]

        res = self.client.get('/suppliers/opportunities/1234/responses/5/section-three')
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath("//input[@class='button-save']/@value")[0] == 'Submit application'

    def test_content_from_manifest_is_shown(self):
        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/email-address-the-buyer-should-use-to-contact-you'
        )
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath("//h1/text()")[0].strip() == 'Email address the buyer should use to contact you'
        assert (doc.xpath("//span[@class=\"question-heading-with-hint\"]/text()")[0].strip() ==
                'Email address the buyer should use to contact you')
        assert (doc.xpath("//span[@class=\"question-advice\"]/text()")[0].strip() ==
                'All communication about your application will be sent to this address.')

    def test_essential_requirements_met_question_replays_all_brief_requirements(self):
        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/do-you-have-all-the-essential-skills-and-experience'
        )
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        list_items = doc.xpath("//*[@id='input-essentialRequirementsMet-question-advice']/ul/li/text()")
        assert len(self.brief['briefs']['essentialRequirements']) == len(list_items)
        for index, requirement in enumerate(self.brief['briefs']['essentialRequirements']):
            assert requirement == list_items[index]

    def test_essential_requirements_met_question_escapes_brief_data(self):
        self.brief['briefs']['essentialRequirements'] = [
            '<h1>Essential one with xss</h1>',
            '**Essential two with markdown**'
        ]
        self.data_api_client.get_brief.return_value = self.brief

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/do-you-have-all-the-essential-skills-and-experience'
        )
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        list_items = doc.xpath("//*[@id='input-essentialRequirementsMet-question-advice']/ul/li/text()")
        assert list_items[0] == '<h1>Essential one with xss</h1>'
        assert list_items[1] == '**Essential two with markdown**'

    def test_day_rate_question_replays_buyers_budget_range_and_suppliers_max_day_rate(self):
        self.brief['briefs']['budgetRange'] = '1 million dollars'
        self.brief['briefs']['specialistRole'] = 'deliveryManager'
        self.data_api_client.find_services.return_value = {"services": [{"deliveryManagerPriceMax": 600}]}

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/how-much-you-charge-each-day'
        )
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        day_rate_headings = doc.xpath("//*[@id='input-dayRate-question-advice']/h2/text()")
        buyers_max_day_rate = doc.xpath(
            "//*[@id='input-dayRate-question-advice']/descendant::h2[1]/following::p[1]/text()")[0]
        suppliers_max_day_rate = doc.xpath(
            "//*[@id='input-dayRate-question-advice']/descendant::h2[2]/following::p[1]/text()")[0]

        assert day_rate_headings[0] == "Buyer's maximum day rate:"
        assert buyers_max_day_rate == '1 million dollars'
        assert day_rate_headings[1] == "Your maximum day rate:"
        assert suppliers_max_day_rate == '£600'

    def test_day_rate_question_escapes_brief_day_rate_markdown(self):
        self.brief['briefs']['budgetRange'] = '**markdown**'

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/how-much-you-charge-each-day'
        )
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        buyers_max_day_rate = doc.xpath(
            "//*[@id='input-dayRate-question-advice']/descendant::h2[1]/following::p[1]/text()")[0]
        assert buyers_max_day_rate == '**markdown**'

    def test_day_rate_question_escapes_brief_day_rate_html(self):
        self.brief['briefs']['budgetRange'] = '<h1>xss</h1>'

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/how-much-you-charge-each-day'
        )
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        buyers_max_day_rate = doc.xpath(
            "//*[@id='input-dayRate-question-advice']/descendant::h2[1]/following::p[1]/text()")[0]
        assert buyers_max_day_rate == '<h1>xss</h1>'

    def test_day_rate_question_does_not_replay_buyers_budget_range_if_not_provided(self):
        self.brief['briefs']['specialistRole'] = 'deliveryManager'
        self.data_api_client.find_services.return_value = {"services": [{"deliveryManagerPriceMax": 600}]}

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/how-much-you-charge-each-day'
        )
        assert res.status_code == 200
        data = res.get_data(as_text=True)
        assert "Buyer's maximum day rate:" not in data

    def test_start_date_question_escapes_brief_start_date_markdown(self):
        self.brief['briefs']['startDate'] = '**markdown**'

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/the-earliest-the-specialist-can-start'
        )
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        start_date = doc.xpath(
            "//*[@id='input-availability-question-advice']/text()")[0].strip()
        assert start_date == "The buyer needs the specialist to start by **markdown**."

    def test_start_date_question_escapes_brief_start_date_html(self):
        self.brief['briefs']['startDate'] = '<h1>xss</h1>'

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/the-earliest-the-specialist-can-start'
        )
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        start_date = doc.xpath(
            "//*[@id='input-availability-question-advice']/text()")[0].strip()
        assert start_date == "The buyer needs the specialist to start by <h1>xss</h1>."

    def test_existing_brief_response_data_is_prefilled(self):
        self.data_api_client.get_brief_response.return_value = self.brief_response(
            data={'respondToEmailAddress': 'test@example.com'}
        )

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/email-address-the-buyer-should-use-to-contact-you'
        )
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath("//input[@type='text']/@value")[0] == 'test@example.com'

    def test_error_message_shown_and_attempted_input_prefilled_if_invalid_input(self):
        self.data_api_client.update_brief_response.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'respondToEmailAddress': 'invalid_format'}
        )

        res = self.client.post(
            '/suppliers/opportunities/1234/responses/5/email-address-the-buyer-should-use-to-contact-you',
            data={
                "respondToEmailAddress": "not-a-valid-email"
            }
        )

        assert res.status_code == 400
        doc = html.fromstring(res.get_data(as_text=True))
        assert (doc.xpath("//h1[@class=\"validation-masthead-heading\"]/text()")[0].strip() ==
                'There was a problem with your answer to:')
        assert (doc.xpath("//a[@class=\"validation-masthead-link\"]/text()")[0].strip() ==
                'Email address')
        assert (doc.xpath("//span[@class=\"validation-message\"]/text()")[0].strip() ==
                'You must enter a valid email address.')
        assert doc.xpath('//*[@id="input-respondToEmailAddress"]/@value')[0] == "not-a-valid-email"

    def test_post_form_updates_api_and_redirects_to_next_section(self):
        data = {'dayRate': '500'}
        res = self.client.post(
            '/suppliers/opportunities/1234/responses/5/how-much-you-charge-each-day',
            data=data
        )
        assert res.status_code == 302

        self.data_api_client.update_brief_response.assert_called_once_with(
            5,
            data,
            'email@email.com',
            page_questions=['dayRate']
        )

        assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/5/do-you-have-all-the-essential-skills-and-experience'  # NOQA

    def test_post_final_section_submits_response_redirects_to_results(self):
        data = {'respondToEmailAddress': 'bob@example.com'}
        res = self.client.post(
            '/suppliers/opportunities/1234/responses/5/email-address-the-buyer-should-use-to-contact-you',
            data=data
        )
        assert res.status_code == 302

        self.data_api_client.update_brief_response.assert_called_once_with(
            5,
            data,
            'email@email.com',
            page_questions=['respondToEmailAddress']
        )

        self.data_api_client.submit_brief_response.assert_called_once_with(
            5,
            'email@email.com',
        )

        assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/result'


@mock.patch("app.main.views.briefs.data_api_client")
class TestLegacyRespondToBrief(BaseApplicationTest):
    """Tests for the old single page flow for applying for a brief which is being phased out"""

    def setup(self):
        super(TestLegacyRespondToBrief, self).setup()

        self.brief = api_stubs.brief(status='live', lot_slug='digital-specialists')
        self.brief['briefs']['essentialRequirements'] = ['Essential one', 'Essential two', 'Essential three']
        self.brief['briefs']['niceToHaveRequirements'] = ['Nice one', 'Top one', 'Get sorted']

        lots = [api_stubs.lot(slug="digital-specialists", allows_brief=True)]
        self.framework = api_stubs.framework(status="live", slug="digital-outcomes-and-specialists",
                                             clarification_questions_open=False, lots=lots)

        with self.app.test_client():
            self.login()

    def _test_breadcrumbs_on_brief_response_page(self, response):
        breadcrumbs = html.fromstring(response.get_data(as_text=True)).xpath(
            '//*[@id="global-breadcrumb"]/nav/ol/li'
        )
        brief = self.brief['briefs']

        breadcrumbs_we_expect = [
            ('Digital Marketplace', '/'),
            ('Supplier opportunities', '/digital-outcomes-and-specialists/opportunities'),
            (brief['title'], '/digital-outcomes-and-specialists/opportunities/{}'.format(brief['id']))
        ]

        assert len(breadcrumbs) == len(breadcrumbs_we_expect)

        for index, link in enumerate(breadcrumbs_we_expect):
            assert breadcrumbs[index].find('a').text_content().strip() == link[0]
            assert breadcrumbs[index].find('a').get('href').strip() == link[1]

    def test_get_brief_response_page(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        res = self.client.get('/suppliers/opportunities/1234/responses/create')
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 200
        data_api_client.get_brief.assert_called_once_with(1234)
        assert len(doc.xpath('//h1[contains(text(), "Apply for ‘I need a thing to do a thing’")]')) == 1
        assert len(doc.xpath('//h2[contains(text(), "Do you have the essential skills and experience?")]')) == 1
        assert len(doc.xpath(
            '//h2[contains(text(), "Do you have any of the nice-to-have skills and experience?")]')) == 1
        self._test_breadcrumbs_on_brief_response_page(res)

    def test_get_brief_response_returns_404_for_not_live_brief(self, data_api_client):
        brief = self.brief.copy()
        brief['briefs']['status'] = 'draft'
        data_api_client.get_brief.return_value = brief
        data_api_client.get_framework.return_value = self.framework
        res = self.client.get('/suppliers/opportunities/1234/responses/create')

        assert res.status_code == 404

    def test_get_brief_response_returns_404_for_not_live_framework(self, data_api_client):
        framework = self.framework.copy()
        framework['frameworks']['status'] = 'standstill'
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = framework
        res = self.client.get('/suppliers/opportunities/1234/responses/create')

        assert res.status_code == 404

    def test_get_brief_response_returns_error_page_if_supplier_has_no_services_on_lot(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_brief.return_value['briefs']['frameworkName'] = 'Digital Outcomes and Specialists'
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = False
        data_api_client.find_services.side_effect = lambda *args, **kwargs: (
            {"services": [{"something": "nonempty"}]} if kwargs.get("lot") is None else {"services": []}
        )

        res = self.client.get('/suppliers/opportunities/1234/responses/create')
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 400
        assert doc.xpath('normalize-space(//h1/text())') == ERROR_MESSAGE_PAGE_HEADING_APPLICATION
        assert len(doc.xpath(
            '//*[contains(normalize-space(text()), normalize-space("{}"))]'.format(
                ERROR_MESSAGE_NO_SERVICE_ON_LOT_APPLICATION
            )
        )) == 1
        assert len(doc.xpath('//*[@data-reason="supplier-not-on-lot"]')) == 1
        assert not data_api_client.create_audit_event.called

    def test_get_brief_response_returns_error_page_if_supplier_has_no_pub_services_on_lot(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_brief.return_value['briefs']['frameworkName'] = 'Digital Outcomes and Specialists'
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = False
        # simulating the case where we have non-"published", but matching, services
        data_api_client.find_services.side_effect = lambda *args, **kwargs: (
            {"services": [{"something": "nonempty"}]}
            if kwargs.get("lot") is None or kwargs.get("status") is None else
            {"services": []}
        )

        res = self.client.get('/suppliers/opportunities/1234/responses/create')
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 400
        assert doc.xpath('normalize-space(//h1/text())') == ERROR_MESSAGE_PAGE_HEADING_APPLICATION
        assert len(doc.xpath(
            '//*[contains(normalize-space(text()), normalize-space("{}"))]'.format(
                ERROR_MESSAGE_NO_SERVICE_ON_LOT_APPLICATION
            )
        )) == 1
        assert len(doc.xpath('//*[@data-reason="supplier-not-on-lot"]')) == 1
        assert not data_api_client.create_audit_event.called

    def test_get_brief_response_returns_error_page_if_supplier_has_no_services_on_framework(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_brief.return_value['briefs']['frameworkFramework'] = 'dos'
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = False
        data_api_client.find_services.return_value = {"services": []}

        res = self.client.get('/suppliers/opportunities/1234/responses/create')
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 400
        assert doc.xpath('normalize-space(//h1/text())') == ERROR_MESSAGE_PAGE_HEADING_APPLICATION
        assert len(doc.xpath(
            '//*[contains(normalize-space(text()), normalize-space("{}"))]'.format(
                ERROR_MESSAGE_NO_SERVICE_ON_FRAMEWORK_APPLICATION
            )
        )) == 1
        assert len(doc.xpath('//*[@data-reason="supplier-not-on-dos"]')) == 1
        assert not data_api_client.create_audit_event.called

    def test_get_brief_response_returns_error_page_if_supplier_has_no_pub_services_on_framework(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_brief.return_value['briefs']['frameworkFramework'] = 'dos'
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = False
        # simulating the case where we have non-"published", but on-framework, services
        data_api_client.find_services.side_effect = lambda *args, **kwargs: (
            {"services": [{"something": "nonempty"}]}
            if kwargs.get("status") is None else
            {"services": []}
        )

        res = self.client.get('/suppliers/opportunities/1234/responses/create')
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 400
        assert doc.xpath('normalize-space(//h1/text())') == ERROR_MESSAGE_PAGE_HEADING_APPLICATION
        assert len(doc.xpath(
            '//*[contains(normalize-space(text()), normalize-space("{}"))]'.format(
                ERROR_MESSAGE_NO_SERVICE_ON_FRAMEWORK_APPLICATION
            )
        )) == 1
        assert len(doc.xpath('//*[@data-reason="supplier-not-on-dos"]')) == 1
        assert not data_api_client.create_audit_event.called

    def test_get_brief_response_returns_error_page_if_supplier_has_no_services_with_role(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_brief.return_value['briefs']['frameworkName'] = 'Digital Outcomes and Specialists'
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = False
        data_api_client.find_services.return_value = {"services": [{"something": "nonempty"}]}

        res = self.client.get('/suppliers/opportunities/1234/responses/create')
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 400
        assert doc.xpath('normalize-space(//h1/text())') == ERROR_MESSAGE_PAGE_HEADING_APPLICATION
        assert len(doc.xpath(
            '//*[contains(normalize-space(text()), normalize-space("{}"))]'.format(
                ERROR_MESSAGE_NO_SERVICE_WITH_ROLE_APPLICATION
            )
        )) == 1
        assert len(doc.xpath('//*[@data-reason="supplier-not-on-role"]')) == 1
        assert not data_api_client.create_audit_event.called

    def test_get_brief_response_does_not_contain_data_reason_if_supplier_is_eligible(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        res = self.client.get('/suppliers/opportunities/1234/responses/create')

        assert res.status_code == 200
        assert 'data-reason='not in res.get_data(as_text=True)

    def test_get_brief_response_flashes_error_on_result_page_if_response_already_exists(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': [{
                'briefId': self.brief['briefs']['id'],
                'supplierId': 1234
            }]
        }

        res = self.client.get('/suppliers/opportunities/1234/responses/create')
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/result'
        self.assert_flashes("already_applied", "error")

    def test_get_brief_response_page_includes_essential_requirements(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        res = self.client.get('/suppliers/opportunities/1234/responses/create')
        doc = html.fromstring(res.get_data(as_text=True))

        assert len(doc.xpath('//span[contains(text(), "Essential one")]')) == 1
        assert len(doc.xpath('//span[contains(text(), "Essential two")]')) == 1
        assert len(doc.xpath('//span[contains(text(), "Essential three")]')) == 1

    def test_get_brief_response_page_includes_nice_to_have_requirements(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        res = self.client.get('/suppliers/opportunities/1234/responses/create')
        doc = html.fromstring(res.get_data(as_text=True))

        assert len(doc.xpath('//span[contains(text(), "Top one")]')) == 1
        assert len(doc.xpath('//span[contains(text(), "Nice one")]')) == 1
        assert len(doc.xpath('//span[contains(text(), "Get sorted")]')) == 1

    def test_get_brief_response_page_redirects_to_login_for_buyer(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        self.login_as_buyer()
        res = self.client.get('/suppliers/opportunities/1234/responses/create')

        assert res.status_code == 302
        assert res.location == "http://localhost/login?next=%2Fsuppliers%2Fopportunities%2F1234%2Fresponses%2Fcreate"
        self.assert_flashes("supplier-role-required", "error")

    def test_create_new_brief_response(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.create_brief_response.return_value = {
            'briefResponses': {"id": 6, "essentialRequirements": [True, True, True]}
        }

        res = self.client.post(
            '/suppliers/opportunities/1234/responses/create',
            data=brief_form_submission
        )
        assert res.status_code == 302
        assert res.location == "http://localhost/suppliers/opportunities/1234/responses/result?result=success"
        data_api_client.create_brief_response.assert_called_once_with(
            1234,
            1234,
            processed_brief_submission,
            'email@email.com',
            page_questions=[
                'respondToEmailAddress', 'essentialRequirements', 'niceToHaveRequirements', 'availability', 'dayRate'
            ]
        )
        data_api_client.submit_brief_response.assert_called_once_with(
            6, 'email@email.com')

    def test_create_new_brief_response_redirects_to_result_page_if_not_all_essentials_are_true(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.create_brief_response.return_value = {
            'briefResponses': {"id": 6, "essentialRequirements": [True, False, True]}
        }

        res = self.client.post(
            '/suppliers/opportunities/1234/responses/create',
            data=brief_form_submission
        )
        assert res.status_code == 302
        assert res.location == "http://localhost/suppliers/opportunities/1234/responses/result?result=fail"
        data_api_client.create_brief_response.assert_called_once_with(
            1234,
            1234,
            processed_brief_submission,
            'email@email.com',
            page_questions=[
                'respondToEmailAddress', 'essentialRequirements', 'niceToHaveRequirements', 'availability', 'dayRate'
            ]
        )

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
            '/suppliers/opportunities/1234/responses/create',
            data=incomplete_brief_form_submission,
            follow_redirects=True
        )
        doc = html.fromstring(res.get_data(as_text=True))

        assert len(doc.xpath(
            '//*[@id="validation-masthead-heading"]'
            '[contains(text(), "There was a problem with your answer to:")]')) == 1
        assert doc.xpath(
            '//*[@id="content"]//a[@href="#essentialRequirements-2"]')[0].text_content() == 'Essential three'
        assert len(doc.xpath('//h1[contains(text(), "Apply for ‘I need a thing to do a thing’")]')) == 1
        assert len(doc.xpath('//h2[contains(text(), "Do you have the essential skills and experience?")]')) == 1
        assert len(doc.xpath(
            '//h2[contains(text(), "Do you have any of the nice-to-have skills and experience?")]')) == 1
        self._test_breadcrumbs_on_brief_response_page(res)

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
            '/suppliers/opportunities/1234/responses/create',
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
        self._test_breadcrumbs_on_brief_response_page(res)

    def test_create_new_brief_response_404_if_not_live_brief(self, data_api_client):
        brief = self.brief.copy()
        brief['briefs']['status'] = 'draft'
        data_api_client.get_brief.return_value = brief
        data_api_client.get_framework.return_value = self.framework

        res = self.client.post(
            '/suppliers/opportunities/1234/responses/create',
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
            '/suppliers/opportunities/1234/responses/create',
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
                'supplierId': 1234
            }]
        }

        res = self.client.post(
            '/suppliers/opportunities/1234/responses/create',
            data=brief_form_submission
        )
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/result'
        self.assert_flashes("already_applied", "error")
        assert not data_api_client.create_brief_response.called

    def test_create_new_brief_returns_error_page_if_supplier_has_no_services_on_lot(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_brief.return_value['briefs']['frameworkName'] = 'Digital Outcomes and Specialists'
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = False
        data_api_client.find_services.side_effect = lambda *args, **kwargs: (
            {"services": [{"something": "nonempty"}]} if kwargs.get("lot") is None else {"services": []}
        )

        res = self.client.post(
            '/suppliers/opportunities/1234/responses/create',
            data=brief_form_submission
        )
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 400
        assert doc.xpath('normalize-space(//h1/text())') == ERROR_MESSAGE_PAGE_HEADING_APPLICATION
        assert len(doc.xpath(
            '//*[contains(normalize-space(text()), normalize-space("{}"))]'.format(
                ERROR_MESSAGE_NO_SERVICE_ON_LOT_APPLICATION
            )
        )) == 1
        assert not data_api_client.create_brief_response.called

    def test_create_new_brief_returns_error_page_if_supplier_has_no_services_on_framework(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_brief.return_value['briefs']['frameworkFramework'] = 'dos'
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = False
        data_api_client.find_services.return_value = {"services": []}

        res = self.client.post(
            '/suppliers/opportunities/1234/responses/create',
            data=brief_form_submission
        )
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 400
        assert doc.xpath('normalize-space(//h1/text())') == ERROR_MESSAGE_PAGE_HEADING_APPLICATION
        assert len(doc.xpath(
            '//*[contains(normalize-space(text()), normalize-space("{}"))]'.format(
                ERROR_MESSAGE_NO_SERVICE_ON_FRAMEWORK_APPLICATION
            )
        )) == 1
        assert not data_api_client.create_brief_response.called

    def test_create_new_brief_returns_error_page_if_supplier_has_no_services_with_role(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_brief.return_value['briefs']['frameworkName'] = 'Digital Outcomes and Specialists'
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = False
        data_api_client.find_services.return_value = {"services": [{"something": "nonempty"}]}

        res = self.client.post(
            '/suppliers/opportunities/1234/responses/create',
            data=brief_form_submission
        )
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 400
        assert doc.xpath('normalize-space(//h1/text())') == ERROR_MESSAGE_PAGE_HEADING_APPLICATION
        assert len(doc.xpath(
            '//*[contains(normalize-space(text()), normalize-space("{}"))]'.format(
                ERROR_MESSAGE_NO_SERVICE_WITH_ROLE_APPLICATION
            )
        )) == 1
        assert not data_api_client.create_brief_response.called

    def test_create_new_brief_response_with_api_error_fails(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.create_brief_response.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {'availability': 'answer_required'}
        )

        res = self.client.post(
            '/suppliers/opportunities/1234/responses/create',
            data=brief_form_submission
        )

        assert res.status_code == 400
        assert "You need to answer this question." in res.get_data(as_text=True)
        data_api_client.create_brief_response.assert_called_once_with(
            1234,
            1234,
            processed_brief_submission,
            'email@email.com',
            page_questions=[
                'respondToEmailAddress', 'essentialRequirements', 'niceToHaveRequirements', 'availability', 'dayRate'
            ]
        )

    def test_create_new_brief_response_redirects_to_login_for_buyer(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        self.login_as_buyer()
        res = self.client.post(
            '/suppliers/opportunities/1234/responses/create',
            data=brief_form_submission
        )
        assert res.status_code == 302
        assert res.location == "http://localhost/login"
        self.assert_flashes("supplier-role-required", "error")
        assert not data_api_client.get_brief.called


@mock.patch("app.main.views.briefs.data_api_client")
class TestStartBriefResponseApplication(BaseApplicationTest):
    def setup(self):
        super(TestStartBriefResponseApplication, self).setup()

        with self.app.test_client():
            self.login()

    @mock.patch("app.main.views.briefs.is_supplier_eligible_for_brief")
    def test_will_show_not_eligible_response_if_supplier_is_not_eligible_for_brief(
        self, is_supplier_eligible_for_brief, data_api_client
    ):
        brief = api_stubs.brief(status='live', lot_slug='digital-specialists')
        data_api_client.get_brief.return_value = brief
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': []
        }
        is_supplier_eligible_for_brief.return_value = False

        res = self.client.get('/suppliers/opportunities/1234/responses/start')
        assert res.status_code == 400

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath('//title')[0].text == 'Not eligible for opportunity – Digital Marketplace'

    def test_start_application_contains_brief_title(self, data_api_client):
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', lot_slug='digital-specialists')
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': []
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/start')
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath('//h1')[0].text.strip() == "Apply for ‘I need a thing to do a thing’"
        assert doc.xpath("//input[@class='button-save']/@value")[0] == 'Start application'

    def test_start_page_is_viewable_and_has_start_button_if_no_existing_brief_response(
        self, data_api_client
    ):
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', lot_slug='digital-specialists')
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': []
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/start')

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath("//input[@class='button-save']/@value")[0] == 'Start application'

    def test_start_page_is_viewable_and_has_continue_link_if_draft_brief_response_exists(
        self, data_api_client
    ):
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', lot_slug='digital-specialists')
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': [
                {
                    "id": 2,
                    "status": "draft",
                }
            ]
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/start')

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath("//a[@class='link-button']/text()")[0] == 'Continue application'
        assert doc.xpath("//a[@class='link-button']/@href")[0] == '/suppliers/opportunities/1234/responses/2'

    def test_will_show_not_eligible_response_if_supplier_has_already_submitted_application(self, data_api_client):
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', lot_slug='digital-specialists')
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': [
                {
                    "id": 2,
                    "status": "submitted",
                    "submittedAt": "2016-07-20T10:34:08.993952Z",
                }
            ]
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/start')
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/result'

    def test_start_page_for_specialist_brief_shows_specialist_content(self, data_api_client):
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', lot_slug='digital-specialists')
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': []
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/start')
        assert res.status_code == 200

        data = res.get_data(as_text=True)

        assert 'give the date the specialist will be available to start work' in data
        assert "provide the specialist's day rate" in data
        assert "say which skills and experience the specialist has" in data
        assert "give evidence for all the skills and experience the specialist has" in data
        assert "The buyer will assess and score your evidence to shortlist the best specialists." in data
        assert "the work the specialist did" in data

    def test_start_page_for_outcomes_brief_shows_outcomes_content(self, data_api_client):
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', lot_slug='digital-outcomes')
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': []
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/start')
        assert res.status_code == 200

        data = res.get_data(as_text=True)

        assert 'give the date the team will be available to start work' in data
        assert "say which skills and experience the team have" in data
        assert "give evidence for all the skills and experience the team have" in data
        assert "The buyer will assess and score your evidence to shortlist the best suppliers." in data
        assert "the work the team did" in data

        assert "provide the specialist's day rate" not in data

    def test_start_page_for_user_research_participants_brief_shows_user_research_content(self, data_api_client):
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', lot_slug='user-research-participants')
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': []
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/start')
        assert res.status_code == 200

        data = res.get_data(as_text=True)

        assert 'give the date you will be available to start work' in data
        assert "say which skills and experience you have" in data
        assert "give evidence for all the skills and experience you have" in data
        assert "The buyer will assess and score your evidence to shortlist the best suppliers." in data
        assert "the work you did" in data

        assert "provide the specialist's day rate" not in data

    def test_start_page_is_hidden_by_feature_flag(self, data_api_client):
        self.app.config['FEATURE_FLAGS_NEW_SUPPLIER_FLOW'] = False
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', lot_slug='digital-outcomes')
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': []
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/start')
        assert res.status_code == 404


@mock.patch("app.main.views.briefs.data_api_client")
class TestPostStartBriefResponseApplication(BaseApplicationTest):
    def setup(self):
        super(TestPostStartBriefResponseApplication, self).setup()

        with self.app.test_client():
            self.login()

    @mock.patch("app.main.views.briefs.is_supplier_eligible_for_brief")
    def test_will_show_not_eligible_response_if_supplier_is_not_eligible_for_brief(
        self, is_supplier_eligible_for_brief, data_api_client
    ):
        brief = api_stubs.brief(status='live', lot_slug='digital-specialists')
        data_api_client.get_brief.return_value = brief
        is_supplier_eligible_for_brief.return_value = False

        res = self.client.post('/suppliers/opportunities/2345/responses/start')
        assert res.status_code == 400

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath('//title')[0].text == 'Not eligible for opportunity – Digital Marketplace'

    def test_valid_post_calls_api_and_redirects_to_edit_the_created_brief_response(self, data_api_client):
        brief = api_stubs.brief(status='live', lot_slug='digital-specialists')
        data_api_client.get_brief.return_value = brief
        data_api_client.create_brief_response.return_value = {
            'briefResponses': {
                'id': 10
            }
        }

        res = self.client.post('/suppliers/opportunities/1234/responses/start')
        data_api_client.create_brief_response.assert_called_once_with(1234, 1234, {}, "email@email.com")
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/10'

    def test_post_to_start_page_is_hidden_by_feature_flag(self, data_api_client):
        self.app.config['FEATURE_FLAGS_NEW_SUPPLIER_FLOW'] = False
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', lot_slug='digital-outcomes')
        res = self.client.post('/suppliers/opportunities/1234/responses/start')
        assert res.status_code == 404


@mock.patch("app.main.views.briefs.data_api_client")
class TestResponseResultPage(BaseApplicationTest):

    def setup(self):
        super(TestResponseResultPage, self).setup()
        lots = [api_stubs.lot(slug="digital-specialists", allows_brief=True)]
        self.framework = api_stubs.framework(status="live", slug="digital-outcomes-and-specialists",
                                             clarification_questions_open=False, lots=lots)
        self.brief = api_stubs.brief(status='live')
        self.brief['briefs']['essentialRequirements'] = ['Must one', 'Must two', 'Must three']
        self.brief['briefs']['evaluationType'] = ['Interview']
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
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath('//h1')[0].text.strip() == \
            "Your response to ‘I need a thing to do a thing’ has been sent"

    def test_view_response_result_submitted_ok_for_closed_brief(self, data_api_client):
        closed_brief = self.brief.copy()
        closed_brief['briefs']['status'] = 'closed'
        data_api_client.get_brief.return_value = closed_brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {
            "briefResponses": [
                {"essentialRequirements": [True, True, True]}
            ]
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath('//h1')[0].text.strip() == \
            "Your response to ‘I need a thing to do a thing’ has been sent"

    def test_view_response_result_submitted_unsuccessful(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {
            "briefResponses": [
                {"essentialRequirements": [True, False, True]}
            ]
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath('//h1')[0].text.strip() == "You don’t meet all the essential requirements"

    def test_view_response_result_not_submitted_redirect_to_submit_page(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {"briefResponses": []}
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/create'

    def test_essential_skills_shown_with_response(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {
            "briefResponses": [
                {"essentialRequirements": [True, True, True]}
            ]
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//h2[contains(normalize-space(text()), "Your essential skills and experience")]')) == 1

    def test_nice_to_haves_shown_with_response_when_they_exist(self, data_api_client):
        brief_with_nice_to_haves = self.brief.copy()
        brief_with_nice_to_haves['briefs']['niceToHaveRequirements'] = ['Nice one', 'Top one', 'Get sorted']
        data_api_client.get_brief.return_value = brief_with_nice_to_haves
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {
            "briefResponses": [
                {
                    "essentialRequirements": [True, True, True],
                    "niceToHaveRequirements": [False, True, False]
                }
            ]
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(
            doc.xpath('//h2[contains(normalize-space(text()), "Your nice-to-have skills and experience")]')
        ) == 1

    def test_nice_to_haves_heading_not_shown_when_there_are_none(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {
            "briefResponses": [
                {"essentialRequirements": [True, True, True]}
            ]
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(
            doc.xpath('//h2[contains(normalize-space(text()), "Your nice-to-have skills and experience")]')
        ) == 0

    def test_supplier_details_shown(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {
            "briefResponses": [
                {"essentialRequirements": [True, True, True]}
            ]
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//h2[contains(normalize-space(text()), "Your details")]')) == 1

    def test_budget_message_shown_if_budget_is_set_for_specialists(self, data_api_client):
        brief_with_budget_range = self.brief.copy()
        brief_with_budget_range['briefs']['budgetRange'] = 'Up to £200 per day'
        data_api_client.get_brief.return_value = brief_with_budget_range
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {
            "briefResponses": [
                {"essentialRequirements": [True, True, True]}
            ]
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/result')
        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//li[contains(normalize-space(text()), "your day rate exceeds their budget")]')) == 1

    def test_budget_message_not_shown_if_budget_is_not_set_for_specialists(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {
            "briefResponses": [
                {"essentialRequirements": [True, True, True]}
            ]
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//li[contains(normalize-space(text()), "your day rate exceeds their budget")]')) == 0

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
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//li[contains(normalize-space(text()), "a work history")]')) == 1

    def test_evaluation_methods_shown_with_a_or_an(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True
        data_api_client.find_brief_responses.return_value = {
            "briefResponses": [
                {"essentialRequirements": [True, True, True]}
            ]
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//li[contains(normalize-space(text()), "a work history")]')) == 1
        assert len(doc.xpath('//li[contains(normalize-space(text()), "an interview")]')) == 1
