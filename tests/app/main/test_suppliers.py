# coding=utf-8
from datetime import datetime
from urllib.parse import urlparse

from flask import session, current_app
from lxml import html
import mock
import pytest
from werkzeug.exceptions import ServiceUnavailable

from dmapiclient import APIError, HTTPError
from dmapiclient.audit import AuditTypes
from dmtestutils.api_model_stubs import FrameworkStub, SupplierFrameworkStub
from dmutils import direct_plus_client

from tests.app.helpers import BaseApplicationTest, assert_args_and_return
from app.main.forms.suppliers import CompanyOrganisationSizeForm, CompanyTradingStatusForm


def framework_stub_dates(month):
    return {
        'applications_close_at': datetime(2000, month, 3),
        'intention_to_award_at': datetime(2000, month, 4),
        'clarifications_close_at': datetime(2000, month, 1),
        'clarifications_publish_at': datetime(2000, month, 2),
        'framework_live_at': datetime(2000, month, 5),
    }


FIND_FRAMEWORKS_RETURN_VALUE = {
    "frameworks": [
        FrameworkStub(
            status='expired',
            slug='h-cloud-88',
            name='H-Cloud 88',
            framework_family='g-cloud',
            **framework_stub_dates(1)
        ).response(),
        FrameworkStub(status='live', slug='g-cloud-6', **framework_stub_dates(2)).response(),
        FrameworkStub(status='open', slug='digital-outcomes-and-specialists', **framework_stub_dates(4)).response(),
        FrameworkStub(
            status='live',
            slug='digital-rhymes-and-reasons',
            name='Digital Rhymes and Reasons',
            framework_family='digital-outcomes-and-specialists',
            **framework_stub_dates(3)
        ).response(),
        FrameworkStub(status='open', slug='g-cloud-7', **framework_stub_dates(5)).response(),
    ]
}


def get_supplier(*args, **kwargs):
    supplier_info = {
        "id": 1234,
        "dunsNumber": "987654321",
        "companiesHouseNumber": "CH123456",
        "registeredName": "Official Name Inc",
        "registrationCountry": "country:BZ",
        "otherCompanyRegistrationNumber": "BEL153",
        "organisationSize": "small",
        "tradingStatus": "Open for business",
        "name": "Supplier Name",
        "description": "Supplier Description",
        "companyDetailsConfirmed": True,
        "contactInformation": [{
            "id": 2,
            "website": "supplier.dmdev",
            "email": "supplier@user.dmdev",
            "contactName": "Supplier Person",
            "phoneNumber": "0800123123",
            "address1": "1 Street",
            "address2": "2 Building",
            "city": "Supplierville",
            "country": "Supplierland",
            "postcode": "11 AB",
        }],
        "service_counts": {
            "G-Cloud 6": 12,
            "G-Cloud 5": 34
        }
    }
    supplier_info.update(kwargs)
    return {"suppliers": dict(
        filter(lambda x: x[1] is not None, supplier_info.items())
    )}


def get_user():
    return [{
        'id': 123,
        'name': "User Name",
        'emailAddress': "email@email.com",
        'loggedInAt': "2015-05-06T11:57:28.008690Z",
        'locked': False,
        'active': True,
        'role': 'supplier',
        'supplier': {
            'name': "Supplier Name",
            'supplierId': 1234,
            'supplierOrganisationSize': 'small'
        }
    }]


class TestSuppliersDashboard(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.suppliers.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_error_and_success_flashed_messages_only_are_shown_in_banner_messages(self):
        with self.client.session_transaction() as session:
            session['_flashes'] = [
                ('error', 'This is an error'),
                ('success', 'This is a success'),
            ]

        self.data_api_client.get_framework.return_value = self.framework('open')
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.find_audit_events.return_value = {
            "auditEvents": []
        }
        self.login()

        res = self.client.get("/suppliers")
        doc = html.fromstring(res.get_data(as_text=True))

        assert doc.cssselect(".dm-alert:contains('This is an error')")
        assert doc.cssselect(".dm-alert:contains('This is a success')")

    def test_shows_edit_buttons(self):
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.find_frameworks.return_value = FIND_FRAMEWORKS_RETURN_VALUE
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {
                    'frameworkSlug': 'h-cloud-88',
                    'services_count': 12,
                    "onFramework": True,
                    "agreementReturned": True,
                },
                {
                    'frameworkSlug': 'g-cloud-6',
                    'services_count': 99,
                    "onFramework": True,
                    "agreementReturned": True,
                },
            ],
        }

        self.login()

        res = self.client.get("/suppliers")
        assert res.status_code == 200

        document = html.fromstring(res.get_data(as_text=True))

        assert document.xpath(
            "//*[(.//h3)[1][normalize-space(string())=$f]][.//a[normalize-space(string())=$t][@href=$u]]",
            f="G-Cloud 6",
            t="View services",
            u="/suppliers/frameworks/g-cloud-6/services",
        )

        assert not document.xpath(
            "//*[(.//h3)[1][normalize-space(string())=$f]][.//a[normalize-space(string())=$t]]",
            f="G-Cloud 7",
            t="View services",
        )
        assert not document.xpath("//a[@href=$u]", u="/suppliers/frameworks/g-cloud-7/services")
        assert not document.xpath(
            "//*[(.//h3)[1][normalize-space(string())=$f]][.//a[normalize-space(string())=$t]]",
            f="H-Cloud 88",
            t="View services",
        )
        assert not document.xpath("//a[@href=$u]", u="/suppliers/frameworks/h-cloud-88/services")
        assert not document.xpath(
            "//*[(.//h3)[1][normalize-space(string())=$f]][.//a[normalize-space(string())=$t]]",
            f="Digital Rhymes and Reasons",
            t="View services",
        )
        assert not document.xpath("//a[@href=$u]", u="/suppliers/frameworks/digital-rhymes-and-reasons/services")

    @pytest.mark.parametrize('on_framework', (True, False))
    def test_only_shows_expired_dos3_if_supplier_was_on_framework(self, on_framework):
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(status='expired', slug='digital-outcomes-and-specialists-3').response(),
            ]
        }
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {
                    'frameworkSlug': 'digital-outcomes-and-specialists-3',
                    'onFramework': on_framework,
                }
            ]
        }

        self.login()

        response = self.client.get("/suppliers")
        assert response.status_code == 200

        document = html.fromstring(response.get_data(as_text=True))

        if on_framework:
            assert document.xpath(
                "//h3[normalize-space(string())=$f]"
                "[(following::a)[1][normalize-space(string())=$t1][@href=$u1]]",
                f="Digital Outcomes and Specialists 3",
                t1="View your opportunities",
                u1="/suppliers/opportunities/frameworks/digital-outcomes-and-specialists-3",
            )
            assert not document.xpath(
                "//h3[normalize-space(string())=$f]"
                "/..//a[normalize-space(string())=$t1]",
                f="Digital Outcomes and Specialists 3",
                t1="View services",
            )
            assert not document.xpath(
                "//h3[normalize-space(string())=$f]"
                "/..//a[normalize-space(string())=$t1]",
                f="Digital Outcomes and Specialists 3",
                t1="View documents",
            )
        else:
            assert not document.xpath("//h3[normalize-space(string())='Digital Outcomes and Specialists 3']")

    def test_shows_correct_expired_framework(self):
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(
                    status='expired',
                    slug='digital-outcomes-and-specialists-2',
                    frameworkExpiresAtUTC='2000-01-01T01:00:00.000000Z'
                ).response(),
                FrameworkStub(
                    status='expired',
                    slug='digital-outcomes-and-specialists-1',
                    frameworkExpiresAtUTC='2001-01-01T01:00:00.000000Z'
                ).response(),
            ]
        }
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {'frameworkSlug': 'digital-outcomes-and-specialists-1', 'onFramework': True},
                {'frameworkSlug': 'digital-outcomes-and-specialists-2', 'onFramework': True},
            ]
        }

        self.login()

        response = self.client.get("/suppliers")
        assert response.status_code == 200

        document = html.fromstring(response.get_data(as_text=True))

        assert document.xpath("//h3[normalize-space(string())='Digital Outcomes and Specialists 1']")
        assert not document.xpath("//h3[normalize-space(string())='Digital Outcomes and Specialists 2']")

    def test_shows_gcloud_7_application_button(self):
        self.data_api_client.get_framework_interest.return_value = {'frameworks': []}
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(status='expired', slug='digital-outcomes-and-specialists').response(),
                FrameworkStub(status='open', slug='g-cloud-7').response(),
            ]
        }

        self.login()

        response = self.client.get("/suppliers")
        document = html.fromstring(response.get_data(as_text=True))

        assert response.status_code == 200

        apply_button = document.xpath(
            "//h2[normalize-space()='G-Cloud 7 is open for applications']/following::input[1]"
        )[0]

        assert apply_button.value == "Apply"

    def test_shows_gcloud_7_continue_link(self):
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {'frameworkSlug': 'g-cloud-7'}
            ]
        }
        self.data_api_client.find_frameworks.return_value = FIND_FRAMEWORKS_RETURN_VALUE
        self.login()

        response = self.client.get("/suppliers")
        document = html.fromstring(response.get_data(as_text=True))

        assert response.status_code == 200
        continue_link = document.xpath(
            "//h2[normalize-space()='Your G-Cloud 7 application']"
            "/following::a[1][normalize-space()='Continue your application']"
        )
        assert continue_link
        assert continue_link[0].values()[0] == "/suppliers/frameworks/g-cloud-7"

    def test_shows_gcloud_7_closed_message_if_pending_and_no_interest(self):  # noqa
        self.data_api_client.get_framework.return_value = self.framework('pending')
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.get_supplier_frameworks.return_value = {'frameworkInterest': []}
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(status='pending', slug='g-cloud-7').response(),
            ]
        }
        self.login()

        res = self.client.get("/suppliers")
        doc = html.fromstring(res.get_data(as_text=True))

        message = doc.xpath('//aside[@class="temporary-message"]')
        assert len(message) > 0
        assert u"G-Cloud 7 is closed for applications" in message[0].xpath('h2/text()')[0]

    def test_shows_gcloud_7_closed_message_if_pending_and_no_application(self):  # noqa
        self.data_api_client.get_framework.return_value = self.framework('pending')
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {
                    'frameworkSlug': 'g-cloud-7',
                    'declaration': {'status': 'started'},
                    'drafts_count': 1,
                    'complete_drafts_count': 0
                }
            ]
        }
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(status='pending', slug='g-cloud-7').response(),
            ]
        }
        self.login()

        res = self.client.get("/suppliers")
        doc = html.fromstring(res.get_data(as_text=True))

        message = doc.xpath('//aside[@class="temporary-message"]')
        assert len(message) > 0
        assert u"G-Cloud 7 is closed for applications" in message[0].xpath('h2/text()')[0]
        assert u"You didn’t submit an application" in message[0].xpath('p[1]/text()')[0]
        assert len(message[0].xpath('p[2]/a[contains(@href, "suppliers/frameworks/g-cloud-7")]')) > 0

    def test_shows_gcloud_7_closed_message_if_pending_and_application_done(self):
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {
                    'frameworkSlug': 'g-cloud-7',
                    'declaration': {'status': 'complete'},
                    'drafts_count': 0,
                    'complete_drafts_count': 99
                }
            ]
        }
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(status='pending', slug='g-cloud-7').response(),
            ]
        }
        self.login()
        res = self.client.get("/suppliers")
        doc = html.fromstring(res.get_data(as_text=True))
        headings = doc.xpath('//h2[@class="summary-item-heading"]')
        assert len(headings) > 0
        assert u"G-Cloud 7 is closed for applications" in headings[0].xpath('text()')[0]
        assert u"You submitted 99 services for consideration" in headings[0].xpath('../p[1]/text()')[0]
        assert len(headings[0].xpath('../p[1]/a[contains(@href, "suppliers/frameworks/g-cloud-7")]')) > 0
        assert u"View your submitted application" in headings[0].xpath('../p[1]/a/text()')[0]

    def test_shows_gcloud_7_in_standstill_application_passed_with_message(self):
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {
                    'frameworkSlug': 'g-cloud-7',
                    'declaration': {'status': 'complete'},
                    'drafts_count': 0,
                    'complete_drafts_count': 99,
                    'onFramework': True,
                    'agreementReturned': False
                }
            ]
        }
        self.data_api_client.find_frameworks.return_value = {
            'frameworks': [self.framework(status='standstill', slug='g-cloud-7')['frameworks']]
        }

        self.login()
        res = self.client.get("/suppliers")
        doc = html.fromstring(res.get_data(as_text=True))
        headings = doc.xpath('//h2[@class="summary-item-heading"]')

        assert u"Pending services" in headings[0].xpath('text()')[0]

        first_table = doc.xpath(
            '//table[@class="summary-item-body"]'
        )

        assert u"Pending services" in first_table[0].xpath('caption/text()')[0]

        first_row = "".join(first_table[0].xpath('tbody/descendant::*/text()'))
        assert u"G-Cloud 7" in first_row
        assert u"Live from Monday 23 November 2015" in first_row
        assert u"99 services" in first_row
        assert u"99 services" in first_row
        assert u"You must sign the framework agreement to sell these services" in first_row

    def test_shows_gcloud_7_in_standstill_fw_agreement_returned(self):
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {
                    'frameworkSlug': 'g-cloud-7',
                    'declaration': {'status': 'complete'},
                    'drafts_count': 0,
                    'complete_drafts_count': 99,
                    'onFramework': True,
                    'agreementReturned': True
                }
            ]
        }
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [self.framework(status='standstill', slug='g-cloud-7')['frameworks']]
        }

        self.login()
        res = self.client.get("/suppliers")
        doc = html.fromstring(res.get_data(as_text=True))
        headings = doc.xpath('//h2[@class="summary-item-heading"]')

        assert u"Pending services" in headings[0].xpath('text()')[0]

        first_table = doc.xpath(
            '//table[@class="summary-item-body"]'
        )

        assert u"Pending services" in first_table[0].xpath('caption/text()')[0]

        first_row = "".join(first_table[0].xpath('tbody/descendant::*/text()'))
        assert u"G-Cloud 7" in first_row
        assert u"Live from Monday 23 November 2015" in first_row
        assert u"99 services" in first_row
        assert u"You must sign the framework agreement to sell these services" not in first_row

    def test_shows_gcloud_7_in_standstill_no_application(self):
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': []
        }
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(status='standstill', slug='g-cloud-7').response(),
            ]
        }

        self.login()
        res = self.client.get("/suppliers")
        doc = html.fromstring(res.get_data(as_text=True))

        assert not doc.xpath('//h2[normalize-space(string())=$t]', t="Pending services")

    def test_shows_gcloud_7_in_standstill_application_failed(self):
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {
                    'frameworkSlug': 'g-cloud-7',
                    'declaration': {'status': 'complete'},
                    'drafts_count': 0,
                    'complete_drafts_count': 99,
                    'onFramework': False,
                    'agreementReturned': False
                }
            ]
        }
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(status='standstill', slug='g-cloud-7').response(),
            ]
        }

        self.login()
        res = self.client.get("/suppliers")
        doc = html.fromstring(res.get_data(as_text=True))
        headings = doc.xpath('//h2[@class="summary-item-heading"]')

        assert u"Pending services" in headings[0].xpath('text()')[0]

        first_table = doc.xpath(
            '//table[@class="summary-item-body"]'
        )

        assert u"Pending services" in first_table[0].xpath('caption/text()')[0]

        first_row = "".join(first_table[0].xpath('tbody/descendant::*/text()'))
        assert u"G-Cloud 7" in first_row
        assert u"Live from Monday 23 November 2015" not in first_row
        assert u"99 services submitted" in first_row
        assert u"You must sign the framework agreement to sell these services" not in first_row
        assert u"View your services" in first_row

    def test_shows_gcloud_7_in_standstill_application_passed(self):
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {
                    'frameworkSlug': 'g-cloud-7',
                    'declaration': {'status': 'complete'},
                    'drafts_count': 0,
                    'complete_drafts_count': 99,
                    'onFramework': True,
                    'agreementReturned': True
                }
            ]
        }
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(
                    status='standstill', slug='g-cloud-7', framework_live_at=datetime(2015, 11, 23)
                ).response(),
            ]
        }

        self.login()
        res = self.client.get("/suppliers")
        doc = html.fromstring(res.get_data(as_text=True))
        headings = doc.xpath('//h2[@class="summary-item-heading"]')

        assert u"Pending services" in headings[0].xpath('text()')[0]

        first_table = doc.xpath(
            '//table[@class="summary-item-body"]'
        )

        assert u"Pending services" in first_table[0].xpath('caption/text()')[0]

        first_row = "".join(first_table[0].xpath('tbody/descendant::*/text()'))
        assert u"G-Cloud 7" in first_row
        assert u"Live from Monday 23 November 2015" in first_row
        assert u"99 services" in first_row
        assert u"You must sign the framework agreement to sell these services" not in first_row

    def test_shows_register_for_dos_button(self):
        self.data_api_client.get_framework.return_value = self.framework(status='other')
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(status='open', slug='digital-outcomes-and-specialists').response(),
                FrameworkStub(status='live', slug='g-cloud-7').response(),
            ]
        }
        self.login()

        response = self.client.get("/suppliers")
        document = html.fromstring(response.get_data(as_text=True))

        assert response.status_code == 200

        apply_button = document.xpath(
            "//h2[normalize-space()='Digital Outcomes and Specialists is open for applications']"
            "/following::input[1]"
        )[0]

        assert apply_button.value == "Apply"

    def test_shows_continue_with_dos_link(self):
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {'frameworkSlug': 'digital-outcomes-and-specialists'}
            ]
        }
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(status='open', slug='digital-outcomes-and-specialists').response(),
                FrameworkStub(status='live', slug='g-cloud-7').response(),
            ]
        }
        self.login()

        response = self.client.get("/suppliers")
        document = html.fromstring(response.get_data(as_text=True))

        assert response.status_code == 200
        continue_link = document.xpath(
            "//h2[normalize-space()='Your Digital Outcomes and Specialists application']"
            "/following::a[1][normalize-space()='Continue your application']"
        )
        assert continue_link
        assert continue_link[0].values()[0] == "/suppliers/frameworks/digital-outcomes-and-specialists"

    @mock.patch('app.main.views.suppliers.are_new_frameworks_live')
    def test_should_hide_banner_when_not_needed(self, are_new_frameworks_live):
        are_new_frameworks_live.return_value = False
        self.login()

        res = self.client.get("/suppliers")
        assert res.status_code == 200
        assert "Important information" not in res.get_data(as_text=True)

    @mock.patch('app.main.views.suppliers.are_new_frameworks_live')
    def test_should_show_banner_when_needed(self, are_new_frameworks_live):
        are_new_frameworks_live.return_value = True
        self.login()

        res = self.client.get("/suppliers")
        assert res.status_code == 200
        assert "Important information" in res.get_data(as_text=True)

    @mock.patch('app.main.views.suppliers.are_new_frameworks_live')
    def test_should_pass_through_request_parameters(self, are_new_frameworks_live):
        are_new_frameworks_live.return_value = True
        self.login()
        self.client.get("/suppliers?show_dmp_so_banner=true")
        assert are_new_frameworks_live.call_args[0][0].to_dict() == {"show_dmp_so_banner": 'true'}


