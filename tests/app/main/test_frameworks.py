# -*- coding: utf-8 -*-
import mock
from collections import OrderedDict
from datetime import datetime
from io import BytesIO
from itertools import chain
from urllib.parse import urljoin

from freezegun import freeze_time
from lxml import html
import pytest

from dmapiclient import (
    APIError,
    HTTPError
)
from dmapiclient.audit import AuditTypes
from dmcontent.errors import ContentNotFoundError
from dmtestutils.api_model_stubs import FrameworkStub, SupplierStub
from dmtestutils.fixtures import valid_pdf_bytes
from dmutils.email.exceptions import EmailError
from dmutils.s3 import S3ResponseError

from ..helpers import (
    BaseApplicationTest,
    MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin,
    FULL_G7_SUBMISSION,
    valid_g9_declaration_base,
    assert_args_and_raise,
    assert_args_and_return,
)


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


def _extract_guidance_links(doc):
    return OrderedDict(
        (
            section_li.xpath("normalize-space(string(.//h2))"),
            tuple(
                (
                    item_li.xpath("normalize-space(string(.//a))") or None,
                    item_li.xpath("string(.//a/@href)") or None,
                    item_li.xpath(
                        (
                            "normalize-space(string(.//time"
                            " | "
                            "./following-sibling::p[@class='dm-attachment__metadata']//time))"
                        )
                    ) or None,
                    item_li.xpath(
                        (
                            "string(.//time/@datetime"
                            " | "
                            "./following-sibling::p[@class='dm-attachment__metadata']//time/@datetime)"
                        )
                    ) or None,
                )
                for item_li in section_li.xpath(".//p[.//a] | .//h3[.//a]")
            ),
        )
        for section_li in doc.xpath(
            (
                "//main//*[./h2[not(text()='Application progress')]][.//p//a"
                "|"
                "//section[@class='dm-attachment']//a]"
            )
        )
    )


@mock.patch('dmutils.s3.S3')
class TestFrameworksDashboard(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_framework_dashboard_shows_for_pending_if_declaration_exists(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath("//h1[normalize-space(string())=$b]", b="Your G-Cloud 7 application")) == 1

    def test_framework_dashboard_shows_for_live_if_declaration_exists(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='live')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath("//h1[normalize-space(string())=$b]", b="G-Cloud 7 documents")) == 1

    def test_does_not_show_for_live_if_no_declaration(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='live')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(declaration=None)
        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        assert res.status_code == 404

    @mock.patch('app.main.views.frameworks.DMNotifyClient', autospec=True)
    def test_email_sent_when_interest_registered_in_framework(self, mock_dmnotifyclient_class, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
        self.data_api_client.find_users_iter.return_value = [
            {'emailAddress': 'email1', 'active': True},
            {'emailAddress': 'email2', 'active': True},
            {'emailAddress': 'email3', 'active': False}
        ]
        mock_dmnotifyclient_instance = mock_dmnotifyclient_class.return_value
        mock_dmnotifyclient_instance.templates = {'framework-application-started': '123456789'}
        res = self.client.post("/suppliers/frameworks/g-cloud-7")

        self.data_api_client.register_framework_interest.assert_called_once_with(
            1234,
            "g-cloud-7",
            "email@email.com"
        )
        assert res.status_code == 200

        assert mock_dmnotifyclient_instance.send_email.call_count == 2
        assert mock_dmnotifyclient_instance.send_email.call_args[1].get('template_name_or_id') == '123456789'

    def test_interest_not_registered_in_framework_on_get(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
        res = self.client.get("/suppliers/frameworks/digital-outcomes-and-specialists")

        assert res.status_code == 200
        assert self.data_api_client.register_framework_interest.called is False

    def test_interest_set_but_no_declaration(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.get_framework_interest.return_value = {'frameworks': ['g-cloud-7']}
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
        ]

        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(declaration=None)

        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        assert res.status_code == 200

    def test_shows_closed_message_if_pending_and_no_application_done(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.get_framework_interest.return_value = {'frameworks': ['g-cloud-7']}
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'not-submitted'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))

        heading = doc.xpath('//div[@class="summary-item-lede"]//h2[@class="summary-item-heading"]')
        assert len(heading) > 0
        assert "G-Cloud 7 is closed for applications" in heading[0].xpath('text()')[0]
        assert "You didn't submit an application." in heading[0].xpath('../p[1]/text()')[0]

    def test_shows_closed_message_if_pending_and_application(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.get_framework_interest.return_value = {'frameworks': ['g-cloud-7']}
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        heading = doc.xpath('//div[@class="summary-item-lede"]//h2[@class="summary-item-heading"]')
        assert len(heading) > 0
        assert "G-Cloud 7 is closed for applications" in heading[0].xpath('text()')[0]
        lede = doc.xpath('//div[@class="summary-item-lede"]')
        expected_string = "You made your supplier declaration and submitted 1 service for consideration."
        assert (expected_string in lede[0].xpath('./p[1]/text()')[0])
        assert "We’ll let you know the result of your application by " in lede[0].xpath('./p[2]/text()')[0]


@mock.patch('dmutils.s3.S3')
class TestFrameworksDashboardOpenApplications(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_declaration_status_when_complete_for_open_framework(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//main//strong[@id="dm-declaration-done"][contains(text(), "Completed")]')) == 1

    def test_declaration_status_when_started_for_open_framework(self, s3):
        self.login()

        submission = FULL_G7_SUBMISSION.copy()
        # User has not yet submitted page 3 of the declaration
        del submission['SQ2-1abcd']
        del submission['SQ2-1e']
        del submission['SQ2-1f']
        del submission['SQ2-1ghijklmn']

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            declaration=submission, status='started')

        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//main//strong[@id="dm-declaration-inprogress"][contains(text(), "In progress")]')) == 1

    def test_declaration_status_when_company_details_not_complete_for_open_framework(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_framework_info.side_effect = APIError(mock.Mock(status_code=404))
        self.data_api_client.get_supplier.return_value = SupplierStub().single_result_response()

        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//main//strong[@id="dm-declaration-cantstart"]')) == 1

    def test_downloads_shown_for_open_framework(self, s3):
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

        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        extracted_guidance_links = _extract_guidance_links(doc)

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
                    "Download the proposed \u2018call-off\u2019 contract",
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
            a="until 5pm BST, Tuesday 22 September 2015",
        )) == 1
        assert not doc.xpath(
            "//main//table[normalize-space(string(./caption))=$b]",
            b="Agreement details",
        )
        assert s3.return_value.list.call_args_list == [
            mock.call("g-cloud-7/communications", load_timestamps=True)
        ]

    def test_downloads_shown_open_framework_clarification_questions_closed(self, s3):
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

        self.login()

        self.data_api_client.get_framework.return_value = self.framework(
            status="open", clarification_questions_open=False
        )
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        extracted_guidance_links = _extract_guidance_links(doc)

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
                    "Download the proposed \u2018call-off\u2019 contract",
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
            for href_part
            in ("g-cloud-7-final-framework-agreement.pdf", "g-cloud-7-supplier-pack.zip")
        )
        assert not doc.xpath("//main[contains(normalize-space(string()), $a)]",
                             a="until 5pm BST, Tuesday 22 September 2015")
        assert not doc.xpath("//main//table[normalize-space(string(./caption))=$b]", b="Agreement details")

        assert s3.return_value.list.call_args_list == [
            mock.call("g-cloud-7/communications", load_timestamps=True)
        ]

    def test_final_agreement_download_shown_open_framework(self, s3):
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

        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        extracted_guidance_links = _extract_guidance_links(doc)

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
                    "Download the proposed \u2018call-off\u2019 contract",
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
            for href_part
            in ("g-cloud-7-proposed-framework-agreement.pdf", "g-cloud-7-supplier-pack.zip")
        )
        assert len(
            doc.xpath("//main//p[contains(normalize-space(string()), $a)]",
                      a="until 5pm BST, Tuesday 22 September 2015")
        ) == 1
        assert not doc.xpath("//main//table[normalize-space(string(./caption))=$b]", b="Agreement details")

    def test_no_updates_open_framework(self, s3):
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

        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        extracted_guidance_links = _extract_guidance_links(doc)

        assert (
            "View communications and ask clarification questions",
            "/suppliers/frameworks/g-cloud-7/updates",
            None,
            None,
        ) in extracted_guidance_links["Communications"]
        assert len(
            doc.xpath("//main//p[contains(normalize-space(string()), $a)]",
                      a="until 5pm BST, Tuesday 22 September 2015")
        ) == 1
        assert not doc.xpath("//main//table[normalize-space(string(./caption))=$b]", b="Agreement details")

    def test_no_files_exist_open_framework(self, s3):
        s3.return_value.list.return_value = []

        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()
        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        extracted_guidance_links = _extract_guidance_links(doc)

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
                    "Download the proposed \u2018call-off\u2019 contract",
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
        assert len(
            doc.xpath("//main//p[contains(normalize-space(string()), $a)]",
                      a="until 5pm BST, Tuesday 22 September 2015")
        ) == 1
        assert not doc.xpath("//main//table[normalize-space(string(./caption))=$b]", b="Agreement details")

    def test_returns_404_if_framework_does_not_exist(self, s3):
        self.login()
        self.data_api_client.get_framework.side_effect = APIError(mock.Mock(status_code=404))

        res = self.client.get('/suppliers/frameworks/does-not-exist')

        assert res.status_code == 404

    def test_visit_to_framework_dashboard_saved_in_session_if_framework_open(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(slug="g-cloud-9", status="open")
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        response = self.client.get("/suppliers/frameworks/g-cloud-9")

        assert response.status_code == 200
        with self.client.session_transaction() as session:
            assert session["currently_applying_to"] == "g-cloud-9"

    @pytest.mark.parametrize(
        "framework_status",
        ["coming", "pending", "standstill", "live", "expired"]
    )
    def test_visit_to_framework_dashboard_not_saved_in_session_if_framework_not_open(self, s3, framework_status):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(slug="g-cloud-9", status=framework_status)
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        self.client.get("/suppliers/frameworks/g-cloud-9")

        with self.client.session_transaction() as session:
            assert "currently_applying_to" not in session


@mock.patch('dmutils.s3.S3')
class TestFrameworksDashboardSuccessBanner(BaseApplicationTest):
    """Tests for the confidence banner on the declaration page."""

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()
        self.data_api_client.get_framework.return_value = self.framework(status='open')

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_success_banner_on_page_for_open_framework(self, _):
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'foo'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            status='complete',
            application_company_details_confirmed=True,
        )
        self.data_api_client.get_supplier.return_value = SupplierStub(
            company_details_confirmed=True).single_result_response()

        self.login()
        res = self.client.get("/suppliers/frameworks/g-cloud-8")
        assert res.status_code == 200

        document = html.fromstring(res.get_data(as_text=True))

        alert_banner = document.xpath('//div[@class="dm-alert dm-alert--success"]')
        assert len(alert_banner) == 1
        assert alert_banner[0].xpath(
            "//h2[contains(normalize-space(string()), $t)]",
            t="Your application is complete and will be submitted automatically.",
        )
        assert alert_banner[0].xpath(
            "//div[contains(normalize-space(string()), $t)]",
            t="You can change it at any time before the deadline."
        )

        # Check GA custom dimension values
        assert len(document.xpath("//meta[@data-id='29' and @data-value='application_confirmed']")) == 1

    def test_success_banner_with_unsubmitted_drafts_shows_different_message(self, _):
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'foo'},
            {'serviceName': 'A service', 'status': 'not-submitted', 'lotSlug': 'foo'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            status='complete',
            application_company_details_confirmed=True,
        )
        self.data_api_client.get_supplier.return_value = SupplierStub(
            company_details_confirmed=True).single_result_response()

        self.login()
        res = self.client.get("/suppliers/frameworks/g-cloud-8")
        assert res.status_code == 200

        document = html.fromstring(res.get_data(as_text=True))

        alert_banner = document.xpath('//div[@class="dm-alert dm-alert--success"]')
        assert len(alert_banner) == 1
        assert alert_banner[0].xpath(
            "//h2[contains(normalize-space(string()), $t)]",
            t="Your application is complete and will be submitted automatically.",
        )
        assert alert_banner[0].xpath(
            "//div[contains(normalize-space(string()), $t)]",
            t="You still have 1 unsubmitted draft service. "
              "You can edit or remove draft services at any time before the deadline.",
        )

        # Check GA custom dimension values
        assert len(document.xpath("//meta[@data-id='29' and @data-value='application_confirmed']")) == 1

    @pytest.mark.parametrize(
        ('declaration_status', 'draft_service_status', 'details_confirmed', 'ga_value'),
        (
            ('started', 'submitted', True, 'services_confirmed'),
            ('complete', 'not-submitted', True, 'declaration_confirmed'),
            ('unstarted', 'not-submitted', True, 'company_details_confirmed'),
            ('unstarted', 'not-submitted', False, 'application_started'),
        )
    )
    def test_success_banner_not_on_page_if_sections_incomplete(
        self, _, declaration_status, draft_service_status, details_confirmed, ga_value
    ):
        """Change value and assert that confidence banner is not displayed."""
        supplier_data = SupplierStub(company_details_confirmed=details_confirmed).single_result_response()

        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': draft_service_status, 'lotSlug': 'foo'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            status=declaration_status,
            declaration={'status': declaration_status},
            application_company_details_confirmed=supplier_data['suppliers']['companyDetailsConfirmed'],
        )
        self.data_api_client.get_supplier.return_value = supplier_data

        self.login()
        res = self.client.get("/suppliers/frameworks/g-cloud-8")
        assert res.status_code == 200

        document = html.fromstring(res.get_data(as_text=True))

        # Alert banner should not be shown
        alert_banner = document.xpath('//div[@class="dm-alert dm-alert--success"]')
        assert len(alert_banner) == 0
        assert 'Your application is complete and will be submitted automatically.' not in res.get_data(as_text=True)

        # Check GA custom dimension values
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath("//meta[@data-id='29' and @data-value='{}']".format(ga_value))) == 1


