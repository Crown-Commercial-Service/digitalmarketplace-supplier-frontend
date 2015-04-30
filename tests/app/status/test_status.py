import json
from ..helpers import BaseApplicationTest
from requests import Response

import mock
from nose.tools import assert_equal, assert_in


class TestStatus(BaseApplicationTest):
    def setup(self):
        super(TestStatus, self).setup()

        self._api_response = mock.patch(
            'app.status.utils.return_response_from_api_status_call',
        ).start()

    def teardown(self):
        self._api_response.stop()

    def test_status_ok(self):
        api_response = Response()
        api_response.status_code = 200
        api_response._content = json.dumps({
            'status': 'ok'
        }).encode('utf-8')
        self._api_response.return_value = api_response

        status_response = self.client.get('/_status')
        assert_equal(200, status_response.status_code)

        json_data = json.loads(status_response.get_data().decode('utf-8'))
        assert_equal(
            "ok", "{}".format(json_data['status']))
        assert_equal(
            "ok", "{}".format(json_data['api_status']['status']))

    def test_status_api_responses_return_500(self):
        api_response = Response()
        api_response.status_code = 500
        api_response._content = json.dumps({
            'status': 'error'
        }).encode('utf-8')
        self._api_response.return_value = api_response

        status_response = self.client.get('/_status')
        assert_equal(500, status_response.status_code)

        json_data = json.loads(status_response.get_data().decode('utf-8'))
        assert_equal(
            "error", "{}".format(json_data['status']))
        assert_equal(
            "error", "{}".format(json_data['api_status']['status']))
        assert_in(
            "Error connecting to", "{}".format(json_data['message']))

    def test_status_api_responses_are_none(self):
        self._api_response.return_value = None

        status_response = self.client.get('/_status')
        assert_equal(500, status_response.status_code)

        json_data = json.loads(status_response.get_data().decode('utf-8'))
        assert_equal(
            "error", "{}".format(json_data['status']))
        assert_equal(None, json_data['api_status'])
        assert_in("Error connecting to", "{}".format(json_data['message']))
