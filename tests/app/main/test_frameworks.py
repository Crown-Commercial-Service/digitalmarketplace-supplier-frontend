# -*- coding: utf-8 -*-
from collections import OrderedDict
from itertools import chain

from dmapiclient import HTTPError
from flask import request

try:
    from StringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO
import mock
import pytest
from six.moves.urllib.parse import urljoin

from flask import session
from lxml import html
from dmapiclient import APIError
from dmapiclient.audit import AuditTypes
from dmutils.email.exceptions import EmailError
from dmutils.s3 import S3ResponseError

from ..helpers import BaseApplicationTest, FULL_G7_SUBMISSION, FakeMail, valid_g9_declaration_base


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


def _assert_args_and_raise(e, *args, **kwargs):
    def _inner(*inner_args, **inner_kwargs):
        assert args == inner_args
        assert kwargs == inner_kwargs
        raise e
    return _inner


def _assert_args_and_return(retval, *args, **kwargs):
    def _inner(*inner_args, **inner_kwargs):
        assert args == inner_args
        assert kwargs == inner_kwargs
        return retval
    return _inner


@pytest.fixture(params=("GET", "POST"))
def get_or_post(request):
    return request.param


@mock.patch('dmutils.s3.S3')
@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
class TestFrameworksDashboard(BaseApplicationTest):
    @staticmethod
    def _extract_guidance_links(doc):
        return OrderedDict(
            (
                section_li.xpath("normalize-space(string(.//h2))"),
                tuple(
                    (
                        item_li.xpath("normalize-space(string(.//a))") or None,
                        item_li.xpath("string(.//a/@href)") or None,
                        item_li.xpath("normalize-space(string(.//time))") or None,
                        item_li.xpath("string(.//time/@datetime)") or None,
                    )
                    for item_li in section_li.xpath(".//p[.//a]")
                ),
            )
            for section_li in doc.xpath("//main//*[./h2][.//p//a]")
        )

    @staticmethod
    def _extract_signing_details_table_rows(doc):
        return tuple(
            tuple(
                td_th_elem.xpath("normalize-space(string())")
                for td_th_elem in tr_elem.xpath("td|th")
            )
            for tr_elem in doc.xpath(
                "//main//table[normalize-space(string(./caption))=$b]/tbody/tr",
                b="Agreement details",
            )
        )

    @property
    def _boring_agreement_details(self):
        # property so we always get a clean copy
        return {
            'frameworkAgreementVersion': 'v1.0',
            'signerName': 'Martin Cunningham',
            'signerRole': 'Foreman',
            'uploaderUserId': 123,
            'uploaderUserName': 'User',
            'uploaderUserEmail': 'email@email.com',
        }

    _boring_agreement_returned_at = "2016-07-10T21:20:00.000000Z"

    @property
    def _boring_agreement_details_expected_table_results(self):
        # property so we always get a clean copy
        return (
            (
                'Person who signed',
                'Martin Cunningham Foreman'
            ),
            (
                'Submitted by',
                'User email@email.com Sunday 10 July 2016 at 22:20'
            ),
            (
                'Countersignature',
                'Waiting for CCS to countersign'
            ),
        )

    def test_framework_dashboard_shows_for_pending_if_declaration_exists(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(status='pending')
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath(
            "//h1[normalize-space(string())=$b]",
            b="Your G-Cloud 7 application",
        )) == 1

    def test_framework_dashboard_shows_for_live_if_declaration_exists(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(status='live')
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath(
            "//h1[normalize-space(string())=$b]",
            b="G-Cloud 7 documents",
        )) == 1

    def test_does_not_show_for_live_if_no_declaration(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(status='live')
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(declaration=None)
        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        assert res.status_code == 404

    @mock.patch('app.main.views.frameworks.send_email')
    def test_interest_registered_in_framework_on_post(self, send_email, data_api_client, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
            res = self.client.post("/suppliers/frameworks/digital-outcomes-and-specialists")

            assert res.status_code == 200
            data_api_client.register_framework_interest.assert_called_once_with(
                1234,
                "digital-outcomes-and-specialists",
                "email@email.com"
            )

    @mock.patch('app.main.views.frameworks.send_email')
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

            assert res.status_code == 200
            send_email.assert_called_once_with(
                ['email1', 'email2'],
                mock.ANY,
                'MANDRILL',
                'You started a G-Cloud 7 application',
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

            assert res.status_code == 200
            assert data_api_client.register_framework_interest.called is False

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

            assert res.status_code == 200

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
            assert res.status_code == 200

            doc = html.fromstring(res.get_data(as_text=True))

            heading = doc.xpath('//div[@class="summary-item-lede"]//h2[@class="summary-item-heading"]')
            assert len(heading) > 0
            assert u"G-Cloud 7 is closed for applications" in heading[0].xpath('text()')[0]
            assert u"You didn't submit an application." in heading[0].xpath('../p[1]/text()')[0]

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
            assert res.status_code == 200

            doc = html.fromstring(res.get_data(as_text=True))
            heading = doc.xpath('//div[@class="summary-item-lede"]//h2[@class="summary-item-heading"]')
            assert len(heading) > 0
            assert u"G-Cloud 7 is closed for applications" in heading[0].xpath('text()')[0]
            lede = doc.xpath('//div[@class="summary-item-lede"]')
            assert u"You made your supplier declaration and submitted 1 service for consideration." in \
                lede[0].xpath('./p[1]/text()')[0]
            assert u"We’ll let you know the result of your application by " in \
                lede[0].xpath('./p[2]/text()')[0]

    def test_declaration_status_when_complete(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

            res = self.client.get("/suppliers/frameworks/g-cloud-7")
            assert res.status_code == 200

            doc = html.fromstring(res.get_data(as_text=True))
            assert len(doc.xpath(u'//p/strong[contains(text(), "You’ve made the supplier declaration")]')) == 1

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
            assert res.status_code == 200

            doc = html.fromstring(res.get_data(as_text=True))
            assert len(doc.xpath('//p[contains(text(), "You need to finish making the supplier declaration")]')) == 1

    def test_declaration_status_when_not_complete(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.side_effect = APIError(mock.Mock(status_code=404))

            res = self.client.get("/suppliers/frameworks/g-cloud-7")
            assert res.status_code == 200

            doc = html.fromstring(res.get_data(as_text=True))
            assert len(doc.xpath('//p[contains(text(), "You need to make the supplier declaration")]')) == 1

    def test_downloads_shown_open_framework(self, data_api_client, s3):
        files = [
            ('updates/communications/', 'file 1', 'odt', '2015-01-01T14:00:00.000Z'),
            ('updates/clarifications/', 'file 2', 'odt', '2015-02-02T14:00:00.000Z'),
            ('', 'g-cloud-7-proposed-call-off', 'pdf', '2016-05-01T14:00:00.000Z'),
            ('', 'g-cloud-7-invitation', 'pdf', '2016-05-01T14:00:00.000Z'),
            ('', 'g-cloud-7-proposed-framework-agreement', 'pdf', '2016-06-01T14:00:00.000Z'),
            ('', 'g-cloud-7-reporting-template', 'xls', '2016-06-06T14:00:00.000Z'),
            # superfluous file that shouldn't be shown
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
            assert res.status_code == 200

            doc = html.fromstring(res.get_data(as_text=True))
            extracted_guidance_links = self._extract_guidance_links(doc)

            assert extracted_guidance_links == OrderedDict((
                ("Guidance", (
                    (
                        "Download the invitation to apply",
                        "/suppliers/frameworks/g-cloud-7/files/g-cloud-7-invitation.pdf",
                        None,
                        None,
                    ),
                    (
                        "Read about how to apply",
                        "https://www.gov.uk/guidance/g-cloud-suppliers-guide#how-to-apply",
                        None,
                        None,
                    ),
                )),
                ("Legal documents", (
                    (
                        "Download the proposed framework agreement",
                        "/suppliers/frameworks/g-cloud-7/files/g-cloud-7-proposed-framework-agreement.pdf",
                        "Wednesday 1 June 2016",
                        "2016-06-01T14:00:00.000Z",
                    ),
                    (
                        u"Download the proposed \u2018call-off\u2019 contract",
                        "/suppliers/frameworks/g-cloud-7/files/g-cloud-7-proposed-call-off.pdf",
                        "Sunday 1 May 2016",
                        "2016-05-01T14:00:00.000Z",
                    ),
                )),
                ("Communications", (
                    (
                        "View communications and ask clarification questions",
                        "/suppliers/frameworks/g-cloud-7/updates",
                        "Monday 2 February 2015",
                        "2015-02-02T14:00:00.000Z",
                    ),
                )),
                ("Reporting", (
                    (
                        "Download the reporting template",
                        "/suppliers/frameworks/g-cloud-7/files/g-cloud-7-reporting-template.xls",
                        None,
                        None,
                    ),
                )),
            ))
            assert not any(
                doc.xpath("//main//a[contains(@href, $href_part)]", href_part=href_part)
                for href_part in (
                    "g-cloud-7-final-framework-agreement.pdf",
                    "g-cloud-7-supplier-pack.zip",
                )
            )
            assert len(doc.xpath(
                "//main//p[contains(normalize-space(string()), $a)]",
                a="until 5pm BST, 22 September 2015",
            )) == 1
            assert not doc.xpath(
                "//main//table[normalize-space(string(./caption))=$b]",
                b="Agreement details",
            )

    def test_downloads_shown_open_framework_clarification_questions_closed(self, data_api_client, s3):
        files = [
            ('updates/communications/', 'file 1', 'odt', '2015-01-01T14:00:00.000Z'),
            ('updates/clarifications/', 'file 2', 'odt', '2015-02-02T14:00:00.000Z'),
            ('', 'g-cloud-7-proposed-call-off', 'pdf', '2016-05-01T14:00:00.000Z'),
            ('', 'g-cloud-7-invitation', 'pdf', '2016-05-01T14:00:00.000Z'),
            ('', 'g-cloud-7-proposed-framework-agreement', 'pdf', '2016-06-01T14:00:00.000Z'),
            ('', 'g-cloud-7-reporting-template', 'xls', '2016-06-06T14:00:00.000Z'),
            # superfluous file that shouldn't be shown
            ('', 'g-cloud-7-supplier-pack', 'zip', '2015-01-01T14:00:00.000Z'),
        ]

        s3.return_value.list.return_value = [
            _return_fake_s3_file_dict(
                'g-cloud-7/communications/{}'.format(section), filename, ext, last_modified=last_modified
            ) for section, filename, ext, last_modified in files
        ]

        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(
                status="open",
                clarification_questions_open=False,
            )
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
            res = self.client.get("/suppliers/frameworks/g-cloud-7")
            assert res.status_code == 200

            doc = html.fromstring(res.get_data(as_text=True))
            extracted_guidance_links = self._extract_guidance_links(doc)

            assert extracted_guidance_links == OrderedDict((
                ("Guidance", (
                    (
                        "Download the invitation to apply",
                        "/suppliers/frameworks/g-cloud-7/files/g-cloud-7-invitation.pdf",
                        None,
                        None,
                    ),
                    (
                        "Read about how to apply",
                        "https://www.gov.uk/guidance/g-cloud-suppliers-guide#how-to-apply",
                        None,
                        None,
                    ),
                )),
                ("Legal documents", (
                    (
                        "Download the proposed framework agreement",
                        "/suppliers/frameworks/g-cloud-7/files/g-cloud-7-proposed-framework-agreement.pdf",
                        "Wednesday 1 June 2016",
                        "2016-06-01T14:00:00.000Z",
                    ),
                    (
                        u"Download the proposed \u2018call-off\u2019 contract",
                        "/suppliers/frameworks/g-cloud-7/files/g-cloud-7-proposed-call-off.pdf",
                        "Sunday 1 May 2016",
                        "2016-05-01T14:00:00.000Z",
                    ),
                )),
                ("Communications", (
                    (
                        "View communications and clarification questions",
                        "/suppliers/frameworks/g-cloud-7/updates",
                        "Monday 2 February 2015",
                        "2015-02-02T14:00:00.000Z",
                    ),
                )),
                ("Reporting", (
                    (
                        "Download the reporting template",
                        "/suppliers/frameworks/g-cloud-7/files/g-cloud-7-reporting-template.xls",
                        None,
                        None,
                    ),
                )),
            ))
            assert not any(
                doc.xpath("//main//a[contains(@href, $href_part)]", href_part=href_part)
                for href_part in (
                    "g-cloud-7-final-framework-agreement.pdf",
                    "g-cloud-7-supplier-pack.zip",
                )
            )
            assert not doc.xpath(
                "//main[contains(normalize-space(string()), $a)]",
                a="until 5pm BST, 22 September 2015",
            )
            assert not doc.xpath(
                "//main//table[normalize-space(string(./caption))=$b]",
                b="Agreement details",
            )

    def test_final_agreement_download_shown_open_framework(self, data_api_client, s3):
        files = [
            ('updates/communications/', 'file 1', 'odt', '2015-01-01T14:00:00.000Z'),
            ('updates/clarifications/', 'file 2', 'odt', '2015-02-02T14:00:00.000Z'),
            ('', 'g-cloud-7-proposed-call-off', 'pdf', '2016-05-01T14:00:00.000Z'),
            ('', 'g-cloud-7-invitation', 'pdf', '2016-05-01T14:00:00.000Z'),
            ('', 'g-cloud-7-reporting-template', 'xls', '2016-06-06T14:00:00.000Z'),
            ('', 'g-cloud-7-final-framework-agreement', 'pdf', '2016-06-02T14:00:00.000Z'),
            # present but should be overridden by final agreement file
            ('', 'g-cloud-7-proposed-framework-agreement', 'pdf', '2016-06-11T14:00:00.000Z'),
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
            assert res.status_code == 200

            doc = html.fromstring(res.get_data(as_text=True))
            extracted_guidance_links = self._extract_guidance_links(doc)

            assert extracted_guidance_links == OrderedDict((
                ("Guidance", (
                    (
                        "Download the invitation to apply",
                        "/suppliers/frameworks/g-cloud-7/files/g-cloud-7-invitation.pdf",
                        None,
                        None,
                    ),
                    (
                        "Read about how to apply",
                        "https://www.gov.uk/guidance/g-cloud-suppliers-guide#how-to-apply",
                        None,
                        None,
                    ),
                )),
                ("Legal documents", (
                    (
                        "Download the framework agreement",
                        "/suppliers/frameworks/g-cloud-7/files/g-cloud-7-final-framework-agreement.pdf",
                        "Thursday 2 June 2016",
                        "2016-06-02T14:00:00.000Z",
                    ),
                    (
                        u"Download the proposed \u2018call-off\u2019 contract",
                        "/suppliers/frameworks/g-cloud-7/files/g-cloud-7-proposed-call-off.pdf",
                        "Sunday 1 May 2016",
                        "2016-05-01T14:00:00.000Z",
                    ),
                )),
                ("Communications", (
                    (
                        "View communications and ask clarification questions",
                        "/suppliers/frameworks/g-cloud-7/updates",
                        "Monday 2 February 2015",
                        "2015-02-02T14:00:00.000Z",
                    ),
                )),
                ("Reporting", (
                    (
                        "Download the reporting template",
                        "/suppliers/frameworks/g-cloud-7/files/g-cloud-7-reporting-template.xls",
                        None,
                        None,
                    ),
                )),
            ))
            assert not any(
                doc.xpath("//main//a[contains(@href, $href_part)]", href_part=href_part)
                for href_part in (
                    "g-cloud-7-proposed-framework-agreement.pdf",
                    "g-cloud-7-supplier-pack.zip",
                )
            )
            assert len(doc.xpath(
                "//main//p[contains(normalize-space(string()), $a)]",
                a="until 5pm BST, 22 September 2015",
            )) == 1
            assert not doc.xpath(
                "//main//table[normalize-space(string(./caption))=$b]",
                b="Agreement details",
            )

    def test_no_updates_open_framework(self, data_api_client, s3):
        files = [
            ('', 'g-cloud-7-call-off', 'pdf', '2016-05-01T14:00:00.000Z'),
            ('', 'g-cloud-7-invitation', 'pdf', '2016-05-01T14:00:00.000Z'),
            ('', 'g-cloud-7-proposed-framework-agreement', 'pdf', '2016-06-01T14:00:00.000Z'),
            ('', 'g-cloud-7-reporting-template', 'xls', '2016-06-06T14:00:00.000Z'),
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
            assert res.status_code == 200

            doc = html.fromstring(res.get_data(as_text=True))
            extracted_guidance_links = self._extract_guidance_links(doc)

            assert (
                "View communications and ask clarification questions",
                "/suppliers/frameworks/g-cloud-7/updates",
                None,
                None,
            ) in extracted_guidance_links["Communications"]
            assert len(doc.xpath(
                "//main//p[contains(normalize-space(string()), $a)]",
                a="until 5pm BST, 22 September 2015",
            )) == 1
            assert not doc.xpath(
                "//main//table[normalize-space(string(./caption))=$b]",
                b="Agreement details",
            )

    def test_no_files_exist_open_framework(self, data_api_client, s3):
        s3.return_value.list.return_value = []

        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
            res = self.client.get("/suppliers/frameworks/g-cloud-7")
            assert res.status_code == 200

            doc = html.fromstring(res.get_data(as_text=True))
            extracted_guidance_links = self._extract_guidance_links(doc)

            assert extracted_guidance_links == OrderedDict((
                ("Guidance", (
                    (
                        "Read about how to apply",
                        "https://www.gov.uk/guidance/g-cloud-suppliers-guide#how-to-apply",
                        None,
                        None,
                    ),
                )),
                ("Communications", (
                    (
                        "View communications and ask clarification questions",
                        "/suppliers/frameworks/g-cloud-7/updates",
                        None,
                        None,
                    ),
                )),
            ))
            assert not any(
                doc.xpath(
                    "//a[contains(@href, $href_part) or normalize-space(string())=$label]",
                    href_part=href_part,
                    label=label,
                ) for href_part, label in (
                    (
                        "g-cloud-7-invitation.pdf",
                        "Download the invitation to apply",
                    ),
                    (
                        "g-cloud-7-proposed-framework-agreement.pdf",
                        "Download the proposed framework agreement",
                    ),
                    (
                        "g-cloud-7-call-off.pdf",
                        u"Download the proposed \u2018call-off\u2019 contract",
                    ),
                    (
                        "g-cloud-7-reporting-template.xls",
                        "Download the reporting template",
                    ),
                    (
                        "result-letter.pdf",
                        "Download your application result letter",
                    ),
                )
            )
            assert len(doc.xpath(
                "//main//p[contains(normalize-space(string()), $a)]",
                a="until 5pm BST, 22 September 2015",
            )) == 1
            assert not doc.xpath(
                "//main//table[normalize-space(string(./caption))=$b]",
                b="Agreement details",
            )

    def test_returns_404_if_framework_does_not_exist(self, data_api_client, s3):
        with self.app.test_client():
            self.login()
            data_api_client.get_framework.side_effect = APIError(mock.Mock(status_code=404))

            res = self.client.get('/suppliers/frameworks/does-not-exist')

            assert res.status_code == 404

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

            assert u'Download your application result letter' in data

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

            assert u'Download your application result letter' not in data

    def test_result_letter_is_not_shown_when_no_application(self, data_api_client, s3):
        with self.app.test_client():
            self.login()
            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.find_draft_services.return_value = {
                "services": [
                    {'serviceName': 'A service', 'status': 'not-submitted'}
                ]
            }
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

            res = self.client.get("/suppliers/frameworks/g-cloud-7")

            data = res.get_data(as_text=True)

            assert u'Download your application result letter' not in data

    def test_link_to_unsigned_framework_agreement_is_shown_if_supplier_is_on_framework(self, data_api_client, s3):
        with self.app.test_client():
            self.login()
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

            assert u'Sign and return your framework agreement' in data
            assert u'Download your countersigned framework agreement' not in data

    def test_pending_success_message_is_explicit_if_supplier_is_on_framework(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(status='standstill')
        data_api_client.find_draft_services.return_value = {
            "services": [
                {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
            ]
        }
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(on_framework=True)
        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        data = res.get_data(as_text=True)

        for success_message in [
            u'Your application was successful. '
                u'You must return a signed framework agreement signature page before you can '
                u'sell services on the Digital Marketplace.',
            u'Download your application award letter (.pdf)',
            u'This letter is a record of your successful G-Cloud 7 application.'
        ]:
            assert success_message in data

        for equivocal_message in [
            u'You made your supplier declaration and submitted 1 service.',
            u'Download your application result letter (.pdf)',
            u'This letter informs you if your G-Cloud 7 application has been successful.'
        ]:
            assert equivocal_message not in data

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

            assert u'Sign and return your framework agreement' not in data

    def test_pending_success_message_is_equivocal_if_supplier_is_on_framework(self, data_api_client, s3):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(status='standstill')
        data_api_client.find_draft_services.return_value = {
            "services": [
                {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
            ]
        }
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(on_framework=False)
        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        data = res.get_data(as_text=True)

        for success_message in [
            u'Your application was successful. You\'ll be able to sell services when the G-Cloud 7 framework is live',
            u'Download your application award letter (.pdf)',
            u'This letter is a record of your successful G-Cloud 7 application.'
        ]:
            assert success_message not in data

        for equivocal_message in [
            u'You made your supplier declaration and submitted 1 service.',
            u'Download your application result letter (.pdf)',
            u'This letter informs you if your G-Cloud 7 application has been successful.'
        ]:
            assert equivocal_message in data

    def test_countersigned_framework_agreement_non_fav_framework(self, data_api_client, s3):
        # "fav" being "frameworkAgreementVersion"
        files = [
            ('', 'g-cloud-7-final-call-off', 'pdf', '2016-05-01T14:00:00.000Z'),
            ('', 'g-cloud-7-invitation', 'pdf', '2016-05-01T14:00:00.000Z'),
            ('', 'g-cloud-7-final-framework-agreement', 'pdf', '2016-06-01T14:00:00.000Z'),
            ('', 'g-cloud-7-reporting-template', 'xls', '2016-06-06T14:00:00.000Z'),
        ]

        s3.return_value.list.return_value = [
            _return_fake_s3_file_dict(
                'g-cloud-7/communications/{}'.format(section), filename, ext, last_modified=last_modified
            ) for section, filename, ext, last_modified in files
        ]

        with self.app.test_client():
            self.login()
            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.find_draft_services.return_value = {
                "services": [
                    {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
                ]
            }
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True,
                agreement_returned=True,
                agreement_details=self._boring_agreement_details,
                agreement_path='pathy/mc/path.face',
                countersigned=True,
                countersigned_path='g-cloud-7/agreements/1234/1234-countersigned-agreement.pdf',
            )

            res = self.client.get("/suppliers/frameworks/g-cloud-7")
            assert res.status_code == 200

            data = res.get_data(as_text=True)

            doc = html.fromstring(data)

            assert not doc.xpath(
                "//main//a[@href=$href or normalize-space(string())=$label]",
                href="/frameworks/g-cloud-7/agreement",
                label="Sign and return your framework agreement",
            )

            extracted_guidance_links = self._extract_guidance_links(doc)

            assert extracted_guidance_links == OrderedDict((
                ("Legal documents", (
                    (
                        'Download the standard framework agreement',
                        '/suppliers/frameworks/g-cloud-7/files/g-cloud-7-final-framework-agreement.pdf',
                        None,
                        None,
                    ),
                    (
                        "Download your signed framework agreement",
                        "/suppliers/frameworks/g-cloud-7/agreements/pathy/mc/path.face",
                        None,
                        None,
                    ),
                    (
                        u"Download your countersigned framework agreement",
                        "/suppliers/frameworks/g-cloud-7/agreements/countersigned-agreement.pdf",
                        None,
                        None,
                    ),
                    (
                        'Download your application result letter',
                        '/suppliers/frameworks/g-cloud-7/agreements/result-letter.pdf',
                        None,
                        None,
                    ),
                    (
                        'Download the call-off contract template',
                        '/suppliers/frameworks/g-cloud-7/files/g-cloud-7-final-call-off.pdf',
                        None,
                        None,
                    ),
                )),
                ("Guidance", (
                    (
                        'Download the invitation to apply',
                        '/suppliers/frameworks/g-cloud-7/files/g-cloud-7-invitation.pdf',
                        None,
                        None,
                    ),
                    (
                        "Read about how to sell your services",
                        "https://www.gov.uk/guidance/g-cloud-suppliers-guide#how-to-apply",
                        None,
                        None,
                    ),
                )),
                ("Communications", (
                    (
                        "View communications and clarification questions",
                        "/suppliers/frameworks/g-cloud-7/updates",
                        None,
                        None,
                    ),
                )),
                ('Reporting', (
                    (
                        'Download the reporting template',
                        '/suppliers/frameworks/g-cloud-7/files/g-cloud-7-reporting-template.xls',
                        None,
                        None,
                    ),
                )),
            ))
            assert not doc.xpath(
                "//main//table[normalize-space(string(./caption))=$b]",
                b="Agreement details",
            )
            assert not doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="You can start selling your",
            )
            # neither of these should exist because it's a pre-frameworkAgreementVersion framework
            assert not doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your original and counterpart signature pages",
            )
            assert not doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your framework agreement signature page has been sent to the Crown Commercial Service",
            )

    def test_countersigned_framework_agreement_fav_framework(self, data_api_client, s3):
        # "fav" being "frameworkAgreementVersion"
        files = [
            ('', 'g-cloud-8-final-call-off', 'pdf', '2016-05-01T14:00:00.000Z'),
            ('', 'g-cloud-8-invitation', 'pdf', '2016-05-01T14:00:00.000Z'),
            ('', 'g-cloud-8-final-framework-agreement', 'pdf', '2016-06-01T14:00:00.000Z'),
            ('', 'g-cloud-8-reporting-template', 'xls', '2016-06-06T14:00:00.000Z'),
        ]

        s3.return_value.list.return_value = [
            _return_fake_s3_file_dict(
                'g-cloud-8/communications/{}'.format(section), filename, ext, last_modified=last_modified
            ) for section, filename, ext, last_modified in files
        ]

        with self.app.test_client():
            self.login()
            data_api_client.get_framework.return_value = get_g_cloud_8()
            data_api_client.find_draft_services.return_value = {
                "services": [
                    {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
                ]
            }
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True,
                agreement_returned=True,
                agreement_details=self._boring_agreement_details,
                agreement_path='pathy/mc/path.face',
                agreement_returned_at=self._boring_agreement_returned_at,
                countersigned=True,
                countersigned_path='g-cloud-8/agreements/1234/1234-countersigned-agreement.pdf',
            )

            res = self.client.get("/suppliers/frameworks/g-cloud-8")
            assert res.status_code == 200

            data = res.get_data(as_text=True)

            doc = html.fromstring(data)

            assert not doc.xpath(
                "//main//a[@href=$href or normalize-space(string())=$label]",
                href="/frameworks/g-cloud-8/agreement",
                label="Sign and return your framework agreement",
            )
            assert not doc.xpath(
                "//main//a[@href=$href or normalize-space(string())=$label]",
                href="/suppliers/frameworks/g-cloud-7/agreements/result-letter.pdf",
                label="Download your application result letter",
            )

            extracted_guidance_links = self._extract_guidance_links(doc)

            assert extracted_guidance_links == OrderedDict((
                ("Legal documents", (
                    (
                        'Read the standard framework agreement',
                        'https://www.gov.uk/government/publications/g-cloud-8-framework-agreement',
                        None,
                        None,
                    ),
                    (
                        u"Download your \u2018original\u2019 framework agreement signature page",
                        "/suppliers/frameworks/g-cloud-8/agreements/pathy/mc/path.face",
                        None,
                        None,
                    ),
                    (
                        u"Download your \u2018counterpart\u2019 framework agreement signature page",
                        "/suppliers/frameworks/g-cloud-8/agreements/countersigned-agreement.pdf",
                        None,
                        None,
                    ),
                    (
                        'Download the call-off contract template',
                        '/suppliers/frameworks/g-cloud-8/files/g-cloud-8-final-call-off.pdf',
                        None,
                        None,
                    ),
                )),
                ("Guidance", (
                    (
                        'Download the invitation to apply',
                        '/suppliers/frameworks/g-cloud-8/files/g-cloud-8-invitation.pdf',
                        None,
                        None,
                    ),
                    (
                        "Read about how to sell your services",
                        "https://www.gov.uk/guidance/g-cloud-suppliers-guide#how-to-apply",
                        None,
                        None,
                    ),
                )),
                ("Communications", (
                    (
                        "View communications and clarification questions",
                        "/suppliers/frameworks/g-cloud-8/updates",
                        None,
                        None,
                    ),
                )),
                ('Reporting', (
                    (
                        'Download the reporting template',
                        '/suppliers/frameworks/g-cloud-8/files/g-cloud-8-reporting-template.xls',
                        None,
                        None,
                    ),
                )),
            ))
            assert not doc.xpath(
                "//main//table[normalize-space(string(./caption))=$b]",
                b="Agreement details",
            )
            assert not doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="You can start selling your",
            )
            assert doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your original and counterpart signature pages",
            )
            assert not doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your framework agreement signature page has been sent to the Crown Commercial Service",
            )

    def test_shows_returned_agreement_details(self, data_api_client, s3):
        with self.app.test_client():
            self.login()
            data_api_client.get_framework.return_value = get_g_cloud_8()
            data_api_client.find_draft_services.return_value = {
                "services": [
                    {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
                ]
            }
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True,
                agreement_returned=True,
                agreement_details=self._boring_agreement_details,
                agreement_path='g-cloud-8/agreements/123-framework-agreement.pdf',
                agreement_returned_at=self._boring_agreement_returned_at,
            )

            res = self.client.get("/suppliers/frameworks/g-cloud-8")
            assert res.status_code == 200

            data = res.get_data(as_text=True)
            doc = html.fromstring(data)

            assert not doc.xpath(
                "//main//a[@href=$href or normalize-space(string())=$label]",
                href="/frameworks/g-cloud-7/agreement",
                label="Sign and return your framework agreement",
            )
            assert not doc.xpath(
                "//main//a[@href=$href or normalize-space(string())=$label]",
                href="/suppliers/frameworks/g-cloud-7/agreements/result-letter.pdf",
                label="Download your application result letter",
            )

            extracted_guidance_links = self._extract_guidance_links(doc)
            assert extracted_guidance_links == OrderedDict((
                ('Legal documents', (
                    (
                        'Read the standard framework agreement',
                        'https://www.gov.uk/government/publications/g-cloud-8-framework-agreement',
                        None,
                        None,
                    ),
                    (
                        u'Download your \u2018original\u2019 framework agreement signature page',
                        '/suppliers/frameworks/g-cloud-8/agreements/framework-agreement.pdf',
                        None,
                        None,
                    ),
                )),
                ('Guidance', (
                    (
                        'Read about how to sell your services',
                        'https://www.gov.uk/guidance/g-cloud-suppliers-guide#how-to-apply',
                        None,
                        None,
                    ),
                )),
                ('Communications', (
                    (
                        'View communications and clarification questions',
                        '/suppliers/frameworks/g-cloud-8/updates',
                        None,
                        None,
                    ),
                )),
            ))
            extracted_signing_details_table_rows = self._extract_signing_details_table_rows(doc)
            assert extracted_signing_details_table_rows == \
                self._boring_agreement_details_expected_table_results
            assert len(doc.xpath(
                "//main//h1[normalize-space(string())=$b]",
                b="Your G-Cloud 8 application",
            )) == 1
            assert doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="You can start selling your",
            )
            assert not doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your original and counterpart signature pages",
            )
            assert doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your framework agreement signature page has been sent to the Crown Commercial Service",
            )

    def test_countersigned_but_no_countersigned_path(self, data_api_client, s3):
        with self.app.test_client():
            self.login()
            data_api_client.get_framework.return_value = get_g_cloud_8()
            data_api_client.find_draft_services.return_value = {
                "services": [
                    {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
                ]
            }
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True,
                agreement_returned=True,
                agreement_details=self._boring_agreement_details,
                agreement_path='g-cloud-8/agreements/123-framework-agreement.pdf',
                agreement_returned_at=self._boring_agreement_returned_at,
                countersigned=True,
                # note `countersigned_path` is not set: we're testing that the view behaves as though not countersigned
                # i.e. is not depending on the `countersigned` property
            )

            res = self.client.get("/suppliers/frameworks/g-cloud-8")
            assert res.status_code == 200

            data = res.get_data(as_text=True)
            doc = html.fromstring(data)

            assert not doc.xpath(
                "//main//a[@href=$href or normalize-space(string())=$label]",
                href="/frameworks/g-cloud-7/agreement",
                label="Sign and return your framework agreement",
            )

            extracted_guidance_links = self._extract_guidance_links(doc)
            assert extracted_guidance_links == OrderedDict((
                ('Legal documents', (
                    (
                        'Read the standard framework agreement',
                        'https://www.gov.uk/government/publications/g-cloud-8-framework-agreement',
                        None,
                        None,
                    ),
                    (
                        u'Download your \u2018original\u2019 framework agreement signature page',
                        '/suppliers/frameworks/g-cloud-8/agreements/framework-agreement.pdf',
                        None,
                        None,
                    ),
                )),
                ('Guidance', (
                    (
                        'Read about how to sell your services',
                        'https://www.gov.uk/guidance/g-cloud-suppliers-guide#how-to-apply',
                        None,
                        None,
                    ),
                )),
                ('Communications', (
                    (
                        'View communications and clarification questions',
                        '/suppliers/frameworks/g-cloud-8/updates',
                        None,
                        None,
                    ),
                )),
            ))
            extracted_signing_details_table_rows = self._extract_signing_details_table_rows(doc)
            assert extracted_signing_details_table_rows == \
                self._boring_agreement_details_expected_table_results
            assert len(doc.xpath(
                "//main//h1[normalize-space(string())=$b]",
                b="Your G-Cloud 8 application",
            )) == 1
            assert doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="You can start selling your",
            )
            assert not doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your original and counterpart signature pages",
            )
            assert doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your framework agreement signature page has been sent to the Crown Commercial Service",
            )

    def test_shows_contract_variation_link_after_agreement_returned(self, data_api_client, s3):
        with self.app.test_client():
            self.login()
            g8_with_variation = get_g_cloud_8()
            g8_with_variation['frameworks']['variations'] = {"1": {"createdAt": "2018-08-16"}}
            data_api_client.get_framework.return_value = g8_with_variation
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True,
                agreement_returned=True,
                agreement_details=self._boring_agreement_details,
                agreement_path='g-cloud-8/agreements/123-framework-agreement.pdf',
                agreement_returned_at=self._boring_agreement_returned_at,
            )

            res = self.client.get("/suppliers/frameworks/g-cloud-8")
            assert res.status_code == 200

            data = res.get_data(as_text=True)
            doc = html.fromstring(data)

            assert not doc.xpath(
                "//main//a[@href=$href or normalize-space(string())=$label]",
                href="/frameworks/g-cloud-7/agreement",
                label="Sign and return your framework agreement",
            )

            extracted_guidance_links = self._extract_guidance_links(doc)
            assert extracted_guidance_links == OrderedDict((
                ('Legal documents', (
                    (
                        'Read the standard framework agreement',
                        'https://www.gov.uk/government/publications/g-cloud-8-framework-agreement',
                        None,
                        None,
                    ),
                    (
                        u'Download your \u2018original\u2019 framework agreement signature page',
                        '/suppliers/frameworks/g-cloud-8/agreements/framework-agreement.pdf',
                        None,
                        None,
                    ),
                    (
                        'Read the proposed contract variation',
                        '/suppliers/frameworks/g-cloud-8/contract-variation/1',
                        None,
                        None,
                    ),
                )),
                ('Guidance', (
                    (
                        'Read about how to sell your services',
                        'https://www.gov.uk/guidance/g-cloud-suppliers-guide#how-to-apply',
                        None,
                        None,
                    ),
                )),
                ('Communications', (
                    (
                        'View communications and clarification questions',
                        '/suppliers/frameworks/g-cloud-8/updates',
                        None,
                        None,
                    ),
                )),
            ))
            extracted_signing_details_table_rows = self._extract_signing_details_table_rows(doc)
            assert extracted_signing_details_table_rows == \
                self._boring_agreement_details_expected_table_results
            assert doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="You can start selling your",
            )
            assert not doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your original and counterpart signature pages",
            )
            assert doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your framework agreement signature page has been sent to the Crown Commercial Service",
            )

    def test_does_not_show_contract_variation_link_if_feature_flagged_off(self, data_api_client, s3):
        with self.app.test_client():
            self.app.config['FEATURE_FLAGS_CONTRACT_VARIATION'] = False
            self.login()
            g8_with_variation = get_g_cloud_8()
            g8_with_variation['frameworks']['variations'] = {"1": {"createdAt": "2018-08-16"}}
            data_api_client.get_framework.return_value = g8_with_variation
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True,
                agreement_returned=True,
                agreement_details=self._boring_agreement_details,
                agreement_path='g-cloud-8/agreements/123-framework-agreement.pdf',
                agreement_returned_at=self._boring_agreement_returned_at,
            )

            res = self.client.get("/suppliers/frameworks/g-cloud-8")
            assert res.status_code == 200

            data = res.get_data(as_text=True)
            doc = html.fromstring(data)

            assert not doc.xpath(
                "//main//a[@href=$href or normalize-space(string())=$label]",
                href="/frameworks/g-cloud-7/agreement",
                label="Sign and return your framework agreement",
            )

            assert not doc.xpath(
                "//main//a[contains(@href, $href_part) or normalize-space(string())=$label]",
                href_part="contract-variation/1",
                label="Read the proposed contract variation",
            )
            extracted_signing_details_table_rows = self._extract_signing_details_table_rows(doc)
            assert extracted_signing_details_table_rows == \
                self._boring_agreement_details_expected_table_results
            assert doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="You can start selling your",
            )
            assert not doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your original and counterpart signature pages",
            )
            assert doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your framework agreement signature page has been sent to the Crown Commercial Service",
            )

    def test_does_not_show_contract_variation_link_if_no_variation(self, data_api_client, s3):
        with self.app.test_client():
            self.login()
            data_api_client.get_framework.return_value = get_g_cloud_8()
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True,
                agreement_returned=True,
                agreement_details=self._boring_agreement_details,
                agreement_path='g-cloud-8/agreements/123-framework-agreement.pdf',
                agreement_returned_at=self._boring_agreement_returned_at,
            )

            res = self.client.get("/suppliers/frameworks/g-cloud-8")
            assert res.status_code == 200

            data = res.get_data(as_text=True)
            doc = html.fromstring(data)

            assert not doc.xpath(
                "//main//a[@href=$href or normalize-space(string())=$label]",
                href="/frameworks/g-cloud-7/agreement",
                label="Sign and return your framework agreement",
            )
            assert not doc.xpath(
                "//main//a[normalize-space(string())=$label]",
                label="Read the proposed contract variation",
            )
            extracted_signing_details_table_rows = self._extract_signing_details_table_rows(doc)
            assert extracted_signing_details_table_rows == \
                self._boring_agreement_details_expected_table_results
            assert doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="You can start selling your",
            )
            assert not doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your original and counterpart signature pages",
            )
            assert doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your framework agreement signature page has been sent to the Crown Commercial Service",
            )

    def test_does_not_show_contract_variation_link_if_agreement_not_returned(self, data_api_client, s3):
        with self.app.test_client():
            self.login()
            g8_with_variation = get_g_cloud_8()
            g8_with_variation['frameworks']['variations'] = {"1": {"createdAt": "2018-08-16"}}
            data_api_client.get_framework.return_value = g8_with_variation
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

            res = self.client.get("/suppliers/frameworks/g-cloud-8")
            assert res.status_code == 200

            data = res.get_data(as_text=True)
            doc = html.fromstring(data)

            assert not doc.xpath(
                "//main//a[@href=$href or normalize-space(string())=$label]",
                href="/frameworks/g-cloud-7/agreement",
                label="Sign and return your framework agreement",
            )
            assert not doc.xpath(
                "//main//a[contains(@href, $href_part) or normalize-space(string())=$label]",
                href_part="contract-variation/1",
                label="Read the proposed contract variation",
            )
            assert not doc.xpath(
                "//main//table[normalize-space(string(./caption))=$b]",
                b="Agreement details",
            )
            assert not doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="You can start selling your",
            )
            assert not doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your original and counterpart signature pages",
            )
            assert not doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your framework agreement signature page has been sent to the Crown Commercial Service",
            )

    def test_shows_contract_variation_alternate_link_text_after_agreed_by_ccs(self, data_api_client, s3):
        with self.app.test_client():
            self.login()
            g8_with_variation = get_g_cloud_8()
            g8_with_variation['frameworks']['variations'] = {
                "1": {
                    "createdAt": "2018-08-16",
                    "countersignedAt": "2018-10-01",
                    "countersignerName": "A.N. Other",
                    "countersignerRole": "Head honcho",
                },
            }
            data_api_client.get_framework.return_value = g8_with_variation
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True,
                agreement_returned=True,
                agreement_details=self._boring_agreement_details,
                agreement_returned_at=self._boring_agreement_returned_at,
                agreement_path='g-cloud-8/agreements/1234/1234-signed-agreement.pdf',
                agreed_variations={
                    "1": {
                        "agreedAt": "2016-08-19T15:47:08.116613Z",
                        "agreedUserId": 1,
                        "agreedUserEmail": "agreed@email.com",
                        "agreedUserName": u"William Drăyton",
                    },
                },
            )

            res = self.client.get("/suppliers/frameworks/g-cloud-8")
            assert res.status_code == 200

            data = res.get_data(as_text=True)
            doc = html.fromstring(data)

            assert not doc.xpath(
                "//main//a[@href=$href or normalize-space(string())=$label]",
                href="/frameworks/g-cloud-7/agreement",
                label="Sign and return your framework agreement",
            )

            extracted_guidance_links = self._extract_guidance_links(doc)
            assert extracted_guidance_links == OrderedDict((
                ('Legal documents', (
                    (
                        'Read the standard framework agreement',
                        'https://www.gov.uk/government/publications/g-cloud-8-framework-agreement',
                        None,
                        None,
                    ),
                    (
                        u'Download your \u2018original\u2019 framework agreement signature page',
                        '/suppliers/frameworks/g-cloud-8/agreements/signed-agreement.pdf',
                        None,
                        None,
                    ),
                    (
                        'View the signed contract variation',
                        '/suppliers/frameworks/g-cloud-8/contract-variation/1',
                        None,
                        None,
                    ),
                )),
                ('Guidance', (
                    (
                        'Read about how to sell your services',
                        'https://www.gov.uk/guidance/g-cloud-suppliers-guide#how-to-apply',
                        None,
                        None,
                    ),
                )),
                ('Communications', (
                    (
                        'View communications and clarification questions',
                        '/suppliers/frameworks/g-cloud-8/updates',
                        None,
                        None,
                    ),
                )),
            ))
            assert not doc.xpath(
                "//main//a[normalize-space(string())=$label]",
                label="Read the proposed contract variation",
            )
            assert doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="You can start selling your",
            )
            assert not doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your original and counterpart signature pages",
            )
            assert doc.xpath(
                "//main//p[contains(normalize-space(string()), $b)]",
                b="Your framework agreement signature page has been sent to the Crown Commercial Service",
            )

    @pytest.mark.parametrize('supplier_framework_kwargs,link_label,link_href', (
        ({'declaration': None}, 'Make supplier declaration', '/suppliers/frameworks/g-cloud-7/start-declaration'),
        ({}, 'Edit supplier declaration', '/suppliers/frameworks/g-cloud-7/declaration'),
    ))
    def test_make_or_edit_supplier_declaration_shows_correct_page(self, data_api_client, s3, supplier_framework_kwargs,
                                                                  link_label, link_href):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                **supplier_framework_kwargs)

            response = self.client.get('/suppliers/frameworks/g-cloud-7')
            document = html.fromstring(response.get_data(as_text=True))

            assert document.xpath("//a[normalize-space(string())=$link_label]/@href", link_label=link_label)[0] \
                == link_href


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

            assert res.status_code == 200
            assert u'Send document to CCS' in data
            assert u'Return your signed signature page' not in data

    def test_page_returns_404_if_framework_in_wrong_state(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)

            res = self.client.get("/suppliers/frameworks/g-cloud-7/agreement")

            assert res.status_code == 404

    def test_page_returns_404_if_supplier_not_on_framework(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=False)

            res = self.client.get("/suppliers/frameworks/g-cloud-7/agreement")

            assert res.status_code == 404

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

            assert res.status_code == 200
            assert u'/suppliers/frameworks/g-cloud-7/agreement' == doc.xpath('//form')[0].action
            assert u'Document uploaded Monday 2 November 2015 at 15:25' in data
            assert u'Your document has been uploaded' in data

    def test_upload_message_if_agreement_is_not_returned(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)

            res = self.client.get('/suppliers/frameworks/g-cloud-7/agreement')
            data = res.get_data(as_text=True)
            doc = html.fromstring(data)

            assert res.status_code == 200
            assert u'/suppliers/frameworks/g-cloud-7/agreement' == doc.xpath('//form')[0].action
            assert u'Document uploaded' not in data
            assert u'Your document has been uploaded' not in data

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
@mock.patch('app.main.views.frameworks.send_email')
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

            assert res.status_code == 404

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

            assert res.status_code == 404

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

            assert res.status_code == 400
            assert u'Document must not be empty' in res.get_data(as_text=True)

    @mock.patch('app.main.views.frameworks.generate_timestamped_document_upload_path')
    def test_api_is_not_updated_and_email_not_sent_if_upload_fails(
        self, generate_timestamped_document_upload_path, data_api_client, send_email, s3
    ):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)
            generate_timestamped_document_upload_path.return_value = 'my/path.pdf'
            s3.return_value.save.side_effect = S3ResponseError(500, 'All fail')

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b'doc'), 'test.pdf'),
                }
            )

            assert res.status_code == 503
            s3.return_value.save.assert_called_with(
                'my/path.pdf',
                mock.ANY,
                acl='private',
                download_filename='Supplier_Nme-1234-signed-framework-agreement.pdf'
            )

            assert data_api_client.create_framework_agreement.called is False
            assert data_api_client.update_framework_agreement.called is False
            assert data_api_client.sign_framework_agreement.called is False
            assert send_email.called is False

    @mock.patch('app.main.views.frameworks.generate_timestamped_document_upload_path')
    def test_email_is_not_sent_if_api_create_framework_agreement_fails(
        self, generate_timestamped_document_upload_path, data_api_client, send_email, s3
    ):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)
            generate_timestamped_document_upload_path.return_value = 'my/path.pdf'
            data_api_client.create_framework_agreement.side_effect = APIError(mock.Mock(status_code=500))

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b'doc'), 'test.pdf'),
                }
            )

            assert res.status_code == 500
            assert data_api_client.create_framework_agreement.called is True
            assert data_api_client.update_framework_agreement.called is False
            assert data_api_client.sign_framework_agreement.called is False
            assert send_email.called is False

    @mock.patch('app.main.views.frameworks.generate_timestamped_document_upload_path')
    def test_email_is_not_sent_if_api_update_framework_agreement_fails(
        self, generate_timestamped_document_upload_path, data_api_client, send_email, s3
    ):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)
            generate_timestamped_document_upload_path.return_value = 'my/path.pdf'
            data_api_client.update_framework_agreement.side_effect = APIError(mock.Mock(status_code=500))

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b'doc'), 'test.pdf'),
                }
            )

            assert res.status_code == 500
            assert data_api_client.create_framework_agreement.called is True
            assert data_api_client.update_framework_agreement.called is True
            assert data_api_client.sign_framework_agreement.called is False
            assert send_email.called is False

    @mock.patch('app.main.views.frameworks.generate_timestamped_document_upload_path')
    def test_email_is_not_sent_if_api_sign_framework_agreement_fails(
        self, generate_timestamped_document_upload_path, data_api_client, send_email, s3
    ):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)
            generate_timestamped_document_upload_path.return_value = 'my/path.pdf'
            data_api_client.sign_framework_agreement.side_effect = APIError(mock.Mock(status_code=500))

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b'doc'), 'test.pdf'),
                }
            )

            assert res.status_code == 500
            assert data_api_client.create_framework_agreement.called is True
            assert data_api_client.update_framework_agreement.called is True
            assert data_api_client.sign_framework_agreement.called is True
            assert send_email.called is False

    @mock.patch('app.main.views.frameworks.generate_timestamped_document_upload_path')
    def test_email_failure(
        self, generate_timestamped_document_upload_path, data_api_client, send_email, s3
    ):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)
            generate_timestamped_document_upload_path.return_value = 'my/path.pdf'
            send_email.side_effect = EmailError()

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b'doc'), 'test.pdf'),
                }
            )

            assert res.status_code == 503
            assert send_email.called is True

    @mock.patch('app.main.views.frameworks.generate_timestamped_document_upload_path')
    def test_upload_agreement_document(
        self, generate_timestamped_document_upload_path, data_api_client, send_email, s3
    ):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)
            data_api_client.create_framework_agreement.return_value = {
                "agreement": {"id": 20}
            }
            generate_timestamped_document_upload_path.return_value = 'my/path.pdf'

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b'doc'), 'test.pdf'),
                }
            )

            generate_timestamped_document_upload_path.assert_called_once_with(
                'g-cloud-7',
                1234,
                'agreements',
                'signed-framework-agreement.pdf'
            )

            s3.return_value.save.assert_called_with(
                'my/path.pdf',
                mock.ANY,
                acl='private',
                download_filename='Supplier_Nme-1234-signed-framework-agreement.pdf'
            )
            data_api_client.create_framework_agreement.assert_called_with(
                1234, 'g-cloud-7', 'email@email.com'
            )
            data_api_client.update_framework_agreement.assert_called_with(
                20,
                {"signedAgreementPath": 'my/path.pdf'},
                'email@email.com'
            )
            data_api_client.sign_framework_agreement.assert_called_with(
                20, 'email@email.com', {"uploaderUserId": 123}
            )
            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-7/agreement'

    @mock.patch('app.main.views.frameworks.generate_timestamped_document_upload_path')
    def test_upload_jpeg_agreement_document(
        self, generate_timestamped_document_upload_path, data_api_client, send_email, s3
    ):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)
            generate_timestamped_document_upload_path.return_value = 'my/path.jpg'

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/agreement',
                data={
                    'agreement': (StringIO(b'doc'), 'test.jpg'),
                }
            )

            s3.return_value.save.assert_called_with(
                'my/path.jpg',
                mock.ANY,
                acl='private',
                download_filename='Supplier_Nme-1234-signed-framework-agreement.jpg'
            )
            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-7/agreement'


