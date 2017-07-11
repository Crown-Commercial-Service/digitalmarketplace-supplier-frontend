# coding: utf-8
from __future__ import unicode_literals

import mock
import pytest
from lxml import html

from dmapiclient import api_stubs, HTTPError
from dmapiclient.audit import AuditTypes
from dmutils.email.exceptions import EmailError

from app.main.views.briefs import _render_not_eligible_for_brief_error_page

from ..helpers import BaseApplicationTest, FakeMail


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

ERROR_MESSAGE_PAGE_HEADING_CLARIFICATION = 'You can’t ask a question about this opportunity'
ERROR_MESSAGE_NO_SERVICE_ON_LOT_CLARIFICATION = \
    'You can’t ask a question about this opportunity because you didn’t say you'\
    ' could provide services in this category when you applied to the Digital Outcomes and Specialists framework.'
ERROR_MESSAGE_NO_SERVICE_ON_FRAMEWORK_CLARIFICATION = \
    'You can’t ask a question about this opportunity because you’re not a Digital Outcomes and Specialists supplier.'
ERROR_MESSAGE_NO_SERVICE_WITH_ROLE_CLARIFICATION = \
    'You can’t ask a question about this opportunity because you didn’t say you'\
    ' could provide this specialist role when you applied to the Digital Outcomes and Specialists framework.'