@mock.patch('dmutils.s3.S3')
class TestFrameworksDashboardPendingStandstill(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    @staticmethod
    def _extract_signing_details_table_rows(doc):
        return tuple(
            tuple(
                td_th_dt_dd_elem.xpath("normalize-space(string())")
                for td_th_dt_dd_elem in tr_elem.xpath("td|th|dt|dd")
            )
            for tr_elem in doc.xpath(
                ("//main//table[normalize-space(string(./caption))=$b]/tbody/tr"
                 "|"
                 "//main//dl/div[@class='govuk-summary-list__row']"),
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
                'User email@email.com Sunday 10 July 2016 at 10:20pm BST'
            ),
            (
                'Countersignature',
                'Waiting for CCS to countersign'
            ),
        )

    def test_dashboard_pending_before_award_company_details_not_confirmed(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.find_draft_services_iter.return_value = []
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            declaration={}, application_company_details_confirmed=False
        )

        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath(
            "//main//p[contains(normalize-space(string()), $details_text)]",
            details_text="You did not confirm your company details.",
        )
        assert doc.xpath(
            "//main//p[contains(normalize-space(string()), $declaration_text)]",
            declaration_text="You did not make a supplier declaration.",
        )
        assert doc.xpath(
            "//main//p[contains(normalize-space(string()), $drafts_text)]",
            drafts_text="You did not create any services.",
        )

    def test_dashboard_pending_before_award_services_but_no_declaration(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            declaration={}
        )

        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath(
            "//main//p[contains(normalize-space(string()), $declaration_text)]",
            declaration_text="You did not make a supplier declaration",
        )
        assert doc.xpath(
            "//main//a[@href=$href or normalize-space(string())=$label]",
            href="/frameworks/g-cloud-7/submissions",
            label="View draft services",
        )

    @pytest.mark.parametrize('declaration_status', ('started', 'complete'))
    def test_dashboard_pending_before_award_with_services_and_declaration(self, s3, declaration_status):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            declaration={'status': declaration_status}
        )

        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath(
            "//main//a[@href=$href or normalize-space(string())=$label]",
            href="/frameworks/g-cloud-7/declaration",
            label="View your declaration",
        )
        if declaration_status == 'complete':
            assert doc.xpath(
                "//main//p[contains(normalize-space(string()), $declaration_text)]",
                declaration_text="You made your supplier declaration",
            )
            assert doc.xpath(
                "//main//a[@href=$href or normalize-space(string())=$label]",
                href="/frameworks/g-cloud-7/submissions",
                label="View submitted services",
            )

    @pytest.mark.parametrize('declaration_status', ('started', 'complete'))
    def test_dashboard_pending_before_award_with_declaration_incomplete_services(self, s3, declaration_status):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'not-submitted', 'lotSlug': 'iaas'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            declaration={'status': declaration_status}
        )

        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath(
            "//main//a[@href=$href or normalize-space(string())=$label]",
            href="/frameworks/g-cloud-7/declaration",
            label="View your declaration",
        )
        assert doc.xpath(
            "//main//a[@href=$href or normalize-space(string())=$label]",
            href="/frameworks/g-cloud-7/submissions",
            label="View draft services",
        )

    @pytest.mark.parametrize('declaration_status', ('started', 'complete'))
    def test_dashboard_pending_before_award_with_declaration_no_services(self, s3, declaration_status):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.find_draft_services_iter.return_value = []
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            declaration={'status': declaration_status}
        )

        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath(
            "//main//a[@href=$href or normalize-space(string())=$label]",
            href="/frameworks/g-cloud-7/declaration",
            label="View your declaration",
        )
        assert doc.xpath(
            "//main//p[contains(normalize-space(string()), $drafts_text)]",
            drafts_text="You did not create any services.",
        )

    def test_result_letter_is_shown_when_is_in_standstill(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='standstill')
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        data = res.get_data(as_text=True)

        assert u'Download your application result letter' in data

    def test_result_letter_is_not_shown_when_not_in_standstill(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        data = res.get_data(as_text=True)

        assert u'Download your application result letter' not in data

    def test_result_letter_is_not_shown_when_no_application(self, s3):
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(status='standstill')
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'not-submitted'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        data = res.get_data(as_text=True)

        assert u'Download your application result letter' not in data

    def test_link_to_unsigned_framework_agreement_is_shown_if_supplier_is_on_framework(self, s3):
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(status='standstill')
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            on_framework=True)

        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        data = res.get_data(as_text=True)

        assert u'Sign and return your framework agreement' in data
        assert u'Download your countersigned framework agreement' not in data

    def test_pending_success_message_is_explicit_if_supplier_is_on_framework(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(
            status='standstill', framework_agreement_version=None
        )
        self.data_api_client.find_draft_services.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(on_framework=True)
        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        data = res.get_data(as_text=True)

        assert (
            'Your application was successful.'
        ) in data
        assert 'Download your application award letter (.pdf)' in data
        assert 'This letter is a record of your successful G-Cloud 7 application.' in data

        assert 'You made your supplier declaration and submitted 1 service.' not in data
        assert 'Download your application result letter (.pdf)' not in data
        assert 'This letter informs you if your G-Cloud 7 application has been successful.' not in data

    def test_link_to_framework_agreement_is_not_shown_if_supplier_is_not_on_framework(self, s3):
        self.login()

        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(on_framework=False)

        res = self.client.get("/suppliers/frameworks/g-cloud-7")

        data = res.get_data(as_text=True)

        assert u'Sign and return your framework agreement' not in data

    def test_pending_success_message_is_equivocal_if_supplier_is_on_framework(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='standstill')
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(on_framework=False)
        res = self.client.get("/suppliers/frameworks/g-cloud-7")
        assert res.status_code == 200

        data = res.get_data(as_text=True)

        assert (
            'Your application was successful. You\'ll be able to sell services when the G-Cloud 7 framework is live'
        ) not in data
        assert 'Download your application award letter (.pdf)' not in data
        assert 'This letter is a record of your successful G-Cloud 7 application.' not in data

        assert 'You made your supplier declaration and submitted 1 service.' in data
        assert 'Download your application result letter (.pdf)' in data
        assert 'This letter informs you if your G-Cloud 7 application has been successful.' in data

    def test_countersigned_framework_agreement_non_fav_framework(self, s3):
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

        self.login()
        self.data_api_client.get_framework.return_value = self.framework(status='standstill')
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
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

        extracted_guidance_links = _extract_guidance_links(doc)

        assert extracted_guidance_links == OrderedDict((
            ("You submitted:", (
                (
                    'View submitted services',
                    '/suppliers/frameworks/g-cloud-7/submissions',
                    None,
                    None,
                ),
                (
                    "View your declaration",
                    "/suppliers/frameworks/g-cloud-7/declaration",
                    None,
                    None,
                ),
            )),
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
                    "Download your countersigned framework agreement",
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

    def test_countersigned_framework_agreement_fav_framework(self, s3):
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

        self.login()
        self.data_api_client.get_framework.return_value = get_g_cloud_8()
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
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

        extracted_guidance_links = _extract_guidance_links(doc)

        assert extracted_guidance_links == OrderedDict((
            ("You submitted:", (
                (
                    'View submitted services',
                    '/suppliers/frameworks/g-cloud-8/submissions',
                    None,
                    None,
                ),
                (
                    "View your declaration",
                    "/suppliers/frameworks/g-cloud-8/declaration",
                    None,
                    None,
                ),
            )),
            ("Legal documents", (
                (
                    'Read the standard framework agreement',
                    'https://www.gov.uk/government/publications/g-cloud-8-framework-agreement',
                    None,
                    None,
                ),
                (
                    "Download your \u2018original\u2019 framework agreement signature page",
                    "/suppliers/frameworks/g-cloud-8/agreements/pathy/mc/path.face",
                    None,
                    None,
                ),
                (
                    "Download your \u2018counterpart\u2019 framework agreement signature page",
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
        assert not doc.xpath("//main//table[normalize-space(string(./caption))=$b]", b="Agreement details")
        assert not doc.xpath("//main//p[contains(normalize-space(string()), $b)]", b="You can start selling your")
        assert doc.xpath(
            "//main//p[contains(normalize-space(string()), $b)]",
            b="Your original and counterpart signature pages"
        )
        assert not doc.xpath(
            "//main//p[contains(normalize-space(string()), $b)]",
            b="Your framework agreement signature page has been sent to the Crown Commercial Service"
        )

    def test_shows_returned_agreement_details(self, s3):
        self.login()
        self.data_api_client.get_framework.return_value = get_g_cloud_8()
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            on_framework=True,
            agreement_returned=True,
            agreement_details=self._boring_agreement_details,
            agreement_path='g-cloud-8/agreements/123-framework-agreement.pdf',
            agreement_returned_at=self._boring_agreement_returned_at
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
            href="/suppliers/frameworks/g-cloud-8/agreements/result-letter.pdf",
            label="Download your application result letter",
        )

        extracted_guidance_links = _extract_guidance_links(doc)
        assert extracted_guidance_links == OrderedDict((
            ("You submitted:", (
                (
                    'View submitted services',
                    '/suppliers/frameworks/g-cloud-8/submissions',
                    None,
                    None,
                ),
                (
                    "View your declaration",
                    "/suppliers/frameworks/g-cloud-8/declaration",
                    None,
                    None,
                ),
            )),
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
        assert doc.xpath("//main//p[contains(normalize-space(string()), $b)]", b="You can start selling your")
        assert not doc.xpath(
            "//main//p[contains(normalize-space(string()), $b)]",
            b="Your original and counterpart signature pages",
        )
        assert doc.xpath(
            "//main//p[contains(normalize-space(string()), $b)]",
            b="Your framework agreement signature page has been sent to the Crown Commercial Service",
        )

    def test_countersigned_but_no_countersigned_path(self, s3):
        self.login()
        self.data_api_client.get_framework.return_value = get_g_cloud_8()
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'A service', 'status': 'submitted', 'lotSlug': 'iaas'}
        ]
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
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
            href="/frameworks/g-cloud-8/agreement",
            label="Sign and return your framework agreement",
        )

        extracted_guidance_links = _extract_guidance_links(doc)
        assert extracted_guidance_links == OrderedDict((
            ("You submitted:", (
                (
                    'View submitted services',
                    '/suppliers/frameworks/g-cloud-8/submissions',
                    None,
                    None,
                ),
                (
                    "View your declaration",
                    "/suppliers/frameworks/g-cloud-8/declaration",
                    None,
                    None,
                ),
            )),
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
        assert len(doc.xpath("//main//h1[normalize-space(string())=$b]", b="Your G-Cloud 8 application")) == 1

        assert doc.xpath("//main//p[contains(normalize-space(string()), $b)]", b="You can start selling your")
        assert not doc.xpath(
            "//main//p[contains(normalize-space(string()), $b)]",
            b="Your original and counterpart signature pages",
        )
        assert doc.xpath(
            "//main//p[contains(normalize-space(string()), $b)]",
            b="Your framework agreement signature page has been sent to the Crown Commercial Service",
        )

    def test_shows_contract_variation_link_after_agreement_returned(self, s3):
        self.login()
        g8_with_variation = get_g_cloud_8()
        g8_with_variation['frameworks']['variations'] = {"1": {"createdAt": "2018-08-16"}}
        self.data_api_client.get_framework.return_value = g8_with_variation
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
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
            href="/frameworks/g-cloud-8/agreement",
            label="Sign and return your framework agreement",
        )

        extracted_guidance_links = _extract_guidance_links(doc)
        assert extracted_guidance_links == OrderedDict((
            ("You submitted:", (
                (
                    'View submitted services',
                    '/suppliers/frameworks/g-cloud-8/submissions',
                    None,
                    None,
                ),
                (
                    "View your declaration",
                    "/suppliers/frameworks/g-cloud-8/declaration",
                    None,
                    None,
                ),
            )),
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
            "//main//p[contains(normalize-space(string()), $b)]", b="You can start selling your")
        assert not doc.xpath(
            "//main//p[contains(normalize-space(string()), $b)]",
            b="Your original and counterpart signature pages",
        )
        assert doc.xpath(
            "//main//p[contains(normalize-space(string()), $b)]",
            b="Your framework agreement signature page has been sent to the Crown Commercial Service",
        )

    def test_does_not_show_contract_variation_link_if_no_variation(self, s3):
        self.login()
        self.data_api_client.get_framework.return_value = get_g_cloud_8()
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
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
        assert doc.xpath("//main//p[contains(normalize-space(string()), $b)]", b="You can start selling your")
        assert not doc.xpath(
            "//main//p[contains(normalize-space(string()), $b)]",
            b="Your original and counterpart signature pages",
        )
        assert doc.xpath(
            "//main//p[contains(normalize-space(string()), $b)]",
            b="Your framework agreement signature page has been sent to the Crown Commercial Service",
        )

    def test_does_not_show_contract_variation_link_if_agreement_not_returned(self, s3):
        self.login()
        g8_with_variation = get_g_cloud_8()
        g8_with_variation['frameworks']['variations'] = {"1": {"createdAt": "2018-08-16"}}
        self.data_api_client.get_framework.return_value = g8_with_variation
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

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
        assert not doc.xpath("//main//p[contains(normalize-space(string()), $b)]", b="You can start selling your")
        assert not doc.xpath(
            "//main//p[contains(normalize-space(string()), $b)]",
            b="Your original and counterpart signature pages",
        )
        assert not doc.xpath(
            "//main//p[contains(normalize-space(string()), $b)]",
            b="Your framework agreement signature page has been sent to the Crown Commercial Service",
        )

    def test_shows_contract_variation_alternate_link_text_after_agreed_by_ccs(self, s3):
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
        self.data_api_client.get_framework.return_value = g8_with_variation
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
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
                    "agreedUserName": "William Drăyton",
                },
            },
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

        extracted_guidance_links = _extract_guidance_links(doc)
        assert extracted_guidance_links == OrderedDict((
            ("You submitted:", (
                (
                    'View submitted services',
                    '/suppliers/frameworks/g-cloud-8/submissions',
                    None,
                    None,
                ),
                (
                    "View your declaration",
                    "/suppliers/frameworks/g-cloud-8/declaration",
                    None,
                    None,
                ),
            )),
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
        assert doc.xpath("//main//p[contains(normalize-space(string()), $b)]", b="You can start selling your")
        assert not doc.xpath(
            "//main//p[contains(normalize-space(string()), $b)]",
            b="Your original and counterpart signature pages",
        )
        assert doc.xpath(
            "//main//p[contains(normalize-space(string()), $b)]",
            b="Your framework agreement signature page has been sent to the Crown Commercial Service",
        )

    @pytest.mark.parametrize(
        'supplier_framework_kwargs,link_href',
        (
            ({'declaration': None}, '/suppliers/frameworks/g-cloud-7/declaration/start'),
            ({}, '/suppliers/frameworks/g-cloud-7/declaration')
        )
    )
    def test_make_supplier_declaration_links_to_correct_page(
        self, s3, supplier_framework_kwargs, link_href
    ):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            application_company_details_confirmed=True,
            **supplier_framework_kwargs,
        )

        response = self.client.get('/suppliers/frameworks/g-cloud-7')
        document = html.fromstring(response.get_data(as_text=True))

        assert (
            document.xpath(
                "//a[contains(normalize-space(string()), $link_label)]/@href",
                link_label="Make your supplier declaration"
            )[0]
        ) == link_href


@mock.patch('dmutils.s3.S3')
class TestFrameworkAgreementDocumentDownload(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_download_document_fails_if_no_supplier_framework(self, S3):
        self.data_api_client.get_supplier_framework_info.side_effect = APIError(mock.Mock(status_code=404))

        self.login()

        res = self.client.get('/suppliers/frameworks/g-cloud-7/agreements/example.pdf')

        assert res.status_code == 404

    def test_download_document_fails_if_no_supplier_declaration(self, S3):
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(declaration=None)

        self.login()

        res = self.client.get('/suppliers/frameworks/g-cloud-7/agreements/example.pdf')

        assert res.status_code == 404

    def test_download_document(self, S3):
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        uploader = mock.Mock()
        S3.return_value = uploader
        uploader.get_signed_url.return_value = 'http://url/path?param=value'

        self.login()

        res = self.client.get('/suppliers/frameworks/g-cloud-7/agreements/example.pdf')

        assert res.status_code == 302
        assert res.location == 'http://asset-host/path?param=value'
        uploader.get_signed_url.assert_called_with('g-cloud-7/agreements/1234/1234-example.pdf')

    def test_download_document_with_asset_url(self, S3):
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        uploader = mock.Mock()
        S3.return_value = uploader
        uploader.get_signed_url.return_value = 'http://url/path?param=value'

        self.app.config['DM_ASSETS_URL'] = 'https://example'
        self.login()

        res = self.client.get('/suppliers/frameworks/g-cloud-7/agreements/example.pdf')

        assert res.status_code == 302
        assert res.location == 'https://example/path?param=value'
        uploader.get_signed_url.assert_called_with('g-cloud-7/agreements/1234/1234-example.pdf')


@mock.patch('dmutils.s3.S3')
class TestFrameworkDocumentDownload(BaseApplicationTest):
    def test_download_document(self, S3):
        uploader = mock.Mock()
        S3.return_value = uploader
        uploader.get_signed_url.return_value = 'http://url/path?param=value'

        self.login()

        res = self.client.get('/suppliers/frameworks/g-cloud-7/files/example.pdf')

        assert res.status_code == 302
        assert res.location == 'http://asset-host/path?param=value'
        uploader.get_signed_url.assert_called_with('g-cloud-7/communications/example.pdf')

    def test_download_document_returns_404_if_url_is_None(self, S3):
        uploader = mock.Mock()
        S3.return_value = uploader
        uploader.get_signed_url.return_value = None

        self.login()

        res = self.client.get('/suppliers/frameworks/g-cloud-7/files/example.pdf')

        assert res.status_code == 404


@mock.patch('dmutils.s3.S3')
class TestDownloadDeclarationDocument(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):
    def setup_method(self, method):
        super().setup_method(method)
        self.login()
        self.data_api_client_patch = mock.patch('app.main.views.services.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_document_url(self, s3):
        s3.return_value.get_signed_url.return_value = 'http://example.com/modern-slavery-statement.pdf'

        res = self.client.get(
            '/suppliers/assets/g-cloud-11/documents/1234/modern-slavery-statement.pdf'
        )

        assert res.status_code == 302
        assert res.headers['Location'] == 'http://asset-host/modern-slavery-statement.pdf'

    def test_missing_document_url(self, s3):
        s3.return_value.get_signed_url.return_value = None

        res = self.client.get(
            '/suppliers/frameworks/g-cloud-11/documents/1234/modern-slavery-statement.pdf'
        )

        assert res.status_code == 404

    def test_document_url_not_matching_user_supplier(self, s3):
        res = self.client.get(
            '/suppliers/frameworks/g-cloud-11/documents/999/modern-slavery-statement.pdf'
        )

        assert res.status_code == 404


class TestStartSupplierDeclaration(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_start_declaration_goes_to_declaration_overview_page(self):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        response = self.client.get('/suppliers/frameworks/g-cloud-7/declaration/start')
        document = html.fromstring(response.get_data(as_text=True))

        assert (
            document.xpath("//a[normalize-space(string(.))='Start your declaration']/@href")[0]
            == '/suppliers/frameworks/g-cloud-7/declaration/reuse'
        )
        assert document.xpath(
            "//p[contains(normalize-space(string()), $t)]",
            t="change your answers before the application deadline at "
            "5pm\u00a0BST,\u00a0Tuesday\u00a06\u00a0October\u00a02015.",
        )


@pytest.mark.parametrize('method', ('get', 'post'))
class TestDeclarationOverviewSubmit(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):
    """Behaviour common to both GET and POST views on path /suppliers/frameworks/g-cloud-7/declaration."""

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_supplier_not_interested(self, method):
        self.login()

        self.data_api_client.get_framework.side_effect = assert_args_and_return(
            self.framework(status="open"), "g-cloud-7"
        )
        self.data_api_client.get_supplier_framework_info.side_effect = assert_args_and_raise(
            APIError(mock.Mock(status_code=404)),
            1234,
            "g-cloud-7",
        )
        self.data_api_client.set_supplier_declaration.side_effect = AssertionError("This shouldn't be called")

        response = getattr(self.client, method)("/suppliers/frameworks/g-cloud-7/declaration")

        assert response.status_code == 404

    def test_framework_coming(self, method):
        self.login()

        self.data_api_client.get_framework.side_effect = assert_args_and_return(
            self.framework(status="coming"),
            "g-cloud-7",
        )
        self.data_api_client.get_supplier_framework_info.side_effect = assert_args_and_return(
            self.supplier_framework(framework_slug="g-cloud-7"),
            1234,
            "g-cloud-7",
        )
        self.data_api_client.set_supplier_declaration.side_effect = AssertionError("This shouldn't be called")

        response = getattr(self.client, method)("/suppliers/frameworks/g-cloud-7/declaration")

        assert response.status_code == 404

    def test_framework_unknown(self, method):
        self.login()

        self.data_api_client.get_framework.side_effect = assert_args_and_raise(
            APIError(mock.Mock(status_code=404)),
            "muttoning-clouds",
        )
        self.data_api_client.get_supplier_framework_info.side_effect = assert_args_and_raise(
            APIError(mock.Mock(status_code=404)),
            1234,
            "muttoning-clouds",
        )
        self.data_api_client.set_supplier_declaration.side_effect = AssertionError("This shouldn't be called")

        response = getattr(self.client, method)("/suppliers/frameworks/muttoning-clouds/declaration")

        assert response.status_code == 404


class TestDeclarationOverview(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    @staticmethod
    def _extract_section_information(doc, section_title, expect_edit_link=True):
        """
            given a section (full text) name, returns that section's relevant information in a tuple (format described
            in comments)
        """

        table_xpath = "//dl[preceding::h2[1][normalize-space(string())=$section_title]]"
        edit_as_xpath = (
            "//span[@class='dm-section-action-link'][preceding::h2[1][normalize-space(string())=$section_title]]"
        )
        caption_xpath = "normalize-space(string(./preceding::h2[1]))"
        row_heading_xpath = "normalize-space(string(./dt))"
        row_value_xpath = "normalize-space(string(./dd))"
        row_a_element_xpath = "./dd//a"
        row_a_href_xpath = "./dd//a/@href"
        row_li_element_xpath = "./dd//li"
        rows_xpath = ".//div[contains(@class,'govuk-summary-list__row')]"

        tables = doc.xpath(
            table_xpath,
            section_title=section_title,
        )
        assert len(tables) == 1
        table = tables[0]

        edit_as = doc.xpath(
            edit_as_xpath,
            section_title=section_title,
        )
        assert ([a.xpath("normalize-space(string())") for a in edit_as] == ["Edit"]) is expect_edit_link

        return (
            # table caption text
            table.xpath(caption_xpath),
            # "Edit" link href
            edit_as[0].xpath("@href")[0] if expect_edit_link else None,
            tuple(
                (
                    # contents of row heading
                    row.xpath(row_heading_xpath),
                    # full text contents of row "value"
                    row.xpath(row_value_xpath),
                    # full text contents of each a element in row value
                    tuple(a.xpath("normalize-space(string())") for a in row.xpath(row_a_element_xpath)),
                    # href of each a element in row value
                    tuple(row.xpath(row_a_href_xpath)),
                    # full text contents of each li element in row value
                    tuple(li.xpath("normalize-space(string())") for li in row.xpath(row_li_element_xpath)),
                ) for row in table.xpath(rows_xpath)
            )
        )

    @staticmethod
    def _section_information_strip_edit_href(section_information):
        row_heading, edit_href, rows = section_information
        return row_heading, None, rows

    def _setup_data_api_client(self, framework_status, framework_slug, declaration, prefill_fw_slug):
        self.data_api_client.get_framework.side_effect = assert_args_and_return(
            self.framework(slug=framework_slug, name="F-Cumulus 0", status=framework_status),
            framework_slug,
        )
        self.data_api_client.get_supplier_framework_info.side_effect = assert_args_and_return(
            self.supplier_framework(
                framework_slug=framework_slug,
                declaration=declaration,
                prefill_declaration_from_framework_slug=prefill_fw_slug,
            ),
            1234,
            framework_slug,
        )
        self.data_api_client.set_supplier_declaration.side_effect = AssertionError("This shouldn't be called")

    # corresponds to the parametrization args:
    # "framework_slug,declaration,decl_valid,prefill_fw_slug,expected_sections"
    _common_parametrization = tuple(
        chain.from_iterable(chain(
        ((  # noqa
            "g-cloud-9",
            empty_declaration,
            False,
            prefill_fw_slug,
            (
                (   # expected result for "Providing suitable services" section as returned by
                    # _extract_section_information
                    "Providing suitable services",
                    "/suppliers/frameworks/g-cloud-9/declaration/edit/providing-suitable-services",
                    (
                        (
                            "Services are cloud-related",
                            "Answer question",
                            ("Answer question",),
                            ("/suppliers/frameworks/g-cloud-9/declaration/edit/providing-suitable-services",),
                            (),
                        ),
                        (
                            "Services in scope for G-Cloud",
                            "Answer question",
                            ("Answer question",),
                            ("/suppliers/frameworks/g-cloud-9/declaration/edit/providing-suitable-"
                                "services#servicesDoNotInclude",),
                            (),
                        ),
                        (
                            "Buyers pay for what they use",
                            "Answer question",
                            ("Answer question",),
                            (
                                "/suppliers/frameworks/g-cloud-9/declaration/edit/providing-suitable-services"
                                "#payForWhatUse",
                            ),
                            (),
                        ),
                        (
                            "What your team will deliver",
                            "Answer question",
                            ("Answer question",),
                            (
                                "/suppliers/frameworks/g-cloud-9/declaration/edit/providing-suitable-"
                                "services#offerServicesYourselves",
                            ),
                            (),
                        ),
                        (
                            "Contractual responsibility and accountability",
                            "Answer question",
                            ("Answer question",),
                            (
                                "/suppliers/frameworks/g-cloud-9/declaration/edit/providing-suitable-"
                                "services#fullAccountability",
                            ),
                            (),
                        ),
                    ),
                ),
                (   # expected result for "Grounds for mandatory exclusion" section as returned by
                    # _extract_section_information
                    "Grounds for mandatory exclusion",
                    "/suppliers/frameworks/g-cloud-9/declaration/edit/grounds-for-mandatory-exclusion",
                    (
                        (
                            "Organised crime or conspiracy convictions",
                            q_link_text_prefillable_section,
                            (q_link_text_prefillable_section,),
                            ("/suppliers/frameworks/g-cloud-9/declaration/edit/grounds-for-mandatory-exclusion",),
                            (),
                        ),
                        (
                            "Bribery or corruption convictions",
                            q_link_text_prefillable_section,
                            (q_link_text_prefillable_section,),
                            (
                                "/suppliers/frameworks/g-cloud-9/declaration/edit/grounds-for-mandatory-"
                                "exclusion#corruptionBribery",
                            ),
                            (),
                        ),
                        (
                            "Fraud convictions",
                            q_link_text_prefillable_section,
                            (q_link_text_prefillable_section,),
                            (
                                "/suppliers/frameworks/g-cloud-9/declaration/edit/grounds-for-mandatory-"
                                "exclusion#fraudAndTheft",
                            ),
                            (),
                        ),
                        (
                            "Terrorism convictions",
                            q_link_text_prefillable_section,
                            (q_link_text_prefillable_section,),
                            (
                                "/suppliers/frameworks/g-cloud-9/declaration/edit/grounds-for-mandatory-"
                                "exclusion#terrorism",
                            ),
                            (),
                        ),
                        (
                            "Organised crime convictions",
                            q_link_text_prefillable_section,
                            (q_link_text_prefillable_section,),
                            (
                                "/suppliers/frameworks/g-cloud-9/declaration/edit/grounds-for-mandatory-"
                                "exclusion#organisedCrime",
                            ),
                            (),
                        ),
                    ),
                ),
                (   # expected result for "How you’ll deliver your services" section as returned by
                    # _extract_section_information
                    "How you’ll deliver your services",
                    "/suppliers/frameworks/g-cloud-9/declaration/edit/how-youll-deliver-your-services",
                    (
                        (
                            "Subcontractors or consortia",
                            q_link_text_prefillable_section,
                            (q_link_text_prefillable_section,),
                            (
                                "/suppliers/frameworks/g-cloud-9/declaration/edit/how-youll-deliver-your-"
                                "services",
                            ),
                            (),
                        ),
                    ),
                ),
            ),
        ) for empty_declaration in (None, {})),  # two possible ways of specifying a "empty" declaration - test both
        ((  # noqa
            "g-cloud-9",
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
                (   # expected result for "Providing suitable services" section as returned by
                    # _extract_section_information
                    "Providing suitable services",
                    "/suppliers/frameworks/g-cloud-9/declaration/edit/providing-suitable-services",
                    (
                        (
                            "Services are cloud-related",
                            "Answer question",
                            ("Answer question",),
                            ("/suppliers/frameworks/g-cloud-9/declaration/edit/providing-suitable-services",),
                            (),
                        ),
                        (
                            "Services in scope for G-Cloud",
                            "Answer question",
                            ("Answer question",),
                            (
                                "/suppliers/frameworks/g-cloud-9/declaration/edit/providing-suitable-"
                                "services#servicesDoNotInclude",
                            ),
                            (),
                        ),
                        (
                            "Buyers pay for what they use",
                            "Answer question",
                            ("Answer question",),
                            (
                                "/suppliers/frameworks/g-cloud-9/declaration/edit/providing-suitable-"
                                "services#payForWhatUse",
                            ),
                            (),
                        ),
                        (
                            "What your team will deliver",
                            "Answer question",
                            ("Answer question",),
                            (
                                "/suppliers/frameworks/g-cloud-9/declaration/edit/providing-suitable-"
                                "services#offerServicesYourselves",
                            ),
                            (),
                        ),
                        (
                            "Contractual responsibility and accountability",
                            "Answer question",
                            ("Answer question",),
                            (
                                "/suppliers/frameworks/g-cloud-9/declaration/edit/providing-suitable-"
                                "services#fullAccountability",
                            ),
                            (),
                        ),
                    ),
                ),
                (   # expected result for "Grounds for mandatory exclusion" section as returned by
                    # _extract_section_information
                    "Grounds for mandatory exclusion",
                    "/suppliers/frameworks/g-cloud-9/declaration/edit/grounds-for-mandatory-exclusion",
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
                (   # expected result for "How you’ll deliver your services" section as returned by
                    # _extract_section_information
                    "How you’ll deliver your services",
                    "/suppliers/frameworks/g-cloud-9/declaration/edit/how-youll-deliver-your-services",
                    (
                        (
                            "Subcontractors or consortia",
                            (
                                "yourself without the use of third parties (subcontractors) as a prime contractor, "
                                "using third parties (subcontractors) to provide all services"
                            ),
                            (),
                            (),
                            (
                                "yourself without the use of third parties (subcontractors)",
                                "as a prime contractor, using third parties (subcontractors) to provide all services",
                            ),
                        ),
                    ),
                ),
            ),
        ),),
        ((  # noqa
            "g-cloud-9",
            dict(status=declaration_status, **(valid_g9_declaration_base())),
            True,
            prefill_fw_slug,
            (
                (   # expected result for "Providing suitable services" section as returned by
                    # _extract_section_information
                    "Providing suitable services",
                    "/suppliers/frameworks/g-cloud-9/declaration/edit/providing-suitable-services",
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
                (   # expected result for "Grounds for mandatory exclusion" section as returned by
                    # _extract_section_information
                    "Grounds for mandatory exclusion",
                    "/suppliers/frameworks/g-cloud-9/declaration/edit/grounds-for-mandatory-exclusion",
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
                (   # expected result for "How you’ll deliver your services" section as returned by
                    # _extract_section_information
                    "How you’ll deliver your services",
                    "/suppliers/frameworks/g-cloud-9/declaration/edit/how-youll-deliver-your-services",
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
            ),
        ) for declaration_status in ("started", "complete",)),
    ) for prefill_fw_slug, q_link_text_prefillable_section in (
        # test all of the previous combinations with two possible values of prefill_fw_slug
        (None, "Answer question",),
        ("some-previous-framework", "Review answer",),
    )))

    # this is more straightforward than _common_parametrization because we only have to care about non-open frameworks
    # G7 doesn't (yet?) have any "short names" for questions and so will be listing the answers in the
    # overview against their full verbose questions so any sections that we wanted to assert the content of
    # would require a reference copy of all its full question texts kept here. we don't want to do this so for
    # now don't assert any G7 sections...
    _g7_parametrization = (
        ("g-cloud-7", dict(FULL_G7_SUBMISSION, status="started"), True, None, ()),
        ("g-cloud-7", dict(FULL_G7_SUBMISSION, status="complete"), True, None, ()),
        ("g-cloud-7", None, False, None, ()),
        ("g-cloud-7", {}, False, None, ()),
    )

    @pytest.mark.parametrize(
        "framework_slug,declaration,decl_valid,prefill_fw_slug,expected_sections",
        _g7_parametrization
    )
    def test_display_open(self, framework_slug, declaration, decl_valid, prefill_fw_slug, expected_sections):
        self._setup_data_api_client("open", framework_slug, declaration, prefill_fw_slug)

        self.login()

        response = self.client.get("/suppliers/frameworks/{}/declaration".format(framework_slug))
        assert response.status_code == 200
        doc = html.fromstring(response.get_data(as_text=True))

        breadcrumbs = doc.xpath("//div[@class='govuk-breadcrumbs']/ol/li")
        assert tuple(li.xpath("normalize-space(string())") for li in breadcrumbs) == (
            "Digital Marketplace",
            "Your account",
            "Apply to F-Cumulus 0",
            "Your declaration overview",
        )
        assert tuple(li.xpath(".//a/@href") for li in breadcrumbs) == (
            ['/'],
            ['/suppliers'],
            [f'/suppliers/frameworks/{framework_slug}'],
            [],
        )

        assert bool(doc.xpath(
            "//p[contains(normalize-space(string()), $t)][contains(normalize-space(string()), $f)]",
            t="You must answer all questions and make your declaration before",
            f="F-Cumulus 0",
        )) is not decl_valid
        assert bool(doc.xpath(
            "//p[contains(normalize-space(string()), $t)][contains(normalize-space(string()), $f)]",
            t="You must make your declaration before",
            f="F-Cumulus 0",
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
        )) is not decl_valid
        if not decl_valid:
            # assert that all links with the label "Answer question" or "Review answer" link to some subpage (by
            # asserting that there are none that don't, having previously determined that such-labelled links exist)
            assert not doc.xpath(
                # we want the href to *contain* $u but not *be* $u
                "//a[normalize-space(string())=$a or normalize-space(string())=$b]"
                "[not(starts-with(@href, $u)) or @href=$u]",
                a="Answer question",
                b="Review answer",
                u="/suppliers/frameworks/{}/declaration/".format(framework_slug),
            )

        if decl_valid and declaration.get("status") != "complete":
            mdf_actions = doc.xpath(
                "//form[@method='POST'][.//button[normalize-space(string())=$t]]"
                "[.//input[@name='csrf_token']]/@action",
                t="Make declaration",
            )
            assert len(mdf_actions) == 2
            assert all(
                urljoin("/suppliers/frameworks/{}/declaration".format(framework_slug), action) ==
                "/suppliers/frameworks/{}/declaration".format(framework_slug)
                for action in mdf_actions
            )
        else:
            assert not doc.xpath("//button[normalize-space(string())=$t]", t="Make declaration")

        assert doc.xpath(
            "//a[normalize-space(string())=$t][@href=$u]",
            t="Return to application",
            u="/suppliers/frameworks/{}".format(framework_slug),
        )

        for expected_section in expected_sections:
            assert self._extract_section_information(doc, expected_section[0]) == expected_section

    @pytest.mark.parametrize(
        "framework_slug,declaration,decl_valid,prefill_fw_slug,expected_sections",
        tuple(
            (
                framework_slug,
                declaration,
                decl_valid,
                prefill_fw_slug,
                expected_sections,
            )
            for framework_slug, declaration, decl_valid, prefill_fw_slug, expected_sections
            in chain(_common_parametrization, _g7_parametrization)
            if (declaration or {}).get("status") == "complete"
        )
    )
    @pytest.mark.parametrize("framework_status", ("pending", "standstill", "live", "expired",))
    def test_display_closed(
        self,
        framework_status,
        framework_slug,
        declaration,
        decl_valid,
        prefill_fw_slug,
        expected_sections,
    ):
        self._setup_data_api_client(framework_status, framework_slug, declaration, prefill_fw_slug)

        self.login()

        response = self.client.get("/suppliers/frameworks/{}/declaration".format(framework_slug))
        assert response.status_code == 200
        doc = html.fromstring(response.get_data(as_text=True))

        breadcrumbs = doc.xpath("//div[@class='govuk-breadcrumbs']/ol/li")
        assert tuple(li.xpath("normalize-space(string())") for li in breadcrumbs) == (
            "Digital Marketplace",
            "Your account",
            "Your F-Cumulus 0 application",
            "Your declaration overview",
        )
        assert tuple(li.xpath(".//a/@href") for li in breadcrumbs) == (
            ['/'],
            ['/suppliers'],
            [f'/suppliers/frameworks/{framework_slug}'],
            [],
        )

        # there shouldn't be any links to the "edit" page
        assert not any(
            urljoin("/suppliers/frameworks/{}/declaration".format(framework_slug), a.attrib["href"]).startswith(
                "/suppliers/frameworks/{}/declaration/edit/".format(framework_slug)
            )
            for a in doc.xpath("//a[@href]")
        )

        # no submittable forms should be pointing at ourselves
        assert not any(
            urljoin(
                "/suppliers/frameworks/{}/declaration".format(framework_slug),
                form.attrib["action"],
            ) == "/suppliers/frameworks/{}/declaration".format(framework_slug)
            for form in doc.xpath("//form[.//input[@type='submit'] or .//button]")
        )

        assert not doc.xpath("//a[@href][normalize-space(string())=$label]", label="Answer question")
        assert not doc.xpath("//a[@href][normalize-space(string())=$label]", label="Review answer")

        assert not doc.xpath("//p[contains(normalize-space(string()), $t)]", t="make your declaration")
        assert not doc.xpath("//p[contains(normalize-space(string()), $t)]", t="edit your answers")

        for expected_section in expected_sections:
            assert self._extract_section_information(
                doc,
                expected_section[0],
                expect_edit_link=False,
            ) == self._section_information_strip_edit_href(expected_section)

    @pytest.mark.parametrize(
        "framework_slug,declaration,decl_valid,prefill_fw_slug,expected_sections",
        tuple(
            (
                framework_slug,
                declaration,
                decl_valid,
                prefill_fw_slug,
                expected_sections,
            )
            for framework_slug, declaration, decl_valid, prefill_fw_slug, expected_sections
            in chain(_common_parametrization, _g7_parametrization)
            if (declaration or {}).get("status") != "complete"
        )
    )
    @pytest.mark.parametrize("framework_status", ("pending", "standstill", "live", "expired",))
    def test_error_closed(
        self,
        framework_status,
        framework_slug,
        declaration,
        decl_valid,
        prefill_fw_slug,
        expected_sections,
    ):
        self._setup_data_api_client(framework_status, framework_slug, declaration, prefill_fw_slug)

        self.login()

        response = self.client.get("/suppliers/frameworks/{}/declaration".format(framework_slug))
        assert response.status_code == 410

    @pytest.mark.parametrize("framework_status", ("coming", "open", "pending", "standstill", "live", "expired",))
    def test_error_nonexistent_framework(self, framework_status):
        self._setup_data_api_client(framework_status, "g-cloud-31415", {"status": "complete"}, None)

        self.login()

        response = self.client.get("/suppliers/frameworks/g-cloud-31415/declaration")
        assert response.status_code == 404


class TestDeclarationSubmit(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

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
    def test_invalid_declaration(self, invalid_declaration, prefill_fw_slug):
        self.login()

        self.data_api_client.get_framework.side_effect = assert_args_and_return(
            self.framework(slug="g-cloud-9", name="G-Cloud 9", status="open"),
            "g-cloud-9",
        )
        self.data_api_client.get_supplier_framework_info.side_effect = assert_args_and_return(
            self.supplier_framework(
                framework_slug="g-cloud-9",
                declaration=invalid_declaration,
                prefill_declaration_from_framework_slug=prefill_fw_slug,  # should have zero effect
            ),
            1234,
            "g-cloud-9",
        )
        self.data_api_client.set_supplier_declaration.side_effect = AssertionError("This shouldn't be called")

        response = self.client.post("/suppliers/frameworks/g-cloud-9/declaration")

        assert response.status_code == 400

    @pytest.mark.parametrize("prefill_fw_slug", (None, "some-previous-framework",))
    @pytest.mark.parametrize("declaration_status", ("started", "complete",))
    @mock.patch("dmutils.s3.S3")  # needed by the framework dashboard which our request gets redirected to
    def test_valid_declaration(self, s3, prefill_fw_slug, declaration_status):
        self.login()

        self.data_api_client.get_framework.side_effect = assert_args_and_return(
            self.framework(slug="g-cloud-9", name="G-Cloud 9", status="open"),
            "g-cloud-9",
        )
        self.data_api_client.get_supplier_framework_info.side_effect = assert_args_and_return(
            self.supplier_framework(
                framework_slug="g-cloud-9",
                declaration=dict(status=declaration_status, **(valid_g9_declaration_base())),
                prefill_declaration_from_framework_slug=prefill_fw_slug,  # should have zero effect
            ),
            1234,
            "g-cloud-9",
        )
        self.data_api_client.set_supplier_declaration.side_effect = assert_args_and_return(
            dict(status="complete", **(valid_g9_declaration_base())),
            1234,
            "g-cloud-9",
            dict(status="complete", **(valid_g9_declaration_base())),
            "email@email.com",
        )

        response = self.client.post("/suppliers/frameworks/g-cloud-9/declaration", follow_redirects=True)

        # args of call are asserted by mock's side_effect
        assert self.data_api_client.set_supplier_declaration.called is True

        # this will be the response from the redirected-to view
        assert response.status_code == 200

    @pytest.mark.parametrize("framework_status", ("standstill", "pending", "live", "expired",))
    def test_closed_framework_state(self, framework_status):
        self.login()

        self.data_api_client.get_framework.side_effect = assert_args_and_return(
            self.framework(status=framework_status),
            "g-cloud-7",
        )
        self.data_api_client.get_supplier_framework_info.side_effect = assert_args_and_return(
            self.supplier_framework(framework_slug="g-cloud-7"),
            1234,
            "g-cloud-7",
        )
        self.data_api_client.set_supplier_declaration.side_effect = AssertionError("This shouldn't be called")

        response = self.client.post("/suppliers/frameworks/g-cloud-7/declaration")

        assert response.status_code == 404


class TestSupplierDeclaration(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    @pytest.mark.parametrize("empty_declaration", ({}, None,))
    def test_get_with_no_previous_answers(self, empty_declaration):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            framework_slug="g-cloud-7",
            declaration=empty_declaration,
        )
        self.data_api_client.get_supplier_declaration.side_effect = APIError(mock.Mock(status_code=404))

        res = self.client.get('/suppliers/frameworks/g-cloud-7/declaration/edit/g-cloud-7-essentials')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath('//input[@id="PR-1-yes"]/@checked') == []
        assert doc.xpath('//input[@id="PR-1-no"]/@checked') == []

    def test_get_with_with_previous_answers(self):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            framework_slug="g-cloud-7",
            declaration={"status": "started", "PR1": False}
        )

        res = self.client.get('/suppliers/frameworks/g-cloud-7/declaration/edit/g-cloud-7-essentials')

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//input[@id="input-PR1-2"]/@checked')) == 1

    def test_get_with_with_prefilled_answers(self):
        self.login()
        # Handle calls for both the current framework and for the framework to pre-fill from
        self.data_api_client.get_framework.side_effect = lambda framework_slug: {
            "g-cloud-9": self.framework(slug='g-cloud-9', name='G-Cloud 9', status='open'),
            "digital-outcomes-and-specialists-2": self.framework(
                slug='digital-outcomes-and-specialists-2',
                name='Digital Stuff 2', status='live'
            )
        }[framework_slug]

        # Current framework application information
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            framework_slug="g-cloud-9",
            declaration={"status": "started"},
            prefill_declaration_from_framework_slug="digital-outcomes-and-specialists-2"
        )

        # The previous declaration to prefill from
        self.data_api_client.get_supplier_declaration.return_value = {
            'declaration': self.supplier_framework(
                framework_slug="digital-outcomes-and-specialists-2",
                declaration={
                    "status": "complete",
                    "conspiracy": True,
                    "corruptionBribery": False,
                    "fraudAndTheft": True,
                    "terrorism": False,
                    "organisedCrime": False,
                }
            )["frameworkInterest"]["declaration"]
        }

        # The grounds-for-mandatory-exclusion section has "prefill: True" in the declaration manifest
        res = self.client.get(
            '/suppliers/frameworks/g-cloud-9/declaration/edit/grounds-for-mandatory-exclusion'
        )

        assert res.status_code == 200
        self.data_api_client.get_supplier_declaration.assert_called_once_with(
            1234, "digital-outcomes-and-specialists-2"
        )
        doc = html.fromstring(res.get_data(as_text=True))

        # Radio buttons have been pre-filled with the correct answers
        assert len(doc.xpath('//input[@id="input-conspiracy-1"][@value="True"]/@checked')) == 1
        assert len(doc.xpath('//input[@id="input-corruptionBribery-2"][@value="False"]/@checked')) == 1
        assert len(doc.xpath('//input[@id="input-fraudAndTheft-1"][@value="True"]/@checked')) == 1
        assert len(doc.xpath('//input[@id="input-terrorism-2"][@value="False"]/@checked')) == 1
        assert len(doc.xpath('//input[@id="input-organisedCrime-2"][@value="False"]/@checked')) == 1

        # Blue banner message is shown at top of page
        assert doc.xpath('normalize-space(string(//section[@class="dm-banner"]))') == \
            "Answers on this page are from an earlier declaration and need review."

        # Blue information messages are shown next to each question
        info_messages = doc.xpath('//span[contains(@class, "dm-error-message--notice")]')
        assert len(info_messages) == 5
        for message in info_messages:
            assert self.strip_all_whitespace(message.text_content()) == self.strip_all_whitespace(
                "Notice: This answer is from your Digital Stuff 2 declaration"
            )

    def test_get_with_with_partially_prefilled_answers(self):
        self.login()
        # Handle calls for both the current framework and for the framework to pre-fill from
        self.data_api_client.get_framework.side_effect = lambda framework_slug: {
            "g-cloud-9": self.framework(slug='g-cloud-9', name='G-Cloud 9', status='open'),
            "digital-outcomes-and-specialists-2": self.framework(
                slug='digital-outcomes-and-specialists-2',
                name='Digital Stuff 2', status='live'
            )
        }[framework_slug]

        # Current framework application information
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            framework_slug="g-cloud-9",
            declaration={"status": "started"},
            prefill_declaration_from_framework_slug="digital-outcomes-and-specialists-2"
        )

        # The previous declaration to prefill from - missing "corruptionBribery" and "terrorism" keys
        self.data_api_client.get_supplier_declaration.return_value = {
            'declaration': self.supplier_framework(
                framework_slug="digital-outcomes-and-specialists-2",
                declaration={
                    "status": "complete",
                    "conspiracy": True,
                    "fraudAndTheft": True,
                    "organisedCrime": False
                }
            )["frameworkInterest"]["declaration"]
        }

        # The grounds-for-mandatory-exclusion section has "prefill: True" in the declaration manifest
        res = self.client.get('/suppliers/frameworks/g-cloud-9/declaration/edit/grounds-for-mandatory-exclusion')

        assert res.status_code == 200
        self.data_api_client.get_supplier_declaration.assert_called_once_with(
            1234, "digital-outcomes-and-specialists-2"
        )
        doc = html.fromstring(res.get_data(as_text=True))

        # Radio buttons have been pre-filled with the correct answers
        assert len(doc.xpath('//input[@id="input-conspiracy-1"][@value="True"]/@checked')) == 1
        assert len(doc.xpath('//input[@id="input-fraudAndTheft-1"][@value="True"]/@checked')) == 1
        assert len(doc.xpath('//input[@id="input-organisedCrime-2"][@value="False"]/@checked')) == 1

        # Radio buttons for missing keys exist but have not been pre-filled
        assert len(doc.xpath('//input[@id="input-corruptionBribery-1"]')) == 1
        assert len(doc.xpath('//input[@id="input-corruptionBribery-2"]')) == 1
        assert len(doc.xpath('//input[@id="input-corruptionBribery-1"]/@checked')) == 0
        assert len(doc.xpath('//input[@id="input-corruptionBribery-2"]/@checked')) == 0
        assert len(doc.xpath('//input[@id="input-terrorism-1"]')) == 1
        assert len(doc.xpath('//input[@id="input-terrorism-2"]')) == 1
        assert len(doc.xpath('//input[@id="input-terrorism-1"]/@checked')) == 0
        assert len(doc.xpath('//input[@id="input-terrorism-2"]/@checked')) == 0

        # Blue banner message is shown at top of page
        assert doc.xpath('normalize-space(string(//section[@class="dm-banner"]))') == \
            "Answers on this page are from an earlier declaration and need review."

        # Blue information messages are shown next to pre-filled questions only
        info_messages = doc.xpath('//span[contains(@class, "dm-error-message--notice")]')
        assert len(info_messages) == 3
        for message in info_messages:
            assert self.strip_all_whitespace(message.text_content()) == self.strip_all_whitespace(
                "Notice: This answer is from your Digital Stuff 2 declaration"
            )

    def test_answers_not_prefilled_if_section_has_already_been_saved(self):
        self.login()
        # Handle calls for both the current framework and for the framework to pre-fill from
        self.data_api_client.get_framework.side_effect = lambda framework_slug: {
            "g-cloud-9": self.framework(slug='g-cloud-9', name='G-Cloud 9', status='open'),
            "digital-outcomes-and-specialists-2": self.framework(
                slug='digital-outcomes-and-specialists-2',
                name='Digital Stuff 2', status='live'
            )
        }[framework_slug]

        # Current framework application information with the grounds-for-mandatory-exclusion section complete
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            framework_slug="g-cloud-9",
            declaration={
                "status": "started",
                "conspiracy": False,
                "corruptionBribery": True,
                "fraudAndTheft": False,
                "terrorism": True,
                "organisedCrime": False
            },
            prefill_declaration_from_framework_slug="digital-outcomes-and-specialists-2"
        )

        # The previous declaration to prefill from - has relevant answers but should not ever be called
        self.data_api_client.get_supplier_declaration.return_value = {
            'declaration': self.supplier_framework(
                framework_slug="digital-outcomes-and-specialists-2",
                declaration={
                    "status": "complete",
                    "conspiracy": True,
                    "corruptionBribery": False,
                    "fraudAndTheft": True,
                    "terrorism": False,
                    "organisedCrime": False
                }
            )["frameworkInterest"]["declaration"]
        }

        # The grounds-for-mandatory-exclusion section has "prefill: True" in the declaration manifest
        res = self.client.get(
            '/suppliers/frameworks/g-cloud-9/declaration/edit/grounds-for-mandatory-exclusion'
        )

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))

        # Previous framework and declaration have not been fetchedself.
        assert self.data_api_client.get_framework.call_args_list == [
            mock.call('g-cloud-9'),
            mock.call('g-cloud-9')
        ]
        assert self.data_api_client.get_supplier_declaration.called is False

        # Radio buttons have been filled with the current answers; not those from previous declaration
        assert len(doc.xpath('//input[@id="input-conspiracy-2"][@value="False"]/@checked')) == 1
        assert len(doc.xpath('//input[@id="input-corruptionBribery-1"][@value="True"]/@checked')) == 1
        assert len(doc.xpath('//input[@id="input-fraudAndTheft-2"][@value="False"]/@checked')) == 1
        assert len(doc.xpath('//input[@id="input-terrorism-1"][@value="True"]/@checked')) == 1
        assert len(doc.xpath('//input[@id="input-organisedCrime-2"][@value="False"]/@checked')) == 1

        # No blue banner message is shown at top of page
        assert len(doc.xpath('//div[@class="banner-information-without-action"]')) == 0

        # No blue information messages are shown next to each question
        info_messages = doc.xpath('//div[@class="message-wrapper"]//span[@class="message-content"]')
        assert len(info_messages) == 0

    def test_answers_not_prefilled_if_section_marked_as_prefill_false(self):
        self.login()
        # Handle calls for both the current framework and for the framework to pre-fill from
        self.data_api_client.get_framework.side_effect = lambda framework_slug: {
            "g-cloud-9": self.framework(slug='g-cloud-9', name='G-Cloud 9', status='open'),
            "digital-outcomes-and-specialists-2": self.framework(
                slug='digital-outcomes-and-specialists-2',
                name='Digital Stuff 2', status='live'
            )
        }[framework_slug]

        # Current framework application information
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            framework_slug="g-cloud-9",
            declaration={"status": "started"},
            prefill_declaration_from_framework_slug="digital-outcomes-and-specialists-2"
        )

        # The previous declaration to prefill from - has relevant answers but should not ever be called
        self.data_api_client.get_supplier_declaration.return_value = {
            'declaration': self.supplier_framework(
                framework_slug="digital-outcomes-and-specialists-2",
                declaration={
                    "status": "complete",
                    "readUnderstoodGuidance": True,
                    "understandTool": True,
                    "understandHowToAskQuestions": False
                }
            )["frameworkInterest"]["declaration"]
        }

        # The how-you-apply section has "prefill: False" in the declaration manifest
        res = self.client.get(
            '/suppliers/frameworks/g-cloud-9/declaration/edit/how-you-apply'
        )

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))

        # Previous framework and declaration have not been fetched
        assert self.data_api_client.get_framework.call_args_list == [
            mock.call('g-cloud-9'),
            mock.call('g-cloud-9'),
        ]
        assert self.data_api_client.get_supplier_declaration.called is False

        # Radio buttons exist on page but have not been populated at all
        assert len(doc.xpath('//input[@id="input-readUnderstoodGuidance-1"]')) == 1
        assert len(doc.xpath('//input[@id="input-readUnderstoodGuidance-2"]')) == 1
        assert len(doc.xpath('//input[@id="input-readUnderstoodGuidance-1"]/@checked')) == 0
        assert len(doc.xpath('//input[@id="input-readUnderstoodGuidance-2"]/@checked')) == 0

        assert len(doc.xpath('//input[@id="input-understandTool-1"]')) == 1
        assert len(doc.xpath('//input[@id="input-understandTool-2"]')) == 1
        assert len(doc.xpath('//input[@id="input-understandTool-1"]/@checked')) == 0
        assert len(doc.xpath('//input[@id="input-understandTool-2"]/@checked')) == 0

        assert len(doc.xpath('//input[@id="input-understandHowToAskQuestions-1"]')) == 1
        assert len(doc.xpath('//input[@id="input-understandHowToAskQuestions-2"]')) == 1
        assert len(doc.xpath('//input[@id="input-understandHowToAskQuestions-1"]/@checked')) == 0
        assert len(doc.xpath('//input[@id="input-understandHowToAskQuestions-2"]/@checked')) == 0

        # No blue banner message is shown at top of page
        assert len(doc.xpath('//div[@class="banner-information-without-action"]')) == 0

        # No blue information messages are shown next to each question
        info_messages = doc.xpath('//div[@class="message-wrapper"]//span[@class="message-content"]')
        assert len(info_messages) == 0

    def test_post_valid_data(self):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            framework_slug="g-cloud-7",
            declaration={"status": "started"}
        )
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/declaration/edit/g-cloud-7-essentials',
            data=FULL_G7_SUBMISSION
        )

        assert res.status_code == 302
        assert self.data_api_client.set_supplier_declaration.called is True

    @mock.patch('dmutils.s3.S3')
    def test_post_valid_data_with_document_upload(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open', slug="g-cloud-11")
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            framework_slug="g-cloud-11",
            declaration={"status": "started"}
        )
        with freeze_time('2017-11-12 13:14:15'):
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-11/declaration/edit/modern-slavery',
                data={
                    'modernSlaveryTurnover': False,
                    'modernSlaveryReportingRequirements': None,
                    'mitigatingFactors3': None,
                    'modernSlaveryStatement': None,
                    'modernSlaveryStatementOptional': (BytesIO(valid_pdf_bytes), 'document.pdf')
                }
            )

        assert res.status_code == 302
        assert self.data_api_client.set_supplier_declaration.call_args_list == [
            mock.call(
                1234,
                "g-cloud-11",
                {
                    'status': 'started',
                    'modernSlaveryTurnover': False,
                    'modernSlaveryReportingRequirements': None,
                    'mitigatingFactors3': None,
                    'modernSlaveryStatement': None,
                    'modernSlaveryStatementOptional': 'http://localhost/suppliers/assets/g-cloud-11/documents/1234/modern-slavery-statement-2017-11-12-1314.pdf'  # noqa
                },
                "email@email.com"
            )
        ]
        s3.return_value.save.assert_called_once_with(
            'g-cloud-11/documents/1234/modern-slavery-statement-2017-11-12-1314.pdf',
            mock.ANY, acl='public-read'
        )

    def test_post_valid_data_to_complete_declaration(self):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            framework_slug="g-cloud-7",
            declaration=FULL_G7_SUBMISSION
        )
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/declaration/edit/grounds-for-discretionary-exclusion',
            data=FULL_G7_SUBMISSION
        )

        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-7/declaration'
        assert self.data_api_client.set_supplier_declaration.called is True
        assert self.data_api_client.set_supplier_declaration.call_args[0][2]['status'] == 'complete'

    def test_post_valid_data_with_api_failure(self):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            framework_slug="g-cloud-7",
            declaration={"status": "started"}
        )
        self.data_api_client.set_supplier_declaration.side_effect = APIError(mock.Mock(status_code=400))

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/declaration/edit/g-cloud-7-essentials',
            data=FULL_G7_SUBMISSION
        )

        assert res.status_code == 400

    def test_post_with_validation_errors(self):
        """Test that answers are not saved if there are errors

        For unit tests of the validation see :mod:`tests.app.main.helpers.test_frameworks`
        """
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(slug="g-cloud-12", status="open")

        # Missing answers to 'offerServicesYourselves' and 'fullAccountability'
        declaration_answers = {
            "servicesHaveOrSupportCloudHostingCloudSoftware": True,
            "servicesHaveOrSupportCloudSupport": True,
            "servicesDoNotInclude": True
        }

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-12/declaration/edit/providing-suitable-services',
            data=declaration_answers
        )

        assert res.status_code == 400
        assert self.data_api_client.set_supplier_declaration.called is False

        doc = html.fromstring(res.get_data(as_text=True))
        error_questions = doc.xpath("//ul[contains(@class, 'govuk-error-summary__list')]/li/a")
        assert len(error_questions) == 2
        assert error_questions[0].text == "Question 4"

    def test_post_invalidating_previously_valid_page(self):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(slug='g-cloud-9', status='open')

        mock_supplier_framework = self.supplier_framework(
            framework_slug="g-cloud-9",
            declaration={
                "status": "started",
                "establishedInTheUK": False,
                "appropriateTradeRegisters": True,
                "appropriateTradeRegistersNumber": "242#353",
                "licenceOrMemberRequired": "licensed",
                "licenceOrMemberRequiredDetails": "Foo Bar"
            }
        )
        self.data_api_client.get_supplier_framework_info.return_value = mock_supplier_framework
        self.data_api_client.get_supplier_declaration.return_value = {
            "declaration": mock_supplier_framework["frameworkInterest"]["declaration"]
        }

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-9/declaration/edit/established-outside-the-uk',
            data={
                "establishedInTheUK": "False",
                "appropriateTradeRegisters": "True",
                "appropriateTradeRegistersNumber": "242#353",
                "licenceOrMemberRequired": "licensed",
                # deliberately missing:
                "licenceOrMemberRequiredDetails": "",
            },
        )

        assert res.status_code == 400
        assert self.data_api_client.set_supplier_declaration.called is False

    def test_cannot_post_data_if_not_open(self):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.get_supplier_declaration.return_value = {
            "declaration": {"status": "started"}
        }
        res = self.client.post(
            '/suppliers/frameworks/g-cloud-7/declaration/edit/g-cloud-7-essentials',
            data=FULL_G7_SUBMISSION
        )

        assert res.status_code == 404
        assert self.data_api_client.set_supplier_declaration.called is False

    @mock.patch('dmutils.s3.S3')
    def test_post_declaration_answer_with_document_upload_errors(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open', slug="g-cloud-11")
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            framework_slug="g-cloud-11",
            declaration={"status": "started"}
        )
        with freeze_time('2017-11-12 13:14:15'):
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-11/declaration/edit/modern-slavery',
                data={
                    'modernSlaveryTurnover': False,
                    'modernSlaveryReportingRequirements': None,
                    'mitigatingFactors3': None,
                    'modernSlaveryStatement': None,
                    'modernSlaveryStatementOptional': (BytesIO(b"doc"), 'document.doc')
                }
            )

        assert res.status_code == 400
        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath(
            "//*[contains(@class,'govuk-error-message')][contains(normalize-space(string()), $text)]",
            text="Your document is not in an open format.",
        )) == 1
        assert self.data_api_client.set_supplier_declaration.called is False
        assert s3.return_value.save.called is False

    @mock.patch('dmutils.s3.S3')
    def test_post_declaration_answer_with_existing_document(self, s3):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open', slug="g-cloud-11")
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            framework_slug="g-cloud-11",
            declaration={"status": "started", "modernSlaveryStatement": "path/to/existing/upload"}
        )
        with freeze_time('2017-11-12 13:14:15'):
            res = self.client.post(
                '/suppliers/frameworks/g-cloud-11/declaration/edit/modern-slavery',
                data={
                    'modernSlaveryTurnover': True,
                    'modernSlaveryReportingRequirements': True,
                    'mitigatingFactors3': None,
                }
            )

        assert res.status_code == 302
        assert self.data_api_client.set_supplier_declaration.called
        assert s3.return_value.save.called is False

    def test_has_session_timeout_warning(self):
        self.data_api_client.get_framework.return_value = self.framework(status='open', slug="g-cloud-11")
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            framework_slug="g-cloud-11",
            declaration={"status": "started"}
        )

        with freeze_time("2019-11-12 13:14:15"):
            self.login()  # need to login after freezing time

            doc = html.fromstring(
                self.client.get(f"/suppliers/frameworks/g-cloud-11/declaration/edit/contact-details").data
            )

        assert "2:14pm GMT" in doc.xpath("string(.//div[@id='session-timeout-warning'])")