@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
@mock.patch('dmutils.s3.S3')
class TestFrameworkAgreementDocumentDownload(BaseApplicationTest):
    def test_download_document_fails_if_no_supplier_framework(self, S3, data_api_client):
        data_api_client.get_supplier_framework_info.side_effect = APIError(mock.Mock(status_code=404))

        with self.app.test_client():
            self.login()

            res = self.client.get('/suppliers/frameworks/g-cloud-7/agreements/example.pdf')

            assert res.status_code == 404

    def test_download_document_fails_if_no_supplier_declaration(self, S3, data_api_client):
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(declaration=None)

        with self.app.test_client():
            self.login()

            res = self.client.get('/suppliers/frameworks/g-cloud-7/agreements/example.pdf')

            assert res.status_code == 404

    def test_download_document(self, S3, data_api_client):
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        uploader = mock.Mock()
        S3.return_value = uploader
        uploader.get_signed_url.return_value = 'http://url/path?param=value'

        with self.app.test_client():
            self.login()

            res = self.client.get('/suppliers/frameworks/g-cloud-7/agreements/example.pdf')

            assert res.status_code == 302
            assert res.location == 'http://asset-host/path?param=value'
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

            assert res.status_code == 302
            assert res.location == 'https://example/path?param=value'
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

            assert res.status_code == 302
            assert res.location == 'http://asset-host/path?param=value'
            uploader.get_signed_url.assert_called_with('g-cloud-7/communications/example.pdf')

    def test_download_document_returns_404_if_url_is_None(self, S3):
        uploader = mock.Mock()
        S3.return_value = uploader
        uploader.get_signed_url.return_value = None

        with self.app.test_client():
            self.login()

            res = self.client.get('/suppliers/frameworks/g-cloud-7/files/example.pdf')

            assert res.status_code == 404