class TestSupplierDetails(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.suppliers.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_shows_supplier_info(self):
        self.data_api_client.get_supplier.side_effect = get_supplier

        self.login()

        res = self.client.get("/suppliers/details")
        assert res.status_code == 200
        page_html = res.get_data(as_text=True)
        document = html.fromstring(page_html)

        for property_str in (
            # "Company details" section at the top
            # Address elements are tested separately in `test_shows_address_details()` due to HTML structure
            "Supplier Person",  # Contact name
            "supplier@user.dmdev",  # Contact email
            "0800123123",  # Phone number
            "Supplier Description",  # Supplier summary
            # "Registration information" section
            "Official Name Inc",  # Registered company name
            "CH123456",  # Companies House number
            "987654321",  # DUNS number
            "Open for business",  # Trading status
            "Small",  # Size
        ):
            # Property exists on page
            assert document.xpath("//*[normalize-space(string())=$t]", t=property_str), property_str
            # Property has associated Change link
            assert document.xpath(f"//dd[normalize-space(text())='{property_str}']/following-sibling::dd/a/text()")[0]\
                .strip() == 'Edit'

        # Registration number not shown if Companies House ID exists
        assert "BEL153" not in page_html

        self.data_api_client.get_supplier.assert_called_once_with(1234)

    def test_registration_number_field_shows_other_registration_num_if_no_companies_house_num(self):
        self.data_api_client.get_supplier.return_value = get_supplier(
            companiesHouseNumber=None, otherCompanyRegistrationNumber="42, EARTH"
        )
        self.login()

        res = self.client.get("/suppliers/details")
        assert res.status_code == 200
        page_html = res.get_data(as_text=True)
        document = html.fromstring(page_html)
        assert document.xpath("//dt[normalize-space(text())='Registration number']/following-sibling::dd")[0]. \
            text.strip() == '42, EARTH'

    def test_shows_united_kingdom_for_old_style_country_code(self):
        self.data_api_client.get_supplier.return_value = get_supplier(
            companiesHouseNumber=None, registrationCountry="gb"
        )
        self.login()

        res = self.client.get("/suppliers/details")
        assert res.status_code == 200
        page_html = res.get_data(as_text=True)
        document = html.fromstring(page_html)
        # Country United Kingdom is shown
        assert document.xpath("//*/node()[normalize-space(string())='United Kingdom']")

    def test_handles_supplier_with_no_registration_country_key(self):
        supplier = get_supplier()
        del supplier['suppliers']['registrationCountry']
        self.data_api_client.get_supplier.return_value = supplier

        self.login()

        res = self.client.get("/suppliers/details")
        assert res.status_code == 200

    def test_shows_address_details(self):
        self.data_api_client.get_supplier.return_value = get_supplier(registrationCountry="country:GB")

        self.login()

        response = self.client.get("/suppliers/details")
        assert response.status_code == 200
        page_html = response.get_data(as_text=True)
        document = html.fromstring(page_html)
        address = (document.
                   xpath("//dt[normalize-space(text())='Registered company address']/following-sibling::dd/text()"))

        assert "1 Street" in address[0]
        assert "Supplierville" in address[1]
        assert "11 AB" in address[2]
        assert "United Kingdom" in address[3]

    def test_handles_supplier_with_no_address_details(self):
        supplier = get_supplier()
        supplier_contact_information = supplier["suppliers"]["contactInformation"][0]
        del supplier_contact_information["address1"]
        del supplier_contact_information["city"]
        del supplier_contact_information["postcode"]
        self.data_api_client.get_supplier.return_value = supplier

        self.login()

        res = self.client.get("/suppliers/details")
        assert res.status_code == 200

    @pytest.mark.parametrize(
        "question,null_attribute,link_address",
        [
            ("Registered company name", {"registeredName": None}, "/suppliers/registered-company-name/edit"),
            ("Registered company address", {"registrationCountry": None}, "/suppliers/registered-address/edit"),
            (
                "Registration number",
                {"companiesHouseNumber": None, "otherCompanyRegistrationNumber": None},
                "/suppliers/registration-number/edit"
            ),
            ("Trading status", {"tradingStatus": None}, "/suppliers/trading-status/edit"),
            ("Company size", {"organisationSize": None}, "/suppliers/organisation-size/edit"),
        ]
    )
    def test_question_field_requires_answer_if_empty(self, question, null_attribute, link_address):
        self.data_api_client.get_supplier.return_value = get_supplier(**null_attribute)

        self.login()

        response = self.client.get("/suppliers/details")
        assert response.status_code == 200
        page_html = response.get_data(as_text=True)
        document = html.fromstring(page_html)
        answer_required_link = document.xpath(f"//dt[normalize-space(text())='{question}']/following-sibling::dd[2]/a")

        assert answer_required_link
        assert answer_required_link[0].values()[1] == link_address
        assert answer_required_link[0].text.strip() == 'Answer required'

    @pytest.mark.parametrize(
        "question,filled_in_attribute,link_address",
        [
            (
                "Registered company name", {"companyDetailsConfirmed": True, "registeredName": "Digital Ponies"},
                "/suppliers/registered-company-name/edit",
            ),
            (
                "Registered company name", {"companyDetailsConfirmed": False, "registeredName": "Digital Ponies"},
                "/suppliers/registered-company-name/edit",
            ),
            ("Registered company address", {"companyDetailsConfirmed": True, "registrationCountry": "country:GB"},
             "/suppliers/registered-address/edit",),
            ("Registered company address", {"companyDetailsConfirmed": False, "registrationCountry": "country:GB"},
             "/suppliers/registered-address/edit",),
            (
                "Registration number",
                {
                    "companyDetailsConfirmed": True, "companiesHouseNumber": "CH123456",
                    "otherCompanyRegistrationNumber": None
                },
                "/suppliers/registration-number/edit",
            ),
            (
                "Registration number",
                {
                    "companyDetailsConfirmed": False, "companiesHouseNumber": "CH123456",
                    "otherCompanyRegistrationNumber": None
                },
                "/suppliers/registration-number/edit",
            ),
            (
                "Registration number",
                {
                    "companyDetailsConfirmed": True, "companiesHouseNumber": None,
                    "otherCompanyRegistrationNumber": "EQ789"
                },
                "/suppliers/registration-number/edit",
            ),
            (
                "Registration number",
                {
                    "companyDetailsConfirmed": False, "companiesHouseNumber": None,
                    "otherCompanyRegistrationNumber": "EQ789"
                },
                "/suppliers/registration-number/edit",
            ),
            ("Trading status", {"companyDetailsConfirmed": False, "tradingStatus": "limited company (LTD)"},
             "/suppliers/trading-status/edit",),
            ("Company size", {"companyDetailsConfirmed": False, "organisationSize": "small"},
             "/suppliers/organisation-size/edit",),
            ("DUNS number", {"companyDetailsConfirmed": True, "dunsNumber": "123456789"},
             "/suppliers/duns-number/edit",),
            ("DUNS number", {"companyDetailsConfirmed": False, "dunsNumber": "123456789"},
             "/suppliers/duns-number/edit",),
        ]
    )
    def test_filled_in_question_field_has_a_change_or_correct_a_mistake_link(
        self, question, filled_in_attribute, link_address
    ):
        self.data_api_client.get_supplier.return_value = get_supplier(**filled_in_attribute)

        self.login()

        response = self.client.get("/suppliers/details")
        assert response.status_code == 200
        page_html = response.get_data(as_text=True)
        document = html.fromstring(page_html)
        answer_required_link = document.xpath(
            f"//dt[normalize-space(text())='{question}']/following-sibling::dd[2]/a"
        )

        assert answer_required_link
        assert answer_required_link[0].values()[1] == link_address

    @pytest.mark.parametrize(
        "summary,expected_key",
        [
            ({"description": "Our company is the best for digital ponies."}, 'Summary'),
            ({"description": ""}, 'Summary (optional)'),
        ]
    )
    def test_hint_text_for_summary_only_visible_if_field_empty(self, summary, expected_key):
        self.data_api_client.get_supplier.return_value = get_supplier(**summary)

        self.login()

        response = self.client.get("/suppliers/details")
        assert response.status_code == 200
        page_html = response.get_data(as_text=True)
        document = html.fromstring(page_html)
        assert document.xpath(f"*//dt[normalize-space(text())='{expected_key}']")

    @pytest.mark.parametrize(
        "framework_slug,framework_name,link_address",
        [
            (
                "digital-outcomes-and-specialists-2",
                "Digital Outcomes and Specialists 2",
                "/suppliers/frameworks/digital-outcomes-and-specialists-2"
            ),
            ("g-cloud-9", "G-Cloud 9", "/suppliers/frameworks/g-cloud-9")
        ]
    )
    def test_back_to_application_link_is_visible_if_currently_applying_to_in_session(
        self, framework_slug, framework_name, link_address
    ):
        self.data_api_client.get_supplier.return_value = get_supplier()
        framework = FrameworkStub(name=framework_name, slug=framework_slug, status='open')
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [framework.response()],
        }
        self.data_api_client.get_framework.return_value = framework.single_result_response()
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                SupplierFrameworkStub(framework_slug=framework_slug).response()
            ]
        }

        self.login()

        with self.client.session_transaction() as session:
            session["currently_applying_to"] = framework_slug

        response = self.client.get("/suppliers/details")
        assert response.status_code == 200

        page_html = response.get_data(as_text=True)
        document = html.fromstring(page_html)
        return_link = (document.xpath(f"//a[contains(text(), 'Return to your {framework_name} application')]"))
        assert return_link
        assert return_link[0].attrib["href"] == link_address

    def test_back_to_application_link_not_visible_if_currently_applying_to_not_in_session(self):
        self.data_api_client.get_supplier.return_value = get_supplier()

        self.login()

        response = self.client.get("/suppliers/details")
        assert response.status_code == 200

        page_html = response.get_data(as_text=True)
        document = html.fromstring(page_html)
        assert "Return to your" not in document.text_content()

    def test_currently_applying_to_removed_from_session_after_account_dashboard_visit(self):
        self.data_api_client.get_supplier.return_value = get_supplier()

        self.login()

        with self.client.session_transaction() as session:
            session["currently_applying_to"] = 'g-bork-2'

        with self.client.session_transaction() as session:
            assert "currently_applying_to" in session

        response = self.client.get("/suppliers")
        assert response.status_code == 200

        with self.client.session_transaction() as session:
            assert "currently_applying_to" not in session

    @pytest.mark.parametrize(
        "supplier_details,open_application,button_should_be_shown",
        [
            # Details complete but not confirmed
            (get_supplier(companyDetailsConfirmed=False), False, True),
            # Details complete and already confirmed
            (get_supplier(companyDetailsConfirmed=True), False, False),
            # Details not complete or confirmed
            (get_supplier(companyDetailsConfirmed=False, dunsNumber=None), False, False),
        ]
    )
    def test_green_button_is_shown_when_details_are_complete_but_not_confirmed(
        self, supplier_details, open_application, button_should_be_shown
    ):
        self.data_api_client.get_supplier.return_value = supplier_details
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                SupplierFrameworkStub().response()
            ]
        }

        self.login()

        response = self.client.get("/suppliers/details")
        assert response.status_code == 200

        document = html.fromstring(response.get_data(as_text=True))
        submit_button = document.xpath("//form//button[normalize-space(string())=$t]", t="Save and confirm")
        assert bool(submit_button) == button_should_be_shown

    @pytest.mark.parametrize('application_company_details_confirmed', (False, None))
    def test_green_button_is_shown_when_company_details_confirmed_for_account_but_not_application(
        self, application_company_details_confirmed
    ):
        self.data_api_client.get_supplier.return_value = get_supplier(companyDetailsConfirmed=True)
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [FrameworkStub(status='open', slug='g-cloud-9').response()]
        }
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                SupplierFrameworkStub(
                    framework_slug='g-cloud-9',
                    application_company_details_confirmed=application_company_details_confirmed
                ).response(),
            ]
        }

        self.login()
        response = self.client.get('/suppliers/details')

        assert response.status_code == 200
        assert (
            "You must confirm that your company details are correct for your application to G-Cloud 9"
            in
            response.get_data(as_text=True)
        )
        document = html.fromstring(response.get_data(as_text=True))
        submit_button = document.xpath("//form//button[normalize-space(string())=$t]", t="Save and confirm")
        assert submit_button

    def test_post_confirms_company_details_for_all_open_framework_applications(self):
        self.data_api_client.get_supplier.return_value = get_supplier(companyDetailsConfirmed=False)
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(status='live', slug='g-cloud-8').response(),
                FrameworkStub(status='open', slug='g-cloud-9').response(),
                FrameworkStub(status='live', slug='digital-outcomes-and-specialists').response(),
                FrameworkStub(status='open', slug='digital-outcomes-and-specialists-2').response(),
            ]
        }
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                SupplierFrameworkStub(
                    framework_slug='g-cloud-8', application_company_details_confirmed=False
                ).response(),
                SupplierFrameworkStub(
                    framework_slug='g-cloud-9', application_company_details_confirmed=False
                ).response(),
                SupplierFrameworkStub(
                    framework_slug='digital-outcomes-and-specialists', application_company_details_confirmed=False
                ).response(),
                SupplierFrameworkStub(
                    framework_slug='digital-outcomes-and-specialists-2', application_company_details_confirmed=False
                ).response(),
            ]
        }

        self.login()
        response = self.client.post('/suppliers/details')

        assert response.status_code == 302
        assert response.location == "http://localhost/suppliers/details"
        assert self.data_api_client.update_supplier.call_args_list == [
            mock.call(supplier_id=1234, supplier={'companyDetailsConfirmed': True}, user="email@email.com"),
        ]
        assert self.data_api_client.set_supplier_framework_application_company_details_confirmed.call_args_list == [
            mock.call(
                supplier_id=1234,
                framework_slug='g-cloud-9',
                application_company_details_confirmed=True,
                user='email@email.com'
            ),
            mock.call(
                supplier_id=1234,
                framework_slug='digital-outcomes-and-specialists-2',
                application_company_details_confirmed=True,
                user='email@email.com'
            ),
        ]

    @pytest.mark.parametrize(
        "complete_supplier",
        (
            get_supplier(),
            get_supplier(companiesHouseNumber=None),
            get_supplier(otherCompanyRegistrationNumber=None),
        )
    )
    def test_post_route_calls_api_and_redirects_when_details_are_complete(self, complete_supplier):
        self.data_api_client.get_supplier.return_value = complete_supplier

        self.login()
        response = self.client.post("/suppliers/details")
        assert response.status_code == 302
        assert self.data_api_client.update_supplier.call_args_list == [
            mock.call(supplier={'companyDetailsConfirmed': True}, supplier_id=1234, user='email@email.com')
        ]

    @pytest.mark.parametrize(
        "incomplete_supplier",
        (
            get_supplier(organisationSize=None),
            get_supplier(dunsNumber=None),
            get_supplier(companiesHouseNumber=None, otherCompanyRegistrationNumber=None),
        )
    )
    def test_post_route_does_not_call_api_and_returns_error_if_incomplete(self, incomplete_supplier):
        self.data_api_client.get_supplier.return_value = incomplete_supplier

        self.login()
        response = self.client.post("/suppliers/details")
        assert response.status_code == 400
        assert self.data_api_client.update_supplier.call_args_list == []

    @pytest.mark.parametrize(
        "current_fwk,expected_destination",
        [
            (None, "/suppliers/details"),
            ("g-things-23", "/suppliers/frameworks/g-things-23"),
            ("digital-widgets-and-stuff", "/suppliers/frameworks/digital-widgets-and-stuff"),
        ]
    )
    def test_post_green_button_redirects_to_the_correct_place(self, current_fwk, expected_destination):
        self.data_api_client.get_supplier.return_value = get_supplier()

        self.login()
        if current_fwk:
            with self.client.session_transaction() as session:
                session["currently_applying_to"] = current_fwk
        response = self.client.post("/suppliers/details")
        assert response.status_code == 302
        assert response.location == f"http://localhost{expected_destination}"


