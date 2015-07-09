import mock
from nose.tools import assert_equal, assert_in, assert_not_in
from tests.app.helpers import BaseApplicationTest


class TestListUsers(BaseApplicationTest):

    @mock.patch('app.main.views.users.data_api_client')
    def test_shows_services_list(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.find_users.return_value = {
                'users': [{
                    'id': 1,
                    'name': "Don Draper",
                    'emailAddress': "don@scdp.com",
                    'loggedInAt': "2015-05-06T11:57:28.008690Z",
                    'locked': False,
                    'supplier': {
                        'name': "Supplier Name",
                        'supplierId': 1234
                    }
                }]
            }

            res = self.client.get('/suppliers/users')
            assert_equal(res.status_code, 200)
            data_api_client.find_users.assert_called_once_with(
                supplier_id=1234)

            for string in [
                "Don Draper",
                "don@scdp.com",
                "Wednesday, 06 May 2015 at 11:57"
            ]:
                assert_in(
                    self.strip_all_whitespace(
                        # class names are slightly different for different cells >.<
                        '{}</td>'.format(string)
                    ),
                    self.strip_all_whitespace(res.get_data(as_text=True))
                )

            assert_not_in(
                self.strip_all_whitespace(
                    '{}</td>'.format("Locked")
                ),
                self.strip_all_whitespace(res.get_data(as_text=True))
            )
