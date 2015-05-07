from app import create_app
from .helpers import BaseApplicationTest

from app.model import User
from nose.tools import assert_equal


class TestModel(BaseApplicationTest):

    def __init__(self):
        self.app = create_app('test')

    def test_user_from_json(self):
        result = User.from_json({
            'users': {
                'id': 987,
                'emailAddress': 'email_address',
                'name': 'name',
                'supplier': {
                    'supplierId': 1234,
                    'name': 'name'
                }
            }
        })
        assert_equal(result.id, 987)
        assert_equal(result.email_address, 'email_address')