class TestSupplierOpportunitiesDashboardLink(BaseApplicationTest):
    def setup_method(self, method):
        super().setup_method(method)
        self.get_supplier_frameworks_response = {
            'agreementReturned': True,
            'complete_drafts_count': 2,
            'declaration': {'status': 'complete'},
            'frameworkSlug': 'digital-outcomes-and-specialists-4',
            'onFramework': True,
            'services_count': 2,
            'supplierId': 1234
        }
        self.data_api_client_patch = mock.patch('app.main.views.suppliers.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def find_frameworks_stub(self):
        return {'frameworks': [
            {
                **FrameworkStub(status='live', slug='digital-outcomes-and-specialists-4').response(),
                'framework': 'digital-outcomes-and-specialists'
            }
        ]}

    def test_opportunities_dashboard_link(self):
        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [self.get_supplier_frameworks_response]}
        self.data_api_client.find_frameworks.return_value = self.find_frameworks_stub()

        self.login()
        res = self.client.get("/suppliers")
        doc = html.fromstring(res.get_data(as_text=True))

        # note how this also tests the ordering of the links
        assert doc.xpath(
            "//h3[normalize-space(string())=$f]"
            "[(following::a)[1][normalize-space(string())=$t1][@href=$u1]]"
            "[(following::a)[2][normalize-space(string())=$t2][@href=$u2]]"
            "[(following::a)[3][normalize-space(string())=$t3][@href=$u3]]",
            f="Digital Outcomes and Specialists 4",
            t1="View your opportunities",
            u1="/suppliers/opportunities/frameworks/digital-outcomes-and-specialists-4",
            t2="View services",
            u2="/suppliers/frameworks/digital-outcomes-and-specialists-4/services",
            t3="View documents",
            u3="/suppliers/frameworks/digital-outcomes-and-specialists-4",
        )

    @pytest.mark.parametrize(
        'incorrect_data',
        (
            {'onFramework': False},
            {'frameworkSlug': 'not-dos'}
        )
    )
    def test_opportunities_dashboard_link_fails_with_incomplete_data(self, incorrect_data):
        self.get_supplier_frameworks_response.update(incorrect_data)

        self.data_api_client.get_supplier.side_effect = get_supplier
        self.data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [self.get_supplier_frameworks_response]}
        self.data_api_client.find_frameworks.return_value = self.find_frameworks_stub()

        self.login()
        res = self.client.get("/suppliers")
        doc = html.fromstring(res.get_data(as_text=True))

        unexpected_link = "/suppliers/opportunities/frameworks/digital-outcomes-and-specialists-4"

        assert not any(filter(lambda i: i[2] == unexpected_link, doc.iterlinks()))


