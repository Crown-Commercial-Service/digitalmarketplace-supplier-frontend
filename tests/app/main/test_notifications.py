from ..helpers import BaseApplicationTest
import mock


@mock.patch("app.main.views.suppliers.data_api_client")
class TestUserResearch(BaseApplicationTest):
    def setup_method(self, method):
        super(TestUserResearch, self).setup_method(method)

    def test_should_see_banner_if_not_subscribed(self, data_api_client):
        with self.app.test_client():
            self.login(supplier_organisation_size=None, user_researh_opted_in=False)
            res = self.client.get('/suppliers')
            assert res.status_code == 200
            assert 'Help us improve the Digital Marketplace' in res.get_data(as_text=True)
            assert 'Sign up to be a potential user research participant' in res.get_data(as_text=True)
            assert 'class="user-research-banner-close-btn"' in res.get_data(as_text=True)
            cookie_value = self.get_cookie_by_name(res, 'seen_user_research_message')
            assert cookie_value is None

    def test_should_not_see_banner_if_subscribed(self, data_api_client):
        with self.app.test_client():
            self.login(supplier_organisation_size=None, user_researh_opted_in=True)
            res = self.client.get('/suppliers')
            assert res.status_code == 200
            assert 'Help us improve the Digital Marketplace' not in res.get_data(as_text=True)
            assert 'Sign up to be a potential user research participant' not in res.get_data(as_text=True)
            assert 'class="user-research-banner-close-btn"' not in res.get_data(as_text=True)

    def test_should_see_subscribed_link_if_not_subscribed(self, data_api_client):
        with self.app.test_client():
            self.login(supplier_organisation_size=None, user_researh_opted_in=False)
            res = self.client.get('/suppliers')
            assert res.status_code == 200
            assert "href=\"/user/notifications/user-research\"" in res.get_data(as_text=True)
            assert "Join the user research mailing list" in res.get_data(as_text=True)
            assert "Unsubscribe from the user research mailing list" not in res.get_data(as_text=True)

    def test_should_see_unsubscribed_link_if_subscribed(self, data_api_client):
        with self.app.test_client():
            self.login(supplier_organisation_size=None, user_researh_opted_in=True)
            res = self.client.get('/suppliers')
            assert res.status_code == 200
            assert "href=\"/user/notifications/user-research\"" in res.get_data(as_text=True)
            assert "Join the user research mailing list" not in res.get_data(as_text=True)
            assert "Unsubscribe from the user research mailing list" in res.get_data(as_text=True)