class Table(object):
    def __init__(self, doc, table_name):
        self._data = []
        self._row_index = None
        query = doc.xpath(
            ''.join([
                '//h2[contains(normalize-space(text()), "{}")]',
                '/following-sibling::table[1]/tbody/tr'
            ]).format(table_name)
        )
        if len(query):
            for row_element in query:
                self._data.append(
                    [
                        element.find('span').text if element.find('span') is not None
                        else '' for element in row_element.findall('td')]
                )

    def exists(self):
        return len(self._data) > 0

    def row(self, idx):
        self._row_index = idx
        return self

    def cell(self, idx):
        if self._row_index is None:
            raise KeyError("no row selected")
        else:
            try:
                return self._data[self._row_index][idx]
            except IndexError as e:
                raise IndexError("{}. Contents of table: {}".format(e, self._data))


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
        assert res.status_code == 403

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
        assert res.status_code == 403

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
            data={'briefId': 1234, 'question': u'important question', 'supplierId': 1234},
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

        send_email.side_effect = EmailError

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

        assert res.status_code == 403
        assert doc.xpath('normalize-space(//h1/text())') == ERROR_MESSAGE_PAGE_HEADING_CLARIFICATION
        assert len(doc.xpath(
            '//*[contains(normalize-space(text()), normalize-space("{}"))]'.format(
                ERROR_MESSAGE_NO_SERVICE_ON_LOT_CLARIFICATION
            )
        )) == 1
        assert data_api_client.create_audit_event.called is False

    @mock.patch('app.main.helpers.briefs.send_email')
    def test_submit_clarification_question_returns_error_page_if_supplier_has_no_services_on_framework(
            self, send_email, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = api_stubs.brief(status='live', lot_slug='digital-specialists')
        data_api_client.is_supplier_eligible_for_brief.return_value = False
        data_api_client.find_services.return_value = {"services": []}

        res = self.client.post('/suppliers/opportunities/1/ask-a-question', data={
            'clarification-question': "important question",
        })
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 403
        assert doc.xpath('normalize-space(//h1/text())') == ERROR_MESSAGE_PAGE_HEADING_CLARIFICATION
        assert len(doc.xpath(
            '//*[contains(normalize-space(text()), normalize-space("{}"))]'.format(
                ERROR_MESSAGE_NO_SERVICE_ON_FRAMEWORK_CLARIFICATION
            )
        )) == 1
        assert data_api_client.create_audit_event.called is False

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

        assert res.status_code == 403
        assert doc.xpath('normalize-space(//h1/text())') == ERROR_MESSAGE_PAGE_HEADING_CLARIFICATION
        assert len(doc.xpath(
            '//*[contains(normalize-space(text()), normalize-space("{}"))]'.format(
                ERROR_MESSAGE_NO_SERVICE_WITH_ROLE_CLARIFICATION
            )
        )) == 1
        assert data_api_client.create_audit_event.called is False

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
    """Tests requests for the multipage flow for applying for a brief"""

    def setup_method(self, method):
        super(TestApplyToBrief, self).setup_method(method)

        self.brief = api_stubs.brief(status='live', lot_slug='digital-specialists')
        self.brief['briefs']['essentialRequirements'] = ['Essential one', 'Essential two', 'Essential three']
        self.brief['briefs']['niceToHaveRequirements'] = ['Nice one', 'Top one', 'Get sorted']

        lots = [
            api_stubs.lot(slug="digital-specialists", allows_brief=True),
            api_stubs.lot(slug="digital-outcomes", allows_brief=True),
            api_stubs.lot(slug="user-research-participants", allows_brief=True)
        ]
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

    def teardown_method(self, method):
        super(TestApplyToBrief, self).teardown_method(method)
        self.data_api_client_patch.stop()

    @mock.patch("app.main.views.briefs.content_loader")
    def test_will_redirect_from_generic_brief_response_url_to_first_question(self, content_loader):
        content_loader.get_manifest.return_value \
            .filter.return_value \
            .get_section.return_value \
            .get_next_question_id.return_value = 'first'

        res = self.client.get('/suppliers/opportunities/1234/responses/5')
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/5/first'

    def test_can_get_question_page_for_live_and_expired_framework(self):
        for framework_status in ['live', 'expired']:
            framework = self.framework.copy()
            framework.update({'status': framework_status})
            self.data_api_client.get_framework.return_value = framework

            res = self.client.get('/suppliers/opportunities/1234/responses/5/respondToEmailAddress')

            assert res.status_code == 200

    def test_can_post_question_page_for_live_and_expired_framework(self):
        for framework_status in ['live', 'expired']:
            framework = self.framework.copy()
            framework.update({'status': framework_status})
            self.data_api_client.get_framework.return_value = framework

            res = self.client.post('/suppliers/opportunities/1234/responses/5/respondToEmailAddress')

            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/result'

    def test_404_if_brief_response_does_not_exist(self):
        for method in ('get', 'post'):
            self.data_api_client.get_brief_response = mock.MagicMock(side_effect=HTTPError(mock.Mock(status_code=404)))

            res = self.client.open('/suppliers/opportunities/1234/responses/250/question-id', method=method)

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

            res = self.client.open('/suppliers/opportunities/1234/responses/5/question-id', method=method)
            assert res.status_code == 404

    @mock.patch("app.main.views.briefs.current_user")
    def test_404_if_brief_response_does_not_relate_to_current_user(self, current_user):
        for method in ('get', 'post'):
            current_user.supplier_id = 789

            res = self.client.open('/suppliers/opportunities/1234/responses/5/question-id', method=method)
            assert res.status_code == 404

    def test_404_for_not_live_brief(self):
        for method in ('get', 'post'):
            self.data_api_client.get_brief.return_value = api_stubs.brief(
                status='closed', lot_slug='digital-specialists'
            )

            res = self.client.open('/suppliers/opportunities/1234/responses/5/question-id', method=method)
            assert res.status_code == 404

    def test_404_for_not_live_or_expired_framework(self):
        for framework_status in ['coming', 'open', 'pending', 'standstill']:
            for method in ('get', 'post'):
                framework = self.framework.copy()
                framework.update({'status': framework_status})
                self.data_api_client.get_framework.return_value = framework
                res = self.client.open('/suppliers/opportunities/1234/responses/5/question-id', method=method)
                assert res.status_code == 404

    @mock.patch("app.main.views.briefs.is_supplier_eligible_for_brief")
    @mock.patch("app.main.views.briefs._render_not_eligible_for_brief_error_page", autospec=True)
    def test_show_not_eligible_page_if_supplier_not_eligible_to_apply_for_brief(
        self, _render_not_eligible_for_brief_error_page, is_supplier_eligible_for_brief
    ):
        is_supplier_eligible_for_brief.return_value = False
        _render_not_eligible_for_brief_error_page.return_value = 'dummy response', 403

        for method in ('get', 'post'):
            res = self.client.open('/suppliers/opportunities/1234/responses/5/question-id', method=method)
            assert res.status_code == 403
            _render_not_eligible_for_brief_error_page.assert_called_with(self.brief['briefs'])

    @mock.patch("app.main.views.briefs.supplier_has_a_brief_response")
    def test_redirect_to_show_brief_response_if_already_applied_for_brief(self, supplier_has_a_brief_response):
        framework = self.framework.copy()
        for framework_status in ['live', 'expired']:
            framework.update({'status': framework_status})
            self.data_api_client.get_framework.return_value = framework
            for method in ('get', 'post'):
                supplier_has_a_brief_response.return_value = True

                res = self.client.open('/suppliers/opportunities/1234/responses/5/question-id', method=method)
                assert res.status_code == 302
                assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/result'
                self.assert_flashes("already_applied", "error")

    @mock.patch("app.main.views.briefs.content_loader")
    def test_should_404_for_non_existent_content_section(self, content_loader):
        for method in ('get', 'post'):
            content_loader.get_manifest.return_value.filter.return_value.get_section.return_value = None

            res = self.client.open('/suppliers/opportunities/1234/responses/5/question-id', method=method)
            assert res.status_code == 404

    @mock.patch("app.main.views.briefs.content_loader")
    def test_should_404_for_non_editable_content_section(self, content_loader):
        for method in ('get', 'post'):
            content_loader.get_manifest.return_value.filter.return_value.get_section.return_value.editable = False

            res = self.client.open('/suppliers/opportunities/1234/responses/5/question-id', method=method)
            assert res.status_code == 404

    @mock.patch("app.main.views.briefs.content_loader")
    def test_should_404_for_non_existent_question(self, content_loader):
        for method in ('get', 'post'):
            content_loader.get_manifest.return_value \
                .filter.return_value \
                .get_section.return_value \
                .get_question.return_value = None

            res = self.client.open('/suppliers/opportunities/1234/responses/5/question-id', method=method)
            assert res.status_code == 404

    def test_non_final_question_shows_continue_button(self):
        res = self.client.get('/suppliers/opportunities/1234/responses/5/dayRate')
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath("//input[@class='button-save']/@value")[0] == 'Continue'

    def test_final_question_shows_submit_application_button(self):
        res = self.client.get('/suppliers/opportunities/1234/responses/5/respondToEmailAddress')
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath("//input[@class='button-save']/@value")[0] == 'Submit application'

    def test_first_question_does_not_show_previous_page_link(self):
        self.brief['briefs']['startDate'] = 'start date'
        res = self.client.get('/suppliers/opportunities/1234/responses/5/availability')
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath("//a[text()='Back to previous page']")) == 0

    def test_non_first_question_shows_previous_page_link(self):
        res = self.client.get('/suppliers/opportunities/1234/responses/5/dayRate')
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert (doc.xpath("//a[text()='Back to previous page']/@href")[0] ==
                '/suppliers/opportunities/1234/responses/5/availability')

    def test_respond_to_email_previous_page_link_skips_nice_to_have_requirements_if_no_nice_to_haves_for_brief(self):
        self.brief['briefs']['niceToHaveRequirements'] = []
        self.data_api_client.get_brief.return_value = self.brief

        res = self.client.get('/suppliers/opportunities/1234/responses/5/respondToEmailAddress')
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert (doc.xpath("//a[text()='Back to previous page']/@href")[0] ==
                '/suppliers/opportunities/1234/responses/5/essentialRequirements')

    def test_content_from_manifest_is_shown(self):
        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/respondToEmailAddress'
        )
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath("//h1/text()")[0].strip() == 'Email address the buyer should use to contact you'
        assert (doc.xpath("//span[@class=\"question-heading\"]/text()")[0].strip() ==
                'Email address the buyer should use to contact you')
        assert (doc.xpath("//span[@class=\"question-advice\"]/text()")[0].strip() ==
                'All communication about your application will be sent to this address.')

    def test_essential_requirements_met_question_replays_all_brief_requirements(self):
        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/essentialRequirementsMet'
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
            '/suppliers/opportunities/1234/responses/5/essentialRequirementsMet'
        )
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        list_items = doc.xpath("//*[@id='input-essentialRequirementsMet-question-advice']/ul/li")
        # if item is excaped correctly it will appear as text rather than an element
        assert list_items[0].find("h1") is None
        assert list_items[0].text == '<h1>Essential one with xss</h1>'
        assert list_items[1].find("strong") is None
        assert list_items[1].text == '**Essential two with markdown**'

    def test_day_rate_question_replays_buyers_budget_range_and_suppliers_max_day_rate(self):
        self.brief['briefs']['budgetRange'] = '1 million dollars'
        self.brief['briefs']['specialistRole'] = 'deliveryManager'
        self.data_api_client.find_services.return_value = {"services": [{"deliveryManagerPriceMax": 600}]}

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/dayRate'
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
            '/suppliers/opportunities/1234/responses/5/dayRate'
        )
        assert res.status_code == 200

        data = res.get_data(as_text=True)

        assert '**markdown**' in data

    def test_day_rate_question_escapes_brief_day_rate_html(self):
        self.brief['briefs']['budgetRange'] = '<h1>xss</h1>'

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/dayRate'
        )
        assert res.status_code == 200

        data = res.get_data(as_text=True)

        assert '&lt;h1&gt;xss&lt;/h1&gt;' in data

    def test_day_rate_question_does_not_replay_buyers_budget_range_if_not_provided(self):
        self.brief['briefs']['specialistRole'] = 'deliveryManager'
        self.data_api_client.find_services.return_value = {"services": [{"deliveryManagerPriceMax": 600}]}

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/dayRate'
        )
        assert res.status_code == 200
        data = res.get_data(as_text=True)
        assert "Buyer's maximum day rate:" not in data

    def test_availability_question_shows_correct_content_for_lot(self):
        self.brief['briefs']['startDate'] = '17/01/2017'
        self.brief['briefs']['researchDates'] = '17/01/2017'
        lot_slugs = ['digital-specialists', 'digital-outcomes', 'user-research-participants']
        question_content = ['the specialist can start work?', 'the team can start?', 'you can recruit participants?']
        hint_content = ['the specialist to start:', 'the team to start:', 'participants:']

        for lot_slug, question, hint in zip(lot_slugs, question_content, hint_content):
            self.brief['briefs']['lotSlug'] = lot_slug

            res = self.client.get(
                '/suppliers/opportunities/1234/responses/5/availability'
            )
            assert res.status_code == 200

            doc = html.fromstring(res.get_data(as_text=True))
            page_heading = doc.xpath("//h1/text()")
            page_hint = doc.xpath("//span[@id='input-availability-question-advice']/p/text()")

            assert len(page_heading) == 1
            assert page_heading[0].strip() == 'When is the earliest {}'.format(question)
            assert len(page_hint) == 1
            assert page_hint[0] == 'The buyer needs {} 17/01/2017'.format(hint)

    @pytest.mark.parametrize(
        ('date_string', 'expected'),
        (('2017-04-25', 'Tuesday 25 April 2017'), ('foo', 'foo'))
    )
    def test_availability_question_renders_date_or_falls_back_to_string(self, date_string, expected):
        self.brief['briefs']['frameworkName'] = "Digital Outcomes and Specialists 2"
        self.brief['briefs']['frameworkSlug'] = "digital-outcomes-and-specialists-2"
        self.brief['briefs']['startDate'] = date_string
        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/availability'
        )
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        page_hint = doc.xpath("//span[@id='input-availability-question-advice']/p/text()")
        assert page_hint[0] == 'The buyer needs the specialist to start: {}'.format(expected)

    def test_availability_question_escapes_brief_start_date_markdown(self):
        self.brief['briefs']['startDate'] = '**markdown**'

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/availability'
        )
        assert res.status_code == 200

        data = res.get_data(as_text=True)

        assert "The buyer needs the specialist to start: **markdown**" in data

    def test_availability_question_escapes_brief_start_date_html(self):
        self.brief['briefs']['startDate'] = '<h1>xss</h1>'
        self.brief['briefs']['lot'] = 'digital-specialists'

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/availability'
        )
        assert res.status_code == 200

        data = res.get_data(as_text=True)

        assert "The buyer needs the specialist to start: &lt;h1&gt;xss&lt;/h1&gt;" in data

    def test_essential_requirements_evidence_has_question_for_every_requirement(self):
        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/essentialRequirements'
        )
        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        questions = doc.xpath(
            "//*[@class='question-heading']/text()")
        questions = list(map(str.strip, questions))
        assert questions == ['Essential one', 'Essential two', 'Essential three']

    def test_essential_and_nice_to_have_requirements_evidence_escapes_brief_data(self):
        for question_slug in ('essentialRequirements', 'niceToHaveRequirements'):
            self.brief['briefs'][question_slug] = [
                '<h1>requirement with xss</h1>',
                '**requirement with markdown**'
            ]
            self.data_api_client.get_brief.return_value = self.brief

            res = self.client.get(
                '/suppliers/opportunities/1234/responses/5/{}'.format(question_slug)
            )
            assert res.status_code == 200

            data = res.get_data(as_text=True)

            assert '&lt;h1&gt;requirement with xss&lt;/h1&gt;' in data
            assert '**requirement with markdown**' in data

    def test_specialist_brief_essential_and_nice_to_have_requirements_evidence_shows_specialist_content(self):
        for question_slug in ('essentialRequirements', 'niceToHaveRequirements'):
            res = self.client.get(
                '/suppliers/opportunities/1234/responses/5/{}'.format(question_slug)
            )
            assert res.status_code == 200
            data = res.get_data(as_text=True)

            assert "the work the specialist did" in data
            assert "the work the team did" not in data

    def test_outcomes_brief_essential_and_nice_to_have_requirements_evidence_shows_outcomes_content(self):
        self.brief['briefs']['lotSlug'] = 'digital-outcomes'
        self.data_api_client.get_brief.return_value = self.brief

        for question_slug in ('essentialRequirements', 'niceToHaveRequirements'):
            res = self.client.get(
                '/suppliers/opportunities/1234/responses/5/{}'.format(question_slug)
            )
            assert res.status_code == 200
            data = res.get_data(as_text=True)

            assert "the work the team did" in data
            assert "the work the specialist did" not in data

    def test_existing_essential_requirements_evidence_prefills_existing_data(self):
        self.data_api_client.get_brief_response.return_value = self.brief_response(
            data={
                'essentialRequirements': [
                    {'evidence': 'evidence0'}, {'evidence': 'evidence1'}, {'evidence': 'evidence2'}
                ]
            }
        )

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/essentialRequirements'
        )
        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        for i in range(3):
            assert doc.xpath("//*[@id='input-evidence-" + str(i) + "']/text()")[0] == 'evidence' + str(i)

    def test_submit_essential_requirements_evidence(self):
        res = self.client.post(
            '/suppliers/opportunities/1234/responses/5/essentialRequirements',
            data={
                "evidence-0": 'first evidence',
                "evidence-1": 'second evidence',
                "evidence-2": 'third evidence'
            }
        )

        assert res.status_code == 302

        self.data_api_client.update_brief_response.assert_called_once_with(
            5,
            {
                "essentialRequirements": [
                    {'evidence': 'first evidence'}, {'evidence': 'second evidence'}, {'evidence': 'third evidence'}
                ]
            },
            'email@email.com',
            page_questions=['essentialRequirements']
        )

    def test_essentials_evidence_page_shows_errors_messages_and_replays_user_input(self):
        self.data_api_client.update_brief_response.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {
                'essentialRequirements': [
                    {'field': 'evidence', 'index': 0, 'error': 'under_100_words'},
                    {'field': 'evidence', 'index': 2, 'error': 'answer_required'}
                ]
            }
        )

        res = self.client.post(
            '/suppliers/opportunities/1234/responses/5/essentialRequirements',
            data={
                "evidence-0": "over100characters" * 10,
                "evidence-1": "valid evidence",
                "evidence-2": ""
            }
        )

        assert res.status_code == 400
        doc = html.fromstring(res.get_data(as_text=True))

        # Test list of questions with errors at top of page
        assert (doc.xpath("//h1[@class=\"validation-masthead-heading\"]/text()")[0].strip() ==
                'There was a problem with your answer to:')
        assert (doc.xpath("//a[@class=\"validation-masthead-link\"]/text()")[0].strip() ==
                'Essential one')
        assert (doc.xpath("//a[@class=\"validation-masthead-link\"]/text()")[1].strip() ==
                'Essential three')

        # Test individual questions errors and prefilled content
        assert (doc.xpath("//span[@class=\"validation-message\"]/text()")[0].strip() ==
                'Your answer must be no more than 100 words.')
        assert doc.xpath("//*[@id='input-evidence-0']/text()")[0] == "over100characters" * 10

        assert doc.xpath("//*[@id='input-evidence-1']/text()")[0] == "valid evidence"

        assert (doc.xpath("//span[@class=\"validation-message\"]/text()")[1].strip() ==
                'You need to provide evidence.')
        assert not doc.xpath("//*[@id='input-evidence-2']/text()") is None

    def test_essential_evidence_page_replays_user_input_instead_of_existing_brief_response_data(self):
        self.data_api_client.get_brief_response.return_value = self.brief_response(
            data={'essentialRequirements': [{'evidence': 'nice valid evidence'}] * 3}
        )

        self.data_api_client.update_brief_response.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {
                'essentialRequirements': [
                    {'field': 'evidence', 'index': 0, 'error': 'under_100_words'}
                ]
            }
        )

        res = self.client.post(
            '/suppliers/opportunities/1234/responses/5/essentialRequirements',
            data={
                "evidence-0": "over100characters" * 10,
                "evidence-1": "valid evidence",
                "evidence-2": ""
            }
        )

        assert res.status_code == 400
        doc = html.fromstring(res.get_data(as_text=True))

        assert (doc.xpath("//span[@class=\"validation-message\"]/text()")[0].strip() ==
                'Your answer must be no more than 100 words.')
        assert doc.xpath("//*[@id='input-evidence-0']/text()")[0] == "over100characters" * 10
        assert doc.xpath("//*[@id='input-evidence-1']/text()")[0] == "valid evidence"
        assert not doc.xpath("//*[@id='input-evidence-2']/text()")

    def test_essential_requirements_evidence_does_not_redirect_to_nice_to_haves_if_brief_has_no_nice_to_haves(self):
        self.brief['briefs']['niceToHaveRequirements'] = []
        self.data_api_client.get_brief.return_value = self.brief

        res = self.client.post(
            '/suppliers/opportunities/1234/responses/5/essentialRequirements',
            data={
                "evidence-0": "valid evidence",
                "evidence-1": "valid evidence",
                "evidence-2": "valid evidence"
            }
        )

        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/5/respondToEmailAddress'

    def test_nice_to_have_requirements_url_404s_if_no_nice_to_have_requirements(self):
        self.brief['briefs']['niceToHaveRequirements'] = []
        self.data_api_client.get_brief.return_value = self.brief

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/niceToHaveRequirements'
        )
        assert res.status_code == 404

    def test_nice_to_have_requirements_evidence_has_question_for_every_requirement(self):
        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/niceToHaveRequirements'
        )
        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        questions = doc.xpath(
            "//*[@class='question-heading']/text()")
        questions = list(map(str.strip, questions))

        assert questions == [
            'Nice one', 'Evidence of Nice one', 'Top one', 'Evidence of Top one', 'Get sorted', 'Evidence of Get sorted'
        ]

    def test_existing_nice_to_have_requirements_evidence_prefills_existing_data(self):
        self.data_api_client.get_brief_response.return_value = self.brief_response(
            data={
                'niceToHaveRequirements': [
                    {'yesNo': True, 'evidence': 'evidence0'}, {'yesNo': False}, {'yesNo': True, 'evidence': 'evidence2'}
                ]
            }
        )

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/niceToHaveRequirements'
        )
        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))

        # Check yesno radio buttons
        for i in (0, 2):
            assert len(doc.xpath("//*[@id='input-yesNo-" + str(i) + "-1' and @checked]")) == 1
        assert len(doc.xpath("//*[@id='input-yesNo-1-2' and @checked]")) == 1

        # Check evidence text
        for i in (0, 2):
            assert doc.xpath("//*[@id='input-evidence-" + str(i) + "']/text()")[0] == 'evidence' + str(i)

    def test_submit_nice_to_have_requirements_evidence(self):
        res = self.client.post(
            '/suppliers/opportunities/1234/responses/5/niceToHaveRequirements',
            data={
                "yesNo-0": True,
                "evidence-0": 'first evidence',
                "yesNo-1": False,
                "evidence-1": "",
                "yesNo-2": False,
                "evidence-2": 'evidence we expect not to be sent'
            }
        )

        assert res.status_code == 302

        self.data_api_client.update_brief_response.assert_called_once_with(
            5,
            {
                "niceToHaveRequirements": [
                    {'yesNo': True, 'evidence': 'first evidence'},
                    {'yesNo': False},
                    {'yesNo': False}
                ]
            },
            'email@email.com',
            page_questions=['niceToHaveRequirements']
        )

    def test_nice_to_have_evidence_page_shows_errors_messages_and_replays_user_input(self):
        self.data_api_client.update_brief_response.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {
                'niceToHaveRequirements': [
                    {'field': 'yesNo', 'index': 0, 'error': 'answer_required'},
                    {'field': 'evidence', 'index': 1, 'error': 'answer_required'},
                    {'field': 'evidence', 'index': 2, 'error': 'under_100_words'}
                ]
            }
        )

        res = self.client.post(
            '/suppliers/opportunities/1234/responses/5/niceToHaveRequirements',
            data={
                "evidence-0": "",
                "yesNo-1": True,
                "evidence-1": "",
                "yesNo-2": True,
                "evidence-2": "word " * 100
            }
        )

        assert res.status_code == 400
        doc = html.fromstring(res.get_data(as_text=True))

        # Test list of questions with errors at top of page
        assert (doc.xpath("//h1[@class=\"validation-masthead-heading\"]/text()")[0].strip() ==
                'There was a problem with your answer to:')
        masthead_errors = doc.xpath("//a[@class=\"validation-masthead-link\"]/text()")
        masthead_errors = list(map(str.strip, masthead_errors))
        assert masthead_errors == ['Nice one', 'Evidence of Top one', 'Evidence of Get sorted']

        # Test individual questions errors and prefilled content
        assert (doc.xpath("//span[@class=\"validation-message\"]/text()")[0].strip() ==
                'You must answer ‘yes’ or ‘no’ to this question.')

        assert (doc.xpath("//span[@class=\"validation-message\"]/text()")[1].strip() ==
                'You must provide evidence if you answer ‘yes’ to this question.')
        assert len(doc.xpath("//*[@id='input-yesNo-1-1' and @checked]")) == 1

        assert (doc.xpath("//span[@class=\"validation-message\"]/text()")[2].strip() ==
                'Your answer must be no more than 100 words.')
        assert len(doc.xpath("//*[@id='input-yesNo-2-1' and @checked]")) == 1
        assert doc.xpath("//*[@id='input-evidence-2']/text()")[0] == 'word ' * 100

    def test_nice_to_have_evidence_page_replays_user_input_instead_of_existing_brief_response_data(self):
        self.data_api_client.get_brief_response.return_value = self.brief_response(
            data={'niceToHaveRequirements': [{'yesNo': True, 'evidence': 'nice valid evidence'}] * 3}
        )

        self.data_api_client.update_brief_response.side_effect = HTTPError(
            mock.Mock(status_code=400),
            {
                'niceToHaveRequirements': [
                    {'field': 'evidence', 'index': 0, 'error': 'under_100_words'}
                ]
            }
        )

        res = self.client.post(
            '/suppliers/opportunities/1234/responses/5/niceToHaveRequirements',
            data={
                "yesNo-0": True,
                "evidence-0": "over 100 words " * 100,
                "yesNo-1": False,
                "evidence-1": "",
                "yesNo-2": True,
                "evidence-2": ""
            }
        )

        assert res.status_code == 400
        doc = html.fromstring(res.get_data(as_text=True))

        assert (doc.xpath("//span[@class=\"validation-message\"]/text()")[0].strip() ==
                'Your answer must be no more than 100 words.')
        assert doc.xpath("//*[@id='input-evidence-0']/text()")[0] == "over 100 words " * 100

        assert len(doc.xpath("//*[@id='input-yesNo-1-2' and @checked]")) == 1
        assert not doc.xpath("//*[@id='input-evidence-1']/text()")

        assert not doc.xpath("//*[@id='input-evidence-2']/text()")

    def test_existing_brief_response_data_is_prefilled(self):
        self.data_api_client.get_brief_response.return_value = self.brief_response(
            data={'respondToEmailAddress': 'test@example.com'}
        )

        res = self.client.get(
            '/suppliers/opportunities/1234/responses/5/respondToEmailAddress'
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
            '/suppliers/opportunities/1234/responses/5/respondToEmailAddress',
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
            '/suppliers/opportunities/1234/responses/5/dayRate',
            data=data
        )
        assert res.status_code == 302

        self.data_api_client.update_brief_response.assert_called_once_with(
            5,
            data,
            'email@email.com',
            page_questions=['dayRate']
        )

        assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/5/essentialRequirementsMet'

    def test_post_final_section_submits_response_redirects_to_results(self):
        data = {'respondToEmailAddress': 'bob@example.com'}
        res = self.client.post(
            '/suppliers/opportunities/1234/responses/5/respondToEmailAddress',
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


class BriefResponseTestHelpers():
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

    def _get_data_from_table(self, doc, table_name):
        return Table(doc, table_name)


@mock.patch("app.main.views.briefs.data_api_client")
class TestStartBriefResponseApplication(BaseApplicationTest, BriefResponseTestHelpers):
    def setup_method(self, method):
        super(TestStartBriefResponseApplication, self).setup_method(method)
        self.brief = api_stubs.brief(status='live', lot_slug='digital-specialists')
        self.brief['briefs']['publishedAt'] = '2016-12-25T12:00:00.000000Z'

        with self.app.test_client():
            self.login()

    def test_will_return_404_if_brief_is_a_legacy_brief(self, data_api_client):
        self.brief['briefs']['publishedAt'] = '2016-10-25T12:00:00.000000Z'
        data_api_client.get_brief.return_value = self.brief

        res = self.client.get('/suppliers/opportunities/1234/responses/start')

        assert res.status_code == 404

    def test_will_return_404_if_new_supplier_flow_flag_set_to_false(self, data_api_client):
        self.app.config['FEATURE_FLAGS_NEW_SUPPLIER_FLOW'] = False
        data_api_client.get_brief.return_value = self.brief

        res = self.client.get('/suppliers/opportunities/1234/responses/start')

        assert res.status_code == 404

    @mock.patch("app.main.views.briefs.is_supplier_eligible_for_brief")
    @mock.patch("app.main.views.briefs._render_not_eligible_for_brief_error_page", autospec=True)
    def test_will_show_not_eligible_response_if_supplier_is_not_eligible_for_brief(
        self, _render_not_eligible_for_brief_error_page, is_supplier_eligible_for_brief, data_api_client
    ):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': []
        }
        is_supplier_eligible_for_brief.return_value = False
        _render_not_eligible_for_brief_error_page.return_value = 'dummy response', 403

        res = self.client.get('/suppliers/opportunities/1234/responses/start')
        assert res.status_code == 403
        _render_not_eligible_for_brief_error_page.assert_called_once_with(self.brief['briefs'])

    def test_start_application_contains_brief_title_and_breadcrumbs(self, data_api_client):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': []
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/start')
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath('//h1')[0].text.strip() == "Apply for ‘I need a thing to do a thing’"
        assert doc.xpath("//input[@class='button-save']/@value")[0] == 'Start application'

        self._test_breadcrumbs_on_brief_response_page(res)

    def test_start_page_is_viewable_and_has_start_button_if_no_existing_brief_response(
        self, data_api_client
    ):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': []
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/start')

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath("//input[@class='button-save']/@value")[0] == 'Start application'

    def test_start_page_is_viewable_and_has_continue_link_if_draft_brief_response_exists(
        self, data_api_client
    ):
        data_api_client.get_brief.return_value = self.brief
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
        data_api_client.get_brief.return_value = self.brief
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
        data_api_client.get_brief.return_value = self.brief
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
        self.brief['briefs']['lotSlug'] = 'digital-outcomes'
        data_api_client.get_brief.return_value = self.brief
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
        self.brief['briefs']['lotSlug'] = 'user-research-participants'
        data_api_client.get_brief.return_value = self.brief
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
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': []
        }
        res = self.client.get('/suppliers/opportunities/1234/responses/start')
        assert res.status_code == 404