@mock.patch('dmutils.s3.S3')
class TestFrameworkUpdatesPage(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def _assert_page_title_and_table_headings(self, doc, check_for_tables=True):

        assert self.strip_all_whitespace('G-Cloud 7 updates') in self.strip_all_whitespace(doc.xpath('//h1')[0].text)

        headers = doc.xpath('//div[@class="govuk-grid-column-full"]//h2 | //table//caption//span')
        assert len(headers) == 2

        assert self.strip_all_whitespace(headers[0].text) == 'Communications'
        assert self.strip_all_whitespace(headers[1].text) == 'Clarificationquestionsandanswers'

        if check_for_tables:
            table_captions = doc.xpath('//div/table/caption/span')
            assert len(table_captions) == 2
            assert self.strip_all_whitespace(table_captions[0].text) == 'Communications'
            assert self.strip_all_whitespace(table_captions[1].text) == 'Clarificationquestionsandanswers'

    def test_should_be_a_503_if_connecting_to_amazon_fails(self, s3):
        self.data_api_client.get_framework.return_value = self.framework('open')
        # if s3 throws a 500-level error
        s3.side_effect = S3ResponseError(
            {'Error': {'Code': 500, 'Message': 'Amazon has collapsed. The internet is over.'}},
            'test_should_be_a_503_if_connecting_to_amazon_fails'
        )

        self.login()

        response = self.client.get('/suppliers/frameworks/g-cloud-7/updates')

        assert response.status_code == 503
        doc = html.fromstring(response.get_data(as_text=True))
        assert doc.xpath('//h1/text()')[0] == "Sorry, we’re experiencing technical difficulties"

    def test_empty_messages_exist_if_no_files_returned(self, s3):
        self.data_api_client.get_framework.return_value = self.framework('open')

        self.login()

        response = self.client.get('/suppliers/frameworks/g-cloud-7/updates')

        assert response.status_code == 200
        doc = html.fromstring(response.get_data(as_text=True))
        self._assert_page_title_and_table_headings(doc, check_for_tables=False)

        response_text = self.strip_all_whitespace(response.get_data(as_text=True))

        assert (
            self.strip_all_whitespace('<p class="govuk-body">No communications have been sent out.</p>')
            in response_text
        )
        assert (
            self.strip_all_whitespace(
                '<p class="govuk-body">No clarification questions and answers have been posted yet.</p>'
            )
            in response_text
        )

    def test_dates_for_open_framework_closed_for_questions(self, s3):
        self.data_api_client.get_framework.return_value = self.framework('open', clarification_questions_open=False)

        self.login()

        response = self.client.get('/suppliers/frameworks/g-cloud-7/updates')
        data = response.get_data(as_text=True)

        assert response.status_code == 200
        assert 'All clarification questions and answers will be published ' \
               'by 5pm BST, Tuesday 29 September 2015.' in data
        assert "You can ask clarification questions until " not in data

    def test_dates_for_open_framework_open_for_questions(self, s3):
        self.data_api_client.get_framework.return_value = self.framework('open', clarification_questions_open=True)
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        self.login()

        response = self.client.get('/suppliers/frameworks/g-cloud-7/updates')
        data = response.get_data(as_text=True)

        assert response.status_code == 200
        assert 'All clarification questions and answers will be published ' \
               'by 5pm BST, Tuesday 29 September 2015.' not in data
        assert 'You can ask clarification questions until 5pm BST, Tuesday 22 September 2015.' in data

    def test_the_tables_should_be_displayed_correctly(self, s3):
        self.data_api_client.get_framework.return_value = self.framework('open')

        files = [
            ('updates/communications/', 'file 1', 'odt'),
            ('updates/communications/', 'file 2', 'odt'),
            ('updates/clarifications/', 'file 3', 'odt'),
            ('updates/clarifications/', 'file 4', 'odt'),
        ]

        # the communications table is always before the clarifications table
        s3.return_value.list.return_value = [
            _return_fake_s3_file_dict("g-cloud-7/communications/{}".format(section), filename, ext)
            for section, filename, ext
            in files
        ]

        self.login()

        response = self.client.get('/suppliers/frameworks/g-cloud-7/updates')
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

    def test_names_with_the_section_name_in_them_will_display_correctly(self, s3):
        self.data_api_client.get_framework.return_value = self.framework('open')

        # for example: 'g-cloud-7-updates/clarifications/communications%20file.odf'
        files = [
            ('updates/communications/', 'clarifications file', 'odt'),
            ('updates/clarifications/', 'communications file', 'odt')
        ]

        s3.return_value.list.return_value = [
            _return_fake_s3_file_dict("g-cloud-7/communications/{}".format(section), filename, ext)
            for section, filename, ext
            in files
        ]

        self.login()

        response = self.client.get('/suppliers/frameworks/g-cloud-7/updates')
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

    @pytest.mark.parametrize('countersigned_path, contact_link_shown', [("path", False), (None, True)])
    def test_contact_link_only_shown_if_countersigned_agreement_is_not_yet_returned(
        self, s3, countersigned_path, contact_link_shown
    ):
        self.data_api_client.get_framework.return_value = self.framework('live', clarification_questions_open=False)
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            countersigned_path=countersigned_path
        )

        self.login()

        response = self.client.get('/suppliers/frameworks/g-cloud-7/updates')
        data = response.get_data(as_text=True)

        assert response.status_code == 200
        assert ('Contact the support team' in data) == contact_link_shown

    def test_clarification_question_validation_errors_appear(self, s3):
        self.data_api_client.get_framework.return_value = self.framework('live', clarification_questions_open=True)
        self.login()
        form_data = {
            "clarification_question": None
        }
        response = self.client.post("suppliers/frameworks/g-cloud-7/updates", data=form_data)
        data = response.get_data(as_text=True)
        assert response.status_code == 400
        assert "There was a problem with your submitted question" in data
        doc = html.fromstring(data)
        error_links = doc.xpath("//ul[contains(@class, 'govuk-error-summary__list')]/li/a")
        assert len(error_links) == 1
        assert error_links[0].text_content() == "Add text if you want to ask a question."
        assert error_links[0].get("href") == "#clarification_question"


