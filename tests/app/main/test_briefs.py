import mock
from dmapiclient import HTTPError
from dmutils.email import MandrillException

from ..helpers import BaseApplicationTest, FakeMail


@mock.patch('app.main.views.briefs.data_api_client', autospec=True)
class TestBriefClarificationQuestions(BaseApplicationTest):
    def test_clarification_question_form_requires_login(self, data_api_client):
        res = self.client.get('/suppliers/opportunities/1/ask-a-question')
        assert res.status_code == 302
        assert '/login' in res.headers['Location']

    def test_clarification_question_form(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = {'briefs': {'status': 'live'}}

        res = self.client.get('/suppliers/opportunities/1/ask-a-question')
        assert res.status_code == 200

    def test_clarification_question_form_requires_existing_brief_id(self, data_api_client):
        self.login()
        data_api_client.get_brief.side_effect = HTTPError(mock.Mock(status_code=404))

        res = self.client.get('/suppliers/opportunities/1/ask-a-question')
        assert res.status_code == 404

    def test_clarification_question_form_requires_live_brief(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = {'briefs': {'status': 'expired'}}

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
        data_api_client.get_brief.return_value = {'briefs': {
            'status': 'live',
            'title': 'Important Opportunity',
            'users': [
                {'emailAddress': 'a@user.dmdev', 'active': True},
                {'emailAddress': 'b@user.dmdev', 'active': False},
            ],
            'frameworkName': 'Brief Framework Name',
        }}

        res = self.client.post('/suppliers/opportunities/1/ask-a-question', data={
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
                to_email_addresses=['a@user.dmdev'],
                subject='Important Opportunity clarification question'),
            mock.call(
                from_name='Digital Marketplace Admin',
                tags=['brief-clarification-question-confirmation'],
                email_body=FakeMail("important question"),
                from_email='do-not-reply@digitalmarketplace.service.gov.uk',
                api_key='MANDRILL',
                to_email_addresses=['email@email.com'],
                subject='Your Important Opportunity clarification question')
        ])

    @mock.patch('app.main.helpers.briefs.send_email')
    def test_submit_clarification_question_fails_on_mandrill_error(self, send_email, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = {'briefs': {
            'id': 1,
            'status': 'live',
            'title': 'Important Opportunity',
            'users': [
                {'emailAddress': 'a@user.dmdev', 'active': True},
                {'emailAddress': 'b@user.dmdev', 'active': False},
            ],
            'frameworkName': 'Brief Framework Name',
        }}

        send_email.side_effect = MandrillException

        res = self.client.post('/suppliers/opportunities/1/ask-a-question', data={
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
        data_api_client.get_brief.return_value = {'briefs': {'status': 'expired'}}

        res = self.client.post('/suppliers/opportunities/1/ask-a-question')
        assert res.status_code == 404

    def test_submit_empty_clarification_question_returns_validation_error(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = {'briefs': {'status': 'live'}}

        res = self.client.post('/suppliers/opportunities/1/ask-a-question', data={
            'clarification-question': "",
        })
        assert res.status_code == 400
        assert "cannot be empty" in res.get_data(as_text=True)

    def test_submit_empty_clarification_question_has_max_length_limit(self, data_api_client):
        self.login()
        data_api_client.get_brief.return_value = {'briefs': {'status': 'live'}}

        res = self.client.post('/suppliers/opportunities/1/ask-a-question', data={
            'clarification-question': "a" * 5100,
        })
        assert res.status_code == 400
        assert "cannot be longer than" in res.get_data(as_text=True)