@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
class TestStartSupplierDeclaration(BaseApplicationTest):
    def test_start_declaration_goes_to_declaration_overview_page(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

            response = self.client.get('/suppliers/frameworks/g-cloud-7/start-declaration')
            document = html.fromstring(response.get_data(as_text=True))

            assert document.xpath("//a[normalize-space(string(.))='Start your declaration']/@href")[0] \
                == '/suppliers/frameworks/g-cloud-7/declaration/reuse'


@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
class TestDeclarationOverviewSubmit(BaseApplicationTest):
    """
        Behaviour common to both GET and POST views on path /suppliers/frameworks/g-cloud-7/declaration
    """
    def test_supplier_not_interested(self, data_api_client, get_or_post):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.side_effect = _assert_args_and_return(
                self.framework(status="open"),
                "g-cloud-7",
            )
            data_api_client.get_supplier_framework_info.side_effect = _assert_args_and_raise(
                APIError(mock.Mock(status_code=404)),
                1234,
                "g-cloud-7",
            )
            data_api_client.set_supplier_declaration.side_effect = AssertionError("This shouldn't be called")

            response = getattr(self.client, get_or_post.lower())("/suppliers/frameworks/g-cloud-7/declaration")

            assert response.status_code == 404

    def test_framework_standstill(self, data_api_client, get_or_post):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.side_effect = _assert_args_and_return(
                self.framework(status="standstill"),
                "g-cloud-7",
            )
            data_api_client.get_supplier_framework_info.side_effect = _assert_args_and_return(
                self.supplier_framework(framework_slug="g-cloud-7"),
                1234,
                "g-cloud-7",
            )
            data_api_client.set_supplier_declaration.side_effect = AssertionError("This shouldn't be called")

            response = getattr(self.client, get_or_post.lower())("/suppliers/frameworks/g-cloud-7/declaration")

            assert response.status_code == 404

    def test_framework_unknown(self, data_api_client, get_or_post):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.side_effect = _assert_args_and_raise(
                APIError(mock.Mock(status_code=404)),
                "muttoning-clouds",
            )
            data_api_client.get_supplier_framework_info.side_effect = _assert_args_and_raise(
                APIError(mock.Mock(status_code=404)),
                1234,
                "muttoning-clouds",
            )
            data_api_client.set_supplier_declaration.side_effect = AssertionError("This shouldn't be called")

            response = getattr(self.client, get_or_post.lower())("/suppliers/frameworks/muttoning-clouds/declaration")

            assert response.status_code == 404


@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
class TestDeclarationOverview(BaseApplicationTest):
    @staticmethod
    def _extract_section_information(doc, section_title):
        """
            given a section (full text) name, returns that section's relevant information in a tuple (format described
            in comments)
        """
        tables = doc.xpath(
            "//table[preceding::h2[1][normalize-space(string())=$section_title]]",
            section_title=section_title,
        )
        assert len(tables) == 1
        table = tables[0]

        edit_as = doc.xpath(
            "//a[@class='summary-change-link'][preceding::h2[1][normalize-space(string())=$section_title]]",
            section_title=section_title,
        )
        assert [a.xpath("normalize-space(string())") for a in edit_as] == ["Edit"]
        edit_a = edit_as[0]

        return (
            # table caption text
            table.xpath("normalize-space(string(./caption))"),
            # "Edit" link href
            edit_a.xpath("@href")[0],
            tuple(
                (
                    # contents of row heading
                    row.xpath("normalize-space(string(./td[@class='summary-item-field-first-two-thirds']))"),
                    # full text contents of row "value"
                    row.xpath("normalize-space(string(./td[@class='summary-item-field']))"),
                    # full text contents of each a element in row value
                    tuple(a.xpath("normalize-space(string())") for a in row.xpath(
                        "./td[@class='summary-item-field']//a"
                    )),
                    # href of each a element in row value
                    tuple(row.xpath("./td[@class='summary-item-field']//a/@href")),
                    # full text contents of each li element in row value
                    tuple(li.xpath("normalize-space(string())") for li in row.xpath(
                        "./td[@class='summary-item-field']//li"
                    )),
                ) for row in table.xpath(".//tr[contains(@class,'summary-item-row')]")
            )
        )

    @pytest.mark.parametrize("declaration,decl_valid,prefill_fw_slug,expected_pss,expected_gme,expected_dys", tuple(
        chain.from_iterable(chain(
        ((
            empty_declaration,  # noqa
            False,
            prefill_fw_slug,
            (
                "Providing suitable services",
                "/suppliers/frameworks/g-cloud-9/declaration/providing-suitable-services",
                (
                    (
                        "Services are cloud-related",
                        "Answer question",
                        ("Answer question",),
                        ("/suppliers/frameworks/g-cloud-9/declaration/providing-suitable-services#"
                         "servicesHaveOrSupport",),
                        (),
                    ),
                    (
                        "Services in scope for G-Cloud",
                        "Answer question",
                        ("Answer question",),
                        ("/suppliers/frameworks/g-cloud-9/declaration/providing-suitable-services#"
                         "servicesDoNotInclude",),
                        (),
                    ),
                    (
                        "Buyers pay for what they use",
                        "Answer question",
                        ("Answer question",),
                        ("/suppliers/frameworks/g-cloud-9/declaration/providing-suitable-services#payForWhatUse",),
                        (),
                    ),
                    (
                        "What your team will deliver",
                        "Answer question",
                        ("Answer question",),
                        ("/suppliers/frameworks/g-cloud-9/declaration/providing-suitable-"
                            "services#offerServicesYourselves",),
                        (),
                    ),
                    (
                        "Contractual responsibility and accountability",
                        "Answer question",
                        ("Answer question",),
                        ("/suppliers/frameworks/g-cloud-9/declaration/providing-suitable-services#fullAccountability",),
                        (),
                    ),
                ),
            ),
            (
                "Grounds for mandatory exclusion",
                "/suppliers/frameworks/g-cloud-9/declaration/grounds-for-mandatory-exclusion",
                (
                    (
                        "Organised crime or conspiracy convictions",
                        q_link_text_prefillable_section,
                        (q_link_text_prefillable_section,),
                        ("/suppliers/frameworks/g-cloud-9/declaration/grounds-for-mandatory-exclusion#conspiracy",),
                        (),
                    ),
                    (
                        "Bribery or corruption convictions",
                        q_link_text_prefillable_section,
                        (q_link_text_prefillable_section,),
                        ("/suppliers/frameworks/g-cloud-9/declaration/grounds-for-mandatory-"
                            "exclusion#corruptionBribery",),
                        (),
                    ),
                    (
                        "Fraud convictions",
                        q_link_text_prefillable_section,
                        (q_link_text_prefillable_section,),
                        ("/suppliers/frameworks/g-cloud-9/declaration/grounds-for-mandatory-"
                            "exclusion#fraudAndTheft",),
                        (),
                    ),
                    (
                        "Terrorism convictions",
                        q_link_text_prefillable_section,
                        (q_link_text_prefillable_section,),
                        ("/suppliers/frameworks/g-cloud-9/declaration/grounds-for-mandatory-exclusion#terrorism",),
                        (),
                    ),
                    (
                        "Organised crime convictions",
                        q_link_text_prefillable_section,
                        (q_link_text_prefillable_section,),
                        ("/suppliers/frameworks/g-cloud-9/declaration/grounds-for-mandatory-"
                            "exclusion#organisedCrime",),
                        (),
                    ),
                ),
            ),
            (
                u"How you’ll deliver your services",
                "/suppliers/frameworks/g-cloud-9/declaration/how-youll-deliver-your-services",
                (
                    (
                        "Subcontractors or consortia",
                        q_link_text_prefillable_section,
                        (q_link_text_prefillable_section,),
                        ("/suppliers/frameworks/g-cloud-9/declaration/how-youll-deliver-your-"
                            "services#subcontracting",),
                        (),
                    ),
                ),
            ),
        ) for empty_declaration in (None, {})),
        ((
            {
                "status": "started",
                "conspiracy": True,
                "corruptionBribery": False,
                "fraudAndTheft": True,
                "terrorism": False,
                "organisedCrime": True,
                "subcontracting": [
                    "yourself without the use of third parties (subcontractors)",
                    "as a prime contractor, using third parties (subcontractors) to provide all services",
                ],
            },
            False,
            prefill_fw_slug,
            (
                "Providing suitable services",
                "/suppliers/frameworks/g-cloud-9/declaration/providing-suitable-services",
                (
                    (
                        "Services are cloud-related",
                        "Answer question",
                        ("Answer question",),
                        ("/suppliers/frameworks/g-cloud-9/declaration/providing-suitable-services#"
                         "servicesHaveOrSupport",),
                        (),
                    ),
                    (
                        "Services in scope for G-Cloud",
                        "Answer question",
                        ("Answer question",),
                        ("/suppliers/frameworks/g-cloud-9/declaration/providing-suitable-services#"
                         "servicesDoNotInclude",),
                        (),
                    ),
                    (
                        "Buyers pay for what they use",
                        "Answer question",
                        ("Answer question",),
                        ("/suppliers/frameworks/g-cloud-9/declaration/providing-suitable-services#payForWhatUse",),
                        (),
                    ),
                    (
                        "What your team will deliver",
                        "Answer question",
                        ("Answer question",),
                        ("/suppliers/frameworks/g-cloud-9/declaration/providing-suitable-"
                            "services#offerServicesYourselves",),
                        (),
                    ),
                    (
                        "Contractual responsibility and accountability",
                        "Answer question",
                        ("Answer question",),
                        ("/suppliers/frameworks/g-cloud-9/declaration/providing-suitable-services#fullAccountability",),
                        (),
                    ),
                ),
            ),
            (
                "Grounds for mandatory exclusion",
                "/suppliers/frameworks/g-cloud-9/declaration/grounds-for-mandatory-exclusion",
                (
                    (
                        "Organised crime or conspiracy convictions",
                        "Yes",
                        (),
                        (),
                        (),
                    ),
                    (
                        "Bribery or corruption convictions",
                        "No",
                        (),
                        (),
                        (),
                    ),
                    (
                        "Fraud convictions",
                        "Yes",
                        (),
                        (),
                        (),
                    ),
                    (
                        "Terrorism convictions",
                        "No",
                        (),
                        (),
                        (),
                    ),
                    (
                        "Organised crime convictions",
                        "Yes",
                        (),
                        (),
                        (),
                    ),
                ),
            ),
            (
                u"How you’ll deliver your services",
                "/suppliers/frameworks/g-cloud-9/declaration/how-youll-deliver-your-services",
                (
                    (
                        "Subcontractors or consortia",
                        "yourself without the use of third parties (subcontractors) as a prime contractor, using "
                            "third parties (subcontractors) to provide all services",
                        (),
                        (),
                        (
                            "yourself without the use of third parties (subcontractors)",
                            "as a prime contractor, using third parties (subcontractors) to provide all services",
                        ),
                    ),
                ),
            ),
        ),),
        ((
            dict(status=declaration_status, **(valid_g9_declaration_base())),
            True,
            prefill_fw_slug,
            (
                "Providing suitable services",
                "/suppliers/frameworks/g-cloud-9/declaration/providing-suitable-services",
                (
                    (
                        "Services are cloud-related",
                        "Yes",
                        (),
                        (),
                        (),
                    ),
                    (
                        "Services in scope for G-Cloud",
                        "Yes",
                        (),
                        (),
                        (),
                    ),
                    (
                        "Buyers pay for what they use",
                        "Yes",
                        (),
                        (),
                        (),
                    ),
                    (
                        "What your team will deliver",
                        "No",
                        (),
                        (),
                        (),
                    ),
                    (
                        "Contractual responsibility and accountability",
                        "Yes",
                        (),
                        (),
                        (),
                    ),
                ),
            ),
            (
                "Grounds for mandatory exclusion",
                "/suppliers/frameworks/g-cloud-9/declaration/grounds-for-mandatory-exclusion",
                (
                    (
                        "Organised crime or conspiracy convictions",
                        "No",
                        (),
                        (),
                        (),
                    ),
                    (
                        "Bribery or corruption convictions",
                        "Yes",
                        (),
                        (),
                        (),
                    ),
                    (
                        "Fraud convictions",
                        "No",
                        (),
                        (),
                        (),
                    ),
                    (
                        "Terrorism convictions",
                        "Yes",
                        (),
                        (),
                        (),
                    ),
                    (
                        "Organised crime convictions",
                        "No",
                        (),
                        (),
                        (),
                    ),
                ),
            ),
            (
                u"How you’ll deliver your services",
                "/suppliers/frameworks/g-cloud-9/declaration/how-youll-deliver-your-services",
                (
                    (
                        "Subcontractors or consortia",
                        "yourself without the use of third parties (subcontractors)",
                        (),
                        (),
                        (),
                    ),
                ),
            ),
        ) for declaration_status in ("started", "complete",)),
    ) for prefill_fw_slug, q_link_text_prefillable_section in (
        (None, "Answer question",),
        ("some-previous-framework", "Review answer",),
    ))))
    def test_display(
            self,
            data_api_client,
            declaration,
            decl_valid,
            prefill_fw_slug,
            expected_pss,
            expected_gme,
            expected_dys,
            ):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.side_effect = _assert_args_and_return(
                self.framework(slug="g-cloud-9", name="G-Cloud 9", status="open"),
                "g-cloud-9",
            )
            data_api_client.get_supplier_framework_info.side_effect = _assert_args_and_return(
                self.supplier_framework(
                    framework_slug="g-cloud-9",
                    declaration=declaration,
                    prefill_declaration_from_framework_slug=prefill_fw_slug,
                ),
                1234,
                "g-cloud-9",
            )
            data_api_client.set_supplier_declaration.side_effect = AssertionError("This shouldn't be called")

            response = self.client.get("/suppliers/frameworks/g-cloud-9/declaration")
            assert response.status_code == 200
            doc = html.fromstring(response.get_data(as_text=True))

            assert [e.xpath("normalize-space(string())") for e in doc.xpath(
                "//nav//*[@role='breadcrumbs']//a",
            )] == [
                "Digital Marketplace",
                "Your account",
                "Apply to G-Cloud 9",
            ]
            assert doc.xpath(
                "//nav//*[@role='breadcrumbs']//a/@href",
            ) == [
                "/",
                "/suppliers",
                "/suppliers/frameworks/g-cloud-9",
            ]

            assert bool(doc.xpath(
                "//p[contains(normalize-space(string()), $t)][contains(normalize-space(string()), $f)]",
                t="You must answer all questions and make your declaration before",
                f="G-Cloud 9",
            )) is (not decl_valid)
            assert bool(doc.xpath(
                "//p[contains(normalize-space(string()), $t)][contains(normalize-space(string()), $f)]",
                t="You must make your declaration before",
                f="G-Cloud 9",
            )) is (decl_valid and declaration.get("status") != "complete")

            assert len(doc.xpath(
                "//p[contains(normalize-space(string()), $t)]",
                t="You can come back and edit your answers at any time before the deadline.",
            )) == (2 if decl_valid and declaration.get("status") != "complete" else 0)
            assert len(doc.xpath(
                "//p[contains(normalize-space(string()), $t)][not(contains(normalize-space(string()), $d))]",
                t="You can come back and edit your answers at any time",
                d="deadline",
            )) == (2 if decl_valid and declaration.get("status") == "complete" else 0)

            if prefill_fw_slug is None:
                assert not doc.xpath("//a[normalize-space(string())=$t]", t="Review answer")

            assert bool(doc.xpath(
                "//a[normalize-space(string())=$a or normalize-space(string())=$b]",
                a="Answer question",
                b="Review answer",
            )) is (not decl_valid)
            if not decl_valid:
                # assert that all links with the label "Answer question" or "Review answer" link to some subpage (by
                # asserting that there are none that don't, having previously determined that such-labelled links exist)
                assert not doc.xpath(
                    # we want the href to *contain* $u but not *be* $u
                    "//a[normalize-space(string())=$a or normalize-space(string())=$b]"
                    "[not(starts-with(@href, $u)) or @href=$u]",
                    a="Answer question",
                    b="Review answer",
                    u="/suppliers/frameworks/g-cloud-9/declaration/",
                )

            if decl_valid and declaration.get("status") != "complete":
                mdf_actions = doc.xpath(
                    "//form[@method='POST'][.//input[@value=$t][@type='submit']][.//input[@name='csrf_token']]/@action",
                    t="Make declaration",
                )
                assert len(mdf_actions) == 2
                assert all(
                    urljoin("/suppliers/frameworks/g-cloud-9/declaration", action) ==
                    "/suppliers/frameworks/g-cloud-9/declaration"
                    for action in mdf_actions
                )
            else:
                assert not doc.xpath("//input[@value=$t]", t="Make declaration")

            assert doc.xpath(
                "//a[normalize-space(string())=$t][@href=$u]",
                t="Return to application",
                u="/suppliers/frameworks/g-cloud-9",
            )

            assert self._extract_section_information(doc, "Providing suitable services") == expected_pss
            assert self._extract_section_information(doc, "Grounds for mandatory exclusion") == expected_gme
            assert self._extract_section_information(doc, u"How you’ll deliver your services") == expected_dys


@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
class TestDeclarationSubmit(BaseApplicationTest):
    @pytest.mark.parametrize("prefill_fw_slug", (None, "some-previous-framework",))
    @pytest.mark.parametrize("invalid_declaration", (
        None,
        {},
        {
            # not actually complete - only first section is
            "status": "complete",
            "unfairCompetition": False,
            "skillsAndResources": False,
            "offerServicesYourselves": False,
            "fullAccountability": True,
        },
    ))
    def test_invalid_declaration(self, data_api_client, invalid_declaration, prefill_fw_slug):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.side_effect = _assert_args_and_return(
                self.framework(slug="g-cloud-9", name="G-Cloud 9", status="open"),
                "g-cloud-9",
            )
            data_api_client.get_supplier_framework_info.side_effect = _assert_args_and_return(
                self.supplier_framework(
                    framework_slug="g-cloud-9",
                    declaration=invalid_declaration,
                    prefill_declaration_from_framework_slug=prefill_fw_slug,  # should have zero effect
                ),
                1234,
                "g-cloud-9",
            )
            data_api_client.set_supplier_declaration.side_effect = AssertionError("This shouldn't be called")

            response = self.client.post("/suppliers/frameworks/g-cloud-9/declaration")

            assert response.status_code == 400

    @pytest.mark.parametrize("prefill_fw_slug", (None, "some-previous-framework",))
    @pytest.mark.parametrize("declaration_status", ("started", "complete",))
    @mock.patch("dmutils.s3.S3")  # needed by the framework dashboard which our request gets redirected to
    def test_valid_declaration(self, s3, data_api_client, prefill_fw_slug, declaration_status):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.side_effect = _assert_args_and_return(
                self.framework(slug="g-cloud-9", name="G-Cloud 9", status="open"),
                "g-cloud-9",
            )
            data_api_client.get_supplier_framework_info.side_effect = _assert_args_and_return(
                self.supplier_framework(
                    framework_slug="g-cloud-9",
                    declaration=dict(status=declaration_status, **(valid_g9_declaration_base())),
                    prefill_declaration_from_framework_slug=prefill_fw_slug,  # should have zero effect
                ),
                1234,
                "g-cloud-9",
            )
            data_api_client.set_supplier_declaration.side_effect = _assert_args_and_return(
                dict(status="complete", **(valid_g9_declaration_base())),
                1234,
                "g-cloud-9",
                dict(status="complete", **(valid_g9_declaration_base())),
                "email@email.com",
            )

            response = self.client.post("/suppliers/frameworks/g-cloud-9/declaration", follow_redirects=True)

            # args of call are asserted by mock's side_effect
            assert data_api_client.set_supplier_declaration.called is True

            # this will be the response from the redirected-to view
            assert response.status_code == 200
            doc = html.fromstring(response.get_data(as_text=True))

            assert doc.xpath(
                "//*[@data-analytics='trackPageView'][@data-url=$k]",
                k="/suppliers/frameworks/g-cloud-9/declaration_complete",
            )


@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
class TestSupplierDeclaration(BaseApplicationTest):
    def test_get_with_no_previous_answers(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                framework_slug="g-cloud-7",
                declaration={}
            )
            data_api_client.get_supplier_declaration.side_effect = APIError(mock.Mock(status_code=404))

            res = self.client.get(
                '/suppliers/frameworks/g-cloud-7/declaration/g-cloud-7-essentials')

            assert res.status_code == 200
            doc = html.fromstring(res.get_data(as_text=True))
            assert doc.xpath('//input[@id="PR-1-yes"]/@checked') == []
            assert doc.xpath('//input[@id="PR-1-no"]/@checked') == []

    def test_get_with_with_previous_answers(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                framework_slug="g-cloud-7",
                declaration={"status": "started", "PR1": False}
            )

            res = self.client.get(
                '/suppliers/frameworks/g-cloud-7/declaration/g-cloud-7-essentials')

            assert res.status_code == 200
            doc = html.fromstring(res.get_data(as_text=True))
            assert len(doc.xpath('//input[@id="input-PR1-2"]/@checked')) == 1

    def test_get_with_with_prefilled_answers(self, data_api_client):
        with self.app.test_client():
            self.login()
            # Handle calls for both the current framework and for the framework to pre-fill from
            data_api_client.get_framework.side_effect = lambda framework_slug: {
                "g-cloud-9": self.framework(slug='g-cloud-9', name='G-Cloud 9', status='open'),
                "digital-outcomes-and-specialists-2": self.framework(slug='digital-outcomes-and-specialists-2',
                                                                     name='Digital Stuff 2', status='live'),
            }[framework_slug]

            # Current framework application information
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                framework_slug="g-cloud-9",
                declaration={"status": "started"},
                prefill_declaration_from_framework_slug="digital-outcomes-and-specialists-2"
            )

            # The previous declaration to prefill from
            data_api_client.get_supplier_declaration.return_value = {
                'declaration': self.supplier_framework(
                    framework_slug="digital-outcomes-and-specialists-2",
                    declaration={"status": "complete",
                                 "conspiracy": True,
                                 "corruptionBribery": False,
                                 "fraudAndTheft": True,
                                 "terrorism": False,
                                 "organisedCrime": False,
                                 },
                )["frameworkInterest"]["declaration"]
            }

            # The grounds-for-mandatory-exclusion section has "prefill: True" in the declaration manifest
            res = self.client.get(
                '/suppliers/frameworks/g-cloud-9/declaration/grounds-for-mandatory-exclusion')

            assert res.status_code == 200
            data_api_client.get_supplier_declaration.assert_called_once_with(1234, "digital-outcomes-and-specialists-2")
            doc = html.fromstring(res.get_data(as_text=True))

            # Radio buttons have been pre-filled with the correct answers
            assert len(doc.xpath('//input[@id="input-conspiracy-yes"]/@checked')) == 1
            assert len(doc.xpath('//input[@id="input-corruptionBribery-no"]/@checked')) == 1
            assert len(doc.xpath('//input[@id="input-fraudAndTheft-yes"]/@checked')) == 1
            assert len(doc.xpath('//input[@id="input-terrorism-no"]/@checked')) == 1
            assert len(doc.xpath('//input[@id="input-organisedCrime-no"]/@checked')) == 1

            # Blue banner message is shown at top of page
            assert doc.xpath('normalize-space(string(//div[@class="banner-information-without-action"]))') == \
                "Answers on this page are from an earlier declaration and need review."

            # Blue information messages are shown next to each question
            info_messages = doc.xpath('//div[@class="message-wrapper"]//span[@class="message-content"]')
            assert len(info_messages) == 5
            for message in info_messages:
                assert self.strip_all_whitespace(message.text) == self.strip_all_whitespace(
                    "This answer is from your Digital Stuff 2 declaration"
                )

    def test_get_with_with_partially_prefilled_answers(self, data_api_client):
        with self.app.test_client():
            self.login()
            # Handle calls for both the current framework and for the framework to pre-fill from
            data_api_client.get_framework.side_effect = lambda framework_slug: {
                "g-cloud-9": self.framework(slug='g-cloud-9', name='G-Cloud 9', status='open'),
                "digital-outcomes-and-specialists-2": self.framework(slug='digital-outcomes-and-specialists-2',
                                                                     name='Digital Stuff 2', status='live'),
            }[framework_slug]

            # Current framework application information
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                framework_slug="g-cloud-9",
                declaration={"status": "started"},
                prefill_declaration_from_framework_slug="digital-outcomes-and-specialists-2"
            )

            # The previous declaration to prefill from - missing "corruptionBribery" and "terrorism" keys
            data_api_client.get_supplier_declaration.return_value = {
                'declaration': self.supplier_framework(
                    framework_slug="digital-outcomes-and-specialists-2",
                    declaration={"status": "complete",
                                 "conspiracy": True,
                                 "fraudAndTheft": True,
                                 "organisedCrime": False,
                                 },
                )["frameworkInterest"]["declaration"]
            }

            # The grounds-for-mandatory-exclusion section has "prefill: True" in the declaration manifest
            res = self.client.get(
                '/suppliers/frameworks/g-cloud-9/declaration/grounds-for-mandatory-exclusion')

            assert res.status_code == 200
            data_api_client.get_supplier_declaration.assert_called_once_with(1234, "digital-outcomes-and-specialists-2")
            doc = html.fromstring(res.get_data(as_text=True))

            # Radio buttons have been pre-filled with the correct answers
            assert len(doc.xpath('//input[@id="input-conspiracy-yes"]/@checked')) == 1
            assert len(doc.xpath('//input[@id="input-fraudAndTheft-yes"]/@checked')) == 1
            assert len(doc.xpath('//input[@id="input-organisedCrime-no"]/@checked')) == 1

            # Radio buttons for missing keys exist but have not been pre-filled
            assert len(doc.xpath('//input[@id="input-corruptionBribery-no"]')) == 1
            assert len(doc.xpath('//input[@id="input-corruptionBribery-no"]/@checked')) == 0
            assert len(doc.xpath('//input[@id="input-corruptionBribery-yes"]/@checked')) == 0
            assert len(doc.xpath('//input[@id="input-terrorism-no"]')) == 1
            assert len(doc.xpath('//input[@id="input-terrorism-no"]/@checked')) == 0
            assert len(doc.xpath('//input[@id="input-terrorism-yes"]/@checked')) == 0

            # Blue banner message is shown at top of page
            assert doc.xpath('normalize-space(string(//div[@class="banner-information-without-action"]))') == \
                "Answers on this page are from an earlier declaration and need review."

            # Blue information messages are shown next to pre-filled questions only
            info_messages = doc.xpath('//div[@class="message-wrapper"]//span[@class="message-content"]')
            assert len(info_messages) == 3
            for message in info_messages:
                assert self.strip_all_whitespace(message.text) == self.strip_all_whitespace(
                    "This answer is from your Digital Stuff 2 declaration"
                )

    def test_answers_not_prefilled_if_section_has_already_been_saved(self, data_api_client):
        with self.app.test_client():
            self.login()
            # Handle calls for both the current framework and for the framework to pre-fill from
            data_api_client.get_framework.side_effect = lambda framework_slug: {
                "g-cloud-9": self.framework(slug='g-cloud-9', name='G-Cloud 9', status='open'),
                "digital-outcomes-and-specialists-2": self.framework(slug='digital-outcomes-and-specialists-2',
                                                                     name='Digital Stuff 2', status='live'),
            }[framework_slug]

            # Current framework application information with the grounds-for-mandatory-exclusion section complete
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                framework_slug="g-cloud-9",
                declaration={"status": "started",
                             "conspiracy": False,
                             "corruptionBribery": True,
                             "fraudAndTheft": False,
                             "terrorism": True,
                             "organisedCrime": False,
                             },
                prefill_declaration_from_framework_slug="digital-outcomes-and-specialists-2"
            )

            # The previous declaration to prefill from - has relevant answers but should not ever be called
            data_api_client.get_supplier_declaration.return_value = {
                'declaration': self.supplier_framework(
                    framework_slug="digital-outcomes-and-specialists-2",
                    declaration={"status": "complete",
                                 "conspiracy": True,
                                 "corruptionBribery": False,
                                 "fraudAndTheft": True,
                                 "terrorism": False,
                                 "organisedCrime": False,
                                 },
                )["frameworkInterest"]["declaration"]
            }

            # The grounds-for-mandatory-exclusion section has "prefill: True" in the declaration manifest
            res = self.client.get(
                '/suppliers/frameworks/g-cloud-9/declaration/grounds-for-mandatory-exclusion')

            assert res.status_code == 200
            doc = html.fromstring(res.get_data(as_text=True))

            # Previous framework and declaration have not been fetched
            data_api_client.get_framework.assert_called_once_with('g-cloud-9')
            assert data_api_client.get_supplier_declaration.called is False

            # Radio buttons have been filled with the current answers; not those from previous declaration
            assert len(doc.xpath('//input[@id="input-conspiracy-no"]/@checked')) == 1
            assert len(doc.xpath('//input[@id="input-corruptionBribery-yes"]/@checked')) == 1
            assert len(doc.xpath('//input[@id="input-fraudAndTheft-no"]/@checked')) == 1
            assert len(doc.xpath('//input[@id="input-terrorism-yes"]/@checked')) == 1
            assert len(doc.xpath('//input[@id="input-organisedCrime-no"]/@checked')) == 1

            # No blue banner message is shown at top of page
            assert len(doc.xpath('//div[@class="banner-information-without-action"]')) == 0

            # No blue information messages are shown next to each question
            info_messages = doc.xpath('//div[@class="message-wrapper"]//span[@class="message-content"]')
            assert len(info_messages) == 0

    def test_answers_not_prefilled_if_section_marked_as_prefill_false(self, data_api_client):
        with self.app.test_client():
            self.login()
            # Handle calls for both the current framework and for the framework to pre-fill from
            data_api_client.get_framework.side_effect = lambda framework_slug: {
                "g-cloud-9": self.framework(slug='g-cloud-9', name='G-Cloud 9', status='open'),
                "digital-outcomes-and-specialists-2": self.framework(slug='digital-outcomes-and-specialists-2',
                                                                     name='Digital Stuff 2', status='live'),
            }[framework_slug]

            # Current framework application information
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                framework_slug="g-cloud-9",
                declaration={"status": "started"},
                prefill_declaration_from_framework_slug="digital-outcomes-and-specialists-2"
            )

            # The previous declaration to prefill from - has relevant answers but should not ever be called
            data_api_client.get_supplier_declaration.return_value = {
                'declaration': self.supplier_framework(
                    framework_slug="digital-outcomes-and-specialists-2",
                    declaration={"status": "complete",
                                 "readUnderstoodGuidance": True,
                                 "understandTool": True,
                                 "understandHowToAskQuestions": False,
                                 },
                )["frameworkInterest"]["declaration"]
            }

            # The how-you-apply section has "prefill: False" in the declaration manifest
            res = self.client.get(
                '/suppliers/frameworks/g-cloud-9/declaration/how-you-apply')

            assert res.status_code == 200
            doc = html.fromstring(res.get_data(as_text=True))

            # Previous framework and declaration have not been fetched
            data_api_client.get_framework.assert_called_once_with('g-cloud-9')
            assert data_api_client.get_supplier_declaration.called is False

            # Radio buttons exist on page but have not been populated at all
            assert len(doc.xpath('//input[@id="input-readUnderstoodGuidance-no"]')) == 1
            assert len(doc.xpath('//input[@id="input-readUnderstoodGuidance-yes"]')) == 1
            assert len(doc.xpath('//input[@id="input-readUnderstoodGuidance-no"]/@checked')) == 0
            assert len(doc.xpath('//input[@id="input-readUnderstoodGuidance-yes"]/@checked')) == 0

            assert len(doc.xpath('//input[@id="input-understandTool-no"]')) == 1
            assert len(doc.xpath('//input[@id="input-understandTool-yes"]')) == 1
            assert len(doc.xpath('//input[@id="input-understandTool-no"]/@checked')) == 0
            assert len(doc.xpath('//input[@id="input-understandTool-yes"]/@checked')) == 0

            assert len(doc.xpath('//input[@id="input-understandHowToAskQuestions-no"]')) == 1
            assert len(doc.xpath('//input[@id="input-understandHowToAskQuestions-yes"]')) == 1
            assert len(doc.xpath('//input[@id="input-understandHowToAskQuestions-no"]/@checked')) == 0
            assert len(doc.xpath('//input[@id="input-understandHowToAskQuestions-yes"]/@checked')) == 0

            # No blue banner message is shown at top of page
            assert len(doc.xpath('//div[@class="banner-information-without-action"]')) == 0

            # No blue information messages are shown next to each question
            info_messages = doc.xpath('//div[@class="message-wrapper"]//span[@class="message-content"]')
            assert len(info_messages) == 0

    def test_post_valid_data(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                framework_slug="g-cloud-7",
                declaration={"status": "started"}
            )
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration/g-cloud-7-essentials',
                data=FULL_G7_SUBMISSION)

            assert res.status_code == 302
            assert data_api_client.set_supplier_declaration.called is True

    def test_post_valid_data_to_complete_declaration(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                framework_slug="g-cloud-7",
                declaration=FULL_G7_SUBMISSION
            )
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration/grounds-for-discretionary-exclusion',
                data=FULL_G7_SUBMISSION)

            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-7/declaration'
            assert data_api_client.set_supplier_declaration.called is True
            assert data_api_client.set_supplier_declaration.call_args[0][2]['status'] == 'complete'

    def test_post_valid_data_with_api_failure(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='open')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                framework_slug="g-cloud-7",
                declaration={"status": "started"}
            )
            data_api_client.set_supplier_declaration.side_effect = APIError(mock.Mock(status_code=400))

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-7/declaration/g-cloud-7-essentials',
                data=FULL_G7_SUBMISSION)

            assert res.status_code == 400

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

            assert res.status_code == 400
            assert data_api_client.set_supplier_declaration.called is False

            doc = html.fromstring(res.get_data(as_text=True))
            elems = doc.cssselect('#input-PR1-1')
            assert elems[0].value == 'True'

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

            assert res.status_code == 404
            assert data_api_client.set_supplier_declaration.called is False


