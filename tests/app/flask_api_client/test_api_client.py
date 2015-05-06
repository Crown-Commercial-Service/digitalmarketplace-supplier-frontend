from app.flask_api_client.api_client import ApiClient
from flask import json
from nose.tools import assert_equal
from datetime import datetime

import requests
import requests_mock
from app import create_app


class TestApiClient():
    api_client = None

    def __init__(self):
        self.app = create_app('test')
        self.api_client = ApiClient(self.app)
        self.session = requests.Session()
        self.adapter = requests_mock.Adapter()
        self.session.mount('mock', self.adapter)

    def test_auth_is_called_with_correct_params(self):
        with requests_mock.mock() as m:
            m.post(
                'http://localhost/users/auth',
                text=json.dumps(self.user()),
                status_code=200)

            user = self.api_client.users_auth(
                'email_address',
                'password'
            )
            assert_equal(
                m.last_request.json(),
                {'authUsers':
                    {'emailAddress': 'email_address', 'password': 'password'}
                 }
            )
            assert_equal(user.id, 987)
            assert_equal(user.email_address, 'email_address')
            assert_equal(user.supplier_id, 1234)
            assert_equal(user.supplier_name, 'name')

    def test_auth_returns_none_on_404(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                m.post(
                    'http://localhost/users/auth',
                    text=json.dumps({'authorization': False}),
                    status_code=404)

                user = self.api_client.users_auth(
                    'email_address',
                    'password'
                )
                assert_equal(user, None)

    def test_auth_returns_none_on_403(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                m.post(
                    'http://localhost/users/auth',
                    text=json.dumps({'authorization': False}),
                    status_code=403)

                user = self.api_client.users_auth(
                    'email_address',
                    'password'
                )
                assert_equal(user, None)

    def test_auth_returns_none_on_a_non_supplier_user(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                user_with_no_supplier = self.user()
                del user_with_no_supplier["users"]["supplier"]

                m.post(
                    'http://localhost/users/auth',
                    text=json.dumps(user_with_no_supplier),
                    status_code=200)

                user = self.api_client.users_auth(
                    'email_address',
                    'password'
                )
                assert_equal(user, None)

    def test_auth_returns_none_on_400(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                m.post(
                    'http://localhost/users/auth',
                    text=json.dumps({'authorization': False}),
                    status_code=400)

                user = self.api_client.users_auth(
                    'email_address',
                    'password'
                )
                assert_equal(user, None)

    def test_auth_returns_none_on_500(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                m.post(
                    'http://localhost/users/auth',
                    text=json.dumps({'authorization': False}),
                    status_code=500)

                user = self.api_client.users_auth(
                    'email_address',
                    'password'
                )
                assert_equal(user, None)

    def test_get_user_by_id_calls_api_with_correct_param(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                m.get(
                    'http://localhost/users/987',
                    text=json.dumps(self.user()),
                    status_code=200
                )
                user = self.api_client.user_by_id(987)
                assert_equal(m.last_request.path, "/users/987")
                assert_equal(user.id, 987)
                assert_equal(user.email_address, 'email_address')
                assert_equal(user.supplier_id, 1234)
                assert_equal(user.supplier_name, 'name')

    def test_get_user_by_email_calls_api_with_correct_param(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                m.get(
                    'http://localhost/users?email=email_address',
                    text=json.dumps(self.user()),
                    status_code=200
                )
                user = self.api_client.user_by_email('email_address')
                assert_equal(m.last_request.path, "/users")
                assert_equal(m.last_request.query, "email=email_address")
                assert_equal(user.id, 987)
                assert_equal(user.email_address, 'email_address')
                assert_equal(user.supplier_id, 1234)
                assert_equal(user.supplier_name, 'name')

    def test_update_password_calls_api_with_correct_payload(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                m.post(
                    'http://localhost/users/987',
                    status_code=200
                )
                result = self.api_client.user_update_password(987, 'new_pass')
                assert_equal(result, True)
                assert_equal(
                    m.last_request.json(),
                    {'users': {'password': 'new_pass'}}
                )

    def test_update_password_returns_true_for_200(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                m.post(
                    'http://localhost/users/987',
                    status_code=200
                )
                result = self.api_client.user_update_password(987, 'new_pass')
                assert_equal(result, True)

    def test_update_password_returns_false_for_404(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                m.post(
                    'http://localhost/users/987',
                    status_code=404
                )
                result = self.api_client.user_update_password(987, 'new_pass')
                assert_equal(result, False)

    def test_services_by_supplier_id_calls_api_with_correct_params(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                m.get(
                    'http://localhost/services?supplier_id=1234',
                    text=json.dumps(self.user()),
                    status_code=200
                )
                services = self.api_client.services_by_supplier_id(1234)
                assert_equal(m.last_request.path, "/services")
                assert_equal(m.last_request.query, "supplier_id=1234")

    def test_services_by_supplier_id_returns_empty_on_error(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                m.get(
                    'http://localhost/services?supplier_id=1234',
                    json={"error": "supplier_id 1234 not found"},
                    status_code=404
                )
                services = self.api_client.services_by_supplier_id(1234)
                assert_equal(m.last_request.path, "/services")
                assert_equal(m.last_request.query, "supplier_id=1234")
                assert_equal(services, {"services": {}})

    @staticmethod
    def user():
        timestamp = datetime.now()

        return {'users': {
            'id': 987,
            'emailAddress': 'email_address',
            'name': 'name',
            'role': 'role',
            'active': 'active',
            'locked': False,
            'createdAt': timestamp,
            'updatedAt': timestamp,
            'passwordChangedAt': timestamp,
            'supplier': {
                'supplierId': 1234,
                'name': 'name'
            }
        }}
