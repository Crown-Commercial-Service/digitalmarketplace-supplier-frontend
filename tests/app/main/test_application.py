import mock
from nose.tools import assert_equal, assert_true
from ..helpers import BaseApplicationTest


class TestApplication(BaseApplicationTest):
    def setup(self):
        super(TestApplication, self).setup()