@mock.patch("app.main.views.briefs.data_api_client")
class TestPostStartBriefResponseApplication(BaseApplicationTest):
    def setup_method(self, method):
        super(TestPostStartBriefResponseApplication, self).setup_method(method)
        self.brief = api_stubs.brief(status='live', lot_slug='digital-specialists')
        self.brief['briefs']['publishedAt'] = '2016-12-25T12:00:00.000000Z'

        with self.app.test_client():
            self.login()

    @mock.patch("app.main.views.briefs.is_supplier_eligible_for_brief")
    @mock.patch("app.main.views.briefs._render_not_eligible_for_brief_error_page", autospec=True)
    def test_will_show_not_eligible_response_if_supplier_is_not_eligible_for_brief(
        self, _render_not_eligible_for_brief_error_page, is_supplier_eligible_for_brief, data_api_client
    ):
        data_api_client.get_brief.return_value = self.brief
        is_supplier_eligible_for_brief.return_value = False
        _render_not_eligible_for_brief_error_page.return_value = 'dummy response', 403

        res = self.client.post('/suppliers/opportunities/2345/responses/start')
        assert res.status_code == 403
        _render_not_eligible_for_brief_error_page.assert_called_once_with(self.brief['briefs'])

    def test_valid_post_calls_api_and_redirects_to_edit_the_created_brief_response_if_no_application_started(
        self, data_api_client
    ):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': []
        }
        data_api_client.create_brief_response.return_value = {
            'briefResponses': {
                'id': 10
            }
        }

        res = self.client.post('/suppliers/opportunities/1234/responses/start')
        data_api_client.create_brief_response.assert_called_once_with(1234, 1234, {}, "email@email.com")
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/10'

    @mock.patch("app.main.views.briefs.supplier_has_a_brief_response")
    def test_redirects_to_beginning_of_ongoing_application_if_application_in_progress_but_not_submitted(
        self, supplier_has_a_brief_response, data_api_client
    ):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': [
                {
                    'id': 11,
                    'status': 'draft'
                }
            ]
        }

        res = self.client.post('/suppliers/opportunities/1234/responses/start')
        data_api_client.create_brief_response.assert_not_called()
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/11'

    @mock.patch("app.main.views.briefs.supplier_has_a_brief_response")
    def test_redirects_to_response_page_with_flash_message_if_application_already_submitted(
        self, supplier_has_a_brief_response, data_api_client
    ):
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = {
            'briefResponses': [
                {
                    'status': 'submitted'
                }
            ]
        }

        res = self.client.post('/suppliers/opportunities/1234/responses/start')
        data_api_client.create_brief_response.assert_not_called()
        self.assert_flashes("already_applied", "error")
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/result'

    def test_post_to_start_page_is_hidden_by_feature_flag(self, data_api_client):
        self.app.config['FEATURE_FLAGS_NEW_SUPPLIER_FLOW'] = False
        data_api_client.get_brief.return_value = self.brief
        res = self.client.post('/suppliers/opportunities/1234/responses/start')
        assert res.status_code == 404


