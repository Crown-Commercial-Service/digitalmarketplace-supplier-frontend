from .helpers import BaseApplicationTest


class TestApplication(BaseApplicationTest):

    def test_404(self):
        response = self.client.get('/not-found')
        assert 404 == response.status_code

    def test_url_with_non_canonical_trailing_slash(self):
        response = self.client.get('/suppliers/')
        assert 301 == response.status_code
        assert "http://localhost/suppliers" == response.location
