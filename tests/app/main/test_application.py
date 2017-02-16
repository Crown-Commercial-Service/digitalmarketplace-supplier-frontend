import mock
from ..helpers import BaseApplicationTest


class TestApplication(BaseApplicationTest):

    def test_analytics_code_should_be_in_javascript(self):
        res = self.client.get('/suppliers/static/javascripts/application.js')
        assert res.status_code == 200
        assert 'analytics.trackPageview' in res.get_data(as_text=True)
