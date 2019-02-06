import mock
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
        # inactive user
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

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.users.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_shows_user_list(self):
        self.login()

        self.data_api_client.find_users_iter.return_value = get_users()['users']

        res = self.client.get('/suppliers/users')
        assert res.status_code == 200
        self.data_api_client.find_users_iter.assert_called_once_with(supplier_id=1234)

        # strings we would expect to find in the output
        for string in [
            "User Name",
            "email@email.com",
            "Don Draper",
            "don@scdp.com",
            # deactivate button for Don
            "<form method=\"post\" action=\"/suppliers/users/1/deactivate\">"
        ]:
            assert self.strip_all_whitespace('{}'.format(string)) in \
                self.strip_all_whitespace(res.get_data(as_text=True))

        # strings we would hope not to find in the output
        for string in [
            "Lane Pryce",
            "lane@scdp.com",
            # deactivate button for logged-in user
            "<form method=\"post\" action=\"/suppliers/users/123/deactivate\">"
        ]:
            assert self.strip_all_whitespace('{}'.format(string)) not in \
                self.strip_all_whitespace(res.get_data(as_text=True))


class TestPostUsers(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.users.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_cannot_deactivate_user_unless_logged_in(self):
        res = self.client.post(
            '/suppliers/users/123/deactivate'
        )
        assert res.status_code == 302
        assert res.location == 'http://localhost/user/login'

    def test_cannot_deactivate_self(self):
        self.login()

        res = self.client.post('/suppliers/users/123/deactivate')
        assert res.status_code == 404

    def test_cannot_deactivate_nonexistent_id(self):
        self.login()

        self.data_api_client.get_user.return_value = None
        target_user_id = 1231231231231

        res = self.client.post(f'/suppliers/users/{target_user_id}/deactivate')

        assert self.data_api_client.get_user.call_args_list == [mock.call(user_id=target_user_id)]
        assert res.status_code == 404

    def test_cannot_deactivate_a_user_without_supplier_role(self):
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
        self.data_api_client.get_user.return_value = get_users(additional_users, index=3)

        res = self.client.post('/suppliers/users/3/deactivate')

        assert self.data_api_client.get_user.call_args_list == [mock.call(user_id=3)]
        assert res.status_code == 404

    def test_cannot_deactivate_another_suppliers_user(self):
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
        self.data_api_client.get_user.return_value = get_users(additional_users, index=3)

        res = self.client.post('/suppliers/users/4/deactivate')

        assert self.data_api_client.get_user.call_args_list == [mock.call(user_id=4)]
        assert res.status_code == 404

    def can_deactivate_a_user(self):
        self.login()

        self.data_api_client.get_user.return_value = get_users(index=1)
        self.data_api_client.update_user.return_value = True

        res = self.client.post(
            '/suppliers/users/1/deactivate', follow_redirects=True)

        assert self.data_api_client.get_user.call_args_list == [mock.call(user_id=1)]
        assert self.data_api_client.update_user.call_args_list == [
            mock.call(user_id=1, active=False, updater='email@email.com')
        ]
        assert res.status_code == 200
        assert self.strip_all_whitespace('Don Draper (don@scdp.com) has been removed as a contributor') in \
            self.strip_all_whitespace(res.get_data(as_text=True))
