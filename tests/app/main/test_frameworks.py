# -*- coding: utf-8 -*-
try:
    from StringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO
from nose.tools import assert_equal, assert_true, assert_in, assert_not_in
import mock
from flask import session
from lxml import html
from dmapiclient import APIError
from dmapiclient.audit import AuditTypes
from dmutils.email import MandrillException
from dmutils.s3 import S3ResponseError

from ..helpers import BaseApplicationTest, FULL_G7_SUBMISSION, FakeMail


def _return_fake_s3_file_dict(directory, filename, ext, last_modified=None, size=None):

    return {
        'path': '{}{}.{}'.format(directory, filename, ext),
        'filename': filename,
        'ext': ext,
        'last_modified': last_modified or '2015-08-17T14:00:00.000Z',
        'size': size if size is not None else 1
    }


def get_g_cloud_8():
    return BaseApplicationTest.framework(
        status='standstill',
        name='G-Cloud 8',
        slug='g-cloud-8',
        framework_agreement_version='v1.0'
    )


@mock.patch('dmutils.s3.S3')
@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
class TestFrameworksDashboard(BaseApplicationTest):
    @staticmethod
    def _assert_last_updated_times(doc, last_updateds):

        for last_updated in last_updateds:
            hint = doc.xpath(
                '//li[contains(@class, "browse-list-item")]'
                '//span[contains(text(), "{}")]'
                '/../..'
                '/div[@class="hint"]'.format(last_updated['text'])
            )

            if last_updated.get('time'):
                time = hint[0].find('./time')
                assert_equal(
                    BaseApplicationTest.strip_all_whitespace(last_updated['time']['text']),
                    BaseApplicationTest.strip_all_whitespace(time.text))
                assert_equal(
                    BaseApplicationTest.strip_all_whitespace(last_updated['time']['datetime']),
                    BaseApplicationTest.strip_all_whitespace(time.get('datetime')))

            else:
                assert_equal(len(hint), 0)

    def test_framework_dashboard_shows_for_pending_if_declaration_exists(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(status='pending')
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        assert_equal(res.status_code, 200)
        doc = html.fromstring(res.get_data(as_text=True))
        assert_equal(
            len(doc.xpath('//h1[contains(text(), "Your G-Cloud 7 application")]')), 1)

    def test_framework_dashboard_shows_for_live_if_declaration_exists(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(status='live')
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        assert_equal(res.status_code, 200)
        doc = html.fromstring(res.get_data(as_text=True))
        assert_equal(
            len(doc.xpath('//h1[contains(text(), "Your G-Cloud 7 documents")]')), 1)

    def test_does_not_show_for_live_if_no_declaration(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(status='live')
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(declaration=None)
        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        assert_equal(res.status_code, 404)

    @mock.patch('app.main.frameworks.send_email')
    def test_interest_registered_in_framework_on_post(self, send_email, data_api_client, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
            res = self.client.post("/suppliers/frameworks/digital-outcomes-and-specialists")

            assert_equal(res.status_code, 200)
            data_api_client.register_framework_interest.assert_called_once_with(
                1234,
                "digital-outcomes-and-specialists",
                "email@email.com"
            )

    @mock.patch('app.main.frameworks.send_email')
    def test_email_sent_when_interest_registered_in_framework(self, send_email, data_api_client, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
            data_api_client.find_users.return_value = {'users': [
                {'emailAddress': 'email1', 'active': True},
                {'emailAddress': 'email2', 'active': True},
                {'emailAddress': 'email3', 'active': False}
            ]}
            res = self.client.post("/suppliers/frameworks/digital-outcomes-and-specialists")

            assert_equal(res.status_code, 200)
            send_email.assert_called_once_with(
                ['email1', 'email2'],
                mock.ANY,
                'MANDRILL',
                'You have started your G-Cloud 7 application',
                'do-not-reply@digitalmarketplace.service.gov.uk',
                'Digital Marketplace Admin',
                ['digital-outcomes-and-specialists-application-started']
            )

    def test_interest_not_registered_in_framework_on_get(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='pending')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
            res = self.client.get("/suppliers/frameworks/digital-outcomes-and-specialists")

            assert_equal(res.status_code, 200)
            assert not data_api_client.register_framework_interest.called

    def test_interest_set_but_no_declaration(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='pending')
            data_api_client.get_framework_interest.return_value = {'frameworks': ['g-cloud-7']}
            data_api_client.find_draft_services.return_value = {
                "services": [
                    {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
                ]
            }
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(declaration=None)

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            assert_equal(res.status_code, 200)

    def test_shows_gcloud_7_closed_message_if_pending_and_no_application_done(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='pending')
            data_api_client.get_framework_interest.return_value = {'frameworks': ['g-cloud-7']}
            data_api_client.find_draft_services.return_value = {
                "services": [
                    {'serviceName': 'A service', 'status': 'not-submitted'}
                ]
            }
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            doc = html.fromstring(res.get_data(as_text=True))

            heading = doc.xpath('//div[@class="summary-item-lede"]//h2[@class="summary-item-heading"]')
            assert_true(len(heading) > 0)
            assert_in(u"G-Cloud 7 is closed for applications",
                      heading[0].xpath('text()')[0])
            assert_in(u"You didn't submit an application.",
                      heading[0].xpath('../p[1]/text()')[0])

    def test_shows_gcloud_7_closed_message_if_pending_and_application(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='pending')
            data_api_client.get_framework_interest.return_value = {'frameworks': ['g-cloud-7']}
            data_api_client.find_draft_services.return_value = {
                "services": [
                    {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
                ]
            }
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            doc = html.fromstring(res.get_data(as_text=True))
            heading = doc.xpath('//div[@class="summary-item-lede"]//h2[@class="summary-item-heading"]')
            assert_true(len(heading) > 0)
            assert_in(u"G-Cloud 7 is closed for applications",
                      heading[0].xpath('text()')[0])
            lede = doc.xpath('//div[@class="summary-item-lede"]')
            assert_in(u"You made your supplier declaration and submitted 1 service for consideration.",
                      lede[0].xpath('./p[1]/text()')[0])
            assert_in(u"We’ll let you know the result of your application by ",  # noqa
                      lede[0].xpath('./p[2]/text()')[0])  # noqa

    def test_declaration_status_when_complete(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            doc = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                len(doc.xpath(u'//p/strong[contains(text(), "You’ve made the supplier declaration")]')),
                1)

    def test_declaration_status_when_started(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

            submission = FULL_G7_SUBMISSION.copy()
            # User has not yet submitted page 3 of the declaration
            del submission['SQ2-1abcd']
            del submission['SQ2-1e']
            del submission['SQ2-1f']
            del submission['SQ2-1ghijklmn']

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                declaration=submission, status='started')

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            doc = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                len(doc.xpath('//p[contains(text(), "You need to finish making the supplier declaration")]')),  # noqa
                1)

    def test_declaration_status_when_not_complete(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.side_effect = APIError(mock.Mock(status_code=404))

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            doc = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                len(doc.xpath('//p[contains(text(), "You need to make the supplier declaration")]')),
                1)

    def test_last_updated_exists_for_both_sections(self, data_api_client, s3):
        files = [
            ('updates/communications/', 'file 1', 'odt', '2015-01-01T14:00:00.000Z'),
            ('updates/clarifications/', 'file 2', 'odt', '2015-02-02T14:00:00.000Z'),
            ('', 'g-cloud-7-supplier-pack', 'zip', '2015-01-01T14:00:00.000Z'),
        ]

        s3.return_value.list.return_value = [
            _return_fake_s3_file_dict(
                'g-cloud-7/communications/{}'.format(section), filename, ext, last_modified=last_modified
            ) for section, filename, ext, last_modified in files
        ]

        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
            res = self.client.get("/suppliers/frameworks/g-cloud-7")
            doc = html.fromstring(res.get_data(as_text=True))
            last_updateds = [
                {
                    'text': "Download guidance and legal documentation (.zip)",
                    'time': {
                        'text': 'Thursday 1 January 2015',
                        'datetime': '2015-01-01T14:00:00.000Z'
                    }
                },
                {
                    'text': "Read updates and ask clarification questions",
                    'time': {
                        'text': 'Monday 2 February 2015',
                        'datetime': '2015-02-02T14:00:00.000Z'
                    }
                }
            ]

            self._assert_last_updated_times(doc, last_updateds)

    def test_last_updated_exists_for_one_section(self, data_api_client, s3):
        files = [
            ('', 'g-cloud-7-supplier-pack', 'zip', '2015-01-01T14:00:00.000Z'),
        ]

        s3.return_value.list.return_value = [
            _return_fake_s3_file_dict(
                'g-cloud-7/communications/{}'.format(section), filename, ext, last_modified=last_modified
            ) for section, filename, ext, last_modified in files
        ]

        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
            res = self.client.get("/suppliers/frameworks/g-cloud-7")
            doc = html.fromstring(res.get_data(as_text=True))
            last_updateds = [
                {
                    'text': "Download guidance and legal documentation (.zip)",
                    'time': {
                        'text': 'Thursday 1 January 2015',
                        'datetime': '2015-01-01T14:00:00.000Z'
                    }
                },
                {
                    'text': "Read updates and ask clarification questions"
                }
            ]

            self._assert_last_updated_times(doc, last_updateds)

    def test_last_updated_does_not_exist(self, data_api_client, s3):
        s3.return_value.list.return_value = []

        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
            res = self.client.get("/suppliers/frameworks/g-cloud-7")
            doc = html.fromstring(res.get_data(as_text=True))
            last_updateds = [
                {'text': "Download guidance and legal documentation (.zip)"},
                {'text': "Read updates and ask clarification questions"}
            ]

            self._assert_last_updated_times(doc, last_updateds)

    def test_returns_404_if_framework_does_not_exist(self, data_api_client, s3):
        with self.app.test_client():
            self.login()
            data_api_client.get_framework.side_effect = APIError(mock.Mock(status_code=404))

            res = self.client.get('/suppliers/frameworks/does-not-exist')

            assert_equal(res.status_code, 404)

    def test_result_letter_is_shown_when_is_in_standstill(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.find_draft_services.return_value = {
                "services": [
                    {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
                ]
            }
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            data = res.get_data(as_text=True)

            assert_in(u'Download your application result letter', data)

    def test_result_letter_is_not_shown_when_not_in_standstill(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='pending')
            data_api_client.find_draft_services.return_value = {
                "services": [
                    {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
                ]
            }
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            data = res.get_data(as_text=True)

            assert_not_in(u'Download your application result letter', data)

    def test_result_letter_is_not_shown_when_no_application(self, data_api_client, s3):
        with self.app.test_client():
            self.login()
            s3.return_value.path_exists.return_value = False
            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.find_draft_services.return_value = {
                "services": [
                    {'serviceName': 'A service', 'status': 'not-submitted'}
                ]
            }
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            data = res.get_data(as_text=True)

            assert_not_in(u'Download your application result letter', data)

    def test_link_to_unsigned_framework_agreement_is_shown_if_supplier_is_on_framework(self, data_api_client, s3):
        with self.app.test_client():
            self.login()
            s3.return_value.path_exists.return_value = False
            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.find_draft_services.return_value = {
                "services": [
                    {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
                ]
            }
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            data = res.get_data(as_text=True)

            assert_in(u'Sign and return your framework agreement', data)
            assert_not_in(u'Download your countersigned framework agreement', data)

    def test_pending_success_message_is_explicit_if_supplier_is_on_framework(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

        s3.return_value.path_exists.return_value = False
        data_api_client.get_framework.return_value = self.framework(status='standstill')
        data_api_client.find_draft_services.return_value = {
            "services": [
                {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
            ]
        }
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(on_framework=True)
        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert_equal(res.status_code, 200)

        data = res.get_data(as_text=True)

        for success_message in [
            u'Your application was successful. You\'ll be able to sell services when the G-Cloud 7 framework is live',
            u'Download your application award letter (.pdf)',
            u'This letter is a record of your successful G-Cloud 7 application.'
        ]:
            assert_in(success_message, data)

        for equivocal_message in [
            u'You made your supplier declaration and submitted 1 service.',
            u'Download your application result letter (.pdf)',
            u'This letter informs you if your G-Cloud 7 application has been successful.'
        ]:
            assert_not_in(equivocal_message, data)

    def test_link_to_framework_agreement_is_not_shown_if_supplier_is_not_on_framework(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

            data_api_client.find_draft_services.return_value = {
                "services": [
                    {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
                ]
            }
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=False)

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            data = res.get_data(as_text=True)

            assert_not_in(u'Sign and return your framework agreement', data)

    def test_pending_success_message_is_equivocal_if_supplier_is_on_framework(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

        s3.return_value.path_exists.return_value = False
        data_api_client.get_framework.return_value = self.framework(status='standstill')
        data_api_client.find_draft_services.return_value = {
            "services": [
                {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
            ]
        }
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(on_framework=False)
        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert_equal(res.status_code, 200)

        data = res.get_data(as_text=True)

        for success_message in [
            u'Your application was successful. You\'ll be able to sell services when the G-Cloud 7 framework is live',
            u'Download your application award letter (.pdf)',
            u'This letter is a record of your successful G-Cloud 7 application.'
        ]:
            assert_not_in(success_message, data)

        for equivocal_message in [
            u'You made your supplier declaration and submitted 1 service.',
            u'Download your application result letter (.pdf)',
            u'This letter informs you if your G-Cloud 7 application has been successful.'
        ]:
            assert_in(equivocal_message, data)

    def test_link_to_countersigned_framework_agreement_is_shown_if_it_exists(self, data_api_client, s3):
        with self.app.test_client():
            self.login()
            s3.return_value.path_exists.return_value = True
            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.find_draft_services.return_value = {
                "services": [
                    {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
                ]
            }
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            data = res.get_data(as_text=True)

            assert_not_in(u'Sign and return your framework agreement', data)
            assert_in(u'Download your countersigned framework agreement', data)


@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
class TestFrameworkAgreement(BaseApplicationTest):
    def test_page_renders_if_all_ok(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)

            res = self.client.get("/suppliers/frameworks/g-cloud-7/agreement")
            data = res.get_data(as_text=True)

            assert_equal(res.status_code, 200)
            assert_in(u'Send document to CCS', data)
            assert_not_in(u'Return your signed signature page', data)

    def test_page_returns_404_if_framework_in_wrong_state(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)

            res = self.client.get("/suppliers/frameworks/g-cloud-7/agreement")

            assert_equal(res.status_code, 404)

    def test_page_returns_404_if_supplier_not_on_framework(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=False)

            res = self.client.get("/suppliers/frameworks/g-cloud-7/agreement")

            assert_equal(res.status_code, 404)

    @mock.patch('dmutils.s3.S3')
    def test_upload_message_if_agreement_is_returned(self, s3, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True, agreement_returned=True, agreement_returned_at='2015-11-02T15:25:56.000000Z'
            )

            res = self.client.get('/suppliers/frameworks/g-cloud-7/agreement')
            data = res.get_data(as_text=True)
            doc = html.fromstring(data)

            assert_equal(res.status_code, 200)
            assert_equal(
                u'/suppliers/frameworks/g-cloud-7/agreement',
                doc.xpath('//form')[0].action
            )
            assert_in(u'Document uploaded Monday 2 November 2015 at 15:25', data)
            assert_in(u'Your document has been uploaded', data)

    def test_upload_message_if_agreement_is_not_returned(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)

            res = self.client.get('/suppliers/frameworks/g-cloud-7/agreement')
            data = res.get_data(as_text=True)
            doc = html.fromstring(data)

            assert_equal(res.status_code, 200)
            assert_equal(
                u'/suppliers/frameworks/g-cloud-7/agreement',
                doc.xpath('//form')[0].action
            )
            assert_not_in(u'Document uploaded', data)
            assert_not_in(u'Your document has been uploaded', data)

    def test_loads_contract_start_page_if_framework_agreement_version_exists(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = get_g_cloud_8()
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)

            res = self.client.get("/suppliers/frameworks/g-cloud-8/agreement")
            data = res.get_data(as_text=True)

            assert res.status_code == 200
            assert u'Return your signed signature page' in data
            assert u'Send document to CCS' not in data

    def test_two_lots_passed_on_contract_start_page(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = get_g_cloud_8()
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)
            data_api_client.find_draft_services.return_value = {
                'services': [
                    {'lotSlug': 'saas', 'status': 'submitted'},
                    {'lotSlug': 'scs', 'status': 'submitted'}
                ]
            }
            expected_lots_and_statuses = [
                ('Software as a Service', 'Pass'),
                ('Platform as a Service', 'No application'),
                ('Infrastructure as a Service', 'No application'),
                ('Specialist Cloud Services', 'Pass'),
            ]

            res = self.client.get("/suppliers/frameworks/g-cloud-8/agreement")
            doc = html.fromstring(res.get_data(as_text=True))

            assert res.status_code == 200

            lots_and_statuses = []
            lot_table_rows = doc.xpath('//*[@id="content"]//table/tbody/tr')
            for row in lot_table_rows:
                cells = row.findall('./td')
                lots_and_statuses.append(
                    (cells[0].text_content().strip(), cells[1].text_content().strip())
                )

            assert len(lots_and_statuses) == len(expected_lots_and_statuses)
            for lot_and_status in lots_and_statuses:
                assert lot_and_status in expected_lots_and_statuses


@mock.patch('dmutils.s3.S3')
@mock.patch('app.main.frameworks.send_email')
@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
class TestFrameworkAgreementUpload(BaseApplicationTest):
    def test_page_returns_404_if_framework_in_wrong_state(self, data_api_client, send_email, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b'doc'), 'test.pdf'),
                }
            )

            assert_equal(res.status_code, 404)

    def test_page_returns_404_if_supplier_not_on_framework(self, data_api_client, send_email, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=False)

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b'doc'), 'test.pdf'),
                }
            )

            assert_equal(res.status_code, 404)

    @mock.patch('app.main.views.frameworks.file_is_less_than_5mb')
    def test_page_returns_400_if_file_is_too_large(self, file_is_less_than_5mb, data_api_client, send_email, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)
            file_is_less_than_5mb.return_value = False

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b'doc'), 'test.pdf'),
                }
            )

            assert res.status_code == 400
            assert u'Document must be less than 5MB' in res.get_data(as_text=True)

    @mock.patch('app.main.views.frameworks.file_is_empty')
    def test_page_returns_400_if_file_is_empty(self, file_is_empty, data_api_client, send_email, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)
            file_is_empty.return_value = True

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b''), 'test.pdf'),
                }
            )

            assert_equal(res.status_code, 400)
            assert_in(u'Document must not be empty', res.get_data(as_text=True))

    def test_api_is_not_updated_and_email_not_sent_if_upload_fails(self, data_api_client, send_email, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)
            s3.return_value.save.side_effect = S3ResponseError(500, 'All fail')

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b'doc'), 'test.pdf'),
                }
            )

            assert_equal(res.status_code, 503)
            s3.return_value.save.assert_called_with(
                'g-cloud-7/agreements/1234/1234-signed-framework-agreement.pdf',
                mock.ANY,
                acl='private',
                download_filename='Supplier_Name-1234-signed-framework-agreement.pdf'
            )
            assert not data_api_client.register_framework_agreement_returned.called
            assert not send_email.called

    def test_email_is_not_sent_if_api_update_fails(self, data_api_client, send_email, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)
            data_api_client.register_framework_agreement_returned.side_effect = APIError(mock.Mock(status_code=500))

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b'doc'), 'test.pdf'),
                }
            )

            assert_equal(res.status_code, 500)
            s3.return_value.save.assert_called_with(
                'g-cloud-7/agreements/1234/1234-signed-framework-agreement.pdf',
                mock.ANY,
                acl='private',
                download_filename='Supplier_Name-1234-signed-framework-agreement.pdf'
            )
            data_api_client.register_framework_agreement_returned.assert_called_with(
                1234, 'g-cloud-7', 'email@email.com')
            assert not send_email.called

    def test_email_failure(self, data_api_client, send_email, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)
            send_email.side_effect = MandrillException()

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b'doc'), 'test.pdf'),
                }
            )

            assert_equal(res.status_code, 503)
            s3.return_value.save.assert_called_with(
                'g-cloud-7/agreements/1234/1234-signed-framework-agreement.pdf',
                mock.ANY,
                acl='private',
                download_filename='Supplier_Name-1234-signed-framework-agreement.pdf'
            )
            data_api_client.register_framework_agreement_returned.assert_called_with(
                1234, 'g-cloud-7', 'email@email.com')
            send_email.assert_called()

    def test_upload_agreement_document(self, data_api_client, send_email, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b'doc'), 'test.pdf'),
                }
            )

            s3.return_value.save.assert_called_with(
                'g-cloud-7/agreements/1234/1234-signed-framework-agreement.pdf',
                mock.ANY,
                acl='private',
                download_filename='Supplier_Name-1234-signed-framework-agreement.pdf'
            )
            assert_equal(res.status_code, 302)
            assert_equal(res.location, 'http://localhost/suppliers/frameworks/g-cloud-7/agreement')

    def test_upload_jpeg_agreement_document(self, data_api_client, send_email, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b'doc'), 'test.jpg'),
                }
            )

            s3.return_value.save.assert_called_with(
                'g-cloud-7/agreements/1234/1234-signed-framework-agreement.jpg',
                mock.ANY,
                acl='private',
                download_filename='Supplier_Name-1234-signed-framework-agreement.jpg'
            )
            assert_equal(res.status_code, 302)
            assert_equal(res.location, 'http://localhost/suppliers/frameworks/g-cloud-7/agreement')