@mock.patch('app.main.views.frameworks.data_api_client')
@mock.patch('dmutils.s3.S3')
class TestFrameworkUpdatesPage(BaseApplicationTest):

    def _assert_page_title_and_table_headings(self, doc, tables_exist=True):

        assert self.strip_all_whitespace('G-Cloud 7 updates') in self.strip_all_whitespace(doc.xpath('//h1')[0].text)

        section_names = [
            'Communications',
            'Clarification questions and answers',
        ]

        headers = doc.xpath('//div[contains(@class, "updates-document-tables")]/h2[@class="summary-item-heading"]')
        assert len(headers) == 2
        for index, section_name in enumerate(section_names):
            assert self.strip_all_whitespace(section_name) in self.strip_all_whitespace(headers[index].text)

        if tables_exist:
            table_captions = doc.xpath('//div[contains(@class, "updates-document-tables")]/table/caption')
            assert len(table_captions) == 2
            for index, section_name in enumerate(section_names):
                assert self.strip_all_whitespace(section_name) in self.strip_all_whitespace(table_captions[index].text)

    def test_should_be_a_503_if_connecting_to_amazon_fails(self, s3, data_api_client):
        data_api_client.get_framework.return_value = self.framework('open')
        # if s3 throws a 500-level error
        s3.side_effect = S3ResponseError(500, 'Amazon has collapsed. The internet is over.')

        with self.app.test_client():
            self.login()

            response = self.client.get(
                '/suppliers/frameworks/g-cloud-7/updates'
            )

            assert response.status_code == 503
            assert self.strip_all_whitespace(u"<h1>Sorry, we’re experiencing technical difficulties</h1>") in \
                self.strip_all_whitespace(response.get_data(as_text=True))

    def test_empty_messages_exist_if_no_files_returned(self, s3, data_api_client):
        data_api_client.get_framework.return_value = self.framework('open')

        with self.app.test_client():
            self.login()

            response = self.client.get(
                '/suppliers/frameworks/g-cloud-7/updates'
            )

            assert response.status_code == 200
            doc = html.fromstring(response.get_data(as_text=True))
            self._assert_page_title_and_table_headings(doc, tables_exist=False)

            for empty_message in [
                '<p class="summary-item-no-content">No communications have been sent out.</p>',
                '<p class="summary-item-no-content">No clarification questions and answers have been posted yet.</p>',
            ]:
                assert self.strip_all_whitespace(empty_message) in \
                    self.strip_all_whitespace(response.get_data(as_text=True))

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
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

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
                assert len(item_rows) == 2

                # test that the file names and urls are right
                for row in item_rows:
                    section, filename, ext = files.pop(0)
                    filename_link = row.find('.//a[@class="document-link-with-icon"]')

                    assert filename in filename_link.text_content()
                    assert filename_link.get('href') == '/suppliers/frameworks/g-cloud-7/files/{}{}.{}'.format(
                        section,
                        filename.replace(' ', '%20'),
                        ext,
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
                assert len(item_rows) == 1

                # test that the file names and urls are right
                for row in item_rows:
                    section, filename, ext = files.pop(0)
                    filename_link = row.find('.//a[@class="document-link-with-icon"]')

                    assert filename in filename_link.text_content()
                    assert filename_link.get('href') == '/suppliers/frameworks/g-cloud-7/files/{}{}.{}'.format(
                        section,
                        filename.replace(' ', '%20'),
                        ext,
                    )

    def test_question_box_is_shown_if_countersigned_agreement_is_not_yet_returned(self, s3, data_api_client):
        data_api_client.get_framework.return_value = self.framework('live', clarification_questions_open=False)
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        with self.app.test_client():
            self.login()

            response = self.client.get('/suppliers/frameworks/g-cloud-7/updates')
            data = response.get_data(as_text=True)

            assert response.status_code == 200
            assert u'Ask a question about your G-Cloud 7 application' in data

    def test_no_question_box_shown_if_countersigned_agreement_is_returned(self, s3, data_api_client):
        data_api_client.get_framework.return_value = self.framework('live', clarification_questions_open=False)
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(countersigned_path="path")

        with self.app.test_client():
            self.login()

            response = self.client.get('/suppliers/frameworks/g-cloud-7/updates')
            data = response.get_data(as_text=True)

            assert response.status_code == 200
            assert u'Ask a question about your G-Cloud 7 application' not in data


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
            assert send_email.call_count == 2
        elif is_called:
            assert send_email.call_count == 1
        else:
            assert send_email.call_count == 0

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
            assert send_email.call_count == 1
        else:
            assert send_email.call_count == 0

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
        data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

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

            assert response.status_code == 400
            assert self.strip_all_whitespace('There was a problem with your submitted question') in \
                self.strip_all_whitespace(response.get_data(as_text=True))
            assert self.strip_all_whitespace(invalid_clarification_question['error_message']) in \
                self.strip_all_whitespace(response.get_data(as_text=True))

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.data_api_client')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_call_send_email_with_correct_params(self, send_email, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework('open', name='Test Framework')

        clarification_question = 'This is a clarification question.'
        response = self._send_email(clarification_question)

        self._assert_clarification_email(send_email)

        assert response.status_code == 200
        assert self.strip_all_whitespace(
            '<p class="banner-message">Your clarification question has been sent. Answers to all ' +
            'clarification questions will be published on this page.</p>'
        ) in self.strip_all_whitespace(response.get_data(as_text=True))

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.data_api_client')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_call_send_g7_email_with_correct_params(self, send_email, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework('open', name='Test Framework',
                                                                    clarification_questions_open=False)
        clarification_question = 'This is a G7 question.'
        response = self._send_email(clarification_question)

        self._assert_application_email(send_email)

        assert response.status_code == 200
        assert self.strip_all_whitespace(
            '<p class="banner-message">Your question has been sent. You&#39;ll get a reply from ' +
            'the Crown Commercial Service soon.</p>'
        ) in self.strip_all_whitespace(response.get_data(as_text=True))

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.data_api_client')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_should_create_audit_event(self, send_email, data_api_client, s3):
        data_api_client.get_framework.return_value = self.framework('open', name='Test Framework')
        clarification_question = 'This is a clarification question'
        response = self._send_email(clarification_question)

        self._assert_clarification_email(send_email)

        assert response.status_code == 200
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

        assert response.status_code == 200
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
        send_email.side_effect = EmailError("Arrrgh")

        clarification_question = 'This is a clarification question.'
        response = self._send_email(clarification_question)
        self._assert_clarification_email(send_email, succeeds=False)

        assert response.status_code == 503


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
        assert response.status_code == 404

    def test_404_when_g7_pending_and_no_declaration(self, count_unanswered, data_api_client):
        with self.app.test_client():
            self.login()
        data_api_client.get_framework.return_value = self.framework(status='pending')
        data_api_client.get_supplier_declaration.return_value = {
            "declaration": {"status": "started"}
        }
        response = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/iaas')
        assert response.status_code == 404

    def test_no_404_when_g7_open_and_no_complete_services(self, count_unanswered, data_api_client):
        with self.app.test_client():
            self.login()
        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.find_draft_services.return_value = {'services': []}
        count_unanswered.return_value = 0
        response = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/iaas')
        assert response.status_code == 200

    def test_no_404_when_g7_open_and_no_declaration(self, count_unanswered, data_api_client):
        with self.app.test_client():
            self.login()

        data_api_client.get_framework.return_value = self.framework(status='open')
        data_api_client.get_supplier_declaration.return_value = {
            "declaration": {"status": "started"}
        }
        response = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/iaas')
        assert response.status_code == 200

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

        assert response.status_code == 200
        heading = doc.xpath('//div[@class="summary-item-lede"]//h2[@class="summary-item-heading"]')
        assert len(heading) > 0
        assert u"G-Cloud 7 is closed for applications" in heading[0].xpath('text()')[0]
        assert u"You made your supplier declaration and submitted 1 complete service." in \
            heading[0].xpath('../p[1]/text()')[0]

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

        assert u'Service can be moved to complete' not in lot_page.get_data(as_text=True)
        assert u'4 unanswered questions' in lot_page.get_data(as_text=True)

        assert u'1 draft service' in submissions.get_data(as_text=True)
        assert u'complete service' not in submissions.get_data(as_text=True)

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

        assert u'Service can be marked as complete' in res.get_data(as_text=True)
        assert u'1 optional question unanswered' in res.get_data(as_text=True)

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

        assert u'Service can be moved to complete' not in lot_page.get_data(as_text=True)
        assert u'1 optional question unanswered' in lot_page.get_data(as_text=True)
        assert u'make the supplier&nbsp;declaration' in lot_page.get_data(as_text=True)

        assert u'1 service marked as complete' in submissions.get_data(as_text=True)
        assert u'draft service' not in submissions.get_data(as_text=True)

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

        assert u'1 service will be submitted' in submissions.get_data(as_text=True)
        assert u'1 complete service was submitted' not in submissions.get_data(as_text=True)
        assert u'browse-list-item-status-happy' in submissions.get_data(as_text=True)

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

        assert u'1 complete service was submitted' in submissions.get_data(as_text=True)

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

        assert u'This will be submitted' in submissions.get_data(as_text=True)
        assert u'browse-list-item-status-happy' in submissions.get_data(as_text=True)
        assert u'Apply to provide' in submissions.get_data(as_text=True)

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
        assert u'Submitted' in submissions.get_data(as_text=True)
        assert u'Apply to provide' not in submissions.get_data(as_text=True)