class ResponseResultPageBothFlows(BaseApplicationTest, BriefResponseTestHelpers):

    def setup_method(self, method):
        super(ResponseResultPageBothFlows, self).setup_method(method)
        lots = [api_stubs.lot(slug="digital-specialists", allows_brief=True)]
        self.framework = api_stubs.framework(status="live", slug="digital-outcomes-and-specialists",
                                             clarification_questions_open=False, lots=lots)
        self.brief = api_stubs.brief(status='live')
        self.brief['briefs']['essentialRequirements'] = ['Must one', 'Must two', 'Must three']
        self.brief['briefs']['evaluationType'] = ['Interview']
        with self.app.test_client():
            self.login()

    def set_framework_and_eligibility_for_api_client(self, data_api_client):
        data_api_client.get_framework.return_value = self.framework
        data_api_client.is_supplier_eligible_for_brief.return_value = True

    def test_already_applied_flash_message_appears_in_result_page(self, data_api_client):
        # Requests to either the start page of a response or any of its question pages
        # will redirect to the results page with 'already applied' a flash message.
        # Test this message is rendered when present.

        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        with self.client.session_transaction() as session:
            session['_flashes'] = [(u'error', u'already_applied')]

        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath('//h1')[0].text.strip() == "Your application for ‘I need a thing to do a thing’"
        assert doc.xpath('//p[contains(@class, "banner-message")]')[0].text.strip() == \
            "You’ve already applied so you can’t apply again."

    def test_evaluation_methods_load_default_value(self, data_api_client):
        no_extra_eval_brief = self.brief.copy()
        no_extra_eval_brief['briefs'].pop('evaluationType')

        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = no_extra_eval_brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//li[contains(normalize-space(text()), "a work history")]')) == 1

    def test_evaluation_methods_shown_with_a_or_an(self, data_api_client):
        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//li[contains(normalize-space(text()), "a work history")]')) == 1
        assert len(doc.xpath('//li[contains(normalize-space(text()), "an interview")]')) == 1


