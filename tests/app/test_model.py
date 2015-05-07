from app import create_app
from .flask_api_client.test_api_client import TestApiClient
from .helpers import BaseApplicationTest

from app.model import User
from nose.tools import assert_equal


class TestModel(BaseApplicationTest):

    def __init__(self):
        self.app = create_app('test')

    def test_user_from_json(self):
        result = User.from_json(TestApiClient.user())
        assert_equal(result.id, 987)
        assert_equal(result.email_address, 'email_address')
