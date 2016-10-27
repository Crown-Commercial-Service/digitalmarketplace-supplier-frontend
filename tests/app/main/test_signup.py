import mock
from ..helpers import BaseApplicationTest
from react.render_server import RenderedComponent


class TestStartPage(BaseApplicationTest):
    def setup(self):
        super(TestStartPage, self).setup()

    @mock.patch('app.main.views.signup.render_component')
    def test_start_page_renders(self, render_component):
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        res = self.client.get(self.expand_path(
            '/signup'
            )
        )

        assert res.status_code == 200