@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
class TestCreateFrameworkAgreement(BaseApplicationTest):
    def test_creates_framework_agreement_and_redirects_to_signer_details_page(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(
                slug='g-cloud-8', status='standstill', framework_agreement_version="1.0"
            )
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=True)
            data_api_client.create_framework_agreement.return_value = {"agreement": {"id": 789}}

            res = self.client.post("/suppliers/frameworks/g-cloud-8/create-agreement")

            data_api_client.create_framework_agreement.assert_called_once_with(1234, 'g-cloud-8', 'email@email.com')
            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-8/789/signer-details'

    def test_404_if_supplier_not_on_framework(self, data_api_client):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = self.framework(status='standstill')
            data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                on_framework=False)

            res = self.client.post("/suppliers/frameworks/g-cloud-8/create-agreement")
            assert res.status_code == 404

    def test_404_if_framework_in_wrong_state(self, data_api_client):
        with self.app.test_client():
            self.login()
            # Suppliers can only sign agreements in 'standstill' and 'live' lifecycle statuses
            for status in ('coming', 'open', 'pending', 'expired'):
                data_api_client.get_framework.return_value = self.framework(status=status)
                data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
                    on_framework=True)

                res = self.client.post("/suppliers/frameworks/g-cloud-8/create-agreement")
                assert res.status_code == 404