@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
@mock.patch('dmutils.s3.S3')
class TestFrameworkAgreementDocumentDownload(BaseApplicationTest):
    def test_download_document_fails_if_no_supplier_framework(self, S3, data_api_client):
        data_api_client.get_supplier_framework_info.side_effect = APIError(mock.Mock(status_code=404))

        with self.app.test_client():
            self.login()

            res = self.client.get('/suppliers/frameworks/g-cloud-7/agreements/example.pdf')

            assert_equal(res.status_code, 404)

    def test_download_document_fails_if_no_supplier_declaration(self, S3, data_api_client):
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(declaration=None)

        with self.app.test_client():
            self.login()

            res = self.client.get('/suppliers/frameworks/g-cloud-7/agreements/example.pdf')

            assert_equal(res.status_code, 404)

    def test_download_document(self, S3, data_api_client):
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        uploader = mock.Mock()
        S3.return_value = uploader
        uploader.get_signed_url.return_value = 'http://url/path?param=value'

        with self.app.test_client():
            self.login()

            res = self.client.get('/suppliers/frameworks/g-cloud-7/agreements/example.pdf')

            assert_equal(res.status_code, 302)
            assert_equal(res.location, 'http://asset-host/path?param=value')
            uploader.get_signed_url.assert_called_with(
                'g-cloud-7/agreements/1234/1234-example.pdf')

    def test_download_document_with_asset_url(self, S3, data_api_client):
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        uploader = mock.Mock()
        S3.return_value = uploader
        uploader.get_signed_url.return_value = 'http://url/path?param=value'

        with self.app.test_client():
            self.app.config['DM_ASSETS_URL'] = 'https://example'
            self.login()

            res = self.client.get('/suppliers/frameworks/g-cloud-7/agreements/example.pdf')

            assert_equal(res.status_code, 302)
            assert_equal(res.location, 'https://example/path?param=value')
            uploader.get_signed_url.assert_called_with(
                'g-cloud-7/agreements/1234/1234-example.pdf')