@mock.patch('app.main.views.frameworks.DMNotifyClient.send_email', autospec=True)
class TestSendClarificationQuestionEmail(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()
        self.data_api_client.get_supplier.return_value = SupplierStub().single_result_response()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    @mock.patch('dmutils.s3.S3')
    def _send_email(self, s3, message):
        self.login()

        return self.client.post(
            "/suppliers/frameworks/g-cloud-7/updates",
            data={'clarification_question': message}
        )

    def test_should_call_send_email_with_correct_params_if_clarification_questions_open(self, notify_send_email):
        self.data_api_client.get_framework.return_value = self.framework(
            'open', name='Test Framework', clarification_questions_open=True
        )

        clarification_question = 'This is a clarification question.'
        with freeze_time('2019-07-02 01:02:03'):
            res = self._send_email(message=clarification_question)

        # Assert Notify email 1 is sent (clarification question)
        # Assert Notify email 2 is sent (receipt)
        notify_send_email.assert_has_calls(
            [
                mock.call(
                    mock.ANY,
                    to_email_address="clarification-questions@example.gov.uk",
                    template_name_or_id='framework-clarification-question',
                    personalisation={
                        "framework_name": "Test Framework",
                        "supplier_id": 1234,
                        "supplier_name": "My Little Company",
                        "supplier_reference": "2019-07-02-JRX8IN",
                        "clarification_question": clarification_question,
                    },
                    reference=(
                        "fw-clarification-question-"
                        "42c1W5KnFy1IaDtDEnNsOChYYluckBo_mzTuRxQawFo=-"
                        "9B7i7y6lXFmVCHXyU7sP0nkdNK6l8B98xRimoHMzpAw="
                    ),
                    allow_resend=True,
                ),
                mock.call(
                    mock.ANY,  # DMNotifyClient
                    to_email_address="email@email.com",
                    template_name_or_id='confirmation_of_clarification_question',
                    personalisation={
                        'user_name': 'Năme',
                        'framework_name': 'Test Framework',
                        "supplier_reference": "2019-07-02-JRX8IN",
                        'clarification_question_text': clarification_question,
                    },
                    reference=(
                        "fw-clarification-question-confirm-"
                        "42c1W5KnFy1IaDtDEnNsOChYYluckBo_mzTuRxQawFo=-"
                        "8yc90Y2VvBnVHT5jVuSmeebxOCRJcnKicOe7VAsKu50="
                    ),
                    reply_to_address_id='24908180-b64e-513d-ab48-fdca677cec52',
                )
            ]
        )

        # Assert audit event
        self.data_api_client.create_audit_event.assert_called_with(
            audit_type=AuditTypes.send_clarification_question,
            user="email@email.com",
            object_type="suppliers",
            object_id=1234,
            data={"question": clarification_question, 'framework': 'g-cloud-7'}
        )

        assert res.status_code == 200
        # Assert flash message
        doc = html.fromstring(res.get_data(as_text=True))
        flash_message = doc.cssselect(".dm-alert")[0]
        assert (
            flash_message.cssselect(".dm-alert__title")[0].text.strip()
            ==
            "Your clarification question has been sent. Answers to all "
            "clarification questions will be published on this page."
        )

    def test_email_not_sent_if_clarification_questions_closed(self, notify_send_email):
        self.data_api_client.get_framework.return_value = self.framework(
            'open', name='Test Framework', clarification_questions_open=False
        )
        response = self._send_email(message='I have missed the clarification question deadline!')

        assert response.status_code == 400
        assert notify_send_email.called is False
        assert self.data_api_client.create_audit_event.called is False

    @pytest.mark.parametrize(
        'invalid_clarification_question',
        (
            # Empty question
            {'question': '', 'error_message': 'Add text if you want to ask a question.'},
            # Whitespace only question
            {'question': '\t   \n\n\n', 'error_message': 'Add text if you want to ask a question.'},
            # Question length > 5000 characters
            {'question': ('ten__chars' * 500) + '1', 'error_message': 'Question cannot be longer than 5000 characters'}
        )
    )
    def test_should_not_send_email_if_invalid_clarification_question(
        self,
        notify_send_email,
        invalid_clarification_question,
    ):
        self.data_api_client.get_framework.return_value = self.framework('open')
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework()

        response = self._send_email(message=invalid_clarification_question['question'])

        # Assert no audit
        assert self.data_api_client.create_audit_event.call_count == 0
        # Assert no emails sent
        assert notify_send_email.call_count == 0

        assert response.status_code == 400
        # Assert error message shown
        assert (
            self.strip_all_whitespace('There was a problem with your submitted question')
            in self.strip_all_whitespace(response.get_data(as_text=True))
        )
        assert (
            self.strip_all_whitespace(invalid_clarification_question['error_message'])
            in self.strip_all_whitespace(response.get_data(as_text=True))
        )

    def test_should_be_a_503_if_email_fails(self, notify_send_email):
        self.data_api_client.get_framework.return_value = self.framework('open', name='Test Framework')
        notify_send_email.side_effect = EmailError("Arrrgh")

        clarification_question = 'This is a clarification question.'
        with freeze_time('2019-07-02 01:02:03'):
            response = self._send_email(message=clarification_question)
        # Assert send_email is called only once
        notify_send_email.assert_called_once_with(
            mock.ANY,
            to_email_address="clarification-questions@example.gov.uk",
            template_name_or_id='framework-clarification-question',
            personalisation={
                "framework_name": "Test Framework",
                "supplier_id": 1234,
                "supplier_name": "My Little Company",
                "supplier_reference": "2019-07-02-JRX8IN",
                "clarification_question": clarification_question,
            },
            reference=(
                "fw-clarification-question-"
                "42c1W5KnFy1IaDtDEnNsOChYYluckBo_mzTuRxQawFo=-"
                "9B7i7y6lXFmVCHXyU7sP0nkdNK6l8B98xRimoHMzpAw="
            ),
            allow_resend=True,
        )
        # Assert no audit
        assert self.data_api_client.create_audit_event.call_count == 0
        assert response.status_code == 503

    def test_should_fail_silently_if_receipt_email_fails(self, notify_send_email):
        notify_send_email.side_effect = [None, EmailError("Arrrgh")]
        self.data_api_client.get_framework.return_value = self.framework('open', name='Test Framework',
                                                                         clarification_questions_open=True)
        clarification_question = 'This is a clarification question.'
        with freeze_time('2019-07-02 01:02:03'):
            response = self._send_email(message=clarification_question)
        # first email sends, second email fails
        notify_send_email.assert_has_calls(
            [
                mock.call(
                    mock.ANY,
                    to_email_address="clarification-questions@example.gov.uk",
                    template_name_or_id="framework-clarification-question",
                    personalisation={
                        "framework_name": "Test Framework",
                        "supplier_id": 1234,
                        "supplier_name": "My Little Company",
                        "supplier_reference": "2019-07-02-JRX8IN",
                        "clarification_question": clarification_question,
                    },
                    reference=(
                        "fw-clarification-question-"
                        "42c1W5KnFy1IaDtDEnNsOChYYluckBo_mzTuRxQawFo=-"
                        "9B7i7y6lXFmVCHXyU7sP0nkdNK6l8B98xRimoHMzpAw="
                    ),
                    allow_resend=True,
                ),
                mock.call(
                    mock.ANY,  # DMNotifyClient
                    to_email_address="email@email.com",
                    template_name_or_id='confirmation_of_clarification_question',
                    personalisation={
                        'user_name': 'Năme',
                        'framework_name': 'Test Framework',
                        "supplier_reference": "2019-07-02-JRX8IN",
                        'clarification_question_text': clarification_question,
                    },
                    reference=(
                        "fw-clarification-question-confirm-"
                        "42c1W5KnFy1IaDtDEnNsOChYYluckBo_mzTuRxQawFo=-"
                        "8yc90Y2VvBnVHT5jVuSmeebxOCRJcnKicOe7VAsKu50="
                    ),
                    reply_to_address_id='24908180-b64e-513d-ab48-fdca677cec52',
                )
            ]
        )
        # assert reached end of view and redirected
        assert response.status_code == 200


class TestFrameworkChooseLotsOrServices(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):

    def setup_method(self, method):
        super().setup_method(method)
        self.get_metadata_patch = mock.patch('app.main.views.frameworks.content_loader.get_metadata')
        self.get_metadata = self.get_metadata_patch.start()
        self.get_metadata.return_value = 'g-cloud-6'
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)
        self.get_metadata_patch.stop()

    def test_choose_lot_form(self):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(
            slug='digital-outcomes-and-specialists',
            status='open'
        )

        choose_lot_form = self.client.get(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/service-type'
        )
        doc = html.fromstring(choose_lot_form.get_data(as_text=True))

        assert doc.cssselect('h1')[0].text_content().strip() == u'What type of service do you want to add?'
        radio_values = [radio.get('value') for radio in doc.cssselect('input[type="radio"]')]

        assert radio_values == [
            'digital-outcomes',
            'digital-specialists',
            'user-research-studios',
            'user-research-participants'
        ]

        assert doc.cssselect('main form button[type="submit"]')[0].text_content().strip() == "Save and continue"
        assert doc.cssselect(
            'form + p a'
        )[0].get('href') == "/suppliers/frameworks/digital-outcomes-and-specialists/submissions"

    def test_choose_service_form(self):
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(status='open', slug='g-cloud-12')

        choose_service_form = self.client.get('/suppliers/frameworks/g-cloud-12/submissions/service-type')
        doc = html.fromstring(choose_service_form.get_data(as_text=True))

        assert doc.cssselect('h1')[0].text_content().strip() == u'What type of service do you want to add?'
        radio_values = [radio.get('value') for radio in doc.cssselect('input[type="radio"]')]

        assert radio_values == [
            'cloud-hosting',
            'cloud-software',
            'cloud-support'
        ]

        assert doc.cssselect('main form button[type="submit"]')[0].text_content().strip() == "Save and continue"
        assert doc.cssselect('form + p a')[0].get('href') == "/suppliers/frameworks/g-cloud-12/submissions"

    def test_choose_lot_form_error_if_no_lot_chosen(self):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(
            slug='digital-outcomes-and-specialists',
            status='open'
        )

        choose_service_form = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/service-type', data={}
        )
        doc = html.fromstring(choose_service_form.get_data(as_text=True))

        assert choose_service_form.status_code == 400
        assert doc.cssselect('title')[0].text_content().strip().startswith('Error: ')
        assert doc.cssselect('.govuk-error-summary a')[0].text_content().strip() == "Select a type of service"
        assert len(doc.cssselect('input[type="radio"][checked]')) == 0
        assert len(doc.cssselect('input[type="radio"]:not([checked])')) == 4

    def test_choose_service_form_error_if_no_service_category_chosen(self):
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(status='open', slug='g-cloud-12')

        choose_service_form = self.client.post('/suppliers/frameworks/g-cloud-12/submissions/service-type', data={})
        doc = html.fromstring(choose_service_form.get_data(as_text=True))

        assert choose_service_form.status_code == 400
        assert doc.cssselect('title')[0].text_content().strip().startswith('Error: ')
        assert doc.cssselect('.govuk-error-summary a')[0].text_content().strip() == "Select a type of service"
        assert len(doc.cssselect('input[type="radio"][checked]')) == 0
        assert len(doc.cssselect('input[type="radio"]:not([checked])')) == 3

    def test_choose_service_form_redirect_on_submit(self):
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(status='open', slug='g-cloud-12')

        res = self.client.post(
            '/suppliers/frameworks/g-cloud-12/submissions/service-type',
            data={"lot_slug": "cloud-hosting"}
        )

        assert res.status_code == 302
        assert '/suppliers/frameworks/g-cloud-12/submissions/cloud-hosting' in res.location

    def test_choose_lot_form_redirect_on_submit(self):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(
            slug='digital-outcomes-and-specialists',
            status='open'
        )

        res = self.client.post(
            '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/service-type',
            data={"lot_slug": "digital-specialists"}
        )

        assert res.status_code == 302
        assert '/suppliers/frameworks/digital-outcomes-and-specialists/submissions/digital-specialists' in res.location