@mock.patch("app.main.views.frameworks.data_api_client", autospec=True)
@mock.patch("app.main.views.frameworks.return_supplier_framework_info_if_on_framework_or_abort")
class TestSignerDetailsPage(BaseApplicationTest):

    def test_signer_details_shows_company_name(self, return_supplier_framework, data_api_client):
        self.login()
        data_api_client.get_framework.return_value = get_g_cloud_8()
        data_api_client.get_framework_agreement.return_value = self.framework_agreement()
        supplier_framework = self.supplier_framework(framework_slug='g-cloud-8', on_framework=True)['frameworkInterest']
        supplier_framework['declaration']['nameOfOrganisation'] = u'£unicodename'
        return_supplier_framework.return_value = supplier_framework

        res = self.client.get("/suppliers/frameworks/g-cloud-8/234/signer-details")
        page = res.get_data(as_text=True)
        assert res.status_code == 200
        assert u'Details of the person who is signing on behalf of £unicodename' in page

    def test_signer_details_shows_existing_signer_details(self, return_supplier_framework, data_api_client):
        self.login()
        data_api_client.get_framework.return_value = get_g_cloud_8()
        data_api_client.get_framework_agreement.return_value = self.framework_agreement(
            signed_agreement_details={
                "signerName": "Sid James",
                "signerRole": "Ex funny man"
            }
        )
        supplier_framework = self.supplier_framework(framework_slug='g-cloud-8', on_framework=True)['frameworkInterest']
        return_supplier_framework.return_value = supplier_framework

        res = self.client.get("/suppliers/frameworks/g-cloud-8/234/signer-details")
        page = res.get_data(as_text=True)
        assert res.status_code == 200
        assert "Sid James" in page
        assert "Ex funny man" in page

    def test_404_if_framework_in_wrong_state(self, return_supplier_framework, data_api_client):
        self.login()
        # Suppliers can only sign agreements in 'standstill' and 'live' lifecycle statuses
        data_api_client.get_framework.return_value = self.framework(status='pending')
        data_api_client.get_framework_agreement.return_value = self.framework_agreement()
        supplier_framework = self.supplier_framework(framework_slug='g-cloud-8', on_framework=True)['frameworkInterest']
        return_supplier_framework.return_value = supplier_framework

        res = self.client.get("/suppliers/frameworks/g-cloud-8/234/signer-details")
        assert res.status_code == 404

    @mock.patch('app.main.views.frameworks.check_agreement_is_related_to_supplier_framework_or_abort')
    def test_we_abort_if_agreement_does_not_match_supplier_framework(
        self, check_agreement_is_related_to_supplier_framework_or_abort, return_supplier_framework, data_api_client
    ):
        self.login()
        data_api_client.get_framework.return_value = get_g_cloud_8()
        data_api_client.get_framework_agreement.return_value = self.framework_agreement(supplier_id=2345)
        supplier_framework = self.supplier_framework(framework_slug='g-cloud-8', on_framework=True)['frameworkInterest']
        return_supplier_framework.return_value = supplier_framework

        res = self.client.get("/suppliers/frameworks/g-cloud-8/234/signer-details")
        # This call will abort because supplier_framework has mismatched supplier_id 1234
        check_agreement_is_related_to_supplier_framework_or_abort.assert_called_with(
            self.framework_agreement(supplier_id=2345)['agreement'],
            supplier_framework
        )

    def test_should_be_an_error_if_no_full_name(self, return_supplier_framework, data_api_client):
        self.login()
        data_api_client.get_framework.return_value = get_g_cloud_8()
        data_api_client.get_framework_agreement.return_value = self.framework_agreement()
        supplier_framework = self.supplier_framework(framework_slug='g-cloud-8', on_framework=True)['frameworkInterest']
        return_supplier_framework.return_value = supplier_framework

        res = self.client.post(
            "/suppliers/frameworks/g-cloud-8/234/signer-details",
            data={
                'signerRole': "The Boss"
            }
        )
        assert res.status_code == 400
        page = res.get_data(as_text=True)
        assert "You must provide the full name of the person signing on behalf of the company" in page

    def test_should_be_an_error_if_no_role(self, return_supplier_framework, data_api_client):
        self.login()
        data_api_client.get_framework.return_value = get_g_cloud_8()
        data_api_client.get_framework_agreement.return_value = self.framework_agreement()
        supplier_framework = self.supplier_framework(framework_slug='g-cloud-8', on_framework=True)['frameworkInterest']
        return_supplier_framework.return_value = supplier_framework

        res = self.client.post(
            "/suppliers/frameworks/g-cloud-8/234/signer-details",
            data={
                'signerName': "Josh Moss"
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
        data_api_client.get_framework_agreement.return_value = self.framework_agreement()
        supplier_framework = self.supplier_framework(framework_slug='g-cloud-8', on_framework=True)['frameworkInterest']
        return_supplier_framework.return_value = supplier_framework

        # 255 characters should be fine
        res = self.client.post(
            "/suppliers/frameworks/g-cloud-8/234/signer-details",
            data={
                'signerName': "J" * 255,
                'signerRole': "J" * 255
            }
        )
        assert res.status_code == 302

        # 256 characters should be an error
        res = self.client.post(
            "/suppliers/frameworks/g-cloud-8/234/signer-details",
            data={
                'signerName': "J" * 256,
                'signerRole': "J" * 256
            }
        )
        assert res.status_code == 400
        page = res.get_data(as_text=True)
        assert "You must provide a name under 256 characters" in page
        assert "You must provide a role under 256 characters" in page

    def test_should_strip_whitespace_on_signer_details_fields(self, return_supplier_framework, data_api_client):
        signer_details = {
            'signerName': "   Josh Moss   ",
            'signerRole': "   The Boss   "
        }

        data_api_client.get_framework.return_value = get_g_cloud_8()
        data_api_client.get_framework_agreement.return_value = self.framework_agreement()
        supplier_framework = self.supplier_framework(framework_slug='g-cloud-8', on_framework=True)['frameworkInterest']
        return_supplier_framework.return_value = supplier_framework

        self.login()
        res = self.client.post(
            "/suppliers/frameworks/g-cloud-8/234/signer-details",
            data=signer_details
        )
        assert res.status_code == 302

        data_api_client.update_framework_agreement.assert_called_with(
            234,
            {'signedAgreementDetails': {'signerName': 'Josh Moss', 'signerRole': 'The Boss'}},
            'email@email.com'
        )

    def test_provide_signer_details_form_with_valid_input_redirects_to_upload_page(
            self, return_supplier_framework, data_api_client
    ):
        signer_details = {
            'signerName': "Josh Moss",
            'signerRole': "The Boss"
        }

        data_api_client.get_framework.return_value = get_g_cloud_8()
        data_api_client.get_framework_agreement.return_value = self.framework_agreement()
        supplier_framework = self.supplier_framework(framework_slug='g-cloud-8', on_framework=True)['frameworkInterest']
        return_supplier_framework.return_value = supplier_framework

        with self.client as c:
            self.login()
            res = c.post(
                "/suppliers/frameworks/g-cloud-8/234/signer-details",
                data=signer_details
            )

            assert res.status_code == 302
            assert "suppliers/frameworks/g-cloud-8/234/signature-upload" in res.location
            data_api_client.update_framework_agreement.assert_called_with(
                234,
                {'signedAgreementDetails': {'signerName': 'Josh Moss', 'signerRole': 'The Boss'}},
                'email@email.com'
            )

    def test_provide_signer_details_form_with_valid_input_redirects_to_contract_review_page_if_file_already_uploaded(
            self, return_supplier_framework, data_api_client
    ):
        signer_details = {
            'signerName': "Josh Moss",
            'signerRole': "The Boss",
        }

        data_api_client.get_framework.return_value = get_g_cloud_8()
        data_api_client.get_framework_agreement.return_value = self.framework_agreement(
            signed_agreement_details={'signerName': 'existing name', 'signerRole': 'existing role'},
            signed_agreement_path='existing/path.pdf'
        )
        supplier_framework = self.supplier_framework(framework_slug='g-cloud-8', on_framework=True)['frameworkInterest']
        return_supplier_framework.return_value = supplier_framework

        with self.client as c:
            self.login()

            with self.client.session_transaction() as sess:
                # An already uploaded file will also have set a filename in the session
                sess['signature_page'] = 'test.pdf'

            res = c.post(
                "/suppliers/frameworks/g-cloud-8/234/signer-details",
                data=signer_details
            )

            assert res.status_code == 302
            assert "suppliers/frameworks/g-cloud-8/234/contract-review" in res.location
            data_api_client.update_framework_agreement.assert_called_with(
                234,
                {'signedAgreementDetails': {'signerName': 'Josh Moss', 'signerRole': 'The Boss'}},
                'email@email.com'
            )

    def test_signer_details_form_redirects_to_signature_upload_page_if_file_in_session_but_no_signed_agreement_path(
            self, return_supplier_framework, data_api_client
    ):
        signer_details = {
            'signerName': "Josh Moss",
            'signerRole': "The Boss",
        }

        data_api_client.get_framework.return_value = get_g_cloud_8()
        data_api_client.get_framework_agreement.return_value = self.framework_agreement(
            signed_agreement_details={'signerName': 'existing name', 'signerRole': 'existing role'}
        )
        supplier_framework = self.supplier_framework(framework_slug='g-cloud-8', on_framework=True)['frameworkInterest']
        return_supplier_framework.return_value = supplier_framework

        with self.client as c:
            self.login()

            with self.client.session_transaction() as sess:
                # We set a file name that could be from a previous framework agreement signing attempt but this
                # agreement does not have a signedAgreementPath
                sess['signature_page'] = 'test.pdf'

            res = c.post(
                "/suppliers/frameworks/g-cloud-8/234/signer-details",
                data=signer_details
            )

            assert res.status_code == 302
            assert "suppliers/frameworks/g-cloud-8/234/signature-upload" in res.location


@mock.patch("app.main.views.frameworks.data_api_client", autospec=True)
@mock.patch("app.main.views.frameworks.return_supplier_framework_info_if_on_framework_or_abort")
class TestSignatureUploadPage(BaseApplicationTest):

    @mock.patch('app.main.views.frameworks.check_agreement_is_related_to_supplier_framework_or_abort')
    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.generate_timestamped_document_upload_path')
    def test_we_abort_if_agreement_does_not_match_supplier_framework(
        self,
        generate_timestamped_document_upload_path,
        s3,
        check_agreement_is_related_to_supplier_framework_or_abort,
        return_supplier_framework,
        data_api_client
    ):
        self.login()
        data_api_client.get_framework.return_value = get_g_cloud_8()
        data_api_client.get_framework_agreement.return_value = self.framework_agreement(supplier_id=2345)
        supplier_framework = self.supplier_framework(framework_slug='g-cloud-8', on_framework=True)['frameworkInterest']
        return_supplier_framework.return_value = supplier_framework
        s3.return_value.get_key.return_value = None

        res = self.client.get("/suppliers/frameworks/g-cloud-8/234/signature-upload")
        # This call will abort because supplier_framework has mismatched supplier_id 1234
        check_agreement_is_related_to_supplier_framework_or_abort.assert_called_with(
            self.framework_agreement(supplier_id=2345)['agreement'],
            supplier_framework
        )

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.generate_timestamped_document_upload_path')
    def test_upload_signature_page(
        self, generate_timestamped_document_upload_path, s3, return_supplier_framework, data_api_client
    ):
        with self.client:
            self.login()

            data_api_client.get_framework.return_value = get_g_cloud_8()
            data_api_client.get_framework_agreement.return_value = self.framework_agreement()
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True
            )['frameworkInterest']
            generate_timestamped_document_upload_path.return_value = 'my/path.jpg'

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-8/234/signature-upload',
                data={
                    'signature_page': (StringIO(b'asdf'), 'test.jpg'),
                }
            )

            generate_timestamped_document_upload_path.assert_called_once_with(
                'g-cloud-8',
                1234,
                'agreements',
                'signed-framework-agreement.jpg'
            )

            s3.return_value.save.assert_called_with(
                'my/path.jpg',
                mock.ANY,
                download_filename='Supplier_Nme-1234-signed-signature-page.jpg',
                acl='private',
                disposition_type='inline'
            )
            data_api_client.update_framework_agreement.assert_called_with(
                234,
                {"signedAgreementPath": 'my/path.jpg'},
                'email@email.com'
            )

            assert session['signature_page'] == 'test.jpg'
            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-8/234/contract-review'

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.file_is_empty')
    def test_signature_upload_returns_400_if_file_is_empty(
        self, file_is_empty, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = get_g_cloud_8()
            data_api_client.get_framework_agreement.return_value = self.framework_agreement()
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True
            )['frameworkInterest']
            s3.return_value.get_key.return_value = None
            file_is_empty.return_value = True

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-8/234/signature-upload',
                data={
                    'signature_page': (StringIO(b''), 'test.pdf'),
                }
            )

            assert res.status_code == 400
            assert 'The file must not be empty' in res.get_data(as_text=True)

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.file_is_image')
    def test_signature_upload_returns_400_if_file_is_not_image_or_pdf(
        self, file_is_image, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = get_g_cloud_8()
            data_api_client.get_framework_agreement.return_value = self.framework_agreement()
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True
            )['frameworkInterest']
            s3.return_value.get_key.return_value = None
            file_is_image.return_value = False

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-8/234/signature-upload',
                data={
                    'signature_page': (StringIO(b'asdf'), 'test.txt'),
                }
            )

            assert res.status_code == 400
            assert 'The file must be a PDF, JPG or PNG' in res.get_data(as_text=True)

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.file_is_less_than_5mb')
    def test_signature_upload_returns_400_if_file_is_larger_than_5mb(
        self, file_is_less_than_5mb, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()

            data_api_client.get_framework.return_value = get_g_cloud_8()
            data_api_client.get_framework_agreement.return_value = self.framework_agreement()
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True
            )['frameworkInterest']
            s3.return_value.get_key.return_value = None
            file_is_less_than_5mb.return_value = False

            res = self.client.post(
                '/suppliers/frameworks/g-cloud-8/234/signature-upload',
                data={
                    'signature_page': (StringIO(b'asdf'), 'test.jpg'),
                }
            )

            assert res.status_code == 400
            assert 'The file must be less than 5MB' in res.get_data(as_text=True)

    @mock.patch('dmutils.s3.S3')
    def test_signature_page_displays_uploaded_filename_and_timestamp(
        self, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            data_api_client.get_framework.return_value = get_g_cloud_8()
            data_api_client.get_framework_agreement.return_value = self.framework_agreement(
                signed_agreement_path='already/uploaded/file/path.pdf'
            )
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True
            )['frameworkInterest']

            s3.return_value.get_key.return_value = {
                'last_modified': '2016-07-10T21:18:00.000000Z'
            }

            with self.client as c:
                self.login()

                with self.client.session_transaction() as sess:
                    sess['signature_page'] = 'test.pdf'

                res = c.get(
                    '/suppliers/frameworks/g-cloud-8/234/signature-upload'
                )

                s3.return_value.get_key.assert_called_with('already/uploaded/file/path.pdf')
                assert res.status_code == 200
                assert "test.pdf, uploaded Sunday 10 July 2016 at 22:18" in res.get_data(as_text=True)

    @mock.patch('dmutils.s3.S3')
    def test_signature_page_displays_file_upload_timestamp_if_no_filename_in_session(
            self, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            data_api_client.get_framework.return_value = get_g_cloud_8()
            data_api_client.get_framework_agreement.return_value = self.framework_agreement(
                signed_agreement_path='already/uploaded/file/path.pdf'
            )
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True
            )['frameworkInterest']

            s3.return_value.get_key.return_value = {
                'last_modified': '2016-07-10T21:18:00.000000Z'
            }

            with self.client as c:
                self.login()
                res = c.get(
                    '/suppliers/frameworks/g-cloud-8/234/signature-upload'
                )
                s3.return_value.get_key.assert_called_with('already/uploaded/file/path.pdf')
                assert res.status_code == 200
                assert "Uploaded Sunday 10 July 2016 at 22:18" in res.get_data(as_text=True)

    @mock.patch('dmutils.s3.S3')
    def test_signature_page_allows_continuation_without_file_chosen_to_be_uploaded_if_an_uploaded_file_already_exists(
            self, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            data_api_client.get_framework.return_value = get_g_cloud_8()
            data_api_client.get_framework_agreement.return_value = self.framework_agreement(
                signed_agreement_path='already/uploaded/file/path.pdf'
            )
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True
            )['frameworkInterest']

            s3.return_value.get_key.return_value = {
                'last_modified': '2016-07-10T21:18:00.000000Z'
            }

            with self.client as c:
                self.login()
                res = c.post(
                    '/suppliers/frameworks/g-cloud-8/234/signature-upload',
                    data={
                        'signature_page': (StringIO(b''), ''),
                    }
                )
                s3.return_value.get_key.assert_called_with('already/uploaded/file/path.pdf')
                assert res.status_code == 302
                assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-8/234/contract-review'