@mock.patch('dmutils.s3.S3')
class TestFrameworkDocumentDownload(BaseApplicationTest):
    def test_download_document(self, S3):
        uploader = mock.Mock()
        S3.return_value = uploader
        uploader.get_signed_url.return_value = 'http://url/path?param=value'

        with self.app.test_client():
            self.login()

            res = self.client.get('/suppliers/frameworks/g-cloud-7/files/example.pdf')

            assert_equal(res.status_code, 302)
            assert_equal(res.location, 'http://asset-host/path?param=value')
            uploader.get_signed_url.assert_called_with('g-cloud-7/communications/example.pdf')

    def test_download_document_returns_404_if_url_is_None(self, S3):
        uploader = mock.Mock()
        S3.return_value = uploader
        uploader.get_signed_url.return_value = None

        with self.app.test_client():
            self.login()

            res = self.client.get('/suppliers/frameworks/g-cloud-7/files/example.pdf')

            assert_equal(res.status_code, 404)


@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
class TestSupplierDeclaration(BaseApplicationTest):
    def test_get_with_no_previous_answers(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_declaration.side_effect = APIError(mock.Mock(status_code=404))

            res = self.client.get(
                '/suppliers/frameworks/g-cloud-7/declaration/g-cloud-7-essentials')

            assert_equal(res.status_code, 200)
            doc = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                doc.xpath('//input[@id="PR-1-yes"]/@checked'), [])
            assert_equal(
                doc.xpath('//input[@id="PR-1-no"]/@checked'), [])

    def test_get_with_with_previous_answers(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_declaration.return_value = {
                "declaration": {"status": "started", "PR1": False}
            }

            res = self.client.get(
                '/suppliers/frameworks/g-cloud-7/declaration/g-cloud-7-essentials')

            assert_equal(res.status_code, 200)
            doc = html.fromstring(res.get_data(as_text=True))
            assert_equal(
                len(doc.xpath('//input[@id="input-PR1-no"]/@checked')), 1)

    def test_post_valid_data(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_declaration.return_value = {
                "declaration": {"status": "started"}
            }
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration/g-cloud-7-essentials',
                data=FULL_G7_SUBMISSION)

            assert_equal(res.status_code, 302)
            assert data_api_client.set_supplier_declaration.called

    def test_post_valid_data_to_complete_declaration(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_declaration.return_value = {
                "declaration": FULL_G7_SUBMISSION
            }
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration/grounds-for-discretionary-exclusion',
                data=FULL_G7_SUBMISSION)

            assert_equal(res.status_code, 302)
            assert_equal(res.location, 'http://localhost/suppliers/frameworks/g-cloud-7')
            assert data_api_client.set_supplier_declaration.called
            assert data_api_client.set_supplier_declaration.call_args[0][2]['status'] == 'complete'

    def test_post_valid_data_with_api_failure(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_declaration.return_value = {
                "declaration": {"status": "started"}
            }
            data_api_client.set_supplier_declaration.side_effect = APIError(mock.Mock(status_code=400))

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration/g-cloud-7-essentials',
                data=FULL_G7_SUBMISSION)

            assert_equal(res.status_code, 400)

    @mock.patch('app.main.helpers.validation.G7Validator.get_error_messages_for_page')
    def test_post_with_validation_errors(self, get_error_messages_for_page, data_api_client):
        """Test that answers are not saved if there are errors

        For unit tests of the validation see :mod:`tests.app.main.helpers.test_frameworks`
        """
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            get_error_messages_for_page.return_value = {'PR1': {'input_name': 'PR1', 'message': 'this is invalid'}}

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration/g-cloud-7-essentials',
                data=FULL_G7_SUBMISSION)

            assert_equal(res.status_code, 400)
            assert not data_api_client.set_supplier_declaration.called

            doc = html.fromstring(res.get_data(as_text=True))
            elems = doc.cssselect('#input-PR1-yes')
            assert elems[0].value == 'true'

    def test_cannot_post_data_if_not_open(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = {
                'frameworks': {'status': 'pending'}
            }
            data_api_client.get_supplier_declaration.return_value = {
                "declaration": {"status": "started"}
            }
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration/g-cloud-7-essentials',
                data=FULL_G7_SUBMISSION)

            assert_equal(res.status_code, 404)
            assert not data_api_client.set_supplier_declaration.called


