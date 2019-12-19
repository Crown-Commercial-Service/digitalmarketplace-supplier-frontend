import pytest
from ..helpers import BaseApplicationTest


class TestApplication(BaseApplicationTest):
    def setup_method(self, method):
        super(TestApplication, self).setup_method(method)

    # Analytics temporarily disabled
    @pytest.mark.skip
    def test_analytics_code_should_be_in_javascript(self):
        res = self.client.get('/suppliers/static/javascripts/application.js')
        assert res.status_code == 200
        assert 'analytics.trackPageview' in res.get_data(as_text=True)
