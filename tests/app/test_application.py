from .helpers import BaseApplicationTest


class TestApplication(BaseApplicationTest):
    def test_index(self):
        response = self.client.get('/')
        assert 200 == response.status_code

    def test_404(self):
        response = self.client.get('/not-found')
        assert 404 == response.status_code