@mock.patch('app.main.views.frameworks.data_api_client')
@mock.patch('dmutils.s3.S3')
class TestFrameworkUpdatesPage(BaseApplicationTest):

    def _assert_page_title_and_table_headings(self, doc, tables_exist=True):

        assert_true(
            self.strip_all_whitespace('G-Cloud 7 updates')
            in self.strip_all_whitespace(doc.xpath('//h1')[0].text)
        )

        section_names = [
            'Communications',
            'Clarification questions and answers',
        ]

        headers = doc.xpath('//div[contains(@class, "updates-document-tables")]/h2[@class="summary-item-heading"]')
        assert_equal(len(headers), 2)
        for index, section_name in enumerate(section_names):
            assert_true(
                self.strip_all_whitespace(section_name)
                in self.strip_all_whitespace(headers[index].text)
            )

        if tables_exist:
            table_captions = doc.xpath('//div[contains(@class, "updates-document-tables")]/table/caption')
            assert_equal(len(table_captions), 2)
            for index, section_name in enumerate(section_names):
                assert_true(
                    self.strip_all_whitespace(section_name)
                    in self.strip_all_whitespace(table_captions[index].text)
                )

    def test_should_be_a_503_if_connecting_to_amazon_fails(self, s3, data_api_client):
        data_api_client.get_framework.return_value = self.framework('open')
        # if s3 throws a 500-level error
        s3.side_effect = S3ResponseError(500, 'Amazon has collapsed. The internet is over.')

        with self.app.test_client():
            self.login()

            response = self.client.get(
                '/suppliers/frameworks/g-cloud-7/updates'
            )

            assert_equal(response.status_code, 503)
            assert_true(
                self.strip_all_whitespace("<h1>Sorry, we're experiencing technical difficulties</h1>")
                in self.strip_all_whitespace(response.get_data(as_text=True))
            )

    def test_empty_messages_exist_if_no_files_returned(self, s3, data_api_client):
        data_api_client.get_framework.return_value = self.framework('open')

        with self.app.test_client():
            self.login()

            response = self.client.get(
                '/suppliers/frameworks/g-cloud-7/updates'
            )

            assert_equal(response.status_code, 200)
            doc = html.fromstring(response.get_data(as_text=True))
            self._assert_page_title_and_table_headings(doc, tables_exist=False)

            for empty_message in [
                '<p class="summary-item-no-content">No communications have been sent out.</p>',
                '<p class="summary-item-no-content">No clarification questions and answers have been posted yet.</p>',
            ]:
                assert_true(
                    self.strip_all_whitespace(empty_message)
                    in self.strip_all_whitespace(response.get_data(as_text=True))
                )

    def test_dates_for_open_framework_closed_for_questions(self, s3, data_api_client):
        data_api_client.get_framework.return_value = self.framework('open', clarification_questions_open=False)

        with self.app.test_client():
            self.login()

            response = self.client.get('/suppliers/frameworks/g-cloud-7/updates')
            data = response.get_data(as_text=True)

            assert response.status_code == 200
            assert 'All clarification questions and answers will be published by 5pm BST, 29 September 2015.' in data
            assert "The deadline for clarification questions is" not in data

    def test_dates_for_open_framework_open_for_questions(self, s3, data_api_client):
        data_api_client.get_framework.return_value = self.framework('open', clarification_questions_open=True)
        s3.return_value.path_exists.return_value = False

        with self.app.test_client():
            self.login()

            response = self.client.get('/suppliers/frameworks/g-cloud-7/updates')
            data = response.get_data(as_text=True)

            assert response.status_code == 200
            assert "All clarification questions and answers will be published by" not in data
            assert 'The deadline for clarification questions is 5pm BST, 22 September 2015.' in data

    def test_the_tables_should_be_displayed_correctly(self, s3, data_api_client):
        data_api_client.get_framework.return_value = self.framework('open')

        files = [
            ('updates/communications/', 'file 1', 'odt'),
            ('updates/communications/', 'file 2', 'odt'),
            ('updates/clarifications/', 'file 3', 'odt'),
            ('updates/clarifications/', 'file 4', 'odt'),
        ]

        # the communications table is always before the clarifications table
        s3.return_value.list.return_value = [
            _return_fake_s3_file_dict(
                "g-cloud-7/communications/{}".format(section), filename, ext
            ) for section, filename, ext in files
        ]

        with self.app.test_client():
            self.login()

            response = self.client.get(
                '/suppliers/frameworks/g-cloud-7/updates'
            )
            doc = html.fromstring(response.get_data(as_text=True))
            self._assert_page_title_and_table_headings(doc)

            tables = doc.xpath('//div[contains(@class, "updates-document-tables")]/table')

            # test that for each table, we have the right number of rows
            for table in tables:
                item_rows = table.findall('.//tr[@class="summary-item-row"]')
                assert_equal(len(item_rows), 2)

                # test that the file names and urls are right
                for row in item_rows:
                    section, filename, ext = files.pop(0)
                    filename_link = row.find('.//a[@class="document-link-with-icon"]')

                    assert_true(filename in filename_link.text_content())
                    assert_equal(
                        filename_link.get('href'),
                        '/suppliers/frameworks/g-cloud-7/files/{}{}.{}'.format(
                            section, filename.replace(' ', '%20'), ext
                        )
                    )

    def test_names_with_the_section_name_in_them_will_display_correctly(self, s3, data_api_client):
        data_api_client.get_framework.return_value = self.framework('open')

        # for example: 'g-cloud-7-updates/clarifications/communications%20file.odf'
        files = [
            ('updates/communications/', 'clarifications file', 'odt'),
            ('updates/clarifications/', 'communications file', 'odt')
        ]

        s3.return_value.list.return_value = [
            _return_fake_s3_file_dict(
                "g-cloud-7/communications/{}".format(section), filename, ext
            ) for section, filename, ext in files
        ]

        with self.app.test_client():
            self.login()

            response = self.client.get(
                '/suppliers/frameworks/g-cloud-7/updates'
            )
            doc = html.fromstring(response.get_data(as_text=True))
            self._assert_page_title_and_table_headings(doc)

            tables = doc.xpath('//div[contains(@class, "updates-document-tables")]/table')

            # test that for each table, we have the right number of rows
            for table in tables:
                item_rows = table.findall('.//tr[@class="summary-item-row"]')
                assert_equal(len(item_rows), 1)

                # test that the file names and urls are right
                for row in item_rows:
                    section, filename, ext = files.pop(0)
                    filename_link = row.find('.//a[@class="document-link-with-icon"]')

                    assert_true(filename in filename_link.text_content())
                    assert_equal(
                        filename_link.get('href'),
                        '/suppliers/frameworks/g-cloud-7/files/{}{}.{}'.format(
                            section, filename.replace(' ', '%20'), ext
                        )
                    )

    def test_question_box_is_shown_if_countersigned_agreement_is_not_yet_returned(self, s3, data_api_client):
        data_api_client.get_framework.return_value = self.framework('live', clarification_questions_open=False)
        s3.return_value.path_exists.return_value = False

        with self.app.test_client():
            self.login()

            response = self.client.get('/suppliers/frameworks/g-cloud-7/updates')
            data = response.get_data(as_text=True)

            assert response.status_code == 200
            assert_in(u'Ask a question about your G-Cloud 7 application', data)

    def test_no_question_box_shown_if_countersigned_agreement_is_returned(self, s3, data_api_client):
        data_api_client.get_framework.return_value = self.framework('live', clarification_questions_open=False)
        s3.return_value.path_exists.return_value = True

        with self.app.test_client():
            self.login()

            response = self.client.get('/suppliers/frameworks/g-cloud-7/updates')
            data = response.get_data(as_text=True)

            assert response.status_code == 200
            assert_not_in(u'Ask a question about your G-Cloud 7 application', data)