@mock.patch("app.main.views.briefs.data_api_client")
class TestResponseResultPageLegacyFlow(ResponseResultPageBothFlows):

    def setup_method(self, method):
        super(TestResponseResultPageLegacyFlow, self).setup_method(method)
        self.brief_responses = {
            "briefResponses": [
                {"essentialRequirements": [True, True, True]}
            ]
        }

    def test_view_response_result_if_no_response_submitted_will_404(self, data_api_client):
        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = {"briefResponses": []}

        res = self.client.get('/suppliers/opportunities/1234/responses/result')
        assert res.status_code == 404

    @mock.patch("app.main.views.briefs.is_supplier_eligible_for_brief")
    @mock.patch("app.main.views.briefs._render_not_eligible_for_brief_error_page", autospec=True)
    def test_will_show_not_eligible_response_if_supplier_is_not_eligible_for_brief(
        self, _render_not_eligible_for_brief_error_page, is_supplier_eligible_for_brief, data_api_client
    ):
        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        is_supplier_eligible_for_brief.return_value = False
        _render_not_eligible_for_brief_error_page.return_value = 'dummy response', 403

        res = self.client.get('/suppliers/opportunities/1234/responses/result')
        assert res.status_code == 403
        _render_not_eligible_for_brief_error_page.assert_called_once_with(self.brief['briefs'])

    def test_view_response_result_page_escapes_essential_and_nice_to_have_requirements(self, data_api_client):
        self.brief['briefs']['essentialRequirements'] = [
            '<h1>Essential one with xss</h1>',
            '**Essential two with markdown**'
        ]
        self.brief['briefs']['niceToHaveRequirements'] = [
            '<h1>n2h one with xss</h1>',
            '**n2h two with markdown**'
        ]
        self.brief_responses['briefResponses'][0]['essentialRequirements'] = [True, True]
        self.brief_responses['briefResponses'][0]['niceToHaveRequirements'] = [True, False]

        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses

        res = self.client.get('/suppliers/opportunities/1234/responses/result')
        data = res.get_data(as_text=True)
        doc = html.fromstring(data)

        assert "&lt;h1&gt;Essential one with xss&lt;/h1&gt;" in data
        assert "&lt;h1&gt;n2h one with xss&lt;/h1&gt;" in data
        assert len(doc.xpath('//h1')) == 1

        assert "**Essential two with markdown**" in data
        assert "<strong>Essential two with markdown</strong>" not in data
        assert "**n2h two with markdown**" in data
        assert "<strong>n2h two with markdown</strong>" not in data

    def test_view_response_result_submitted_ok_if_live_or_closed(self, data_api_client):
        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.find_brief_responses.return_value = self.brief_responses
        brief_copy = self.brief.copy()

        for status in ('live', 'closed'):
            brief_copy['briefs']['status'] = status
            data_api_client.get_brief.return_value = brief_copy

            res = self.client.get('/suppliers/opportunities/1234/responses/result')

            assert res.status_code == 200
            doc = html.fromstring(res.get_data(as_text=True))
            assert doc.xpath('//p[contains(@class, "banner-message")]')[0].text.strip() == \
                "Your application has been submitted."

    def test_view_response_result_submitted_unsuccessful(self, data_api_client):
        self.brief_responses['briefResponses'][0]['essentialRequirements'][1] = False
        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath('//h1')[0].text.strip() == "Your application for ‘I need a thing to do a thing’"
        assert doc.xpath('//p[contains(@class, "banner-message")]')[0].text.strip() == \
            "You don’t meet all the essential requirements."

    def test_correct_already_applied_flash_message_appears_in_result_page_if_no_essential_requirements(self, data_api_client):  # noqa
        # Requests to either the start page of a response or any of its question pages
        # will redirect to the results page with 'already applied' a flash message.
        # Test this message is rendered when present.

        self.brief_responses['briefResponses'][0]['essentialRequirements'][1] = False

        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        with self.client.session_transaction() as session:
            session['_flashes'] = [(u'error', u'already_applied')]

        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath('//h1')[0].text.strip() == "Your application for ‘I need a thing to do a thing’"
        assert doc.xpath('//p[contains(@class, "banner-message")]')[0].text.strip() == \
            "You already applied but you didn’t meet the essential requirements."

    def test_essential_skills_shown_with_response(self, data_api_client):
        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))

        requirements_data = self._get_data_from_table(doc, "Your essential skills and experience")
        assert requirements_data.exists()
        assert requirements_data.row(0).cell(1) == "Yes"
        assert requirements_data.row(1).cell(1) == "Yes"
        assert requirements_data.row(2).cell(1) == "Yes"

    def test_nice_to_haves_shown_with_response_when_they_exist(self, data_api_client):
        brief_with_nice_to_haves = self.brief.copy()
        brief_with_nice_to_haves['briefs']['niceToHaveRequirements'] = ['Nice one', 'Top one', 'Get sorted']
        self.brief_responses['briefResponses'][0]['niceToHaveRequirements'] = [False, True, False]

        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = brief_with_nice_to_haves
        data_api_client.find_brief_responses.return_value = self.brief_responses
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))

        requirements_data = self._get_data_from_table(doc, "Your nice-to-have skills and experience")
        assert requirements_data.exists()
        assert requirements_data.row(0).cell(1) == "No"
        assert requirements_data.row(1).cell(1) == "Yes"
        assert requirements_data.row(2).cell(1) == "No"

    def test_supplier_details_shown(self, data_api_client):
        self.brief_responses['briefResponses'][0]['dayRate'] = "300"
        self.brief_responses['briefResponses'][0]['availability'] = "02/02/2017"
        self.brief_responses['briefResponses'][0]['respondToEmailAddress'] = "contact@big.com"

        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))

        requirements_data = self._get_data_from_table(doc, "Your details")
        assert requirements_data.exists()
        assert requirements_data.row(0).cell(0) == "Day rate"
        assert requirements_data.row(0).cell(1) == "£300"
        assert requirements_data.row(1).cell(0) == "Date the specialist can start work"
        assert requirements_data.row(1).cell(1) == "02/02/2017"
        assert requirements_data.row(2).cell(0) == "Email address"
        assert requirements_data.row(2).cell(1) == "contact@big.com"

    def test_nice_to_haves_heading_not_shown_when_there_are_none(self, data_api_client):
        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(
            doc.xpath('//h2[contains(normalize-space(text()), "Your nice-to-have skills and experience")]')
        ) == 0

    def test_budget_message_shown_if_budget_is_set_for_specialists(self, data_api_client):
        brief_with_budget_range = self.brief.copy()
        brief_with_budget_range['briefs']['budgetRange'] = 'Up to £200 per day'

        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = brief_with_budget_range
        data_api_client.find_brief_responses.return_value = self.brief_responses
        res = self.client.get('/suppliers/opportunities/1234/responses/result')
        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//li[contains(normalize-space(text()), "your day rate exceeds their budget")]')) == 1

    def test_budget_message_not_shown_if_budget_is_not_set_for_specialists(self, data_api_client):
        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//li[contains(normalize-space(text()), "your day rate exceeds their budget")]')) == 0