@mock.patch('app.main.views.frameworks.count_unanswered_questions')
class TestFrameworkSubmissionLots(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):

    def setup_method(self, method):
        super().setup_method(method)
        self.get_metadata_patch = mock.patch('app.main.views.frameworks.content_loader.get_metadata')
        self.get_metadata = self.get_metadata_patch.start()
        self.get_metadata.return_value = 'g-cloud-6'
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)
        self.get_metadata_patch.stop()

    def test_drafts_list_progress_count(self, count_unanswered):
        self.login()

        count_unanswered.return_value = 3, 1
        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'not-submitted'}
        ]

        submissions = self.client.get('/suppliers/frameworks/g-cloud-7/submissions')

        assert u'Drafts (1)' in submissions.get_data(as_text=True)
        assert u'You haven’t marked any services as complete yet.' in submissions.get_data(as_text=True)

    @pytest.mark.parametrize('framework_slug, show_service_data', (
        ('digital-outcomes-and-specialists-2', 0),
        ('g-cloud-9', 1),
    ))
    def test_submission_lots_page_shows_use_of_service_data_if_g_cloud_family(
        self, count_unanswered, framework_slug, show_service_data
    ):
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(slug=framework_slug, status="open")
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            framework_slug=framework_slug
        )

        res = self.client.get(f"/suppliers/frameworks/{framework_slug}/submissions")
        assert res.status_code == 200

        doc = html.fromstring(res.get_data(as_text=True))
        use_of_data = doc.xpath('//div[contains(@class, "use-of-service-data")]')
        assert len(use_of_data) == show_service_data

        if show_service_data:
            assert 'The service information you provide in your application:' in use_of_data[0].text_content()

    def test_add_service_button(self, count_unanswered):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        submissions = self.client.get('/suppliers/frameworks/g-cloud-7/submissions')

        doc = html.fromstring(submissions.get_data(as_text=True))

        add_service_button = doc.xpath('//a[contains(text(), "Add a service")]')[0]

        assert add_service_button.attrib["href"] == "/suppliers/frameworks/g-cloud-7/submissions/service-type"

    @pytest.mark.parametrize(
        'declaration, should_show_declaration_link, declaration_link_url',
        (
            ({'declaration': {}}, True, '/suppliers/frameworks/g-cloud-7/declaration/start'),
            ({'declaration': {'status': 'started'}}, True, '/suppliers/frameworks/g-cloud-7/declaration'),
            ({'declaration': {}}, True, '/suppliers/frameworks/g-cloud-7/declaration/start'),
            ({'declaration': {'status': 'started'}}, True, '/suppliers/frameworks/g-cloud-7/declaration'),
            ({'declaration': {'status': 'complete'}}, False, None),
            ({'declaration': {'status': 'complete'}}, False, None),
        )
    )
    def test_banner_on_submission_lot_page_shows_link_to_declaration(
        self, count_unanswered, declaration, should_show_declaration_link, declaration_link_url
    ):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier.return_value = SupplierStub().single_result_response()
        self.data_api_client.get_supplier_declaration.return_value = declaration
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'submitted'}
        ]

        submissions = self.client.get('/suppliers/frameworks/g-cloud-7/submissions')

        if should_show_declaration_link:
            doc = html.fromstring(submissions.get_data(as_text=True))
            assert doc.xpath('//*[@class="banner-information-without-action"]')
            decl_element = doc.xpath(
                "//*[contains(@class,'banner-content')][contains(normalize-space(string()), $text)]",
                text="make your supplier declaration",
            )
            assert decl_element[0].xpath('.//a[@href=$url]', url=declaration_link_url)

        else:
            # Application is done - don't show warning banner
            assert "Your application is not complete" not in submissions.get_data(as_text=True)

    @pytest.mark.parametrize(
        "incomplete_declaration,expected_url",
        (
            ({}, "/suppliers/frameworks/g-cloud-7/declaration/start"),
            ({"status": "started"}, "/suppliers/frameworks/g-cloud-7/declaration")
        )
    )
    def test_drafts_list_completed(self, count_unanswered, incomplete_declaration, expected_url):
        self.login()

        count_unanswered.return_value = 0, 1

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_declaration.return_value = {'declaration': incomplete_declaration}
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'submitted'}
        ]
        self.data_api_client.get_supplier.return_value = SupplierStub(
            company_details_confirmed=False
        ).single_result_response()

        submissions = self.client.get('/suppliers/frameworks/g-cloud-7/submissions')

        submissions_html = submissions.get_data(as_text=True)

        assert u'Ready for submission (1)' in submissions_html
        assert u'You haven’t added any draft services yet.' in submissions_html
        assert "Your application is not complete" in submissions_html

        doc = html.fromstring(submissions_html)
        assert doc.xpath('//*[@class="banner-information-without-action"]')
        decl_element = doc.xpath(
            "//*[contains(@class,'banner-content')][contains(normalize-space(string()), $text)]",
            text="make your supplier declaration",
        )
        assert decl_element[0].xpath('.//a[@href=$url]', url=expected_url)

    def test_drafts_list_completed_with_declaration_status(self, count_unanswered):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_declaration.return_value = {'declaration': {'status': 'complete'}}
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'submitted'}
        ]
        self.data_api_client.get_supplier.return_value = SupplierStub(
            company_details_confirmed=False
        ).single_result_response()

        submissions = self.client.get('/suppliers/frameworks/g-cloud-7/submissions')
        submissions_html = submissions.get_data(as_text=True)

        assert u'Ready for submission (1)' in submissions_html
        assert u'1 complete service was submitted' not in submissions_html
        assert "Your application is not complete" not in submissions_html

    def test_drafts_list_services_were_submitted(self, count_unanswered):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status='standstill')
        self.data_api_client.get_supplier_declaration.return_value = {'declaration': {'status': 'complete'}}
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'not-submitted'},
            {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'submitted'},
        ]

        submissions = self.client.get('/suppliers/frameworks/g-cloud-7/submissions')

        print(submissions.get_data(as_text=True))

        assert u'1 complete service was submitted' in submissions.get_data(as_text=True)

    def test_dos_drafts_list_with_open_framework(self, count_unanswered):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(
            slug='digital-outcomes-and-specialists',
            status='open'
        )
        self.data_api_client.get_supplier_declaration.return_value = {'declaration': {'status': 'complete'}}
        self.data_api_client.get_supplier.return_value = SupplierStub().single_result_response()
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'draft', 'lotSlug': 'digital-specialists', 'status': 'submitted'}
        ]

        submissions = self.client.get('/suppliers/frameworks/digital-outcomes-and-specialists/submissions')

        assert u'Ready for submission (1)' in submissions.get_data(as_text=True)
        assert u'You haven’t marked any services as complete yet.' not in submissions.get_data(as_text=True)
        assert "Your application is not complete" not in submissions.get_data(as_text=True)
        assert "You haven’t added any draft services yet." in submissions.get_data(as_text=True)

    def test_dos_drafts_list_with_closed_framework(self, count_unanswered):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(
            slug="digital-outcomes-and-specialists",
            status='pending'
        )
        self.data_api_client.get_supplier_declaration.return_value = {'declaration': {'status': 'complete'}}
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'draft', 'lotSlug': 'digital-specialists', 'status': 'not-submitted'},
            {'serviceName': 'draft', 'lotSlug': 'digital-specialists', 'status': 'submitted'},
        ]

        submissions = self.client.get('/suppliers/frameworks/digital-outcomes-and-specialists/submissions')

        assert submissions.status_code == 200
        assert u'Submitted' in submissions.get_data(as_text=True)
        assert u'Apply to provide' not in submissions.get_data(as_text=True)