class TestSendClarificationQuestionEmail(BaseApplicationTest):

    def _send_email(self, clarification_question):
        with self.app.test_client():
            self.login()

            return self.client.post(
                "/suppliers/frameworks/g-cloud-7/updates",
                data={
                    'clarification_question': clarification_question,
                }
            )

    def _assert_clarification_email(self, send_email, is_called=True, succeeds=True):

        if succeeds:
            assert_equal(2, send_email.call_count)
        elif is_called:
            assert_equal(1, send_email.call_count)
        else:
            assert_equal(0, send_email.call_count)

        if is_called:
            send_email.assert_any_call(
                "digitalmarketplace@mailinator.com",
                FakeMail('Supplier name:', 'User name:'),
                "MANDRILL",
                "Test Framework clarification question",
                "do-not-reply@digitalmarketplace.service.gov.uk",
                "Test Framework Supplier",
                ["clarification-question"],
                reply_to="suppliers+g-cloud-7@digitalmarketplace.service.gov.uk",
            )
        if succeeds:
            send_email.assert_any_call(
                "email@email.com",
                FakeMail('Thanks for sending your Test Framework clarification', 'Test Framework updates page'),
                "MANDRILL",
                "Thanks for your clarification question",
                "do-not-reply@digitalmarketplace.service.gov.uk",
                "Digital Marketplace Admin",
                ["clarification-question-confirm"]
            )

    def _assert_application_email(self, send_email, succeeds=True):

        if succeeds:
            assert_equal(1, send_email.call_count)
        else:
            assert_equal(0, send_email.call_count)

        if succeeds:
            send_email.assert_called_with(
                "digitalmarketplace@mailinator.com",
                FakeMail('Test Framework question asked'),
                "MANDRILL",
                "Test Framework application question",
                "do-not-reply@digitalmarketplace.service.gov.uk",
                "Test Framework Supplier",
                ["application-question"],
                reply_to="email@email.com",
            )

    @mock.patch('app.main.views.frameworks.data_api_client')
    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_not_send_email_if_invalid_clarification_question(self, send_email, s3, data_api_client):
        data_api_client.get_framework.return_value = self.framework('open')
        s3.return_value.path_exists.return_value = False

        for invalid_clarification_question in [
            {
                'question': '',  # empty question
                'error_message': 'Question cannot be empty'
            }, {
                'question': '\t   \n\n\n',  # whitespace-only question
                'error_message': 'Question cannot be empty'
            },
            {
                'question': ('ten__chars' * 500) + '1',  # 5000+ char question
                'error_message': 'Question cannot be longer than 5000 characters'
            }
        ]:

            response = self._send_email(invalid_clarification_question['question'])
            self._assert_clarification_email(send_email, is_called=False, succeeds=False)

            assert_equal(response.status_code, 400)
            assert_true(
                self.strip_all_whitespace('There was a problem with your submitted question')
                in self.strip_all_whitespace(response.get_data(as_text=True))
            )
            assert_true(
                self.strip_all_whitespace(invalid_clarification_question['error_message'])
                in self.strip_all_whitespace(response.get_data(as_text=True))
            )

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.data_api_client')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_call_send_email_with_correct_params(self, send_email, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework('open', name='Test Framework')

        clarification_question = 'This is a clarification question.'
        response = self._send_email(clarification_question)

        self._assert_clarification_email(send_email)

        assert_equal(response.status_code, 200)
        assert_true(
            self.strip_all_whitespace('<p class="banner-message">Your clarification question has been sent. Answers to all clarification questions will be published on this page.</p>')  # noqa
            in self.strip_all_whitespace(response.get_data(as_text=True))
        )

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.data_api_client')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_call_send_g7_email_with_correct_params(self, send_email, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework('open', name='Test Framework',
                                                                    clarification_questions_open=False)
        clarification_question = 'This is a G7 question.'
        response = self._send_email(clarification_question)

        self._assert_application_email(send_email)

        assert_equal(response.status_code, 200)
        assert_in(
            self.strip_all_whitespace('<p class="banner-message">Your question has been sent. You\'ll get a reply from the Crown Commercial Service soon.</p>'),  # noqa
            self.strip_all_whitespace(response.get_data(as_text=True))
        )

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.data_api_client')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_create_audit_event(self, send_email, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework('open', name='Test Framework')
        clarification_question = 'This is a clarification question'
        response = self._send_email(clarification_question)

        self._assert_clarification_email(send_email)

        assert_equal(response.status_code, 200)
        data_api_client.create_audit_event.assert_called_with(
            audit_type=AuditTypes.send_clarification_question,
            user="email@email.com",
            object_type="suppliers",
            object_id=1234,
            data={"question": clarification_question, 'framework': 'g-cloud-7'})

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.data_api_client')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_create_g7_question_audit_event(self, send_email, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework('open', name='Test Framework',
                                                                    clarification_questions_open=False)
        clarification_question = 'This is a G7 question'
        response = self._send_email(clarification_question)

        self._assert_application_email(send_email)

        assert_equal(response.status_code, 200)
        data_api_client.create_audit_event.assert_called_with(
            audit_type=AuditTypes.send_application_question,
            user="email@email.com",
            object_type="suppliers",
            object_id=1234,
            data={"question": clarification_question, 'framework': 'g-cloud-7'})

    @mock.patch('app.main.views.frameworks.data_api_client')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_be_a_503_if_email_fails(self, send_email, data_api_client):
        data_api_client.get_framework.return_value = self.framework('open', name='Test Framework')
        send_email.side_effect = MandrillException("Arrrgh")

        clarification_question = 'This is a clarification question.'
        response = self._send_email(clarification_question)
        self._assert_clarification_email(send_email, succeeds=False)

        assert_equal(response.status_code, 503)


