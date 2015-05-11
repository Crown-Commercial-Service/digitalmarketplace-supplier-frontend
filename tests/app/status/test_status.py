import json
from ..helpers import BaseApplicationTest

import mock
from nose.tools import assert_equal, assert_in


class TestStatus(BaseApplicationTest):

    @mock.patch('app.status.views.data_api_client')
    def test_status_ok(self, data_api_client):
        data_api_client.get_status.return_value = {
            "status": "ok"
        }

        status_response = self.client.get('/suppliers/_status')
        assert_equal(200, status_response.status_code)

        json_data = json.loads(status_response.get_data().decode('utf-8'))
        assert_equal(
            "ok", "{}".format(json_data['status']))
        assert_equal(
            "ok", "{}".format(json_data['api_status']['status']))

    @mock.patch('app.status.views.data_api_client')
    def test_status_error(self, data_api_client):

        data_api_client.get_status.return_value = {
            'status': 'error',
            'app_version': None,
            'message': 'Cannot connect to (Data) API'
        }

        status_response = self.client.get('/suppliers/_status')
        assert_equal(500, status_response.status_code)

        json_data = json.loads(status_response.get_data().decode('utf-8'))
        assert_equal(
            "error", "{}".format(json_data['status']))
        assert_equal(
            "error", "{}".format(json_data['api_status']['status']))
        assert_in(
            "Error connecting to", "{}".format(json_data['message']))