@mock.patch("app.main.views.frameworks.data_api_client")
@mock.patch("app.main.views.frameworks.return_supplier_framework_info_if_on_framework_or_abort")
class TestContractReviewPage(BaseApplicationTest):

    @mock.patch('dmutils.s3.S3')
    def test_contract_review_page_loads_with_correct_supplier_and_signer_details_and_filename(
        self, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()
            data_api_client.get_framework.return_value = get_g_cloud_8()
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True,
                declaration={
                    "primaryContact": "contact name",
                    "primaryContactEmail": "email@email.com",
                    "nameOfOrganisation": u"£unicodename"
                },
            )['frameworkInterest']
            data_api_client.get_framework_agreement.return_value = self.framework_agreement(
                signed_agreement_details={"signerName": "signer_name", "signerRole": "signer_role"},
                signed_agreement_path="I/have/returned/my/agreement.pdf"
            )
            s3.return_value.get_key.return_value = {
                'last_modified': '2016-07-10T21:18:00.000000Z'
            }

            with self.client.session_transaction() as sess:
                sess['signature_page'] = 'test.pdf'

            res = self.client.get(
                "/suppliers/frameworks/g-cloud-8/234/contract-review"
            )
            assert res.status_code == 200
            s3.return_value.get_key.assert_called_with('I/have/returned/my/agreement.pdf')
            page = res.get_data(as_text=True)
            page_without_whitespace = self.strip_all_whitespace(page)
            assert u'Check the details you’ve given before returning the signature page for £unicodename' in page
            assert '<tdclass="summary-item-field"><span><p>signer_name</p><p>signer_role</p></span></td>' \
                in page_without_whitespace
            assert u"I have the authority to return this agreement on behalf of £unicodename" in page
            assert "Returning the signature page will notify the Crown Commercial Service and the primary contact you "
            "gave in your G-Cloud 8 application, contact name at email@email.com." in page
            assert '<tdclass="summary-item-field-first"><span>test.pdf</span></td>' in page_without_whitespace

    @mock.patch('dmutils.s3.S3')
    def test_contract_review_page_loads_with_uploaded_time_of_file_if_no_filename_in_session(
            self, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()
            data_api_client.get_framework.return_value = get_g_cloud_8()
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True,
                declaration={
                    "primaryContact": "contact name",
                    "primaryContactEmail": "email@email.com",
                    "nameOfOrganisation": u"£unicodename"
                },
            )['frameworkInterest']
            data_api_client.get_framework_agreement.return_value = self.framework_agreement(
                signed_agreement_details={"signerName": "signer_name", "signerRole": "signer_role"},
                signed_agreement_path="I/have/returned/my/agreement.pdf"
            )
            s3.return_value.get_key.return_value = {
                'last_modified': '2016-07-10T21:18:00.000000Z'
            }

            res = self.client.get(
                "/suppliers/frameworks/g-cloud-8/234/contract-review"
            )
            assert res.status_code == 200
            page = res.get_data(as_text=True)
            assert u'Check the details you’ve given before returning the signature page for £unicodename' in page
            assert '<tdclass="summary-item-field-first"><span>UploadedSunday10July2016at22:18</span></td>' in self.strip_all_whitespace(page)  # noqa

    @mock.patch('dmutils.s3.S3')
    def test_contract_review_page_aborts_if_visited_when_information_required_to_return_agreement_does_not_exist(
        self, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()
            data_api_client.get_framework.return_value = get_g_cloud_8()
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True,
                declaration={
                    "primaryContact": "contact name",
                    "primaryContactEmail": "email@email.com",
                    "nameOfOrganisation": u"£unicodename"
                },
            )['frameworkInterest']
            data_api_client.get_framework_agreement.return_value = self.framework_agreement(
                signed_agreement_details={"signerName": "signer_name", "signerRole": "signer_role"}
                # No file has been uploaded
            )

            # no file has been uploaded
            s3.return_value.get_key.return_value = None

            res = self.client.get(
                "/suppliers/frameworks/g-cloud-8/234/contract-review"
            )
            assert res.status_code == 404

    @mock.patch('app.main.views.frameworks.check_agreement_is_related_to_supplier_framework_or_abort')
    @mock.patch('dmutils.s3.S3')
    def test_we_abort_if_agreement_does_not_match_supplier_framework(
        self, s3, check_agreement_is_related_to_supplier_framework_or_abort, return_supplier_framework, data_api_client
    ):
        self.login()
        data_api_client.get_framework.return_value = get_g_cloud_8()
        data_api_client.get_framework_agreement.return_value = self.framework_agreement(supplier_id=2345)
        supplier_framework = self.supplier_framework(framework_slug='g-cloud-8', on_framework=True)['frameworkInterest']
        return_supplier_framework.return_value = supplier_framework
        s3.return_value.get_key.return_value = None

        res = self.client.get("/suppliers/frameworks/g-cloud-8/234/contract-review")
        # This call will abort because supplier_framework has mismatched supplier_id 1234
        check_agreement_is_related_to_supplier_framework_or_abort.assert_called_with(
            self.framework_agreement(supplier_id=2345)['agreement'],
            supplier_framework
        )

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_return_400_response_and_no_email_sent_if_authorisation_not_checked(
            self, send_email, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()
            data_api_client.get_framework.return_value = get_g_cloud_8()
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True,
                declaration={
                    "primaryContact": "contact name",
                    "primaryContactEmail": "email@email.com",
                    "nameOfOrganisation": u"£unicodename"
                },
            )['frameworkInterest']
            data_api_client.get_framework_agreement.return_value = self.framework_agreement(
                signed_agreement_details={"signerName": "signer_name", "signerRole": "signer_role"},
                signed_agreement_path="I/have/returned/my/agreement.pdf"
            )
            s3.return_value.get_key.return_value = {
                'last_modified': '2016-07-10T21:18:00.000000Z'
            }

            res = self.client.post(
                "/suppliers/frameworks/g-cloud-8/234/contract-review",
                data={}
            )
            assert res.status_code == 400
            page = res.get_data(as_text=True)
            assert send_email.called is False
            assert "You must confirm you have the authority to return the agreement" in page

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_valid_framework_agreement_returned_updates_api_and_sends_confirmation_emails_and_unsets_session(
        self, send_email, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()
            data_api_client.get_framework.return_value = get_g_cloud_8()
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True,
                declaration={
                    "primaryContact": "contact name",
                    "primaryContactEmail": "email2@email.com",
                    "nameOfOrganisation": u"£unicodename"
                },
            )['frameworkInterest']
            data_api_client.get_framework_agreement.return_value = self.framework_agreement(
                signed_agreement_details={"signerName": "signer_name", "signerRole": "signer_role"},
                signed_agreement_path="I/have/returned/my/agreement.pdf"
            )
            s3.return_value.get_key.return_value = {
                'last_modified': '2016-07-10T21:18:00.000000Z'
            }

            with self.client.session_transaction() as sess:
                sess['signature_page'] = 'test.pdf'

            res = self.client.post(
                "/suppliers/frameworks/g-cloud-8/234/contract-review",
                data={
                    'authorisation': 'I have the authority to return this agreement on behalf of company name'
                }
            )

            data_api_client.sign_framework_agreement.assert_called_once_with(
                234,
                'email@email.com',
                {'uploaderUserId': 123}
            )

            # Delcaration primaryContactEmail and current_user.email_address are different so expect two recipients
            send_email.assert_called_once_with(
                ['email2@email.com', 'email@email.com'],
                mock.ANY,
                'MANDRILL',
                'Your G-Cloud 8 signature page has been received',
                'do-not-reply@digitalmarketplace.service.gov.uk',
                'Digital Marketplace Admin',
                ['g-cloud-8-framework-agreement']
            )

            # Check 'signature_page' has been removed from session
            with self.client.session_transaction() as sess:
                assert 'signature_page' not in sess

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_valid_framework_agreement_returned_sends_only_one_confirmation_email_if_contact_email_addresses_are_equal(
        self, send_email, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()
            data_api_client.get_framework.return_value = get_g_cloud_8()
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True,
                declaration={
                    "primaryContact": "contact name",
                    "primaryContactEmail": "email@email.com",
                    "nameOfOrganisation": u"£unicodename"
                },
            )['frameworkInterest']
            data_api_client.get_framework_agreement.return_value = self.framework_agreement(
                signed_agreement_details={"signerName": "signer_name", "signerRole": "signer_role"},
                signed_agreement_path="I/have/returned/my/agreement.pdf"
            )
            s3.return_value.get_key.return_value = {
                'last_modified': '2016-07-10T21:18:00.000000Z'
            }

            res = self.client.post(
                "/suppliers/frameworks/g-cloud-8/234/contract-review",
                data={
                    'authorisation': 'I have the authority to return this agreement on behalf of company name'
                }
            )

            send_email.assert_called_once_with(
                ['email@email.com'],
                mock.ANY,
                'MANDRILL',
                'Your G-Cloud 8 signature page has been received',
                'do-not-reply@digitalmarketplace.service.gov.uk',
                'Digital Marketplace Admin',
                ['g-cloud-8-framework-agreement']
            )

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_return_503_response_if_mandrill_exception_raised_by_send_email(
            self, send_email, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()
            data_api_client.get_framework.return_value = get_g_cloud_8()
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True,
                declaration={
                    "primaryContact": "contact name",
                    "primaryContactEmail": "email@email.com",
                    "nameOfOrganisation": u"£unicodename"
                },
            )['frameworkInterest']
            data_api_client.get_framework_agreement.return_value = self.framework_agreement(
                signed_agreement_details={"signerName": "signer_name", "signerRole": "signer_role"},
                signed_agreement_path="I/have/returned/my/agreement.pdf"
            )
            s3.return_value.get_key.return_value = {
                'last_modified': '2016-07-10T21:18:00.000000Z'
            }

            send_email.side_effect = EmailError()

            res = self.client.post(
                "/suppliers/frameworks/g-cloud-8/234/contract-review",
                data={
                    'authorisation': 'I have the authority to return this agreement on behalf of company name'
                }
            )

            assert res.status_code == 503

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_email_not_sent_if_api_call_fails(
            self, send_email, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()
            data_api_client.get_framework.return_value = get_g_cloud_8()
            data_api_client.sign_framework_agreement.side_effect = APIError(mock.Mock(status_code=500))
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True,
                declaration={
                    "primaryContact": "contact name",
                    "primaryContactEmail": "email@email.com",
                    "nameOfOrganisation": u"£unicodename"
                },
            )['frameworkInterest']
            data_api_client.get_framework_agreement.return_value = self.framework_agreement(
                signed_agreement_details={"signerName": "signer_name", "signerRole": "signer_role"},
                signed_agreement_path="I/have/returned/my/agreement.pdf"
            )
            s3.return_value.get_key.return_value = {
                'last_modified': '2016-07-10T21:18:00.000000Z'
            }

            res = self.client.post(
                "/suppliers/frameworks/g-cloud-8/234/contract-review",
                data={
                    'authorisation': 'I have the authority to return this agreement on behalf of company name'
                }
            )

            assert data_api_client.sign_framework_agreement.called is True
            assert res.status_code == 500
            assert send_email.called is False

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_framework_agreement_returned_having_signed_contract_variation_redirects_to_framework_dashboard(
        self, send_email, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()

            framework = get_g_cloud_8()
            framework['variations'] = {
                "1": {"createdAt": "2016-06-06T20:01:34.000000Z"}
            }
            data_api_client.get_framework.return_value = framework
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True,
                declaration={
                    "primaryContact": "contact name",
                    "primaryContactEmail": "email2@email.com",
                    "nameOfOrganisation": u"£unicodename"
                },
                agreed_variations={
                    '1': {
                        "agreedUserId": 2,
                        "agreedAt": "2016-06-06T00:00:00.000000Z",
                    }
                }
            )['frameworkInterest']
            data_api_client.get_framework_agreement.return_value = self.framework_agreement(
                signed_agreement_details={"signerName": "signer_name", "signerRole": "signer_role"},
                signed_agreement_path="I/have/returned/my/agreement.pdf"
            )

            s3.return_value.get_key.return_value = {
                'last_modified': '2016-07-10T21:18:00.000000Z'
            }

            res = self.client.post(
                "/suppliers/frameworks/g-cloud-8/234/contract-review",
                data={
                    'authorisation': 'I have the authority to return this agreement on behalf of company name'
                }
            )

            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-8'

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_framework_agreement_returned_with_feature_flag_off_redirects_to_framework_dashboard(
        self, send_email, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()
            self.app.config['FEATURE_FLAGS_CONTRACT_VARIATION'] = False

            framework = get_g_cloud_8()
            framework['frameworks']['variations'] = {
                "1": {"createdAt": "2016-06-06T20:01:34.000000Z"}
            }
            data_api_client.get_framework.return_value = framework
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True,
                declaration={
                    "primaryContact": "contact name",
                    "primaryContactEmail": "email@email.com",
                    "nameOfOrganisation": u"£unicodename"
                },
            )['frameworkInterest']
            data_api_client.get_framework_agreement.return_value = self.framework_agreement(
                signed_agreement_details={"signerName": "signer_name", "signerRole": "signer_role"},
                signed_agreement_path="I/have/returned/my/agreement.pdf"
            )

            s3.return_value.get_key.return_value = {
                'last_modified': '2016-07-10T21:18:00.000000Z'
            }

            res = self.client.post(
                "/suppliers/frameworks/g-cloud-8/234/contract-review",
                data={
                    'authorisation': 'I have the authority to return this agreement on behalf of company name'
                }
            )

            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-8'

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_framework_agreement_returned_having_not_signed_contract_variation_redirects_to_variation(
        self, send_email, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()

            framework = get_g_cloud_8()
            framework['frameworks']['variations'] = {
                "1": {"createdAt": "2016-06-06T20:01:34.000000Z"}
            }
            data_api_client.get_framework.return_value = framework
            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True,
                declaration={
                    "primaryContact": "contact name",
                    "primaryContactEmail": "email2@email.com",
                    "nameOfOrganisation": u"£unicodename"
                },
                agreed_variations={}
            )['frameworkInterest']
            data_api_client.get_framework_agreement.return_value = self.framework_agreement(
                signed_agreement_details={"signerName": "signer_name", "signerRole": "signer_role"},
                signed_agreement_path="I/have/returned/my/agreement.pdf"
            )

            s3.return_value.get_key.return_value = {
                'last_modified': '2016-07-10T21:18:00.000000Z'
            }

            res = self.client.post(
                "/suppliers/frameworks/g-cloud-8/234/contract-review",
                data={
                    'authorisation': 'I have the authority to return this agreement on behalf of company name'
                }
            )
            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-8/contract-variation/1'

    @mock.patch('dmutils.s3.S3')
    @mock.patch('app.main.views.frameworks.send_email')
    def test_framework_agreement_returned_for_framework_with_no_variations_redirects_to_framework_dashboard(
        self, send_email, s3, return_supplier_framework, data_api_client
    ):
        with self.app.test_client():
            self.login()

            framework = get_g_cloud_8()
            framework['variations'] = {}
            data_api_client.get_framework.return_value = framework

            return_supplier_framework.return_value = self.supplier_framework(
                framework_slug='g-cloud-8',
                on_framework=True,
                declaration={
                    "primaryContact": "contact name",
                    "primaryContactEmail": "email@email.com",
                    "nameOfOrganisation": u"£unicodename"
                },
            )['frameworkInterest']
            data_api_client.get_framework_agreement.return_value = self.framework_agreement(
                signed_agreement_details={"signerName": "signer_name", "signerRole": "signer_role"},
                signed_agreement_path="I/have/returned/my/agreement.pdf"
            )

            s3.return_value.get_key.return_value = {
                'last_modified': '2016-07-10T21:18:00.000000Z'
            }

            res = self.client.post(
                "/suppliers/frameworks/g-cloud-8/234/contract-review",
                data={
                    'authorisation': 'I have the authority to return this agreement on behalf of company name'
                }
            )

            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-8'