@mock.patch('app.main.views.frameworks.count_unanswered_questions')
class TestFrameworkSubmissionServices(BaseApplicationTest, MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):

    def setup_method(self, method):
        super().setup_method(method)
        self.get_metadata_patch = mock.patch('app.main.views.frameworks.content_loader.get_metadata')
        self.get_metadata = self.get_metadata_patch.start()
        self.get_metadata.return_value = 'g-cloud-6'
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)
        self.get_metadata_patch.stop()

    def _assert_incomplete_application_banner_not_visible(self, html):
        assert "Your application is not complete" not in html

    def _assert_incomplete_application_banner(self,
                                              response_html,
                                              decl_item_href=None):
        doc = html.fromstring(response_html)
        assert "Your application is not complete" in response_html
        assert doc.xpath('//*[@class="banner-information-without-action"]')

        decl_element = doc.xpath(
            "//*[contains(@class,'banner-content')][contains(normalize-space(string()), $text)]",
            text="make your supplier declaration",
        )

        assert decl_element

        if decl_item_href:
            assert decl_element[0].xpath('.//a[@href=$url]', url=decl_item_href)

    @pytest.mark.parametrize(
        'framework_status, msg',
        [
            ('open', 'Add a service'),
            ('pending', 'You didn’t mark any services as complete.')
        ]
    )
    def test_services_list_open_or_pending_no_complete_services(self, count_unanswered, framework_status, msg):
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(status=framework_status)
        self.data_api_client.find_draft_services_iter.return_value = []
        count_unanswered.return_value = 0
        response = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/iaas')
        assert response.status_code == 200
        assert msg in response.get_data(as_text=True)

    @pytest.mark.parametrize('framework_status', ['open', 'pending'])
    def test_services_list_open_or_pending_and_no_declaration(self, count_unanswered, framework_status):
        self.login()

        self.data_api_client.get_framework.return_value = self.framework(status=framework_status)
        self.data_api_client.get_supplier_declaration.return_value = {
            "declaration": {"status": "started"}
        }
        response = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/iaas')
        assert response.status_code == 200
        assert 'You made your supplier declaration' not in response.get_data(as_text=True)

    def test_services_list_shows_g7_message_if_pending_and_application_made(self, count_unanswered):
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.get_supplier_declaration.return_value = self.supplier_framework()['frameworkInterest']
        self.data_api_client.get_supplier.return_value = SupplierStub().single_result_response()
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'submitted'}
        ]
        count_unanswered.return_value = 0, 1

        response = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs')
        doc = html.fromstring(response.get_data(as_text=True))

        assert response.status_code == 200
        heading = doc.xpath('//div[@class="summary-item-lede"]//h2[@class="summary-item-heading"]')
        assert len(heading) > 0
        assert "G-Cloud 7 is closed for applications" in heading[0].xpath('text()')[0]
        assert "You made your supplier declaration and submitted 1 complete service." in \
            heading[0].xpath('../p[1]/text()')[0]

        self._assert_incomplete_application_banner_not_visible(response.get_data(as_text=True))

    def test_shows_g7_message_if_pending_and_services_not_submitted(self, count_unanswered):
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(status='pending')
        self.data_api_client.get_supplier_declaration.return_value = self.supplier_framework()['frameworkInterest']
        self.data_api_client.get_supplier.return_value = SupplierStub().single_result_response()
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'not-submitted'}
        ]
        count_unanswered.return_value = 0, 1

        response = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs')
        doc = html.fromstring(response.get_data(as_text=True))

        assert response.status_code == 200
        heading = doc.xpath('//div[@class="summary-item-lede"]//h2[@class="summary-item-heading"]')
        assert len(heading) > 0
        assert "G-Cloud 7 is closed for applications" in heading[0].xpath('text()')[0]
        assert "You made your supplier declaration and submitted 0 complete services." in \
            heading[0].xpath('../p[1]/text()')[0]
        assert "These services were not completed" in doc.xpath('//main//p[@class="hint"]')[0].xpath('text()')[0]

        self._assert_incomplete_application_banner_not_visible(response.get_data(as_text=True))

    def test_drafts_list_progress_count(self, count_unanswered):
        self.login()

        count_unanswered.return_value = 3, 1
        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'not-submitted'}
        ]

        lot_page = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs')

        assert u'Service can be moved to complete' not in lot_page.get_data(as_text=True)
        assert u'4 unanswered questions' in lot_page.get_data(as_text=True)

    def test_drafts_list_can_be_completed(self, count_unanswered):
        self.login()

        count_unanswered.return_value = 0, 1

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'not-submitted'}
        ]

        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs')

        assert u'Service can be marked as complete' in res.get_data(as_text=True)
        assert u'1 optional question unanswered' in res.get_data(as_text=True)

    @pytest.mark.parametrize(
        "incomplete_declaration,expected_url",
        (
            ({}, "/suppliers/frameworks/g-cloud-7/declaration/start"),
            ({"status": "started"}, "/suppliers/frameworks/g-cloud-7/declaration")
        )
    )
    def test_drafts_list_completed(self, count_unanswered, incomplete_declaration, expected_url):
        self.login()

        count_unanswered.return_value = 0, 1

        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.data_api_client.get_supplier_declaration.return_value = {'declaration': incomplete_declaration}
        self.data_api_client.find_draft_services_iter.return_value = [
            {'serviceName': 'draft', 'lotSlug': 'scs', 'status': 'submitted'}
        ]
        self.data_api_client.get_supplier.return_value = SupplierStub(
            company_details_confirmed=False
        ).single_result_response()

        lot_page = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs')

        lot_page_html = lot_page.get_data(as_text=True)
        assert u'Service can be moved to complete' not in lot_page_html
        self._assert_incomplete_application_banner(lot_page_html, decl_item_href=expected_url)

    @pytest.mark.parametrize(
        ('copied', 'link_shown'),
        (
            ((False, False, False), True),
            ((True, False, True), True),
            ((True, True, True), False),
        )
    )
    def test_drafts_list_has_link_to_add_published_services_if_any_services_not_yet_copied(
        self, count_unanswered, copied, link_shown
    ):
        self.data_api_client.find_services.return_value = {
            'services': [
                {'question1': 'answer1', 'copiedToFollowingFramework': copied[0]},
                {'question2': 'answer2', 'copiedToFollowingFramework': copied[1]},
                {'question2': 'answer2', 'copiedToFollowingFramework': copied[2]},
            ],
        }
        self.data_api_client.get_framework.return_value = self.framework(status='open')
        self.login()

        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs')
        doc = html.fromstring(res.get_data(as_text=True))
        link = doc.xpath(
            "//*[@id='main-content']/p[1]/a[normalize-space(string())='View and add your services from G-Cloud\xa07']"
        )

        assert self.data_api_client.find_services.call_args_list == [
            mock.call(
                supplier_id=1234,
                framework='g-cloud-6',
                lot='scs',
                status='published',
            )
        ]

        if link_shown:
            assert link
            assert '/suppliers/frameworks/g-cloud-7/submissions/scs/previous-services' in link[0].values()
        else:
            assert not link

    def test_link_to_add_previous_services_not_shown_if_no_defined_previous_framework(self, count_unanswered):
        self.get_metadata.side_effect = ContentNotFoundError('Not found')
        self.login()

        res = self.client.get('/suppliers/frameworks/g-cloud-7/submissions/scs')
        doc = html.fromstring(res.get_data(as_text=True))

        assert not doc.xpath("//a[normalize-space(string())='View and add your services from G-Cloud\xa07']")

    def test_redirect_to_previous_services_for_lot_with_one_service_limit_and_no_drafts_and_previous_service_to_copy(
        self, count_unanswered
    ):
        self.data_api_client.get_framework.return_value = self.framework(slug='digital-outcomes-and-specialists-3')
        self.data_api_client.find_draft_services_iter.return_value = []
        self.get_metadata.return_value = 'digital-outcomes-and-specialists-2'
        self.data_api_client.find_services.return_value = {"services": [{"copiedToFollowingFramework": False}]}
        self.login()

        res = self.client.get('/suppliers/frameworks/digital-outcomes-and-specialists-3/submissions/digital-outcomes')

        assert res.status_code == 302
        assert '/digital-outcomes-and-specialists-3/submissions/digital-outcomes/previous-services' in res.location

    def test_500s_if_previous_framework_not_found(self, count_unanswered):
        self.data_api_client.get_framework.side_effect = [
            self.framework(slug='g-cloud-10'),
            HTTPError(mock.Mock(status_code=404)),
        ]
        self.data_api_client.find_draft_services_iter.return_value = []
        self.login()

        res = self.client.get('/suppliers/frameworks/g-cloud-10/submissions/cloud-hosting')
        assert res.status_code == 500