@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
@mock.patch('app.main.views.frameworks.count_unanswered_questions')
class TestG7ServicesList(BaseApplicationTest):

    def test_404_when_g7_pending_and_no_complete_services(self, count_unanswered, data_api_client):
        with self.app.test_client():
            self.login()
        data_api_client.get_framework.return_value = self.framework(status='pending')
        data_api_client.find_draft_services.return_value = {'services': []}
        count_unanswered.return_value = 0
        response = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/iaas')
        assert_equal(response.status_code, 404)

    def test_404_when_g7_pending_and_no_declaration(self, count_unanswered, data_api_client):
        with self.app.test_client():
            self.login()
        data_api_client.get_framework.return_value = self.framework(status='pending')
        data_api_client.get_supplier_declaration.return_value = {
            "declaration": {"status": "started"}
        }
        response = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/iaas')
        assert_equal(response.status_code, 404)

    def test_no_404_when_g7_open_and_no_complete_services(self, count_unanswered, data_api_client):
        with self.app.test_client():
            self.login()
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.find_draft_services.return_value = {'services': []}
        count_unanswered.return_value = 0
        response = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/iaas')
        assert_equal(response.status_code, 200)

    def test_no_404_when_g7_open_and_no_declaration(self, count_unanswered, data_api_client):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_supplier_declaration.return_value = {
            "declaration": {"status": "started"}
        }
        response = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/iaas')
        assert_equal(response.status_code, 200)

    def test_shows_g7_message_if_pending_and_application_made(self, count_unanswered, data_api_client):
        with self.app.test_client():
            self.login()
        data_api_client.get_framework.return_value = self.framework(status='pending')
        data_api_client.get_supplier_declaration.return_value = {'declaration': FULL_G7_SUBMISSION}  # noqa
        data_api_client.find_draft_services.return_value = {
            'services': [
                {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'submitted'},
            ]
        }
        count_unanswered.return_value = 0, 1

        response = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs')
        doc = html.fromstring(response.get_data(as_text=True))

        assert_equal(response.status_code, 200)
        heading = doc.xpath('//div[@class="summary-item-lede"]//h2[@class="summary-item-heading"]')
        assert_true(len(heading) > 0)
        assert_in(u"G-Cloud 7 is closed for applications",
                  heading[0].xpath('text()')[0])
        assert_in(u"You made your supplier declaration and submitted 1 complete service.",
                  heading[0].xpath('../p[1]/text()')[0])

    def test_drafts_list_progress_count(self, count_unanswered, data_api_client):
        with self.app.test_client():
            self.login()

        count_unanswered.return_value = 3, 1
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.find_draft_services.return_value = {
            'services': [
                {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'not-submitted'},
            ]
        }

        submissions = self.client.get('/suppliers/frameworks/g-cloud-7/submissions')
        lot_page = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs')

        assert_true(u'Service can be moved to complete' not in lot_page.get_data(as_text=True))
        assert_in(u'4 unanswered questions', lot_page.get_data(as_text=True))

        assert_in(u'1 draft service', submissions.get_data(as_text=True))
        assert_true(u'complete service' not in submissions.get_data(as_text=True))

    def test_drafts_list_can_be_completed(self, count_unanswered, data_api_client):
        with self.app.test_client():
            self.login()

        count_unanswered.return_value = 0, 1

        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.find_draft_services.return_value = {
            'services': [
                {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'not-submitted'},
            ]
        }

        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs')

        assert_in(u'Service can be marked as complete', res.get_data(as_text=True))
        assert_in(u'1 optional question unanswered', res.get_data(as_text=True))

    def test_drafts_list_completed(self, count_unanswered, data_api_client):
        with self.app.test_client():
            self.login()

        count_unanswered.return_value = 0, 1

        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.find_draft_services.return_value = {
            'services': [
                {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'submitted'},
            ]
        }

        submissions = self.client.get('/suppliers/frameworks/g-cloud-7/submissions')
        lot_page = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs')

        assert_true(u'Service can be moved to complete' not in lot_page.get_data(as_text=True))
        assert_in(u'1 optional question unanswered', lot_page.get_data(as_text=True))
        assert_in(u'make the supplier&nbsp;declaration', lot_page.get_data(as_text=True))

        assert_in(u'1 service marked as complete', submissions.get_data(as_text=True))
        assert_true(u'draft service' not in submissions.get_data(as_text=True))

    def test_drafts_list_completed_with_declaration_status(self, count_unanswered, data_api_client):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_supplier_declaration.return_value = {
            'declaration': {
                'status': 'complete'
            }
        }
        data_api_client.find_draft_services.return_value = {
            'services': [
                {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'submitted'},
            ]
        }

        submissions = self.client.get('/suppliers/frameworks/g-cloud-7/submissions')

        assert_in(u'1 service will be submitted', submissions.get_data(as_text=True))
        assert_not_in(u'1 complete service was submitted', submissions.get_data(as_text=True))
        assert_in(u'browse-list-item-status-happy', submissions.get_data(as_text=True))

    def test_drafts_list_services_were_submitted(self, count_unanswered, data_api_client):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(status='standstill')
        data_api_client.get_supplier_declaration.return_value = {
            'declaration': {
                'status': 'complete'
            }
        }
        data_api_client.find_draft_services.return_value = {
            'services': [
                {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'not-submitted'},
                {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'submitted'},
            ]
        }

        submissions = self.client.get('/suppliers/frameworks/g-cloud-7/submissions')

        assert_in(u'1 complete service was submitted', submissions.get_data(as_text=True))

    def test_dos_drafts_list_with_open_framework(self, count_unanswered, data_api_client):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(slug='digital-outcomes-and-specialists',
                                                                    status='open')
        data_api_client.get_supplier_declaration.return_value = {
            'declaration': {
                'status': 'complete'
            }
        }
        data_api_client.find_draft_services.return_value = {
            'services': [
                {'serviceName': 'draft', 'lotSlug': 'digital-specialists', 'status': 'submitted'},
            ]
        }

        submissions = self.client.get('/suppliers/frameworks/digital-outcomes-and-specialists/submissions')

        assert_in(u'This will be submitted', submissions.get_data(as_text=True))
        assert_in(u'browse-list-item-status-happy', submissions.get_data(as_text=True))
        assert_in(u'Apply to provide', submissions.get_data(as_text=True))

    def test_dos_drafts_list_with_closed_framework(self, count_unanswered, data_api_client):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(slug="digital-outcomes-and-specialists",
                                                                    status='pending')
        data_api_client.get_supplier_declaration.return_value = {
            'declaration': {
                'status': 'complete'
            }
        }
        data_api_client.find_draft_services.return_value = {
            'services': [
                {'serviceName': 'draft', 'lotSlug': 'digital-specialists', 'status': 'not-submitted'},
                {'serviceName': 'draft', 'lotSlug': 'digital-specialists', 'status': 'submitted'},
            ]
        }

        submissions = self.client.get('/suppliers/frameworks/digital-outcomes-and-specialists/submissions')

        assert submissions.status_code == 200

        assert_in(u'Submitted', submissions.get_data(as_text=True))
        assert_not_in(u'Apply to provide', submissions.get_data(as_text=True))