@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
class TestContractVariation(BaseApplicationTest):

    def setup_method(self, method):
        super(TestContractVariation, self).setup_method(method)

        self.good_supplier_framework = self.supplier_framework(
            declaration={'nameOfOrganisation': 'A.N. Supplier',
                         'primaryContactEmail': 'bigboss@email.com'},
            on_framework=True,
            agreement_returned=True,
            agreement_details={}
        )
        self.g8_framework = self.framework(
            name='G-Cloud 8',
            slug='g-cloud-8',
            status='live',
            framework_agreement_version='3.1'
        )
        self.g8_framework['frameworks']['variations'] = {"1": {"createdAt": "2018-08-16"}}

        with self.app.test_client():
            self.login()

    def test_get_page_renders_if_all_ok(self, data_api_client):
        data_api_client.get_framework.return_value = self.g8_framework
        data_api_client.get_supplier_framework_info.return_value = self.good_supplier_framework

        res = self.client.get("/suppliers/frameworks/g-cloud-8/contract-variation/1")
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 200
        assert len(doc.xpath('//h1[contains(text(), "G-Cloud 8: proposed contract variation")]')) == 1

    def test_supplier_must_be_on_framework(self, data_api_client):
        supplier_not_on_framework = self.good_supplier_framework.copy()
        supplier_not_on_framework['frameworkInterest']['onFramework'] = False
        data_api_client.get_framework.return_value = self.g8_framework
        data_api_client.get_supplier_framework_info.return_value = supplier_not_on_framework

        res = self.client.get("/suppliers/frameworks/g-cloud-8/contract-variation/1")

        assert res.status_code == 404

    def test_variation_must_exist(self, data_api_client):
        data_api_client.get_framework.return_value = self.g8_framework
        data_api_client.get_supplier_framework_info.return_value = self.good_supplier_framework

        # There is no variation number 2
        res = self.client.get("/suppliers/frameworks/g-cloud-8/contract-variation/2")

        assert res.status_code == 404

    def test_agreement_must_be_returned_already(self, data_api_client):
        agreement_not_returned = self.good_supplier_framework.copy()
        agreement_not_returned['frameworkInterest']['agreementReturned'] = False
        data_api_client.get_framework.return_value = self.g8_framework
        data_api_client.get_supplier_framework_info.return_value = agreement_not_returned

        res = self.client.get("/suppliers/frameworks/g-cloud-8/contract-variation/1")

        assert res.status_code == 404

    def test_shows_form_if_not_yet_agreed(self, data_api_client):
        data_api_client.get_framework.return_value = self.g8_framework
        data_api_client.get_supplier_framework_info.return_value = self.good_supplier_framework

        res = self.client.get("/suppliers/frameworks/g-cloud-8/contract-variation/1")
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 200
        assert len(doc.xpath('//label[contains(text(), "I accept these proposed changes")]')) == 1
        assert len(doc.xpath('//input[@value="Save and continue"]')) == 1

    def test_shows_signer_details_and_no_form_if_already_agreed(self, data_api_client):
        already_agreed = self.good_supplier_framework.copy()
        already_agreed['frameworkInterest']['agreedVariations'] = {
            "1": {
                "agreedAt": "2016-08-19T15:47:08.116613Z",
                "agreedUserId": 1,
                "agreedUserEmail": "agreed@email.com",
                "agreedUserName": u"William Drăyton",
            }}
        data_api_client.get_framework.return_value = self.g8_framework
        data_api_client.get_supplier_framework_info.return_value = already_agreed

        res = self.client.get("/suppliers/frameworks/g-cloud-8/contract-variation/1")
        page_text = res.get_data(as_text=True)
        doc = html.fromstring(page_text)

        assert res.status_code == 200
        assert len(doc.xpath('//h2[contains(text(), "Contract variation status")]')) == 1
        assert u"<span>William Drăyton<br />agreed@email.com<br />Friday 19 August 2016 at 16:47</span>" in page_text
        assert len(doc.xpath('//label[contains(text(), "I accept these proposed changes")]')) == 0
        assert len(doc.xpath('//input[@value="Save and continue"]')) == 0

    def test_shows_updated_heading_and_countersigner_details_but_no_form_if_countersigned(self, data_api_client):
        already_agreed = self.good_supplier_framework.copy()
        already_agreed['frameworkInterest']['agreedVariations'] = {
            "1": {
                "agreedAt": "2016-08-19T15:47:08.116613Z",
                "agreedUserId": 1,
                "agreedUserEmail": "agreed@email.com",
                "agreedUserName": u"William Drăyton",
            }}
        g8_with_countersigned_variation = self.framework(
            status='live',
            name='G-Cloud 8'
        )
        g8_with_countersigned_variation['frameworks']['variations'] = {"1": {
            "createdAt": "2016-08-01T12:30:00.000000Z",
            "countersignedAt": "2016-10-01T02:00:00.000000Z",
            "countersignerName": "A.N. Other",
            "countersignerRole": "Head honcho",
        }
        }
        data_api_client.get_framework.return_value = g8_with_countersigned_variation
        data_api_client.get_supplier_framework_info.return_value = already_agreed

        res = self.client.get("/suppliers/frameworks/g-cloud-8/contract-variation/1")
        page_text = res.get_data(as_text=True)
        doc = html.fromstring(page_text)

        assert res.status_code == 200
        assert len(doc.xpath('//h1[contains(text(), "G-Cloud 8: contract variation")]')) == 1
        assert len(doc.xpath('//h2[contains(text(), "Contract variation status")]')) == 1
        assert u"<span>A.N. Other<br />Head honcho<br />Saturday 1 October 2016</span>" in page_text
        assert len(doc.xpath('//label[contains(text(), "I accept these proposed changes")]')) == 0
        assert len(doc.xpath('//input[@value="Save and continue"]')) == 0

    def test_api_is_called_to_agree(self, data_api_client):
        data_api_client.get_framework.return_value = self.g8_framework
        data_api_client.get_supplier_framework_info.return_value = self.good_supplier_framework

        res = self.client.post("/suppliers/frameworks/g-cloud-8/contract-variation/1",
                               data={"accept_changes": "Yes"}
                               )

        assert res.status_code == 302
        assert res.location == "http://localhost/suppliers/frameworks/g-cloud-8/contract-variation/1"
        data_api_client.agree_framework_variation.assert_called_once_with(
            1234, 'g-cloud-8', '1', 123, 'email@email.com'
        )

    @mock.patch('app.main.views.frameworks.send_email')
    def test_email_is_sent_to_correct_users(self, send_email, data_api_client):
        data_api_client.get_framework.return_value = self.g8_framework
        data_api_client.get_supplier_framework_info.return_value = self.good_supplier_framework
        self.client.post("/suppliers/frameworks/g-cloud-8/contract-variation/1",
                         data={"accept_changes": "Yes"}
                         )

        send_email.assert_called_once_with(
            ['bigboss@email.com', 'email@email.com'],
            mock.ANY,
            'MANDRILL',
            'G-Cloud 8: you have accepted the proposed contract variation',
            'do-not-reply@digitalmarketplace.service.gov.uk',
            'Digital Marketplace Admin',
            ['g-cloud-8-variation-accepted']
        )

    @mock.patch('app.main.views.frameworks.send_email')
    def test_only_one_email_sent_if_user_is_framework_contact(self, send_email, data_api_client):
        same_email_as_current_user = self.good_supplier_framework.copy()
        same_email_as_current_user['frameworkInterest']['declaration']['primaryContactEmail'] = 'email@email.com'
        data_api_client.get_framework.return_value = self.g8_framework
        data_api_client.get_supplier_framework_info.return_value = same_email_as_current_user
        self.client.post("/suppliers/frameworks/g-cloud-8/contract-variation/1",
                         data={"accept_changes": "Yes"}
                         )

        send_email.assert_called_once_with(
            ['email@email.com'],
            mock.ANY,
            'MANDRILL',
            'G-Cloud 8: you have accepted the proposed contract variation',
            'do-not-reply@digitalmarketplace.service.gov.uk',
            'Digital Marketplace Admin',
            ['g-cloud-8-variation-accepted']
        )

    def test_success_message_is_displayed_on_success(self, data_api_client):
        data_api_client.get_framework.return_value = self.g8_framework
        data_api_client.get_supplier_framework_info.return_value = self.good_supplier_framework
        res = self.client.post("/suppliers/frameworks/g-cloud-8/contract-variation/1",
                               data={"accept_changes": "Yes"},
                               follow_redirects=True
                               )
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 200
        assert len(
            doc.xpath('//p[@class="banner-message"][contains(text(), "You have accepted the proposed changes.")]')
        ) == 1, res.get_data(as_text=True)

    @mock.patch('app.main.views.frameworks.send_email')
    def test_api_is_not_called_and_no_email_sent_for_subsequent_posts(self, send_email, data_api_client):
        already_agreed = self.good_supplier_framework.copy()
        already_agreed['frameworkInterest']['agreedVariations'] = {
            "1": {
                "agreedAt": "2016-08-19T15:47:08.116613Z",
                "agreedUserId": 1,
                "agreedUserEmail": "agreed@email.com",
                "agreedUserName": "William Drayton",
            }}
        data_api_client.get_framework.return_value = self.g8_framework
        data_api_client.get_supplier_framework_info.return_value = already_agreed

        res = self.client.post("/suppliers/frameworks/g-cloud-8/contract-variation/1",
                               data={"accept_changes": "Yes"}
                               )
        assert res.status_code == 200
        assert data_api_client.agree_framework_variation.called is False
        assert send_email.called is False

    def test_error_if_box_not_ticked(self, data_api_client):
        data_api_client.get_framework.return_value = self.g8_framework
        data_api_client.get_supplier_framework_info.return_value = self.good_supplier_framework

        res = self.client.post("/suppliers/frameworks/g-cloud-8/contract-variation/1", data={})
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 400
        assert len(
            doc.xpath('//span[@class="validation-message"][contains(text(), "You can only save and continue if you agree to the proposed changes")]')  # noqa
        ) == 1


@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
class TestReuseFrameworkSupplierDeclaration(BaseApplicationTest):
    """Tests for frameworks/<framework_slug>/declaration/reuse view."""

    def setup_method(self, method):
        super(TestReuseFrameworkSupplierDeclaration, self).setup_method(method)
        with self.app.test_client():
            self.login()

    def test_reusable_declaration_framework_slug_param(self, data_api_client):
        """Ensure that when using the param to specify declaration we collect the correct declaration."""

        # Modify the data client.
        t07 = '2009-12-03T01:01:01.000000Z'
        framework = {
            'x_field': 'foo',
            'allow_declaration_reuse': True,
            'application_close_date': t07,
            'slug': 'g-cloud-8',
            'name': 'g-cloud-8'
        }

        data_api_client.get_framework.return_value = {'frameworks': framework}
        data_api_client.get_supplier_framework_info.return_value = {
            'frameworkInterest': {
                'declaration': {'status': 'complete'},
                'onFramework': True
            }
        }

        # Do the get.
        with self.client as cont:
            resp = cont.get(
                '/suppliers/frameworks/g-cloud-9/declaration/reuse?reusable_declaration_framework_slug=g-cloud-8'
            )

            # Assert request arg inside context manager.
            assert request.args['reusable_declaration_framework_slug'] == 'g-cloud-8'

        # Assert response OK.
        assert resp.status_code == 200

        # Assert expected api calls.
        data_api_client.get_framework.assert_has_calls([mock.call('g-cloud-9'), mock.call('g-cloud-8')])
        data_api_client.get_supplier_framework_info.assert_called_once_with(1234, 'g-cloud-8')

    def test_404_when_specified_declaration_not_found(self, data_api_client):
        """Fail on a 404 if declaration is specified but not found."""

        # Modify the data client.
        framework = {}
        data_api_client.get_framework.return_value = {'frameworks': framework}
        data_api_client.get_supplier_framework_info.side_effect = APIError(mock.Mock(status_code=404))

        # Do the get.
        resp = self.client.get(
            '/suppliers/frameworks/g-cloud-9/declaration/reuse?reusable_declaration_framework_slug=g-cloud-8'
        )

        # Assert the 404
        assert resp.status_code == 404

        # Assert expected api calls.
        data_api_client.get_framework.assert_called_once_with('g-cloud-9')
        data_api_client.get_supplier_framework_info.assert_called_once_with(1234, 'g-cloud-8')

    def test_redirect_when_declaration_not_found(self, data_api_client):
        """Redirect if a reusable declaration is not found."""

        # Modify the data client.
        t09 = '2009-03-03T01:01:01.000000Z'

        frameworks = [
            {'x_field': 'foo', 'allow_declaration_reuse': True, 'application_close_date': t09, 'slug': 'ben-cloud-2'},
        ]
        supplier_declarations = []
        data_api_client.find_frameworks.return_value = {'frameworks': frameworks}
        data_api_client.find_supplier_declarations.return_value = dict(
            frameworkInterest=supplier_declarations
        )

        # Do the get.
        with self.client:
            resp = self.client.get(
                '/suppliers/frameworks/g-cloud-9/declaration/reuse',
            )

            # Assert the redirect
            assert resp.location.endswith('/suppliers/frameworks/g-cloud-9/declaration')

        # Assert expected api calls.
        data_api_client.get_framework.assert_called_once_with('g-cloud-9')
        data_api_client.find_supplier_declarations.assert_called_once_with(1234)

    def test_success_reuse_g_cloud_7_for_8(self, data_api_client):
        """Test success path."""

        # Modify the data client.
        t09 = '2009-03-03T01:01:01.000000Z'
        t10 = '2010-03-03T01:01:01.000000Z'
        t11 = '2011-03-03T01:01:01.000000Z'
        t12 = '2012-03-03T01:01:01.000000Z'

        frameworks_response = [
            {
                'x_field': 'foo',
                'allow_declaration_reuse': True,
                'application_close_date': t12,
                'slug': 'g-cloud-8',
                'name': 'G-cloud 8'
            }, {
                'x_field': 'foo',
                'allow_declaration_reuse': True,
                'application_close_date': t11,
                'slug': 'g-cloud-7',
                'name': 'G-cloud 7'
            }, {
                'x_field': 'foo',
                'allow_declaration_reuse': True,
                'application_close_date': t10,
                'slug': 'dos',
                'name': 'Digital'
            }, {
                'x_field': 'foo',
                'allow_declaration_reuse': False,
                'application_close_date': t09,
                'slug': 'g-cloud-6',
                'name': 'G-cloud 6'
            },
        ]
        framework_response = {
            'x_field': 'foo',
            'allow_declaration_reuse': True,
            'application_close_date': t09,
            'slug': 'g-cloud-8',
            'name': 'G-cloud 8'
        }
        supplier_declarations_response = [
            {'x': 'foo', 'frameworkSlug': 'g-cloud-6', 'declaration': {'status': 'complete'}, 'onFramework': True},
            {'x': 'foo', 'frameworkSlug': 'g-cloud-7', 'declaration': {'status': 'complete'}, 'onFramework': True},
            {'x': 'foo', 'frameworkSlug': 'dos', 'declaration': {'status': 'complete'}, 'onFramework': True}
        ]
        data_api_client.find_frameworks.return_value = {'frameworks': frameworks_response}
        data_api_client.get_framework.return_value = {'frameworks': framework_response}
        data_api_client.find_supplier_declarations.return_value = {'frameworkInterest': supplier_declarations_response}

        # Do the get.
        resp = self.client.get(
            '/suppliers/frameworks/g-cloud-8/declaration/reuse',
        )

        # Assert the success.
        assert resp.status_code == 200
        expected = 'In March, 2011, your organisation completed a declaration for G-cloud 7.'
        assert expected in ''.join(map(str, resp.response))

        # Assert expected api calls.
        data_api_client.get_framework.assert_called_once_with('g-cloud-8')
        data_api_client.find_supplier_declarations.assert_called_once_with(1234)


@mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
class TestReuseFrameworkSupplierDeclarationPost(BaseApplicationTest):
    """Tests for frameworks/<framework_slug>/declaration/reuse POST view."""

    def setup_method(self, method):
        super(TestReuseFrameworkSupplierDeclarationPost, self).setup_method(method)
        with self.app.test_client():
            self.login()

    def test_reuse_false(self, data_api_client):
        """Assert that the redirect happens and the client sets the prefill pref to None."""
        data = {'reuse': 'false', 'old_framework_slug': 'should-not-be-used'}
        with self.client:
            resp = self.client.post(
                '/suppliers/frameworks/g-cloud-9/declaration/reuse',
                data=data
            )

            # Assert the redirect
            assert resp.location.endswith('/suppliers/frameworks/g-cloud-9/declaration')

        data_api_client.set_supplier_framework_prefill_declaration.assert_called_once_with(
            1234,
            'g-cloud-9',
            None,
            'email@email.com'
        )

    def test_reuse_true(self, data_api_client):
        """Assert that the redirect happens and the client sets the prefill pref to the desired framework slug."""
        data = {'reuse': True, 'old_framework_slug': 'digital-outcomes-and-specialists-2'}
        data_api_client.get_supplier_framework_info.return_value = {
            'frameworkInterest': {
                'x_field': 'foo',
                'frameworkSlug': 'digital-outcomes-and-specialists-2',
                'declaration': {'status': 'complete'},
                'onFramework': True
            }
        }
        framework_response = {'frameworks': {'x_field': 'foo', 'allow_declaration_reuse': True}}
        data_api_client.get_framework.return_value = framework_response

        with self.client:
            resp = self.client.post(
                '/suppliers/frameworks/g-cloud-9/declaration/reuse',
                data=data
            )

            # Assert the redirect
            assert resp.location.endswith('/suppliers/frameworks/g-cloud-9/declaration')

        # These api calls need to be made so that we can verify the declaration.
        data_api_client.get_framework.assert_called_once_with('digital-outcomes-and-specialists-2')
        data_api_client.get_supplier_framework_info.assert_called_once_with(
            1234,
            'digital-outcomes-and-specialists-2'
        )

        # This end point sets the prefill preference.
        data_api_client.set_supplier_framework_prefill_declaration.assert_called_once_with(
            1234,
            'g-cloud-9',
            'digital-outcomes-and-specialists-2',
            'email@email.com'
        )

    def test_reuse_invalid_framework_post(self, data_api_client):
        """Assert 404 for non reusable framework."""
        data = {'reuse': 'true', 'old_framework_slug': 'digital-outcomes-and-specialists'}

        # A framework with allow_declaration_reuse as False
        data_api_client.get_framework.return_value = {
            'frameworks': {'x_field': 'foo', 'allow_declaration_reuse': False}
        }

        # Do the post.
        resp = self.client.post(
            '/suppliers/frameworks/g-cloud-9/declaration/reuse',
            data=data
        )

        # Should get the framework and error on allow_declaration_reuse as False.
        data_api_client.get_framework.assert_called_once_with('digital-outcomes-and-specialists')
        # Should not do the declaration call if the framework is invalid
        assert not data_api_client.get_supplier_framework_info.called
        # Should 404
        assert resp.status_code == 404

    def test_reuse_non_existent_framework_post(self, data_api_client):
        """Assert 404 for non existent framework."""
        data = {'reuse': 'true', 'old_framework_slug': 'digital-outcomes-and-specialists-1000000'}

        # Attach does not exist.
        data_api_client.get_framework.side_effect = HTTPError()

        # Do the post.
        resp = self.client.post(
            '/suppliers/frameworks/g-cloud-9/declaration/reuse',
            data=data
        )

        # Should error on get.
        data_api_client.get_framework.assert_called_once_with('digital-outcomes-and-specialists-1000000')
        # Should not do the declaration call if the framework is invalid.
        assert not data_api_client.get_supplier_framework_info.called
        # Should 404.
        assert resp.status_code == 404

    def test_reuse_non_existent_declaration_post(self, data_api_client):
        """Assert 404 for non existent declaration."""
        data = {'reuse': 'true', 'old_framework_slug': 'digital-outcomes-and-specialists-2'}
        framework_response = {'frameworks': {'x_field': 'foo', 'allow_declaration_reuse': True}}
        data_api_client.get_framework.return_value = framework_response

        # Attach does not exist.
        data_api_client.get_supplier_framework_info.side_effect = HTTPError()

        # Do the post.
        resp = self.client.post(
            '/suppliers/frameworks/g-cloud-9/declaration/reuse',
            data=data
        )

        # Should get the framework
        data_api_client.get_framework.assert_called_once_with('digital-outcomes-and-specialists-2')
        # Should error getting declaration.
        data_api_client.get_supplier_framework_info.assert_called_once_with(1234, 'digital-outcomes-and-specialists-2')
        # Should 404.
        assert resp.status_code == 404