class TestSupplierDashboardLogin(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.suppliers.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_should_show_supplier_dashboard_logged_in(self):
        self.login()
        self.data_api_client.authenticate_user.return_value = self.user(
            123, "email@email.com", 1234, u'Supplier NĀme', u'Năme')

        self.data_api_client.get_user.return_value = self.user(
            123, "email@email.com", 1234, u'Supplier NĀme', u'Năme')

        self.data_api_client.find_frameworks.return_value = FIND_FRAMEWORKS_RETURN_VALUE

        self.data_api_client.get_supplier.side_effect = get_supplier

        response = self.client.get("/suppliers")

        assert response.status_code == 200

        assert self.strip_all_whitespace(u'<h1 class="govuk-heading-xl">Supplier NĀme</h1>') in \
            self.strip_all_whitespace(response.get_data(as_text=True))
        assert self.strip_all_whitespace("email@email.com") in \
            self.strip_all_whitespace(response.get_data(as_text=True))

        assert self.strip_all_whitespace("Change your password") in \
            self.strip_all_whitespace(response.get_data(as_text=True))

        document = html.fromstring(response.get_data(as_text=True))
        assert len(document.xpath("//a[contains(@href,'/user/change-password')]")) == 1
        # the cookie settings link will appear twice, once in the banner on top
        # and again on the side of the page next to account settings
        assert len(document.xpath("//a[contains(@href,'/user/cookie-settings')]")) == 2

    def test_should_redirect_to_login_if_not_logged_in(self):
        res = self.client.get("/suppliers")
        assert res.status_code == 302
        assert res.location == "http://localhost/user/login?next=%2Fsuppliers"

    def test_custom_dimension_supplier_role_and_organisation_size_is_set_if_supplier_logged_in(self):
        self.data_api_client.find_frameworks.return_value = FIND_FRAMEWORKS_RETURN_VALUE
        self.data_api_client.get_supplier.side_effect = get_supplier

        self.login()
        res = self.client.get('/suppliers')

        doc = html.fromstring(res.get_data(as_text=True))
        # The default company details from self.login() should available as attributes of current_user
        assert len(doc.xpath('//meta[@data-value="supplier"]')) == 1
        assert len(doc.xpath('//meta[@data-value="small"]')) == 1

    def test_custom_dimension_supplier_organisation_size_not_set_if_size_is_null(self):
        self.data_api_client.find_frameworks.return_value = FIND_FRAMEWORKS_RETURN_VALUE
        self.data_api_client.get_supplier.side_effect = get_supplier

        self.login(supplier_organisation_size=None)
        res = self.client.get('/suppliers')

        doc = html.fromstring(res.get_data(as_text=True))
        # The default company details from self.login() should available as attributes of current_user
        assert len(doc.xpath('//meta[@data-value="supplier"]')) == 1
        assert len(doc.xpath('//meta[@data-value="small"]')) == 0

    def test_custom_dimension_supplier_role_and_organisation_size_not_set_if_supplier_logged_out(self):

        # View that does not require login
        res = self.client.get('/suppliers/create/start')

        doc = html.fromstring(res.get_data(as_text=True))
        assert len(doc.xpath('//meta[@data-id="10"]')) == 0
        assert len(doc.xpath('//meta[@data-id="11"]')) == 0


class TestSupplierUpdate(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.suppliers.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def post_supplier_edit(self, data=None, **kwargs):
        if data is None:
            data = {
                "description": "New Description",
                "email": "supplier@user.dmdev",
                "contactName": "Supplier Person",
                "phoneNumber": "0800123123",
            }
        data.update(kwargs)
        res = self.client.post("/suppliers/what-buyers-will-see/edit", data=data)
        return res.status_code, res.get_data(as_text=True)

    def test_should_render_edit_page_with_minimum_data(self):
        self.login()

        def limited_supplier(self):
            return {
                'suppliers': {
                    'contactInformation': [
                        {
                            'phoneNumber': '099887',
                            'id': 1234,
                            'contactName': 'contact name',
                            'email': 'email@email.com'
                        }
                    ],
                    'dunsNumber': '999999999',
                    'id': 12345,
                    'name': 'Supplier Name'
                }
            }

        self.data_api_client.get_supplier.side_effect = limited_supplier

        response = self.client.get("/suppliers/what-buyers-will-see/edit")
        assert response.status_code == 200

    def test_update_all_supplier_fields(self):
        self.login()
        self.data_api_client.get_supplier.side_effect = get_supplier
        status, _ = self.post_supplier_edit()

        assert status == 302

        self.data_api_client.update_supplier.assert_called_once_with(
            1234,
            {
                'description': u'New Description'
            },
            'email@email.com'
        )
        self.data_api_client.update_contact_information.assert_called_once_with(
            1234, 2,
            {
                'email': u'supplier@user.dmdev',
                'phoneNumber': u'0800123123',
                'contactName': u'Supplier Person',
            },
            'email@email.com'
        )

    def test_should_strip_whitespace_surrounding_supplier_update_all_fields(self):
        self.login()
        self.data_api_client.get_supplier.side_effect = get_supplier
        data = {
            "description": "  New Description  ",
            "email": "  supplier@user.dmdev  ",
            "contactName": "  Supplier Person  ",
            "phoneNumber": "  0800123123  ",
        }

        status, _ = self.post_supplier_edit(data=data)

        assert status == 302

        self.data_api_client.update_supplier.assert_called_once_with(
            1234,
            {
                'description': u'New Description'
            },
            'email@email.com'
        )
        self.data_api_client.update_contact_information.assert_called_once_with(
            1234, 2,
            {
                'email': u'supplier@user.dmdev',
                'phoneNumber': u'0800123123',
                'contactName': u'Supplier Person',
            },
            'email@email.com'
        )

    def test_missing_required_supplier_fields(self):
        self.login()

        status, response = self.post_supplier_edit({
            "description": "New Description",
        })
        assert status == 400

        doc = html.fromstring(response)

        for xpath_selector, expected_content in [
            ("[contains(@class, 'govuk-error-summary__list')]/li/a", "Enter a contact name"),
            ("[contains(@class, 'govuk-error-summary__list')]/li/a", "Enter an email address"),
            ("[contains(@class, 'govuk-error-summary__list')]/li/a", "Enter a phone number")
        ]:

            assert doc.xpath(
                f"//*{xpath_selector}[normalize-space(string())='{expected_content}']"
            )

        assert self.data_api_client.update_supplier.called is False
        assert self.data_api_client.update_contact_information.called is False

        assert "New Description" in response

    def test_fields_above_character_length(self):
        self.login()

        status, response = self.post_supplier_edit(
            phoneNumber="0" * 21,
            contactName="A" * 256,
        )
        assert status == 400

        doc = html.fromstring(response)

        for xpath_selector, expected_content in [
            ("[contains(@class, 'govuk-error-summary__list')]/li/a", "Phone number must be 20 characters or fewer"),
            ("[contains(@class, 'govuk-error-summary__list')]/li/a", "Contact name must be 255 characters or fewer")
        ]:
            assert doc.xpath(
                f"//*{xpath_selector}[normalize-space(string())='{expected_content}']"
            )

        assert self.data_api_client.update_supplier.called is False
        assert self.data_api_client.update_contact_information.called is False

    def test_valid_email_address_required(self):
        self.login()

        status, response = self.post_supplier_edit(
            email="This is absolutely not an email address"
        )
        assert status == 400

        doc = html.fromstring(response)

        for xpath_selector, expected_content in [
            ("[contains(@class, 'govuk-error-summary__list')]/li/a",
             "Enter an email address in the correct format, like name@example.com")
        ]:
            assert doc.xpath(
                f"//*{xpath_selector}[normalize-space(string())='{expected_content}']"
            )

        assert self.data_api_client.update_supplier.called is False
        assert self.data_api_client.update_contact_information.called is False

    def test_description_below_word_length(self):
        self.login()

        status, resp = self.post_supplier_edit(
            description="DESCR " * 49
        )

        assert status == 302

        assert self.data_api_client.update_supplier.called is True
        assert self.data_api_client.update_contact_information.called is True

    def test_description_above_word_length(self):
        self.login()

        status, resp = self.post_supplier_edit(
            description="DESCR " * 51
        )

        assert status == 400
        assert 'must not be more than 50' in resp

        assert self.data_api_client.update_supplier.called is False
        assert self.data_api_client.update_contact_information.called is False

    def test_should_redirect_to_login_if_not_logged_in(self):
        res = self.client.get("/suppliers/what-buyers-will-see/edit")
        assert res.status_code == 302
        assert res.location == "http://localhost/user/login?next=%2Fsuppliers%2Fwhat-buyers-will-see%2Fedit"


class TestEditSupplierRegisteredAddress(BaseApplicationTest):
    def setup_method(self, method):
        super().setup_method(self)
        self.data_api_client_patch = mock.patch("app.main.views.suppliers.data_api_client")
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        super().teardown_method(self)
        self.data_api_client_patch.stop()

    def post_supplier_address_edit(self, data=None, **kwargs):
        if data is None:
            data = {
                "street": "1 Street",
                "city": "Supplierville",
                "postcode": "11 AB",
                "country": "country:GB",
            }
        data.update(kwargs)
        res = self.client.post("/suppliers/registered-address/edit", data=data)
        return res.status_code, res.get_data(as_text=True)

    def test_should_render_edit_address_page_with_minimum_data(self):
        self.login()
        self.data_api_client.get_supplier.return_value = {
            'suppliers': {
                'contactInformation': [{'id': 5678}],
                'dunsNumber': '999999999',
                'id': 1234,
                'name': 'Supplier Name',
                'registrationCountry': "",
            }
        }

        response = self.client.get("/suppliers/registered-address/edit")
        assert response.status_code == 200

    def test_should_prepopulate_country_field(self):
        self.login()
        self.data_api_client.get_supplier.return_value = {
            'suppliers': {
                'contactInformation': [{'id': 5678}],
                'dunsNumber': '999999999',
                'id': 1234,
                'registrationCountry': 'country:GB',
                'name': 'Supplier Name'
            }
        }

        response = self.client.get("/suppliers/registered-address/edit")
        assert response.status_code == 200

        doc = html.fromstring(response.get_data(as_text=True))
        assert doc.xpath("//option[@selected='selected'][@value='country:GB']")

    def test_update_all_supplier_address_fields(self):
        self.login()
        self.data_api_client.get_supplier.return_value = {
            'suppliers': {
                'contactInformation': [{'id': 5678}],
                'dunsNumber': '999999999',
                'id': 1234,
                'name': 'Supplier Name',
                'registrationCountry': "",
            }
        }

        status, _ = self.post_supplier_address_edit()
        assert status == 302

        self.data_api_client.update_supplier.assert_called_once_with(
            1234,
            {
                'registrationCountry': 'country:GB'
            },
            'email@email.com'
        )
        self.data_api_client.update_contact_information.assert_called_once_with(
            1234,
            5678,
            {
                'city': 'Supplierville',
                'address1': '1 Street',
                'postcode': '11 AB',
            },
            'email@email.com'
        )

    def test_should_strip_whitespace_surrounding_supplier_update_all_fields(self):
        self.login()
        self.data_api_client.get_supplier.return_value = {
            'suppliers': {
                'contactInformation': [{'id': 5678}],
                'dunsNumber': '999999999',
                'id': 1234,
                'name': 'Supplier Name',
                'registrationCountry': "",
            }
        }

        data = {
            "street": "  1 Street  ",
            "city": "  Supplierville  ",
            "postcode": "  11 AB  ",
            "country": "country:GB",
        }

        status, _ = self.post_supplier_address_edit(data=data)
        assert status == 302

        self.data_api_client.update_contact_information.assert_called_once_with(
            1234,
            5678,
            {
                'city': 'Supplierville',
                'address1': '1 Street',
                'postcode': '11 AB',
            },
            'email@email.com'
        )

    def test_validation_on_required_supplier_address_fields(self):
        self.login()

        status, response = self.post_supplier_address_edit({
            "street": "SomeStreet",
            "city": "",
            "postcode": "11 AB",
            "registeredCountry": "",
        })

        assert status == 400
        assert "Enter a town or city" in response
        assert "Enter a country" in response

        assert self.data_api_client.update_supplier.called is False
        assert self.data_api_client.update_contact_information.called is False

        assert 'value="11 AB"' in response
        assert 'value="SomeStreet"' in response

    @pytest.mark.parametrize(
        'length, validation_error_returned, status_code',
        (
            (255, False, 302),
            (256, True, 400),
        ),
    )
    def test_validation_on_length_of_supplier_address_fields(self, length, validation_error_returned, status_code):
        self.login()

        status, response = self.post_supplier_address_edit({
            "street": "A" * length,
            "city": "C" * length,
            "postcode": "P" * (length - 240),
            "country": "country:GB",
        })

        assert status == status_code

        validation_messages = [
            "Building and street name must be 255 characters or fewer",
            "Town or city name must be 255 characters or fewer",
            "Postcode must be 15 characters or fewer",
        ]
        for message in validation_messages:
            assert (message in response) == validation_error_returned

        assert self.data_api_client.update_supplier.called is not validation_error_returned
        assert self.data_api_client.update_contact_information.called is not validation_error_returned

        data_values = [
            f"value=\"{'A' * length}\"",
            f"value=\"{'C' * length}\"",
            f"value=\"{'P' * (length - 240)}\"",
        ]
        for value in data_values:
            assert (value in response) == validation_error_returned

    def test_validation_fails_for_invalid_country(self):
        self.login()

        status, response = self.post_supplier_address_edit({
            "street": "SomeStreet",
            "city": "Florence",
            "postcode": "11 AB",
            "registeredCountry": "country:BLAH",
        })

        assert status == 400
        assert "Enter a country" in response

        assert self.data_api_client.update_supplier.called is False
        assert self.data_api_client.update_contact_information.called is False

    def test_should_redirect_to_login_if_not_logged_in(self):
        res = self.client.get("/suppliers/registered-address/edit")
        assert res.status_code == 302
        assert res.location == "http://localhost/user/login?next=%2Fsuppliers%2Fregistered-address%2Fedit"

    def test_handles_api_errors_when_updating_supplier_or_contact_information(self):
        self.login()
        self.data_api_client.update_supplier.side_effect = HTTPError(400, "I'm an error from the API")

        status, response = self.post_supplier_address_edit()

        assert status == 503

    def test_handles_api_errors_when_updating_contact_information(self):
        self.login()
        self.data_api_client.update_contact_information.side_effect = HTTPError(400, "I'm an error from the API")

        status, response = self.post_supplier_address_edit()

        assert status == 503


class TestCreateSupplier(BaseApplicationTest):

    direct_plus_api_method = 'app.main.views.suppliers.direct_plus_client.get_organization_by_duns_number'

    @pytest.fixture
    def get_organization_by_duns_number(self):
        with self.app.app_context(), mock.patch(
            self.direct_plus_api_method, return_value={"primaryName": "COMPANY NAME LTD"}
        ) as get_organization_by_duns_number:
            yield get_organization_by_duns_number

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.suppliers.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_old_create_start_page_redirects_to_new_start_page(self):
        res = self.client.get("/suppliers/create")
        assert res.status_code == 301
        assert res.location == "http://localhost/suppliers/create/start"

    def test_create_start_page_get_ok(self):
        res = self.client.get("/suppliers/create/start")
        assert res.status_code == 200

    def test_create_duns_number_page_get_ok(self):
        res = self.client.get("/suppliers/create/duns-number")
        assert res.status_code == 200

    def test_create_company_details_page_get_ok(self):
        res = self.client.get("/suppliers/create/company-details")
        assert res.status_code == 200

    @pytest.mark.parametrize(
        "duns_number,expected_message",
        [(None, 'Enter your 9 digit DUNS number'),
         ('invalid', 'Your DUNS number must be 9 digits'),
         ('12345678', 'Your DUNS number must be 9 digits'),
         ('1234567890', 'Your DUNS number must be 9 digits'),
         ],
    )
    def test_should_be_an_error_if_missing_or_invalid_duns_number(self, duns_number, expected_message):
        """Ensures that validation on duns number prevents submission of:
        1) No value
        2) Non-numerics
        3) Numerics shorter/longer than 9 characters"""
        res = self.client.post(
            "/suppliers/create/duns-number",
            data={'duns_number': duns_number} if duns_number else {}
        )

        self.assert_single_question_page_validation_errors(res, validation_message=expected_message)

    def test_should_be_an_error_if_duns_number_in_use(self, get_organization_by_duns_number):
        self.data_api_client.find_suppliers.return_value = {"suppliers": ["one supplier", "two suppliers"]}
        res = self.client.post("/suppliers/create/duns-number", data={'duns_number': "123456789"})

        assert res.status_code == 400
        page = res.get_data(as_text=True)
        assert "A supplier account already exists with that DUNS number" in page
        assert "DUNS number already used" in page
        assert "If you no longer have your account details, or if you think this may be an error," in page

    def test_direct_plus_api_call(self, get_organization_by_duns_number):
        self.client.post("/suppliers/create/duns-number", data={'duns_number': "123456789"})
        get_organization_by_duns_number.assert_called_once_with('123456789')

    def test_marketplace_data_api_call(self, get_organization_by_duns_number):
        self.client.post("/suppliers/create/duns-number", data={'duns_number': "123456789"})
        self.data_api_client.find_suppliers.assert_called_once_with(duns_number="123456789")

    def test_should_be_an_error_if_duns_number_not_found(self, get_organization_by_duns_number):
        get_organization_by_duns_number.side_effect = direct_plus_client.DUNSNumberNotFound
        res = self.client.post("/suppliers/create/duns-number", data={'duns_number': "123456789"})

        assert res.status_code == 400
        page = res.get_data(as_text=True)
        assert "DUNS number not found" in page

    def test_skips_dnb_api_validation_if_unexpected_error(self, get_organization_by_duns_number):
        get_organization_by_duns_number.side_effect = direct_plus_client.DirectPlusError
        self.data_api_client.find_suppliers.return_value = {"suppliers": []}
        res = self.client.post("/suppliers/create/duns-number", data={'duns_number': "123456789"})

        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/create/company-details'

    def test_duns_added_to_session_if_unexpected_error(self, get_organization_by_duns_number):
        get_organization_by_duns_number.side_effect = direct_plus_client.DirectPlusError

        with self.client as c:
            with c.session_transaction() as sess:
                with pytest.raises(KeyError):
                    sess['duns_number']

            self.data_api_client.find_suppliers.return_value = {"suppliers": []}
            c.post("/suppliers/create/duns-number", data={'duns_number': "123456789"})

            assert session['duns_number'] == '123456789'

    def test_should_allow_nine_digit_duns_number(self, get_organization_by_duns_number):
        self.data_api_client.find_suppliers.return_value = {"suppliers": []}

        res = self.client.post("/suppliers/create/duns-number", data={'duns_number': "123456789"})

        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/create/confirm-company'

    def test_should_allow_duns_numbers_that_start_with_zero(self, get_organization_by_duns_number):
        self.data_api_client.find_suppliers.return_value = {"suppliers": []}
        res = self.client.post("/suppliers/create/duns-number", data={'duns_number': "012345678"})

        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/create/confirm-company'

    def test_should_strip_whitespace_surrounding_duns_number_field(self):
        self.data_api_client.find_suppliers.return_value = {"suppliers": []}
        with self.app.app_context(), self.client as c:
            with mock.patch(self.direct_plus_api_method, return_value={'primaryName': '0 COMPANY LTD'}):
                c.post("/suppliers/create/duns-number", data={'duns_number': "  012345678  "})

                assert "duns_number" in session
                assert session.get("duns_number") == "012345678"

    def test_should_add_company_name_to_session(self):
        with self.app.app_context(), self.client as c:
            with mock.patch(self.direct_plus_api_method, return_value={'primaryName': '0 COMPANY LTD'}):
                with c.session_transaction() as sess:
                    with pytest.raises(KeyError):
                        sess['company_name']

                self.data_api_client.find_suppliers.return_value = {"suppliers": []}
                c.post("/suppliers/create/duns-number", data={'duns_number': "123456789"})
            assert session['company_name'] == '0 COMPANY LTD'

    def test_should_not_add_company_name_to_session_if_unexpected_error(self):
        with self.app.app_context(), self.client as c:
            with mock.patch(self.direct_plus_api_method, side_effect=direct_plus_client.DirectPlusError):
                with c.session_transaction() as sess:
                    with pytest.raises(KeyError):
                        sess['company_name']
                self.data_api_client.find_suppliers.return_value = {"suppliers": []}
                c.post("/suppliers/create/duns-number", data={'duns_number': "123456789"})

            with pytest.raises(KeyError):
                session['company_name']

    def test_should_allow_valid_company_contact_details(self):
        res = self.client.post(
            "/suppliers/create/company-details",
            data={
                'company_name': "My Company",
                'contact_name': "Name",
                'email_address': "name@email.com",
                'phone_number': "999"
            }
        )
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/create/account'

    def test_should_strip_whitespace_surrounding_contact_details_fields(self):
        contact_details = {
            'company_name': "  My Company  ",
            'contact_name': "  Name  ",
            'email_address': "  name@email.com  ",
            'phone_number': "  999  "
        }

        with self.client as c:
            c.post(
                "/suppliers/create/company-details",
                data=contact_details
            )

            for key, value in contact_details.items():
                assert key in session
                assert session.get(key) == value.strip()

    def test_should_not_allow_contact_details_without_company_name(self):
        res = self.client.post(
            "/suppliers/create/company-details",
            data={
                'contact_name': "Name",
                'email_address': "name@email.com",
                'phone_number': "999"
            }
        )
        assert res.status_code == 400
        assert "Enter your company name" in res.get_data(as_text=True)

    def test_should_not_allow_contact_details_with_too_long_company_name(self):
        twofiftysix = "a" * 256
        res = self.client.post(
            "/suppliers/create/company-details",
            data={
                'company_name': twofiftysix,
                'contact_name': "Name",
                'email_address': "name@email.com",
                'phone_number': "999"
            }
        )
        assert res.status_code == 400
        assert "Company name must be 255 characters or fewer" in res.get_data(as_text=True)

    def test_should_not_allow_contact_details_without_contact_name(self):
        res = self.client.post(
            "/suppliers/create/company-details",
            data={
                'company_name': "My Company",
                'email_address': "name@email.com",
                'phone_number': "999"
            }
        )
        assert res.status_code == 400
        assert "Enter a contact name" in res.get_data(as_text=True)

    def test_should_not_allow_contact_details_with_too_long_contact_name(self):
        twofiftysix = "a" * 256
        res = self.client.post(
            "/suppliers/create/company-details",
            data={
                'company_name': "My Company",
                'contact_name': twofiftysix,
                'email_address': "name@email.com",
                'phone_number': "999"
            }
        )
        assert res.status_code == 400
        assert "Contact name must be 255 characters or fewer" in res.get_data(as_text=True)

    def test_should_not_allow_contact_details_without_email(self):
        res = self.client.post(
            "/suppliers/create/company-details",
            data={
                'company_name': "My Company",
                'contact_name': "Name",
                'phone_number': "999"
            }
        )
        assert res.status_code == 400
        assert "Enter an email address" in res.get_data(as_text=True)

    def test_should_not_allow_contact_details_with_invalid_email(self):
        res = self.client.post(
            "/suppliers/create/company-details",
            data={
                'company_name': "My Company",
                'contact_name': "Name",
                'email_address': "notrightatall",
                'phone_number': "999"
            }
        )
        assert res.status_code == 400
        assert "Enter an email address in the correct format, like name@example.com" in res.get_data(as_text=True)

    def test_should_not_allow_contact_details_without_phone_number(self):
        res = self.client.post(
            "/suppliers/create/company-details",
            data={
                'company_name': "My Company",
                'contact_name': "Name",
                'email_address': "name@email.com"
            }
        )
        assert res.status_code == 400
        assert "Enter a phone number" in res.get_data(as_text=True)

    def test_should_not_allow_contact_details_with_too_long_phone_number(self):
        twentyone = "a" * 21
        res = self.client.post(
            "/suppliers/create/company-details",
            data={
                'company_name': "My Company",
                'contact_name': "Name",
                'email_address': "name@email.com",
                'phone_number': twentyone
            }
        )
        assert res.status_code == 400
        assert "Phone number must be 20 characters or fewer" in res.get_data(as_text=True)

    def test_should_show_multiple_errors(self):
        res = self.client.post(
            "/suppliers/create/company-details",
            data={}
        )

        assert res.status_code == 400
        assert "Enter your company name" in res.get_data(as_text=True)
        assert "Enter a phone number" in res.get_data(as_text=True)
        assert "Enter an email address" in res.get_data(as_text=True)
        assert "Enter a contact name" in res.get_data(as_text=True)

    def test_should_populate_duns_from_session(self):
        with self.client.session_transaction() as sess:
            sess['duns_number'] = "999"
        res = self.client.get("/suppliers/create/duns-number")
        assert res.status_code == 200
        assert '<inputtype="text"name="duns_number"id="input-duns_number"class="text-box"value="999"' \
            in self.strip_all_whitespace(res.get_data(as_text=True))

    def test_should_populate_company_name_from_session(self):
        with self.client.session_transaction() as sess:
            sess['company_name'] = "Name"
        res = self.client.get("/suppliers/create/company-details")
        assert res.status_code == 200
        assert '<inputtype="text"name="company_name"id="input-company_name"class="text-box"value="Name"' \
            in self.strip_all_whitespace(res.get_data(as_text=True))

    def test_should_populate_contact_details_from_session(self):
        with self.client.session_transaction() as sess:
            sess['email_address'] = "email_address"
            sess['contact_name'] = "contact_name"
            sess['phone_number'] = "phone_number"
        res = self.client.get("/suppliers/create/company-details")
        assert res.status_code == 200
        stripped_page = self.strip_all_whitespace(res.get_data(as_text=True))
        assert '<inputtype="text"name="email_address"id="input-email_address"class="text-box"value="email_address"' \
            in stripped_page

        assert '<inputtype="text"name="contact_name"id="input-contact_name"class="text-box"value="contact_name"' \
            in stripped_page

        assert '<inputtype="text"name="phone_number"id="input-phone_number"class="text-box"value="phone_number"' \
            in stripped_page

    def test_should_be_an_error_to_be_submit_company_with_incomplete_session(self):
        res = self.client.post("/suppliers/create/company-summary")
        assert res.status_code == 400
        assert 'You must answer all the questions' in res.get_data(as_text=True)

    @mock.patch("app.main.suppliers.send_user_account_email")
    def test_should_redirect_to_create_your_account_if_valid_session(self, send_user_account_email):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_address'] = "email_address"
                sess['phone_number'] = "phone_number"
                sess['contact_name'] = "contact_name"
                sess['duns_number'] = "duns_number"
                sess['company_name'] = "company_name"
                sess['account_email_address'] = "valid@email.com"

            self.data_api_client.create_supplier.return_value = self.supplier()
            res = c.post("/suppliers/create/company-summary")
            assert res.status_code == 302
            assert res.location == "http://localhost/suppliers/create/complete"
            self.data_api_client.create_supplier.assert_called_once_with({
                "contactInformation": [{
                    "email": "email_address",
                    "phoneNumber": "phone_number",
                    "contactName": "contact_name"
                }],
                "dunsNumber": "duns_number",
                "name": "company_name",
            })
            assert 'email_address' not in session
            assert 'phone_number' not in session
            assert 'contact_name' not in session
            assert 'duns_number' not in session
            assert 'company_name' not in session
            assert session['email_supplier_id'] == 12345
            assert session['email_company_name'] == 'Supplier Name'

    @mock.patch("app.main.suppliers.send_user_account_email")
    def test_should_allow_missing_companies_house_number(self, send_user_account_email):
        with self.client.session_transaction() as sess:
            sess['email_address'] = "email_address"
            sess['phone_number'] = "phone_number"
            sess['contact_name'] = "contact_name"
            sess['duns_number'] = "duns_number"
            sess['company_name'] = "company_name"
            sess['account_email_address'] = "account_email_address"

        self.data_api_client.create_supplier.return_value = self.supplier()
        res = self.client.post(
            "/suppliers/create/company-summary",
            data={
                'email_address': 'valid@email.com'
            }
        )
        assert res.status_code == 302
        assert res.location == "http://localhost/suppliers/create/complete"
        self.data_api_client.create_supplier.assert_called_once_with({
            "contactInformation": [{
                "email": "email_address",
                "phoneNumber": "phone_number",
                "contactName": "contact_name"
            }],
            "dunsNumber": "duns_number",
            "name": "company_name"
        })

    def test_should_be_an_error_if_missing_a_field_in_session(self):
        with self.client.session_transaction() as sess:
            sess['email_address'] = "email_address"
            sess['phone_number'] = "phone_number"
            sess['contact_name'] = "contact_name"
            sess['duns_number'] = "duns_number"

        self.data_api_client.create_supplier.return_value = True
        res = self.client.post("/suppliers/create/company-summary")
        assert res.status_code == 400
        assert self.data_api_client.create_supplier.called is False
        assert 'You must answer all the questions' in res.get_data(as_text=True)

    def test_should_return_503_if_api_error(self):
        with self.client.session_transaction() as sess:
            sess['email_address'] = "email_address"
            sess['phone_number'] = "phone_number"
            sess['contact_name'] = "contact_name"
            sess['duns_number'] = "duns_number"
            sess['company_name'] = "company_name"
            sess['account_email_address'] = "account_email_address"

        self.data_api_client.create_supplier.side_effect = HTTPError("gone bad")
        res = self.client.post("/suppliers/create/company-summary")
        assert res.status_code == 503

    def test_should_require_an_email_address(self):
        with self.client.session_transaction() as sess:
            sess['email_company_name'] = "company_name"
            sess['email_supplier_id'] = 1234
        res = self.client.post(
            "/suppliers/create/account",
            data={}
        )
        assert res.status_code == 400
        assert "Enter an email address" in res.get_data(as_text=True)

    def test_should_not_allow_incorrect_email_address(self):
        with self.client.session_transaction() as sess:
            sess['email_company_name'] = "company_name"
            sess['email_supplier_id'] = 1234
        res = self.client.post(
            "/suppliers/create/account",
            data={
                'email_address': "bademail"
            }
        )
        assert res.status_code == 400
        assert "Enter an email address in the correct format, like name@example.com" in res.get_data(as_text=True)

    @mock.patch("app.main.suppliers.send_user_account_email")
    def test_should_allow_correct_email_address(self, send_user_account_email):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_address'] = "email_address"
                sess['phone_number'] = "phone_number"
                sess['contact_name'] = "contact_name"
                sess['duns_number'] = "duns_number"
                sess['company_name'] = "company_name"
                sess['account_email_address'] = "valid@email.com"

            self.data_api_client.create_supplier.return_value = self.supplier()

            res = c.post("/suppliers/create/company-summary")

            send_user_account_email.assert_called_once_with(
                'supplier',
                'valid@email.com',
                current_app.config['NOTIFY_TEMPLATES']['create_user_account'],
                extra_token_data={
                    "supplier_id": 12345,
                    "supplier_name": "Supplier Name"
                }
            )

            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/create/complete'

    @mock.patch('dmutils.email.user_account_email.DMNotifyClient')
    def test_should_correctly_store_email_address_in_session(self, DMNotifyClient):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_address'] = "email_address"
                sess['phone_number'] = "phone_number"
                sess['contact_name'] = "contact_name"
                sess['duns_number'] = "duns_number"
                sess['company_name'] = "company_name"
                sess['account_email_address'] = "valid@email.com"

            self.data_api_client.create_supplier.return_value = self.supplier()

            c.post("/suppliers/create/company-summary")

            assert session['email_sent_to'] == 'valid@email.com'

    @mock.patch("app.main.suppliers.send_user_account_email")
    def test_should_be_an_error_if_incomplete_session_on_account_creation(self, send_user_account_email):
        res = self.client.post(
            "/suppliers/create/company-summary"
        )

        assert send_user_account_email.called is False
        assert res.status_code == 400

    def test_should_show_email_address_on_create_account_complete(self):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_sent_to'] = "my@email.com"
                sess['other_stuff'] = True

            res = c.get("/suppliers/create/complete")

            assert res.status_code == 200
            assert 'my@email.com' in res.get_data(as_text=True)
            assert 'other_stuff' not in session

    def test_should_show_email_address_even_when_refreshed(self):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_sent_to'] = 'my-email@example.com'

            res = c.get('/suppliers/create/complete')

            assert res.status_code == 200
            assert 'my-email@example.com' in res.get_data(as_text=True)

            res = c.get('/suppliers/create/complete')

            assert res.status_code == 200
            assert 'my-email@example.com' in res.get_data(as_text=True)


class TestJoinOpenFrameworkNotificationMailingList(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.suppliers.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    @staticmethod
    def _common_page_asserts_and_get_form(doc):
        assert tuple(h1.xpath("normalize-space(string())") for h1 in doc.xpath("//h1")) == (
            "Sign up for Digital Marketplace email alerts",
        )

        form = next(
            form for form in doc.xpath("//form[@method='POST']")
            if urlparse(form.action)[2:] == ("/suppliers/mailing-list", "", "", "",) and
            form.xpath(".//input[@name='email_address']")
        )
        assert form.xpath(".//input[@name='csrf_token']")
        assert form.xpath(".//button[normalize-space(string())=$t]", t="Subscribe")

        return form

    @mock.patch("app.main.views.suppliers.DMMailChimpClient")
    def test_get(self, mailchimp_client_class):
        self.data_api_client.create_audit_event.side_effect = AssertionError("This should not be called")
        mailchimp_client_instance = mock.Mock(spec=("subscribe_new_email_to_list",))
        mailchimp_client_instance.subscribe_new_email_to_list.side_effect = AssertionError("This should not be called")

        mailchimp_client_class.side_effect = assert_args_and_return(
            mailchimp_client_instance,
            "not_a_real_username",
            "not_a_real_key",
            mock.ANY,
        )

        response = self.client.get(
            "/suppliers/mailing-list",
        )
        assert response.status_code == 200
        doc = html.fromstring(response.get_data(as_text=True), base_url="/suppliers/mailing-list")

        assert not doc.xpath(
            "//*[normalize-space(string())=$t]",
            t="Provide a valid email address.",
        )
        assert not doc.xpath(
            "//*[normalize-space(string())=$t]",
            t="Provide an email address.",
        )
        assert not doc.xpath("//*[contains(@class, 'validation-message')]")

        form = self._common_page_asserts_and_get_form(doc)

        # we have already tested for the existence of input[@name='email_address']
        assert not any(inp.value for inp in form.xpath(".//input[@name='email_address']"))

        self.assert_no_flashes()

    @pytest.mark.parametrize("email_address_value,expected_validation_message", (
        ("pint@twopence", "Enter an email address in the correct format, like name@example.com",),
        ("", "Enter an email address",),
    ))
    @mock.patch("app.main.views.suppliers.DMMailChimpClient")
    def test_post_invalid_email(
        self,
        mailchimp_client_class,
        email_address_value,
        expected_validation_message,
    ):
        self.data_api_client.create_audit_event.side_effect = AssertionError("This should not be called")
        mailchimp_client_instance = mock.Mock(spec=("subscribe_new_email_to_list",))
        mailchimp_client_instance.subscribe_new_email_to_list.side_effect = AssertionError("This should not be called")

        mailchimp_client_class.side_effect = assert_args_and_return(
            mailchimp_client_instance,
            "not_a_real_username",
            "not_a_real_key",
            mock.ANY,
        )

        response = self.client.post(
            "/suppliers/mailing-list",
            data={
                "email_address": email_address_value,
            },
        )
        assert response.status_code == 400
        doc = html.fromstring(response.get_data(as_text=True), base_url="/suppliers/mailing-list")

        form = self._common_page_asserts_and_get_form(doc)
        assert tuple(inp.value for inp in form.xpath(".//input[@name='email_address']")) == (
            email_address_value,
        )

        assert doc.xpath(
            "//label[@for='input-email_address']//*[contains(@class, 'validation-message')]"
            "[normalize-space(string())=$t]",
            t=expected_validation_message,
        )

        self.assert_no_flashes()

    @pytest.mark.parametrize("mc_retval, expected_status, expected_message", (
        (
            {'error_type': 'already_subscribed', 'status_code': 400, 'status': 'error'},
            400, "This email address has already been used to sign up"
        ),
        (
            {'error_type': 'deleted_user', 'status_code': 400, 'status': 'error'},
            400, "This email address cannot be used to sign up"
        ),
        (
            {'error_type': 'invalid_email', 'status_code': 400, 'status': 'error'},
            400, "This email address cannot be used to sign up"
        ),
        (
            {'error_type': 'unexpected_error', 'status_code': 503, 'status': 'error'},
            503, "The service is unavailable at the moment"
        ),
    ))
    @mock.patch("app.main.views.suppliers.DMMailChimpClient")
    def test_post_valid_email_failure(self, mailchimp_client_class, mc_retval, expected_status, expected_message):
        self.data_api_client.create_audit_event.side_effect = AssertionError("This should not be called")
        mailchimp_client_instance = mock.Mock(spec=("subscribe_new_email_to_list",))
        mailchimp_client_instance.subscribe_new_email_to_list.side_effect = assert_args_and_return(
            mc_retval,
            "not_a_real_mailing_list",
            "squinting@ger.ty",
        )

        mailchimp_client_class.side_effect = assert_args_and_return(
            mailchimp_client_instance,
            "not_a_real_username",
            "not_a_real_key",
            mock.ANY,
        )

        with self.app.app_context():
            response = self.client.post(
                "/suppliers/mailing-list",
                data={
                    "email_address": "squinting@ger.ty",
                },
            )

            assert response.status_code == expected_status
            doc = html.fromstring(response.get_data(as_text=True), base_url="/suppliers/mailing-list")

            assert mailchimp_client_instance.subscribe_new_email_to_list.called is True

            form = self._common_page_asserts_and_get_form(doc)
            assert tuple(inp.value for inp in form.xpath(".//input[@name='email_address']")) == (
                "squinting@ger.ty",
            )

            assert not doc.xpath(
                "//*[normalize-space(string())=$t]",
                t="Provide a valid email address.",
            )
            assert not doc.xpath(
                "//*[normalize-space(string())=$t]",
                t="Provide an email address.",
            )
            assert not doc.xpath("//*[contains(@class, 'validation-message')]")

            # test flash message content
            flash_messages = doc.cssselect(".dm-alert")
            assert len(flash_messages) == 1
            assert "dm-alert--error" in flash_messages[0].classes
            assert expected_message in flash_messages[0].cssselect(".dm-alert__body")[0].text.strip()

            email_address_link = flash_messages[0].cssselect("a")[0]
            assert email_address_link.text == current_app.config["SUPPORT_EMAIL_ADDRESS"]
            assert email_address_link.attrib["href"] == f"mailto:{current_app.config['SUPPORT_EMAIL_ADDRESS']}"

            # flash message should have been consumed by view's own page rendering
            self.assert_no_flashes()

    @mock.patch("app.main.views.suppliers.DMMailChimpClient")
    def test_post_valid_email_success(self, mailchimp_client_class):
        self.data_api_client.create_audit_event.side_effect = assert_args_and_return(
            {"convincing": "response"},
            audit_type=AuditTypes.mailing_list_subscription,
            data={
                "subscribedEmail": "qu&rt@four.pence",
                "mailchimp": {
                    "id": "cashregister-clanged",
                    "unique_email_id": "clock-clacked",
                    "timestamp_opt": None,
                    "last_changed": "1904-06-16T16:00:00+00:00",
                    "list_id": "flowered-tables",
                },
            },
        )
        mailchimp_client_instance = mock.Mock(spec=("subscribe_new_email_to_list",))
        mailchimp_client_instance.subscribe_new_email_to_list.side_effect = assert_args_and_return(
            {
                "id": "cashregister-clanged",
                "unique_email_id": "clock-clacked",
                # timestamp_opt deliberately omitted
                "last_changed": "1904-06-16T16:00:00+00:00",
                "list_id": "flowered-tables",
                "has-he-forgotten": "perhaps-a-trick",  # should be ignored
                "status": "success",
                "status_code": 200,
                "error_type": None,
            },
            "not_a_real_mailing_list",
            "qu&rt@four.pence",
        )

        mailchimp_client_class.side_effect = assert_args_and_return(
            mailchimp_client_instance,
            "not_a_real_username",
            "not_a_real_key",
            mock.ANY,
        )

        response = self.client.post(
            "/suppliers/mailing-list",
            data={
                # no, ampersands are probably not valid in this position in an email address but they are accepted
                # by our regex and we want to be able to check their escaping in the flash message
                "email_address": "qu&rt@four.pence",
            },
        )

        assert response.status_code == 302
        assert response.location == "http://localhost/"
        assert mailchimp_client_instance.subscribe_new_email_to_list.called is True

        assert self.get_flash_messages() == (
            ("success", "You will receive email notifications to qu&amp;rt@four.pence when applications are opening.",),
        )


class TestBecomeASupplier(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.suppliers.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_become_a_supplier_page_loads_ok(self):
        res = self.client.get("/suppliers/supply")

        assert res.status_code == 200
        assert self.strip_all_whitespace(u'<h1 class="govuk-heading-l">Become a supplier</h1>') in \
            self.strip_all_whitespace(res.get_data(as_text=True))

    @mock.patch('app.main.suppliers.get_frameworks_closed_and_open_for_applications', autospec=True)
    def test_frameworks_are_sorted_correctly(self, get_frameworks_closed_and_open_for_applications):
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(id=3, status='live', slug='g-cloud-9').response(),
                FrameworkStub(id=1, status='expired', slug='g-cloud-8').response(),
                FrameworkStub(id=5, status='pending', slug='g-cloud-10').response(),
                FrameworkStub(id=2, status='live', slug='digital-outcomes-and-specialists').response(),
                FrameworkStub(id=4, status='coming', slug='digital-outcomes-and-specialists-2').response(),
            ]
        }

        self.client.get("/suppliers/supply")

        ordered_framework_slugs = [
            fw['slug'] for fw in get_frameworks_closed_and_open_for_applications.call_args_list[0][0][0]
        ]

        assert ordered_framework_slugs == [
            'g-cloud-10',
            'digital-outcomes-and-specialists-2',
            'g-cloud-9',
            'digital-outcomes-and-specialists',
            'g-cloud-8',
        ]

    def test_all_open_or_coming_frameworks(self):
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(status='open', slug='g-cloud-9').response(),
                FrameworkStub(status='live', slug='g-cloud-8').response(),
                FrameworkStub(status='coming', slug='digital-outcomes-and-specialists-2').response(),
                FrameworkStub(status='live', slug='digital-outcomes-and-specialists').response(),
            ]
        }

        res = self.client.get("/suppliers/supply")
        data = res.get_data(as_text=True)

        self.data_api_client.find_frameworks.assert_called_once_with()

        # Check right headings are there
        assert 'Services you can apply to sell' in data
        assert 'Services you can’t apply to sell at the moment' not in data
        assert 'You cannot create a supplier account at the moment' not in data

        # Check the right framework content is there
        assert 'Digital Outcomes and Specialists is opening for applications.' in data
        assert 'G-Cloud is open for applications.' in data

        # Check the right calls to action are there
        assert 'Create a supplier account' in data
        assert 'Get notifications when applications are opening' not in data

    def test_all_closed_frameworks(self):
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(status='live', slug='g-cloud-9').response(),
                FrameworkStub(status='expired', slug='g-cloud-8').response(),
                FrameworkStub(status='standstill', slug='digital-outcomes-and-specialists-2').response(),
                FrameworkStub(status='live', slug='digital-outcomes-and-specialists').response(),
            ]
        }

        res = self.client.get("/suppliers/supply")
        data = res.get_data(as_text=True)

        self.data_api_client.find_frameworks.assert_called_once_with()

        # Check right headings are there
        assert 'You cannot create a supplier account at the moment' in data
        assert 'Services you can apply to sell' not in data
        assert 'Services you can’t apply to sell at the moment' not in data

        # Check the right framework content is there
        assert 'Digital Outcomes and Specialists is closed for applications.' in data
        assert 'G-Cloud is closed for applications.' in data

        # Check the right calls to action are there
        assert 'Create a supplier account' not in data
        assert 'Get notifications when applications are opening' in data

    def test_one_open_one_closed_framework(self):
        self.data_api_client.find_frameworks.return_value = {
            "frameworks": [
                FrameworkStub(status='open', slug='g-cloud-9').response(),
                FrameworkStub(status='live', slug='g-cloud-8').response(),
                FrameworkStub(status='live', slug='digital-outcomes-and-specialists-2').response(),
                FrameworkStub(status='expired', slug='digital-outcomes-and-specialists').response(),
            ]
        }

        res = self.client.get("/suppliers/supply")
        data = res.get_data(as_text=True)

        self.data_api_client.find_frameworks.assert_called_once_with()

        # Check right headings are there
        assert 'Services you can apply to sell' in data
        assert 'Services you can’t apply to sell at the moment' in data
        assert 'You cannot create a supplier account at the moment' not in data

        # Check the right framework content is there
        assert 'Digital Outcomes and Specialists is closed for applications.' in data
        assert 'G-Cloud is open for applications.' in data

        # Check the right calls to action are there
        assert 'Create a supplier account' in data
        assert 'Get notifications when applications are opening' in data


