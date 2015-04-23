from .helpers import BaseApplicationTest


class TestApplication(BaseApplicationTest):

    def test_404(self):
        response = self.client.get('/not-found')
        assert 404 == response.status_code
