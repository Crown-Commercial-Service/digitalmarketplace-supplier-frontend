from ..helpers import BaseApplicationTest
import mock


class TestUserResearch(BaseApplicationTest):
    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.suppliers.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_should_see_subscribed_link_if_not_subscribed(self):
        self.login(user_research_opted_in=False)
        res = self.client.get('/suppliers')
        assert res.status_code == 200
        assert "href=\"/user/notifications/user-research\"" in res.get_data(as_text=True)
        assert "Join the user research mailing list" in res.get_data(as_text=True)
        assert "Unsubscribe from the user research mailing list" not in res.get_data(as_text=True)

    def test_should_see_unsubscribed_link_if_subscribed(self):
        self.login(user_research_opted_in=True)
        res = self.client.get('/suppliers')
        assert res.status_code == 200
        assert "href=\"/user/notifications/user-research\"" in res.get_data(as_text=True)
        assert "Join the user research mailing list" not in res.get_data(as_text=True)
        assert "Unsubscribe from the user research mailing list" in res.get_data(as_text=True)