class TestSupplierEditOrganisationSize(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.suppliers.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_edit_organisation_size_page_loads(self):
        self.login()

        res = self.client.get("/suppliers/organisation-size/edit")
        assert res.status_code == 200, 'The edit organisation-size page has not loaded correctly.'

    @pytest.mark.parametrize('organisation_size, expected_error',
                             (
                                 (None, "Select an organisation size"),
                                 ('blah', "Not a valid choice")
                             ))
    def test_missing_or_invalid_choice_shows_validation(self, organisation_size, expected_error):
        self.login()

        res = self.client.post("/suppliers/organisation-size/edit",
                               data={'organisation_size': organisation_size} if organisation_size else {})
        doc = html.fromstring(res.get_data(as_text=True))
        error = doc.xpath('//span[@id="input-organisation_size-error"]')

        assert len(error) == 1, 'Only one validation message should be shown.'

        assert error[0].text_content().strip() == f"Error: {expected_error}", \
            'The validation message is not as anticipated.'

        self.assert_single_question_page_validation_errors(res, validation_message=expected_error)

    @pytest.mark.parametrize('size', (None, 'micro', 'small', 'medium', 'large'))
    def test_post_choice_triggers_api_supplier_update_and_redirect(self, size):
        self.login()

        self.client.post("/suppliers/organisation-size/edit", data={'organisation_size': size})

        call_args_list = self.data_api_client.update_supplier.call_args_list
        if size:
            assert call_args_list == [
                mock.call(supplier_id=1234, supplier={'organisationSize': size}, user='email@email.com')
            ], 'update_supplier was called with the wrong arguments'

        else:
            assert call_args_list == [], 'update_supplier was called with the wrong arguments'

    @pytest.mark.parametrize('existing_size, expected_selection',
                             (
                                 (None, []),
                                 ('some unknown value', []),
                                 *[(x['value'], [x['value']]) for x in CompanyOrganisationSizeForm.OPTIONS],
                             ))
    def test_existing_org_size_sets_current_selection(self, existing_size, expected_selection):
        data = {'organisationSize': existing_size} if existing_size else {}
        self.data_api_client.get_supplier.return_value = {'suppliers': data}

        self.login()

        res = self.client.get("/suppliers/organisation-size/edit")
        doc = html.fromstring(res.get_data(as_text=True))
        selected_value = doc.xpath('//input[@name="organisation_size" and @checked="checked"]/@value')
        assert selected_value == expected_selection, 'The organisation size has not pre-populated correctly.'


class TestSupplierAddRegisteredCompanyName(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.suppliers.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_add_registered_company_name_page_loads(self):
        self.login()
        self.data_api_client.get_supplier.return_value = get_supplier(registeredName=None)

        res = self.client.get("/suppliers/registered-company-name/edit")
        assert res.status_code == 200, 'The add registered company name page has not loaded correctly.'

    def test_no_input_triggers_input_required_validation_and_does_not_call_api_update(self):
        self.login()
        self.data_api_client.get_supplier.return_value = get_supplier(registeredName=None)

        res = self.client.post("/suppliers/registered-company-name/edit")

        self.assert_single_question_page_validation_errors(res, validation_message="Enter your registered company name")
        assert self.data_api_client.update_supplier.call_args_list == []

    def test_post_input_triggers_api_supplier_update_and_redirect(self):
        self.login()
        self.data_api_client.get_supplier.return_value = get_supplier(registeredName=None)

        res = self.client.post("/suppliers/registered-company-name/edit", data={'registered_company_name': "K-Inc"})

        assert self.data_api_client.update_supplier.call_args_list == [
            mock.call(supplier_id=1234, supplier={'registeredName': "K-Inc"}, user='email@email.com')
        ], 'update_supplier was called with the wrong arguments'
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/details'

    def test_fails_if_api_update_fails(self):
        self.login()
        self.data_api_client.get_supplier.return_value = get_supplier(registeredName=None)
        self.data_api_client.update_supplier.side_effect = APIError(ServiceUnavailable())
        res = self.client.post("/suppliers/registered-company-name/edit", data={'registered_company_name': "K-Inc"})
        assert res.status_code == 503

    @pytest.mark.parametrize('overwrite_supplier_data',
                             ({'companyDetailsConfirmed': False}, {'registeredName': None})
                             )
    def test_get_shows_form_on_page_if_supplier_data_not_complete_and_confirmed(self, overwrite_supplier_data):
        self.login()
        self.data_api_client.get_supplier.return_value = get_supplier(**overwrite_supplier_data)
        res = self.client.get("/suppliers/registered-company-name/edit")
        doc = html.fromstring(res.get_data(as_text=True))
        page_heading = doc.xpath('//h1')

        assert res.status_code == 200
        assert page_heading[0].text_content().strip() == "Registered company name"
        assert doc.xpath('//form[@action="/suppliers/registered-company-name/edit"]')
        assert self.data_api_client.update_supplier.call_args_list == []

    def test_get_shows_already_entered_page_and_api_not_called_update_if_data_already_confirmed(self):
        self.login()
        self.data_api_client.get_supplier.side_effect = get_supplier
        res = self.client.get("/suppliers/registered-company-name/edit")
        doc = html.fromstring(res.get_data(as_text=True))
        page_heading = doc.xpath('//h1')

        assert res.status_code == 200
        assert page_heading[0].text.strip() == "Correct a mistake in your registered company name"
        assert self.data_api_client.update_supplier.call_args_list == []

    def test_post_shows_already_entered_page_and_api_not_called_if_data_already_confirmed(self):
        self.login()
        self.data_api_client.get_supplier.side_effect = get_supplier
        res = self.client.post("/suppliers/registered-company-name/edit", data={'registered_company_name': "K-Inc"})
        doc = html.fromstring(res.get_data(as_text=True))
        page_heading = doc.xpath('//h1')

        assert res.status_code == 400
        assert page_heading[0].text.strip() == "Correct a mistake in your registered company name"
        assert self.data_api_client.update_supplier.call_args_list == []


class TestSupplierEditTradingStatus(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.suppliers.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_edit_organisation_size_page_loads(self):
        self.login()

        res = self.client.get("/suppliers/trading-status/edit")
        assert res.status_code == 200, 'The edit trading-status page has not loaded correctly.'

    @pytest.mark.parametrize('trading_status, expected_error',
                             (
                                 (None, "Select a trading status"),
                                 ('blah', "Not a valid choice")
                             ))
    def test_missing_or_invalid_choice_shows_validation(self, trading_status, expected_error):
        self.login()

        res = self.client.post("/suppliers/trading-status/edit",
                               data={'trading_status': trading_status} if trading_status else {})
        doc = html.fromstring(res.get_data(as_text=True))
        error = doc.xpath('//span[@id="input-trading_status-error"]')

        assert len(error) == 1, 'Only one validation message should be shown.'

        assert error[0].text_content().strip() == f"Error: {expected_error}", \
            'The validation message is not as anticipated.'

        self.assert_single_question_page_validation_errors(res, validation_message=expected_error)

    @pytest.mark.parametrize('trading_status', (None, 'limited company (LTD)', 'other'))
    def test_post_choice_triggers_api_supplier_update_and_redirect(self, trading_status):
        self.login()

        self.client.post("/suppliers/trading-status/edit", data={'trading_status': trading_status})

        call_args_list = self.data_api_client.update_supplier.call_args_list
        if trading_status:
            assert call_args_list == [
                mock.call(supplier_id=1234, supplier={'tradingStatus': trading_status}, user='email@email.com')
            ], 'update_supplier was called with the wrong arguments'

        else:
            assert call_args_list == [], 'update_supplier was called with the wrong arguments'

    @pytest.mark.parametrize('existing_trading_status, expected_selection',
                             (
                                 (None, []),
                                 ('some unknown value', []),
                                 *[(x['value'], [x['value']]) for x in CompanyTradingStatusForm.OPTIONS],
                             ))
    def test_existing_org_size_sets_current_selection(self, existing_trading_status, expected_selection):
        data = {'tradingStatus': existing_trading_status} if existing_trading_status else {}
        self.data_api_client.get_supplier.return_value = {'suppliers': data}

        self.login()

        res = self.client.get("/suppliers/trading-status/edit")
        doc = html.fromstring(res.get_data(as_text=True))
        selected_value = doc.xpath('//input[@name="trading_status" and @checked="checked"]/@value')
        assert selected_value == expected_selection, 'The trading status has not pre-populated correctly.'

    def test_api_error_is_not_suppressed(self):
        error_message = 'There was an error with the API'
        self.data_api_client.update_supplier.side_effect = APIError('blah', error_message)

        self.login()

        res = self.client.post("/suppliers/trading-status/edit",
                               data={'trading_status': CompanyTradingStatusForm.OPTIONS[0]['value']})
        assert res.status_code == 503


class TestSupplierAddRegistrationNumber(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.suppliers.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_add_registration_number_page_loads(self):
        self.login()
        self.data_api_client.get_supplier.return_value = get_supplier(
            companiesHouseNumber=None,
            otherCompanyRegistrationNumber=None
        )

        res = self.client.get("/suppliers/registration-number/edit")
        assert res.status_code == 200, 'The add registration number page has not loaded correctly.'

    @pytest.mark.parametrize(
        'incomplete_data, question_mentioned, validation_message',
        (
            (
                {'has_companies_house_number': '',
                 'companies_house_number': '',
                 'other_company_registration_number': ''
                 },
                'Select yes if you are registered with Companies House',
                'Select yes if you are registered with Companies House'
            ),
            (
                {'has_companies_house_number': 'Yes',
                 'companies_house_number': '',
                 'other_company_registration_number': ''
                 },
                'Enter a Companies House number',
                'Enter a Companies House number'
            ),
            (
                {'has_companies_house_number': 'Yes',
                 'companies_house_number': '123456789',
                 'other_company_registration_number': ''
                 },
                "Your Companies House number must be 8 characters",
                "Your Companies House number must be 8 characters"
            ),
            (
                {'has_companies_house_number': 'No',
                 'companies_house_number': '',
                 'other_company_registration_number': 'a' * 256
                 },
                'Registration number must be 255 characters or fewer',
                'Registration number must be 255 characters or fewer'
            )
        )
    )
    def test_incomplete_or_invalid_input_shows_validation_error_and_does_not_update_api(
        self, incomplete_data, question_mentioned, validation_message
    ):
        self.login()
        self.data_api_client.get_supplier.return_value = get_supplier(
            companiesHouseNumber=None,
            otherCompanyRegistrationNumber=None
        )

        res = self.client.post("/suppliers/registration-number/edit", data=incomplete_data)

        self.assert_single_question_page_validation_errors(res, validation_message=validation_message)
        assert self.data_api_client.update_supplier.call_args_list == []

        # Assert the links in the error summary point to elements on the page
        doc = html.fromstring(res.get_data(as_text=True))
        summary_link = doc.xpath("//ul[contains(@class, 'govuk-error-summary__list')]/li/a/@href")[0]
        assert doc.cssselect(summary_link)

    @pytest.mark.parametrize(
        'complete_data, expected_post',
        (
            (
                {'has_companies_house_number': 'Yes',
                 'companies_house_number': 'KK654321',
                 'other_company_registration_number': ''
                 },
                {'companiesHouseNumber': 'KK654321', 'otherCompanyRegistrationNumber': None}
            ),
            (
                {'has_companies_house_number': 'Yes',
                 'companies_house_number': 'kk654321',
                 'other_company_registration_number': ''
                 },
                {'companiesHouseNumber': 'KK654321', 'otherCompanyRegistrationNumber': None}
            ),
            (
                {'has_companies_house_number': 'No',
                 'companies_house_number': '',
                 'other_company_registration_number': 'KK987654321, my special registration number'
                 },
                {'companiesHouseNumber': None,
                 'otherCompanyRegistrationNumber': 'KK987654321, my special registration number'}
            ),
        )
    )
    def test_post_input_triggers_api_supplier_update_and_redirect(self, complete_data, expected_post):
        self.login()
        self.data_api_client.get_supplier.return_value = get_supplier(
            companiesHouseNumber=None,
            otherCompanyRegistrationNumber=None
        )

        res = self.client.post("/suppliers/registration-number/edit", data=complete_data)

        assert self.data_api_client.update_supplier.call_args_list == [
            mock.call(supplier_id=1234, supplier=expected_post, user='email@email.com')
        ], 'update_supplier was called with the wrong arguments'
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/details'

    def test_fails_if_api_update_fails(self):
        self.login()
        valid_post_data = {'has_companies_house_number': 'Yes',
                           'companies_house_number': 'KK654321',
                           'other_company_registration_number': ''
                           }
        self.data_api_client.get_supplier.return_value = get_supplier(
            companiesHouseNumber=None,
            otherCompanyRegistrationNumber=None
        )
        self.data_api_client.update_supplier.side_effect = APIError(ServiceUnavailable())
        res = self.client.post("/suppliers/registration-number/edit", data=valid_post_data)
        assert res.status_code == 503

    @pytest.mark.parametrize('overwrite_supplier_data',
                             (
                                 {'companyDetailsConfirmed': False},
                                 {'companiesHouseNumber': None, 'otherCompanyRegistrationNumber': None},
                             ))
    def test_get_shows_form_on_page_if_supplier_data_not_complete_and_confirmed(self, overwrite_supplier_data):
        self.login()
        self.data_api_client.get_supplier.return_value = get_supplier(**overwrite_supplier_data)
        res = self.client.get("/suppliers/registration-number/edit")
        doc = html.fromstring(res.get_data(as_text=True))
        page_heading = doc.xpath('//h1')

        assert res.status_code == 200
        assert page_heading[0].text_content().strip() == "Are you registered with Companies House?"
        assert doc.xpath('//form[@action="/suppliers/registration-number/edit"]')
        assert self.data_api_client.update_supplier.call_args_list == []

    def test_get_shows_already_entered_page_and_api_not_called_update_if_data_already_confirmed(self):
        self.login()
        # Default get_supplier has companiesHouseNumber and otherCompanyRegistrationNumber complete
        self.data_api_client.get_supplier.side_effect = get_supplier
        res = self.client.get("/suppliers/registration-number/edit")
        doc = html.fromstring(res.get_data(as_text=True))
        page_heading = doc.xpath('//h1')

        assert res.status_code == 200
        assert page_heading[0].text.strip() == "Correct a mistake in your registration number"
        assert self.data_api_client.update_supplier.call_args_list == []

    def test_post_shows_already_entered_page_and_api_not_called_if_data_already_confirmed(self):
        self.login()
        valid_post_data = {'has_companies_house_number': 'Yes',
                           'companies_house_number': 'KK654321',
                           'other_company_registration_number': ''
                           }
        # Default get_supplier has companiesHouseNumber and otherCompanyRegistrationNumber complete
        self.data_api_client.get_supplier.side_effect = get_supplier
        res = self.client.post("/suppliers/registration-number/edit", data=valid_post_data)
        doc = html.fromstring(res.get_data(as_text=True))
        page_heading = doc.xpath('//h1')

        assert res.status_code == 400
        assert page_heading[0].text.strip() == "Correct a mistake in your registration number"
        assert self.data_api_client.update_supplier.call_args_list == []
