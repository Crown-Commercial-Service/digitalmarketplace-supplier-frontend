from nose.tools import assert_equal

from ..helpers import BaseApplicationTest


class TestFrameworksDashboard(BaseApplicationTest):
    def test_shows(self):
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            assert_equal(res.status_code, 200)
