import mock
from ..helpers import BaseApplicationTest


class TestStartPage(BaseApplicationTest):
    def setup(self):
        super(TestStartPage, self).setup()

    @mock.patch('app.main.views.signup.render_component')
    def test_start_page_renders(self, render_component):
        res = self.client.get(self.expand_path(
            '/signup'
            )
        )

        assert res.status_code == 200