class TestContractVariation(BaseApplicationTest):

    def setup_method(self, method):
        super(TestContractVariation, self).setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

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

        self.g9_framework = self.framework(
            name='G-Cloud 9',
            slug='g-cloud-9',
            status='live',
            framework_agreement_version='3.1'
        )
        self.g9_framework['frameworks']['variations'] = {"1": {"createdAt": "2018-08-16"}}

        self.login()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_get_page_renders_if_all_ok(self):
        self.data_api_client.get_framework.return_value = self.g8_framework
        self.data_api_client.get_supplier_framework_info.return_value = self.good_supplier_framework

        res = self.client.get("/suppliers/frameworks/g-cloud-8/contract-variation/1")
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 200
        assert len(doc.xpath('//h1[contains(text(), "Accept the contract variation for G-Cloud 8")]')) == 1

    def test_supplier_must_be_on_framework(self):
        supplier_not_on_framework = self.good_supplier_framework.copy()
        supplier_not_on_framework['frameworkInterest']['onFramework'] = False
        self.data_api_client.get_framework.return_value = self.g8_framework
        self.data_api_client.get_supplier_framework_info.return_value = supplier_not_on_framework

        res = self.client.get("/suppliers/frameworks/g-cloud-8/contract-variation/1")

        assert res.status_code == 404

    def test_variation_must_exist(self):
        self.data_api_client.get_framework.return_value = self.g8_framework
        self.data_api_client.get_supplier_framework_info.return_value = self.good_supplier_framework

        # There is no variation number 2
        res = self.client.get("/suppliers/frameworks/g-cloud-8/contract-variation/2")

        assert res.status_code == 404

    def test_agreement_must_be_returned_already(self):
        agreement_not_returned = self.good_supplier_framework.copy()
        agreement_not_returned['frameworkInterest']['agreementReturned'] = False
        self.data_api_client.get_framework.return_value = self.g8_framework
        self.data_api_client.get_supplier_framework_info.return_value = agreement_not_returned

        res = self.client.get("/suppliers/frameworks/g-cloud-8/contract-variation/1")

        assert res.status_code == 404

    def test_shows_form_if_not_yet_agreed(self):
        self.data_api_client.get_framework.return_value = self.g8_framework
        self.data_api_client.get_supplier_framework_info.return_value = self.good_supplier_framework

        res = self.client.get("/suppliers/frameworks/g-cloud-8/contract-variation/1")
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 200
        assert len(doc.xpath('//label[contains(text(), "I accept these changes")]')) == 1
        assert len(doc.xpath('//button[normalize-space(string())=$t]', t="I accept")) == 1

    def test_shows_signer_details_and_no_form_if_already_agreed(self):
        already_agreed = self.good_supplier_framework.copy()
        already_agreed['frameworkInterest']['agreedVariations'] = {
            "1": {
                "agreedAt": "2016-08-19T15:47:08.116613Z",
                "agreedUserId": 1,
                "agreedUserEmail": "agreed@email.com",
                "agreedUserName": "William Drăyton",
            }}
        self.data_api_client.get_framework.return_value = self.g8_framework
        self.data_api_client.get_supplier_framework_info.return_value = already_agreed

        res = self.client.get("/suppliers/frameworks/g-cloud-8/contract-variation/1")
        page_text = res.get_data(as_text=True)
        doc = html.fromstring(page_text)

        assert res.status_code == 200
        assert len(doc.xpath('//h2[contains(text(), "Contract variation status")]')) == 1
        assert (
            "<span>William Drăyton<br />agreed@email.com<br />Friday 19 August 2016 at 4:47pm BST</span>" in page_text
        )
        assert "<span>Waiting for CCS to countersign</span>" in page_text
        assert len(doc.xpath('//label[contains(text(), "I accept these proposed changes")]')) == 0
        assert len(doc.xpath('//input[@value="I accept"]')) == 0

    def test_shows_signer_details_and_different_text_if_already_agreed_but_no_countersign(self):
        already_agreed = self.good_supplier_framework.copy()
        already_agreed['frameworkInterest']['agreedVariations'] = {
            "1": {
                "agreedAt": "2016-08-19T15:47:08.116613Z",
                "agreedUserId": 1,
                "agreedUserEmail": "agreed@email.com",
                "agreedUserName": "William Drăyton",
            }}
        self.data_api_client.get_framework.return_value = self.g9_framework
        self.data_api_client.get_supplier_framework_info.return_value = already_agreed

        res = self.client.get("/suppliers/frameworks/g-cloud-9/contract-variation/1")
        page_text = res.get_data(as_text=True)
        doc = html.fromstring(page_text)

        assert res.status_code == 200
        assert len(doc.xpath('//h1[contains(text(), "The contract variation for G-Cloud 9")]')) == 1
        assert len(doc.xpath('//h2[contains(text(), "Contract variation status")]')) == 1
        assert (
            "<span>William Drăyton<br />agreed@email.com<br />Friday 19 August 2016 at 4:47pm BST</span>" in page_text
        )
        assert "<span>Waiting for CCS to countersign</span>" in page_text
        assert "You have accepted the Crown Commercial Service’s changes to the framework agreement" in page_text
        assert "They will come into effect when CCS has countersigned them." in page_text
        assert len(doc.xpath('//label[contains(text(), "I accept these proposed changes")]')) == 0
        assert len(doc.xpath('//input[@value="I accept"]')) == 0

    def test_shows_updated_heading_and_countersigner_details_but_no_form_if_countersigned(self):
        already_agreed = self.good_supplier_framework.copy()
        already_agreed['frameworkInterest']['agreedVariations'] = {
            "1": {
                "agreedAt": "2016-08-19T15:47:08.116613Z",
                "agreedUserId": 1,
                "agreedUserEmail": "agreed@email.com",
                "agreedUserName": "William Drăyton",
            }}
        g8_with_countersigned_variation = self.framework(status='live', name='G-Cloud 8')
        g8_with_countersigned_variation['frameworks']['variations'] = {"1": {
            "createdAt": "2016-08-01T12:30:00.000000Z",
            "countersignedAt": "2016-10-01T02:00:00.000000Z",
            "countersignerName": "A.N. Other",
            "countersignerRole": "Head honcho",
        }
        }
        self.data_api_client.get_framework.return_value = g8_with_countersigned_variation
        self.data_api_client.get_supplier_framework_info.return_value = already_agreed

        res = self.client.get("/suppliers/frameworks/g-cloud-8/contract-variation/1")
        page_text = res.get_data(as_text=True)
        doc = html.fromstring(page_text)

        assert res.status_code == 200
        assert len(doc.xpath('//h1[contains(text(), "The contract variation for G-Cloud 8")]')) == 1
        assert len(doc.xpath('//h2[contains(text(), "Contract variation status")]')) == 1
        assert "<span>A.N. Other<br />Head honcho<br />Saturday 1 October 2016</span>" in page_text
        assert len(doc.xpath('//label[contains(text(), "I accept these proposed changes")]')) == 0
        assert len(doc.xpath('//input[@value="I accept"]')) == 0

    @mock.patch('app.main.views.frameworks.DMNotifyClient', autospec=True, create=True)
    def test_email_is_sent_to_correct_users(self, mocked_notify_class):
        mocked_notify_client = mocked_notify_class.return_value
        mocked_notify_client.templates = {'g-cloud-8_variation_1_agreed': 123456789}
        self.data_api_client.get_framework.return_value = self.g8_framework
        self.data_api_client.get_supplier_framework_info.return_value = self.good_supplier_framework
        res = self.client.post(
            "/suppliers/frameworks/g-cloud-8/contract-variation/1",
            data={"accept_changes": "Yes"}
        )

        assert res.status_code == 302
        assert res.location == "http://localhost/suppliers/frameworks/g-cloud-8/contract-variation/1"
        self.data_api_client.agree_framework_variation.assert_called_once_with(
            1234, 'g-cloud-8', '1', 123, 'email@email.com'
        )
        boss_email = mock.call(
            'bigboss@email.com', template_name_or_id=123456789, personalisation={'framework_name': 'g-cloud-8'},
            reference="contract-variation-agreed-confirmation-ouj_ZOpWHvitNdb7O7DDQGEB-lstuMfj9oEl5oWU4C0="
        )
        regular_email = mock.call(
            'email@email.com', template_name_or_id=123456789, personalisation={'framework_name': 'g-cloud-8'},
            reference="contract-variation-agreed-confirmation-8yc90Y2VvBnVHT5jVuSmeebxOCRJcnKicOe7VAsKu50="
        )
        mocked_notify_client.send_email.assert_has_calls([boss_email, regular_email], any_order=False)

    @mock.patch('app.main.views.frameworks.DMNotifyClient', autospec=True)
    def test_only_one_email_sent_if_user_is_framework_contact(self, mocked_notify_class):
        same_email_as_current_user = self.good_supplier_framework.copy()
        same_email_as_current_user['frameworkInterest']['declaration']['primaryContactEmail'] = 'email@email.com'
        self.data_api_client.get_framework.return_value = self.g8_framework
        self.data_api_client.get_supplier_framework_info.return_value = same_email_as_current_user
        mocked_notify_client = mocked_notify_class.return_value
        mocked_notify_client.templates = {'g-cloud-8_variation_1_agreed': 123456789}
        self.client.post(
            "/suppliers/frameworks/g-cloud-8/contract-variation/1",
            data={"accept_changes": "Yes"}
        )

        mocked_notify_client.send_email.assert_called_once_with(
            to_email_address='email@email.com',
            personalisation={'framework_name': 'g-cloud-8'},
            template_name_or_id=123456789,
            reference='contract-variation-agreed-confirmation-8yc90Y2VvBnVHT5jVuSmeebxOCRJcnKicOe7VAsKu50='
        )

    @mock.patch('app.main.views.frameworks.DMNotifyClient', autospec=True)
    def test_success_message_is_displayed_on_success(self, mocked_notify_class):
        mocked_notify_client = mocked_notify_class.return_value
        mocked_notify_client.templates = {'g-cloud-8_variation_1_agreed': 123456789}
        self.data_api_client.get_framework.return_value = self.g8_framework
        self.data_api_client.get_supplier_framework_info.return_value = self.good_supplier_framework
        res = self.client.post(
            "/suppliers/frameworks/g-cloud-8/contract-variation/1",
            data={"accept_changes": "Yes"},
            follow_redirects=True
        )
        doc = html.fromstring(res.get_data(as_text=True))

        assert mocked_notify_client.send_email.called
        assert res.status_code == 200
        assert len(
            doc.cssselect(".dm-alert:contains('You have accepted the proposed changes.')")
        ) == 1

    @mock.patch('app.main.views.frameworks.DMNotifyClient', autospec=True)
    def test_api_is_not_called_and_no_email_sent_for_subsequent_posts(self, mocked_notify_class):
        mocked_notify_client = mocked_notify_class.return_value
        already_agreed = self.good_supplier_framework.copy()
        already_agreed['frameworkInterest']['agreedVariations'] = {
            "1": {
                "agreedAt": "2016-08-19T15:47:08.116613Z",
                "agreedUserId": 1,
                "agreedUserEmail": "agreed@email.com",
                "agreedUserName": "William Drayton",
            }
        }
        self.data_api_client.get_framework.return_value = self.g8_framework
        self.data_api_client.get_supplier_framework_info.return_value = already_agreed

        res = self.client.post(
            "/suppliers/frameworks/g-cloud-8/contract-variation/1",
            data={"accept_changes": "Yes"}
        )
        assert res.status_code == 200
        assert self.data_api_client.agree_framework_variation.called is False
        assert mocked_notify_client.called is False

    def test_error_if_box_not_ticked(self):
        self.data_api_client.get_framework.return_value = self.g8_framework
        self.data_api_client.get_supplier_framework_info.return_value = self.good_supplier_framework

        res = self.client.post("/suppliers/frameworks/g-cloud-8/contract-variation/1", data={})
        doc = html.fromstring(res.get_data(as_text=True))

        assert res.status_code == 400
        validation_message = "You need to accept these changes to continue."
        assert len(
            doc.xpath('//span[@class="validation-message"][contains(text(), "{}")]'.format(validation_message))
        ) == 1


