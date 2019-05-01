# -*- coding: utf-8 -*-
import re

from tests.app.helpers import BaseApplicationTest


def load_prometheus_metrics(response_bytes):
    return dict(re.findall(rb"(\w+{.+?}) (\d+)", response_bytes))


class TestMetricsPage(BaseApplicationTest):

    def test_metrics_page_accessible(self):
        metrics_response = self.client.get('/suppliers/_metrics')

        assert metrics_response.status_code == 200

    def test_metrics_page_contents(self):
        metrics_response = self.client.get('/suppliers/_metrics')
        results = load_prometheus_metrics(metrics_response.data)
        assert (
            b'http_server_requests_total{code="200",host="localhost",method="GET",path="/suppliers/_metrics"}'
        ) in results


class TestMetricsPageRegistersPageViews(BaseApplicationTest):

    def test_metrics_page_registers_page_views(self):
        expected_metric_name = (
            b'http_server_requests_total{code="200",host="localhost",method="GET",path="/suppliers/create/start"}'
        )

        res = self.client.get('/suppliers/create/start')
        assert res.status_code == 200

        metrics_response = self.client.get('/suppliers/_metrics')
        results = load_prometheus_metrics(metrics_response.data)
        assert expected_metric_name in results

    def test_metrics_page_registers_multiple_page_views(self):
        expected_metric_name = (
            b'http_server_requests_total{code="200",host="localhost",method="GET",path="/suppliers/create/start"}'
        )

        initial_metrics_response = self.client.get('/suppliers/_metrics')
        initial_results = load_prometheus_metrics(initial_metrics_response.data)
        initial_metric_value = int(initial_results.get(expected_metric_name, 0))

        for _ in range(3):
            res = self.client.get('/suppliers/create/start')
            assert res.status_code == 200

        metrics_response = self.client.get('/suppliers/_metrics')
        results = load_prometheus_metrics(metrics_response.data)
        metric_value = int(results.get(expected_metric_name, 0))

        assert expected_metric_name in results
        assert metric_value - initial_metric_value == 3