@mock.patch("app.main.views.briefs.data_api_client")
class TestResponseResultPage(ResponseResultPageBothFlows, BriefResponseTestHelpers):

    def setup_method(self, method):
        super(TestResponseResultPage, self).setup_method(method)
        self.brief['briefs']['niceToHaveRequirements'] = []
        self.brief['briefs']['dayRate'] = '300'
        self.brief_responses = {
            'briefResponses': [
                {
                    'essentialRequirementsMet': True,
                    'essentialRequirements': [
                        {'evidence': 'Did a thing'},
                        {'evidence': 'Produced a thing'},
                        {'evidence': 'Did a thing'}
                    ]
                }
            ]
        }

    def test_view_response_result_not_submitted_redirect_to_start_page(self, data_api_client):
        # the new flow has a different start page and the redirection logic uses the feature flag
        self.brief['briefs']['publishedAt'] = '2016-12-25T12:00:00.000000Z'
        self.app.config['FEATURE_FLAGS_NEW_SUPPLIER_FLOW'] = '2016-11-25'

        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = {"briefResponses": []}
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/opportunities/1234/responses/start'

    @mock.patch("app.main.views.briefs.is_supplier_eligible_for_brief")
    @mock.patch("app.main.views.briefs._render_not_eligible_for_brief_error_page", autospec=True)
    def test_will_show_not_eligible_response_if_supplier_is_not_eligible_for_brief(
        self, _render_not_eligible_for_brief_error_page, is_supplier_eligible_for_brief, data_api_client
    ):
        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        is_supplier_eligible_for_brief.return_value = False
        _render_not_eligible_for_brief_error_page.return_value = 'dummy response', 403

        res = self.client.get('/suppliers/opportunities/1234/responses/result')
        assert res.status_code == 403
        _render_not_eligible_for_brief_error_page.assert_called_once_with(self.brief['briefs'])

    def test_view_response_result_page_escapes_essential_and_nice_to_have_requirements(self, data_api_client):
        self.brief['briefs']['essentialRequirements'] = [
            '<h1>Essential one with xss</h1>',
            '**Essential two with markdown**'
        ]
        self.brief['briefs']['niceToHaveRequirements'] = [
            '<h1>n2h one with xss</h1>',
            '**n2h two with markdown**'
        ]
        self.brief_responses['briefResponses'][0]['niceToHaveRequirements'] = [
            {
                'yesNo': True,
                'evidence': 'Did a thing'
            },
            {
                'yesNo': False
            }
        ]

        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses

        res = self.client.get('/suppliers/opportunities/1234/responses/result')
        data = res.get_data(as_text=True)
        doc = html.fromstring(data)

        assert "&lt;h1&gt;Essential one with xss&lt;/h1&gt;" in data
        assert "&lt;h1&gt;n2h one with xss&lt;/h1&gt;" in data
        assert len(doc.xpath('//h1')) == 1

        assert "**Essential two with markdown**" in data
        assert "<strong>Essential two with markdown</strong>" not in data
        assert "**n2h two with markdown**" in data
        assert "<strong>n2h two with markdown</strong>" not in data

    def test_view_response_result_submitted_ok_if_status_is_live_or_closed(self, data_api_client):
        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        brief_copy = self.brief.copy()

        for status in ('live', 'closed'):
            brief_copy['briefs']['status'] = status
            res = self.client.get('/suppliers/opportunities/1234/responses/result')

            assert res.status_code == 200
            doc = html.fromstring(res.get_data(as_text=True))
            assert doc.xpath('//p[contains(@class, "banner-message")]')[0].text.strip() == \
                "Your application has been submitted."

    def test_essential_skills_shown_with_response(self, data_api_client):
        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))

        requirements_data = self._get_data_from_table(doc, "Your essential skills and experience")
        assert requirements_data.exists()
        assert requirements_data.row(0).cell(0) == "Must one"
        assert requirements_data.row(0).cell(1) == "Did a thing"
        assert requirements_data.row(1).cell(0) == "Must two"
        assert requirements_data.row(1).cell(1) == "Produced a thing"
        assert requirements_data.row(2).cell(0) == "Must three"
        assert requirements_data.row(2).cell(1) == "Did a thing"

    def test_nice_to_haves_shown_with_response_when_they_exist(self, data_api_client):
        brief_with_nice_to_haves = self.brief.copy()
        brief_with_nice_to_haves['briefs']['niceToHaveRequirements'] = ['Nice one', 'Top one', 'Get sorted']
        self.brief_responses['briefResponses'][0]['niceToHaveRequirements'] = [
            {
                'yesNo': True,
                'evidence': 'Did a thing'
            },
            {
                'yesNo': False
            },
            {
                'yesNo': False
            }
        ]

        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = brief_with_nice_to_haves
        data_api_client.find_brief_responses.return_value = self.brief_responses
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))

        requirements_data = self._get_data_from_table(doc, "Your nice-to-have skills and experience")
        assert requirements_data.exists()
        assert requirements_data.row(0).cell(0) == "Nice one"
        assert requirements_data.row(0).cell(1) == "Did a thing"
        assert requirements_data.row(1).cell(0) == "Top one"
        assert requirements_data.row(1).cell(1) == ""
        assert requirements_data.row(2).cell(0) == "Get sorted"
        assert requirements_data.row(2).cell(1) == ""

    def test_nice_to_haves_heading_not_shown_when_there_are_none(self, data_api_client):
        self.brief["briefs"]["niceToHaveRequirements"] = []

        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(
            doc.xpath('//h2[contains(normalize-space(text()), "Your nice-to-have skills and experience")]')
        ) == 0

    def test_requirement_evidence_heading_shown_for_essential_requirements(self, data_api_client):
        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))

        # Checks if column headings are visible and contain the correct text
        assert len(doc.xpath(
            ''.join([
                '//h2[contains(normalize-space(text()), "Your essential skills and experience")]',
                '/following-sibling::table[1]/thead[@class="summary-item-field-headings-visible"]',
                '/tr/th[contains(normalize-space(text()), "Requirement")]'  # noqa
            ])
        )) == 1
        assert len(doc.xpath(
            ''.join([
                '//h2[contains(normalize-space(text()), "Your essential skills and experience")]',
                '/following-sibling::table[1]/thead[@class="summary-item-field-headings-visible"]',
                '/tr/th[contains(normalize-space(text()), "Evidence")]'  # noqa
            ])
        )) == 1

    def test_supplier_details_shown(self, data_api_client):
        self.brief_responses['briefResponses'][0]['dayRate'] = "300"
        self.brief_responses['briefResponses'][0]['availability'] = "02/02/2017"
        self.brief_responses['briefResponses'][0]['respondToEmailAddress'] = "contact@big.com"

        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.find_brief_responses.return_value = self.brief_responses
        res = self.client.get('/suppliers/opportunities/1234/responses/result')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))

        requirements_data = self._get_data_from_table(doc, "Your details")
        assert requirements_data.exists()
        assert requirements_data.row(0).cell(0) == "Day rate"
        assert requirements_data.row(0).cell(1) == "£300"
        assert requirements_data.row(1).cell(0) == "Earliest start date"
        assert requirements_data.row(1).cell(1) == "02/02/2017"
        assert requirements_data.row(2).cell(0) == "Email address"
        assert requirements_data.row(2).cell(1) == "contact@big.com"

    def test_analytics_and_messages_applied_on_first_submission(self, data_api_client):
        """Go through submitting to edit_brief_response and the redirect to view_response_result. Assert messages."""
        self.set_framework_and_eligibility_for_api_client(data_api_client)
        data_api_client.get_brief.return_value = self.brief
        data_api_client.get_brief_response.return_value = self.brief_response()
        data_api_client.update_brief_response.return_value = {'success': True}
        data_api_client.find_brief_responses.side_effect = [
            {'briefResponses': []},
            {'briefResponses': [self.brief_response(data={'essentialRequirementsMet': True})['briefResponses']]}
        ]
        data_api_client.is_supplier_eligible_for_brief.return_value = True

        res = self.client.post(
            '/suppliers/opportunities/{brief_id}/responses/{brief_response_id}/{question_slug}'.format(
                brief_id=self.brief['briefs']['id'],
                brief_response_id=self.brief_response()['briefResponses']['id'],
                question_slug='respondToEmailAddress'
            ),
            data={},
            follow_redirects=True
        )
        assert res.status_code == 200
        data = res.get_data(as_text=True)

        # Assert the analytics exists
        assert (
            '<span data-analytics="trackPageView" '
            'data-url=/suppliers/opportunities/1234/responses/result?result=success></span>' in data
        )
        assert data.count('data-analytics') == 1
        # Assert we get the correct banner message (and only the correct one).
        assert 'Your application has been submitted.' in data

        assert 'You don’t meet all the essential requirements.' not in data
        assert 'You’ve already applied so you can’t apply again.' not in data
        assert 'You already applied but you didn’t meet the essential requirements.' not in data


