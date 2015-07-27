import mock
from nose.tools import assert_equal, assert_in, assert_not_in
from tests.app.helpers import BaseApplicationTest


def get_users(additional_users=None, index=None):

        users = [
            {
                'id': 123,
                'name': "User Name",
                'emailAddress': "email@email.com",
                'loggedInAt': "2015-05-06T11:57:28.008690Z",
                'locked': False,
                'active': True,
                'role': 'supplier',
                'supplier': {
                    'name': "Supplier Name",
                    'supplierId': 1234
                }
            },
            {
                'id': 1,
                'name': "Don Draper",
                'emailAddress': "don@scdp.com",
                'loggedInAt': "2015-05-06T11:57:28.008690Z",
                'locked': False,
                'active': True,
                'role': 'supplier',
                'supplier': {
                    'name': "Supplier Name",
                    'supplierId': 1234
                }
            },
            {
                'id': 2,
                'name': "Lane Pryce",
                'emailAddress': "lane@scdp.com",
                'loggedInAt': "2012-06-03T11:57:28.008690Z",
                'locked': False,
                'active': False,
                'role': 'supplier',
                'supplier': {
                    'name': "Supplier Name",
                    'supplierId': 1234
                }
            }
        ]

        if additional_users is not None and isinstance(additional_users, list):
            users += additional_users

        return {'users': users} if index is None else {'users': users[index]}


class TestListUsers(BaseApplicationTest):

    @mock.patch('app.main.helpers.helpers.data_api_client')
    def test_shows_user_list(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.find_users.return_value = get_users()

            res = self.client.get('/suppliers/users')
            assert_equal(res.status_code, 200)
            data_api_client.find_users.assert_called_once_with(supplier_id=1234)

            # strings we would expect to find in the output
            for string in [
                "User Name",
                "email@email.com",
                "Don Draper",
                "don@scdp.com",
                # deactivate button for Don
                "<form method=\"post\" action=\"/suppliers/users/1/deactivate\">"
            ]:
                assert_in(
                    self.strip_all_whitespace(
                        '{}'.format(string)
                    ),
                    self.strip_all_whitespace(res.get_data(as_text=True))
                )

            # strings we would hope not to find in the output
            for string in [
                "Lane Pryce",
                "lane@scdp.com",
                # deactivate button for logged-in user
                "<form method=\"post\" action=\"/suppliers/users/123/deactivate\">"
            ]:
                assert_not_in(
                    self.strip_all_whitespace(
                        '{}'.format(string)
                    ),
                    self.strip_all_whitespace(res.get_data(as_text=True))
                )


class TestPostUsers(BaseApplicationTest):

    def test_cannot_see_deactivate_url_unless_logged_in(self):
        res = self.client.post(
            '/suppliers/users/123/deactivate',
            follow_redirects=True
        )

        assert_equal(res.status_code, 200)
        assert_in(
            self.strip_all_whitespace('<title>Log in'),
            self.strip_all_whitespace(res.get_data(as_text=True))
        )

    def test_cannot_deactivate_self(self):
        with self.app.test_client():
            self.login()

            res = self.client.post('/suppliers/users/123/deactivate')
            assert_equal(res.status_code, 404)

    @mock.patch('app.main.helpers.helpers.data_api_client')
    def test_cannot_deactivate_nonexistent_id(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.find_users.return_value = get_users()

            res = self.client.post('/suppliers/users/1231231231231/deactivate')
            assert_equal(res.status_code, 404)

    @mock.patch('app.main.helpers.helpers.data_api_client')
    def test_cannot_deactivate_a_user_without_supplier_role(self, data_api_client):
        with self.app.test_client():
            self.login()

            additional_users = [
                {
                    'id': 3,
                    'name': "Herb Rennet",
                    'emailAddress': "herb@jaguar.co.uk",
                    'loggedInAt': "2012-05-27T11:57:28.008690Z",
                    'locked': False,
                    'active': True,
                    'role': 'buyer',
                }
            ]
            data_api_client.find_users.return_value = get_users(additional_users)
            data_api_client.get_user.return_value = get_users(additional_users, index=3)

            res = self.client.post('/suppliers/users/3/deactivate')
            assert_equal(res.status_code, 404)

    @mock.patch('app.main.helpers.helpers.data_api_client')
    def test_cannot_deactivate_another_suppliers_user(self, data_api_client):
        with self.app.test_client():
            self.login()

            additional_users = [
                {
                    'id': 3,
                    'name': "Herman Phillips",
                    'emailAddress': "herman@ppl.com",
                    'loggedInAt': "2008-10-26T11:57:28.008690Z",
                    'locked': False,
                    'active': True,
                    'role': 'supplier',
                    'supplier': {
                        'name': "Puttnam, Powell, and Lowe",
                        'supplierId': 9999
                    }
                }
            ]
            data_api_client.find_users.return_value = get_users(additional_users)
            data_api_client.get_user.return_value = get_users(additional_users, index=3)

            res = self.client.post('/suppliers/users/4/deactivate')
            assert_equal(res.status_code, 404)

    @mock.patch('app.main.helpers.helpers.data_api_client')
    def test_everything_works(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.find_users.return_value = get_users()
            data_api_client.get_user.return_value = get_users(index=1)
            data_api_client.update_user.return_value = True

            res = self.client.post(
                '/suppliers/users/1/deactivate', follow_redirects=True)
            assert_equal(res.status_code, 200)
            assert_in(
                self.strip_all_whitespace('Don Draper\'s account has been deactivated'),
                self.strip_all_whitespace(res.get_data(as_text=True))
            )