@mock.patch("app.main.frameworks.data_api_client")
@mock.patch("app.main.frameworks.return_supplier_framework_info_if_on_framework_or_abort")
class TestReturnSignedAgreement(BaseApplicationTest):

    def test_should_be_an_error_if_no_full_name(self, return_supplier_framework, data_api_client):
        self.login()
        data_api_client.get_framework.return_value = get_g_cloud_8()
        return_supplier_framework.return_value = self.supplier_framework(on_framework=True)

        res = self.client.post(
            "/suppliers/frameworks/g-cloud-8/signer-details",
            data={
                'role': "The Boss"
            }
        )
        assert res.status_code == 400
        page = res.get_data(as_text=True)
        assert "You must provide the full name of the person signing on behalf of the company" in page

    def test_should_be_an_error_if_no_role(self, return_supplier_framework, data_api_client):
        self.login()
        data_api_client.get_framework.return_value = get_g_cloud_8()
        return_supplier_framework.return_value = self.supplier_framework(on_framework=True)

        res = self.client.post(
            "/suppliers/frameworks/g-cloud-8/signer-details",
            data={
                'full_name': "Josh Moss"
            }
        )
        assert res.status_code == 400
        page = res.get_data(as_text=True)
        assert "You must provide the role of the person signing on behalf of the company" in page

    def test_should_be_an_error_if_signer_details_fields_more_than_255_characters(
            self, return_supplier_framework, data_api_client
    ):
        self.login()
        data_api_client.get_framework.return_value = get_g_cloud_8()
        return_supplier_framework.return_value = self.supplier_framework(on_framework=True)

        # 255 characters should be fine
        res = self.client.post(
            "/suppliers/frameworks/g-cloud-8/signer-details",
            data={
                'full_name': "J" * 255,
                'role': "J" * 255
            }
        )
        assert res.status_code == 302

        # 256 characters should be an error
        res = self.client.post(
            "/suppliers/frameworks/g-cloud-8/signer-details",
            data={
                'full_name': "J" * 256,
                'role': "J" * 256
            }
        )
        assert res.status_code == 400
        page = res.get_data(as_text=True)
        assert "You must provide a name under 256 characters" in page
        assert "You must provide a role under 256 characters" in page

    def test_should_strip_whitespace_on_signer_details_fields(self, return_supplier_framework, data_api_client):
        signer_details = {
            'full_name': "   Josh Moss   ",
            'role': "   The Boss   "
        }

        data_api_client.get_framework.return_value = get_g_cloud_8()
        return_supplier_framework.return_value = self.supplier_framework(on_framework=True)

        with self.client as c:
            self.login()
            res = c.post(
                "/suppliers/frameworks/g-cloud-8/signer-details",
                data=signer_details
            )
            assert res.status_code == 302

            for key, value in signer_details.items():
                assert key in session
                assert session.get(key) == value.strip()

    def test_provide_signer_details_form_with_valid_input_redirects_to_upload_page(
            self, return_supplier_framework, data_api_client
    ):
        signer_details = {
            'full_name': "Josh Moss",
            'role': "The Boss"
        }

        data_api_client.get_framework.return_value = get_g_cloud_8()
        return_supplier_framework.return_value = self.supplier_framework(on_framework=True)

        with self.client as c:
            self.login()
            res = c.post(
                "/suppliers/frameworks/g-cloud-8/signer-details",
                data=signer_details
            )

            for key, value in signer_details.items():
                assert key in session
                assert session.get(key) == value

            assert res.status_code == 302
            assert "suppliers/frameworks/g-cloud-8/signature-upload" in res.location

    @mock.patch('app.main.views.frameworks.file_is_empty')
    def test_signature_upload_returns_400_if_file_is_empty(
        self, file_is_empty, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = get_g_cloud_8()
            return_supplier_framework.return_value = self.supplier_framework(on_framework=True)
            file_is_empty.return_value = True

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-8/signature-upload',
                data={
                    'signature_page': (StringIO(b''), 'test.pdf'),
                }
            )

            assert res.status_code == 400
            assert 'The file must not be empty' in res.get_data(as_text=True)

    @mock.patch('app.main.views.frameworks.file_is_image')
    def test_signature_upload_returns_400_if_file_is_not_image_or_pdf(
        self, file_is_image, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = get_g_cloud_8()
            return_supplier_framework.return_value = self.supplier_framework(on_framework=True)
            file_is_image.return_value = False

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-8/signature-upload',
                data={
                    'signature_page': (StringIO(b'asdf'), 'test.txt'),
                }
            )

            assert res.status_code == 400
            assert 'The file must be a PDF, JPG or PNG' in res.get_data(as_text=True)

    @mock.patch('app.main.views.frameworks.file_is_less_than_5mb')
    def test_signature_upload_returns_400_if_file_is_larger_than_5mb(
        self, file_is_less_than_5mb, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = get_g_cloud_8()
            return_supplier_framework.return_value = self.supplier_framework(on_framework=True)
            file_is_less_than_5mb.return_value = False

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-8/signature-upload',
                data={
                    'signature_page': (StringIO(b'asdf'), 'test.jpg'),
                }
            )

            assert res.status_code == 400
            assert 'The file must be less than 5MB' in res.get_data(as_text=True)

    @mock.patch('dmutils.s3.S3')
    def test_upload_signature_page(self, s3, return_supplier_framework, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = get_g_cloud_8()
            return_supplier_framework.return_value = self.supplier_framework(on_framework=True)

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-8/signature-upload',
                data={
                    'signature_page': (StringIO(b'asdf'), 'test.jpg'),
                }
            )

            s3.return_value.save.assert_called_with(
                'g-cloud-8/agreements/1234/1234-signed-framework-agreement.jpg',
                mock.ANY,
                acl='private',
                download_filename='Supplier_Name-1234-signed-framework-agreement.jpg'
            )
            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-7/agreement'