class TestReuseFrameworkSupplierDeclaration(BaseApplicationTest,
                                            MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):
    """Tests for frameworks/<framework_slug>/declaration/reuse view."""

    def setup_method(self, method):
        super(TestReuseFrameworkSupplierDeclaration, self).setup_method(method)
        self.login()
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()
        self.framework_stub = FrameworkStub(
            name='g-cloud-8',
            slug='g-cloud-8',
            allow_declaration_reuse=True,
            applications_close_at=datetime(2009, 12, 3, 1, 1, 1)
        ).single_result_response()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_reusable_declaration_framework_slug_param(self):
        """Ensure that when using the param to specify declaration we collect the correct declaration."""
        self.data_api_client.get_framework.return_value = self.framework_stub
        self.data_api_client.get_supplier_framework_info.return_value = {
            'frameworkInterest': {'declaration': {'status': 'complete'}, 'onFramework': True}
        }

        resp = self.client.get(
            '/suppliers/frameworks/g-cloud-9/declaration/reuse?reusable_declaration_framework_slug=g-cloud-8'
        )

        assert resp.status_code == 200
        self.data_api_client.get_framework.assert_has_calls([mock.call('g-cloud-9'), mock.call('g-cloud-8')])
        self.data_api_client.get_supplier_framework_info.assert_called_once_with(1234, 'g-cloud-8')

    def test_404_when_specified_declaration_not_found(self):
        """Fail on a 404 if declaration is specified but not found."""
        self.data_api_client.get_framework.return_value = {'frameworks': {'status': 'open'}}
        self.data_api_client.get_supplier_framework_info.side_effect = APIError(mock.Mock(status_code=404))

        resp = self.client.get(
            '/suppliers/frameworks/g-cloud-9/declaration/reuse?reusable_declaration_framework_slug=g-cloud-8'
        )

        assert resp.status_code == 404

        assert self.data_api_client.get_framework.call_args_list == [
            mock.call('g-cloud-9'),
            mock.call('g-cloud-9'),
        ]
        self.data_api_client.get_supplier_framework_info.assert_called_once_with(1234, 'g-cloud-8')

    def test_redirect_when_declaration_not_found(self):
        """Redirect if a reusable declaration is not found."""
        self.data_api_client.get_framework.return_value = self.framework_stub
        frameworks = [
            FrameworkStub(
                name='ben-cloud-2',
                allow_declaration_reuse=True,
                applications_close_at=datetime(2009, 3, 3, 1, 1, 1)
            ).response()
        ]

        supplier_declarations = []
        self.data_api_client.find_frameworks.return_value = {'frameworks': frameworks}
        self.data_api_client.find_supplier_declarations.return_value = dict(
            frameworkInterest=supplier_declarations
        )

        resp = self.client.get(
            '/suppliers/frameworks/g-cloud-9/declaration/reuse',
        )

        assert resp.location.endswith('/suppliers/frameworks/g-cloud-9/declaration')
        assert self.data_api_client.get_framework.call_args_list == [
            mock.call('g-cloud-9'),
            mock.call('g-cloud-9'),
        ]
        self.data_api_client.find_supplier_declarations.assert_called_once_with(1234)

    def test_success_reuse_g_cloud_7_for_8(self):
        """Test success path."""
        t09 = datetime(2009, 3, 3, 1, 1, 1)
        t10 = datetime(2010, 3, 3, 1, 1, 1)
        t11 = datetime(2011, 3, 3, 1, 1, 1)
        t12 = datetime(2012, 3, 3, 1, 1, 1)

        frameworks_response = [
            FrameworkStub(slug='g-cloud-8', allow_declaration_reuse=True, applications_close_at=t12).response(),
            FrameworkStub(slug='g-cloud-7', allow_declaration_reuse=True, applications_close_at=t11).response(),
            FrameworkStub(
                slug='digital-outcomes-and-specialists', allow_declaration_reuse=True, applications_close_at=t10
            ).response(),
            FrameworkStub(slug='g-cloud-6', allow_declaration_reuse=True, applications_close_at=t09).response(),
        ]
        framework_response = FrameworkStub(
            slug='g-cloud-8', allow_declaration_reuse=True, applications_close_at=t09).response()

        supplier_declarations_response = [
            {'x': 'foo', 'frameworkSlug': 'g-cloud-6', 'declaration': {'status': 'complete'}, 'onFramework': True},
            {'x': 'foo', 'frameworkSlug': 'g-cloud-7', 'declaration': {'status': 'complete'}, 'onFramework': True},
            {'x': 'foo', 'frameworkSlug': 'dos', 'declaration': {'status': 'complete'}, 'onFramework': True}
        ]
        self.data_api_client.find_frameworks.return_value = {'frameworks': frameworks_response}
        self.data_api_client.get_framework.return_value = {'frameworks': framework_response}
        self.data_api_client.find_supplier_declarations.return_value = {
            'frameworkInterest': supplier_declarations_response
        }

        resp = self.client.get(
            '/suppliers/frameworks/g-cloud-8/declaration/reuse',
        )

        assert resp.status_code == 200
        expected = 'In March&nbsp;2011, your organisation completed a declaration for G-Cloud 7.'
        assert expected in str(resp.data)
        assert self.data_api_client.get_framework.call_args_list == [
            mock.call('g-cloud-8'),
            mock.call('g-cloud-8'),
        ]
        self.data_api_client.find_supplier_declarations.assert_called_once_with(1234)


class TestReuseFrameworkSupplierDeclarationPost(BaseApplicationTest,
                                                MockEnsureApplicationCompanyDetailsHaveBeenConfirmedMixin):
    """Tests for frameworks/<framework_slug>/declaration/reuse POST view."""

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()
        self.login()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_reuse_no(self):
        """Assert that the redirect happens and the client sets the prefill pref to None."""
        self.data_api_client.get_framework.return_value = self.framework()

        data = {'reuse': 'no', 'old_framework_slug': 'should-not-be-used'}
        resp = self.client.post('/suppliers/frameworks/g-cloud-9/declaration/reuse', data=data)

        assert resp.location.endswith('/suppliers/frameworks/g-cloud-9/declaration')
        self.data_api_client.set_supplier_framework_prefill_declaration.assert_called_once_with(
            1234,
            'g-cloud-9',
            None,
            'email@email.com'
        )

    def test_reuse_yes(self):
        """Assert that the redirect happens and the client sets the prefill pref to the desired framework slug."""
        data = {'reuse': 'yes', 'old_framework_slug': 'digital-outcomes-and-specialists-2'}
        self.data_api_client.get_supplier_framework_info.return_value = {
            'frameworkInterest': {
                'x_field': 'foo',
                'frameworkSlug': 'digital-outcomes-and-specialists-2',
                'declaration': {'status': 'complete'},
                'onFramework': True
            }
        }
        framework_response = {'frameworks': {'status': 'open', 'x_field': 'foo', 'allowDeclarationReuse': True}}
        self.data_api_client.get_framework.return_value = framework_response

        resp = self.client.post('/suppliers/frameworks/g-cloud-9/declaration/reuse', data=data)

        assert resp.location.endswith('/suppliers/frameworks/g-cloud-9/declaration')
        assert self.data_api_client.get_framework.call_args_list == [
            mock.call('g-cloud-9'),
            mock.call('digital-outcomes-and-specialists-2'),
        ]
        self.data_api_client.get_supplier_framework_info.assert_called_once_with(
            1234,
            'digital-outcomes-and-specialists-2'
        )
        self.data_api_client.set_supplier_framework_prefill_declaration.assert_called_once_with(
            1234,
            'g-cloud-9',
            'digital-outcomes-and-specialists-2',
            'email@email.com'
        )

    def test_reuse_invalid_framework_post(self):
        """Assert 404 for non reusable framework."""
        data = {'reuse': 'yes', 'old_framework_slug': 'digital-outcomes-and-specialists'}

        # A framework with allowDeclarationReuse as False
        self.data_api_client.get_framework.return_value = {
            'frameworks': {'status': 'open', 'x_field': 'foo', 'allowDeclarationReuse': False}
        }

        resp = self.client.post('/suppliers/frameworks/g-cloud-9/declaration/reuse', data=data)

        assert self.data_api_client.get_framework.call_args_list == [
            mock.call('g-cloud-9'),
            mock.call('digital-outcomes-and-specialists'),
        ]
        assert not self.data_api_client.get_supplier_framework_info.called
        assert resp.status_code == 404

    def test_reuse_non_existent_framework_post(self):
        """Assert 404 for non existent framework."""
        data = {'reuse': 'yes', 'old_framework_slug': 'digital-outcomes-and-specialists-1000000'}
        # Attach does not exist.
        self.data_api_client.get_framework.side_effect = [self.framework(), HTTPError()]

        resp = self.client.post('/suppliers/frameworks/g-cloud-9/declaration/reuse', data=data)

        assert resp.status_code == 404
        assert self.data_api_client.get_framework.call_args_list == [
            mock.call('g-cloud-9'),
            mock.call('digital-outcomes-and-specialists-1000000')
        ]
        # Should not do the declaration call if the framework is invalid.
        assert not self.data_api_client.get_supplier_framework_info.called

    def test_reuse_non_existent_declaration_post(self):
        """Assert 404 for non existent declaration."""
        data = {'reuse': 'yes', 'old_framework_slug': 'digital-outcomes-and-specialists-2'}
        framework_response = {'frameworks': {'status': 'open', 'x_field': 'foo', 'allowDeclarationReuse': True}}
        self.data_api_client.get_framework.return_value = framework_response

        self.data_api_client.get_supplier_framework_info.side_effect = HTTPError()

        # Do the post.
        resp = self.client.post('/suppliers/frameworks/g-cloud-9/declaration/reuse', data=data)

        assert resp.status_code == 404
        # Should get the framework
        assert self.data_api_client.get_framework.call_args_list == [
            mock.call('g-cloud-9'),
            mock.call('digital-outcomes-and-specialists-2'),
        ]
        # Should error getting declaration.
        self.data_api_client.get_supplier_framework_info.assert_called_once_with(
            1234, 'digital-outcomes-and-specialists-2'
        )


class TestSignatureLegalAuthority(BaseApplicationTest):
    """Tests for app.main.views.frameworks.legal_authority."""

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    @pytest.mark.parametrize(
        ('framework_status', 'status_code'),
        (
            ('coming', 404),
            ('open', 404),
            ('pending', 404),
            ('standstill', 200),
            ('live', 200),
            ('expired', 404),
        )
    )
    def test_only_works_for_live_and_standstill_frameworks(self, framework_status, status_code):
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(status=framework_status,
                                                                         slug='g-cloud-12',
                                                                         is_e_signature_supported=True)
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            on_framework=True)

        res = self.client.get("/suppliers/frameworks/g-cloud-12/start-framework-agreement-signing")
        assert res.status_code == status_code

    @pytest.mark.parametrize(
        ('is_e_signature_supported', 'on_framework', 'status_code'),
        (
            (False, True, 404),
            (True, True, 200),
            (True, False, 400),
        )
    )
    def test_only_works_for_supported_frameworks(self, is_e_signature_supported, on_framework, status_code):
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(
            status='standstill',
            slug='g-cloud-12',
            is_e_signature_supported=is_e_signature_supported)
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            on_framework=on_framework)

        res = self.client.get(f"/suppliers/frameworks/g-cloud-12/start-framework-agreement-signing")
        assert res.status_code == status_code

    def test_post_yes_redirects_to_signing_page(self):
        framework_slug = 'g-cloud-12'
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(status='standstill',
                                                                         slug=framework_slug,
                                                                         framework_agreement_version="1",
                                                                         is_e_signature_supported=True)
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            on_framework=True)

        res = self.client.post(f"/suppliers/frameworks/{framework_slug}/start-framework-agreement-signing",
                               data={'legal_authority': 'yes'})
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/frameworks/g-cloud-12/sign-framework-agreement'    \


    def test_post_no_shows_info(self):
        framework_slug = 'g-cloud-12'
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(status='standstill',
                                                                         slug=framework_slug,
                                                                         framework_agreement_version="1",
                                                                         is_e_signature_supported=True)
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            on_framework=True)

        res = self.client.post(f"/suppliers/frameworks/{framework_slug}/start-framework-agreement-signing",
                               data={'legal_authority': 'no'})
        assert res.status_code == 200
        assert "You cannot sign the Framework Agreement" in res.get_data(as_text=True)

    def test_post_no_response_shows_error(self):
        framework_slug = 'g-cloud-12'
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(status='standstill',
                                                                         slug=framework_slug,
                                                                         framework_agreement_version="1",
                                                                         is_e_signature_supported=True)
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            on_framework=True)
        res = self.client.post(f"/suppliers/frameworks/{framework_slug}/start-framework-agreement-signing",
                               data={})
        assert res.status_code == 400
        assert "Select yes if you have the legal authority to sign on behalf of your company" in res.get_data(
            as_text=True)


class TestSignFrameworkAgreement(BaseApplicationTest):
    """Tests for app.main.views.frameworks.sign_framework_agreement"""

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.frameworks.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    @pytest.mark.parametrize(
        ('is_e_signature_supported', 'on_framework', 'status_code'),
        (
            (False, True, 404),
            (True, True, 200),
            (True, False, 400),
        )
    )
    def test_only_works_for_supported_frameworks(self, is_e_signature_supported, on_framework, status_code):
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(
            status='standstill',
            slug='g-cloud-12',
            framework_agreement_version="1",
            is_e_signature_supported=is_e_signature_supported)
        self.data_api_client.find_draft_services_by_framework.return_value = {
            'meta': {'total': 1}
        }
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            on_framework=on_framework)

        res = self.client.get(f"/suppliers/frameworks/g-cloud-12/sign-framework-agreement")
        assert res.status_code == status_code

    @pytest.mark.parametrize(
        ('framework_status', 'status_code'),
        (
            ('coming', 404),
            ('open', 404),
            ('pending', 404),
            ('standstill', 200),
            ('live', 200),
            ('expired', 404),
        )
    )
    def test_only_works_for_live_and_standstill_frameworks(self, framework_status, status_code):
        self.data_api_client.get_framework.return_value = self.framework(status=framework_status,
                                                                         slug='g-cloud-12',
                                                                         framework_agreement_version="1",
                                                                         is_e_signature_supported=True)
        self.data_api_client.find_draft_services_by_framework.return_value = {
            'meta': {'total': 1}
        }
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            on_framework=True)
        self.login()

        res = self.client.get("/suppliers/frameworks/g-cloud-12/sign-framework-agreement")
        assert res.status_code == status_code

    def test_shows_error_messages(self):
        self.login()
        self.data_api_client.get_framework.return_value = self.framework(status='standstill',
                                                                         slug='g-cloud-12',
                                                                         framework_agreement_version="1",
                                                                         is_e_signature_supported=True)
        self.data_api_client.find_draft_services_by_framework.return_value = {
            'meta': {'total': 1}
        }
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            on_framework=True)

        res = self.client.post("/suppliers/frameworks/g-cloud-12/sign-framework-agreement", data={})
        assert res.status_code == 400
        text = res.get_data(as_text=True)
        assert 'Enter your full name.' in text
        assert 'Enter your role in the company.' in text
        assert 'Accept the terms and conditions of the Framework Agreement.' in text

    def test_post_signs_agreement(self):
        self.data_api_client.create_framework_agreement.return_value = {"agreement": {"id": 789}}
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            on_framework=True)
        self.data_api_client.find_draft_services_by_framework.return_value = {
            'meta': {'total': 1}
        }
        self.data_api_client.get_framework.return_value = self.framework(status='standstill',
                                                                         slug='g-cloud-12',
                                                                         framework_agreement_version="1",
                                                                         is_e_signature_supported=True)

        self.login()
        res = self.client.get("/suppliers/frameworks/g-cloud-12/sign-framework-agreement")
        assert res.status_code == 200
        res = self.client.post("/suppliers/frameworks/g-cloud-12/sign-framework-agreement",
                               data={"signerName": "Jane Doe",
                                     "signerRole": "Director",
                                     "signer_terms_and_conditions": "True"})

        self.data_api_client.create_framework_agreement.assert_called_once_with(1234, 'g-cloud-12', 'email@email.com')

        self.data_api_client.update_framework_agreement.assert_called_once_with(789, {
            "signedAgreementDetails": {"signerName": "Jane Doe",
                                       "signerRole": "Director"}},
            "email@email.com")

        self.data_api_client.sign_framework_agreement.assert_called_once_with(
            789,
            'email@email.com',
            {'uploaderUserId': 123}
        )

        assert res.status_code == 200
        doc = html.fromstring(res.get_data(as_text=True))
        assert doc.xpath("//h1")[0].text_content().strip() == "You’ve signed the G-Cloud 12 Framework Agreement"

    @mock.patch('app.main.views.frameworks.DMNotifyClient', autospec=True)
    def test_sign_framework_agreement_sends_notify_emails(self, mock_dmnotifyclient_class):
        mock_dmnotifyclient_instance = mock_dmnotifyclient_class.return_value
        self.data_api_client.find_users_iter.return_value = [
            {'emailAddress': 'email1', 'active': True},
            {'emailAddress': 'email2', 'active': True},
            {'emailAddress': 'email3', 'active': False}
        ]
        self.data_api_client.create_framework_agreement.return_value = {"agreement": {"id": 789}}
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(
            on_framework=True)
        self.data_api_client.find_draft_services_by_framework.return_value = {
            'meta': {'total': 1}
        }
        self.data_api_client.get_framework.return_value = self.framework(status='standstill',
                                                                         slug='g-cloud-12',
                                                                         framework_agreement_version="1",
                                                                         is_e_signature_supported=True)

        self.login()
        self.client.post("/suppliers/frameworks/g-cloud-12/sign-framework-agreement",
                         data={"signerName": "Jane Doe",
                               "signerRole": "Director",
                               "signer_terms_and_conditions": "True"})

        assert mock_dmnotifyclient_instance.send_email.call_count == 2
        assert (mock_dmnotifyclient_instance.send_email.call_args[1].get('template_name_or_id') ==
                'sign_framework_agreement_confirmation')

    def test_agreement_text_contains_supplier_details(self):
        self.data_api_client.get_framework.return_value = self.framework(status='standstill',
                                                                         slug='g-cloud-12',
                                                                         framework_agreement_version="1",
                                                                         is_e_signature_supported=True)
        self.data_api_client.find_draft_services_by_framework.return_value = {
            'meta': {'total': 1}
        }
        self.data_api_client.get_supplier_framework_info.return_value = self.supplier_framework(on_framework=True)

        self.data_api_client.get_supplier.return_value = {'suppliers': {'registeredName': 'Acme Company',
                                                                        'companiesHouseNumber': '87654321',
                                                                        'contactInformation':
                                                                            [{'address1': '10 Downing Street',
                                                                              'city': 'London',
                                                                              'postcode': 'SW1A 2AA'
                                                                              }]}}

        self.login()
        res = self.client.get("/suppliers/frameworks/g-cloud-12/sign-framework-agreement")
        text = res.get_data(as_text=True)
        assert "Lot 1: Cloud hosting, Lot 2: Cloud software, Lot 3: Cloud support" in text
        assert "Acme Company" in text
        assert "87654321" in text
        assert "10 Downing Street, London, SW1A 2AA" in text