@mock.patch("app.main.views.briefs.data_api_client", autospec=True)
@mock.patch("app.main.views.briefs.current_user")
@mock.patch("app.main.views.briefs.render_template", autospec=True)
class TestRenderNotEligibleForBriefErrorPage(BaseApplicationTest):
    def setup_method(self, method):
        super(TestRenderNotEligibleForBriefErrorPage, self).setup_method(method)
        self.brief = api_stubs.brief(status='live')["briefs"]

    def test_clarification_question_true(self, render_template, current_user, data_api_client):
        _render_not_eligible_for_brief_error_page(self.brief, True)

        render_template.assert_called_with(
            "briefs/not_is_supplier_eligible_for_brief_error.html",
            clarification_question=True,
            framework_name='Digital Outcomes and Specialists',
            lot=mock.ANY,
            reason=mock.ANY,
            data_reason_slug=mock.ANY,
        )

    def test_not_on_framework(self, render_template, current_user, data_api_client):
        current_user.supplier_id = 100
        data_api_client.find_services.return_value = {"services": []}

        _render_not_eligible_for_brief_error_page(self.brief)

        data_api_client.find_services.assert_called_once_with(
            supplier_id=100,
            framework='digital-outcomes-and-specialists',
            status='published'
        )
        render_template.assert_called_with(
            "briefs/not_is_supplier_eligible_for_brief_error.html",
            clarification_question=False,
            framework_name='Digital Outcomes and Specialists',
            lot='digital-specialists',
            reason='supplier-not-on-framework',
            data_reason_slug='supplier-not-on-digital-outcomes-and-specialists',
        )

    def test_not_on_lot(self, render_template, current_user, data_api_client):
        current_user.supplier_id = 100
        data_api_client.find_services.side_effect = lambda *args, **kwargs: (
            {"services": [{"something": "nonempty"}]} if kwargs.get("lot") is None else {"services": []}
        )

        _render_not_eligible_for_brief_error_page(self.brief)

        data_api_client.find_services.assert_has_calls(
            [
                mock.call(
                    supplier_id=100,
                    framework='digital-outcomes-and-specialists',
                    status='published'
                ),
                mock.call(
                    supplier_id=100,
                    framework='digital-outcomes-and-specialists',
                    status='published',
                    lot='digital-specialists'
                ),
            ],
            any_order=True
        )
        render_template.assert_called_with(
            "briefs/not_is_supplier_eligible_for_brief_error.html",
            clarification_question=False,
            framework_name='Digital Outcomes and Specialists',
            lot='digital-specialists',
            reason='supplier-not-on-lot',
            data_reason_slug='supplier-not-on-lot',
        )

    def test_not_on_role(self, render_template, current_user, data_api_client):
        current_user.supplier_id = 100
        data_api_client.find_services.return_value = {"services": [{"service": "data"}]}

        _render_not_eligible_for_brief_error_page(self.brief)

        data_api_client.find_services.assert_has_calls(
            [
                mock.call(
                    supplier_id=100,
                    framework='digital-outcomes-and-specialists',
                    status='published'
                ),
                mock.call(
                    supplier_id=100,
                    framework='digital-outcomes-and-specialists',
                    status='published',
                    lot='digital-specialists'
                ),
            ],
            any_order=True
        )
        render_template.assert_called_with(
            "briefs/not_is_supplier_eligible_for_brief_error.html",
            clarification_question=False,
            framework_name='Digital Outcomes and Specialists',
            lot='digital-specialists',
            reason='supplier-not-on-role',
            data_reason_slug='supplier-not-on-role',
        )
