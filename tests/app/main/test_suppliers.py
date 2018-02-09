# coding=utf-8
from urllib.parse import urlparse

from flask import session, current_app
from lxml import html
import mock
import pytest

from dmapiclient import HTTPError
from dmapiclient.audit import AuditTypes

from tests.app.helpers import BaseApplicationTest, assert_args_and_return

find_frameworks_return_value = {
    "frameworks": [
        {
            'status': 'expired',
            'slug': 'h-cloud-88',
            'name': 'H-Cloud 88',
            'framework': 'g-cloud',
        },
        {
            'status': 'live',
            'slug': 'g-cloud-6',
            'name': 'G-Cloud 6',
            'framework': 'g-cloud',
        },
        {
            'status': 'open',
            'slug': 'digital-outcomes-and-specialists',
            'name': 'Digital Outcomes and Specialists',
            'framework': 'digital-outcomes-and-specialists',
        },
        {
            'status': 'live',
            'slug': 'digital-rhymes-and-reasons',
            'name': 'Digital Rhymes and Reasons',
            'framework': 'digital-outcomes-and-specialists',
        },
        {
            'status': 'open',
            'slug': 'g-cloud-7',
            'name': 'G-Cloud 7',
            'framework': 'g-cloud',
        },
    ]
}


def get_supplier(*args, **kwargs):
    supplier_info = {
        "id": 1234,
        "dunsNumber": "987654321",
        "companiesHouseNumber": "CH123456",
        "registeredName": "Official Name Inc",
        "registrationCountry": "bz",
        "otherCompanyRegistrationNumber": "BEL153",
        "registrationDate": "1973-01-02",
        "vatNumber": "12345678",
        "organisationSize": "small",
        "tradingStatus": "Open for business",
        "name": "Supplier Name",
        "description": "Supplier Description",
        "clients": ["Client One", "Client Two"],
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
    return {"suppliers": supplier_info}


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
            'supplierId': 1234
        }
    }]


@mock.patch("app.main.views.suppliers.data_api_client", autospec=True)
@mock.patch("app.main.views.suppliers.get_current_suppliers_users", autospec=True)
class TestSuppliersDashboard(BaseApplicationTest):
    def test_error_and_success_flashed_messages_only_are_shown_in_banner_messages(
        self, get_current_suppliers_users, data_api_client
    ):
        with self.client.session_transaction() as session:
            session['_flashes'] = [
                ('error', 'This is an error'),
                ('success', 'This is a success'),
                ('flag', 'account-created')
            ]

        data_api_client.get_framework.return_value = self.framework('open')
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.find_audit_events.return_value = {
            "auditEvents": []
        }
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            data = self.strip_all_whitespace(res.get_data(as_text=True))

            assert '<pclass="banner-message">Thisisanerror</p>' in data
            assert '<pclass="banner-message">Thisisasuccess</p>' in data
            assert '<pclass="banner-message">account-created</p>' not in data

    def test_data_analytics_track_page_view_is_shown_if_account_created_flag_flash_message(
        self, get_current_suppliers_users, data_api_client
    ):
        with self.client.session_transaction() as session:
            session['_flashes'] = [('flag', 'account-created')]

        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            data = res.get_data(as_text=True)

            assert 'data-analytics="trackPageView" data-url="/suppliers?account-created=true"' in data

    def test_data_analytics_track_page_view_is_not_shown_if_no_account_created_flag_flash_message(
        self, get_current_suppliers_users, data_api_client
    ):
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            data = res.get_data(as_text=True)

            assert 'data-analytics="trackPageView" data-url="/suppliers?account-created=true"' not in data

    def test_shows_edit_buttons(self, get_current_suppliers_users, data_api_client):
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.find_frameworks.return_value = find_frameworks_return_value
        data_api_client.get_supplier_frameworks.return_value = {
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
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
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

    def test_shows_dos_is_coming(
        self, get_current_suppliers_users, data_api_client
    ):
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': []
        }
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    'status': 'coming',
                    'slug': 'bad-framework',
                    'name': 'Framework that should’t have coming message'
                },
                {
                    'status': 'coming',
                    'slug': 'digital-outcomes-and-specialists',
                    'name': 'Digital Outcomes and Specialists'
                }
            ]
        }

        with self.app.test_client():
            self.login()
            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))

            message = doc.xpath('//div[@class="temporary-message"]')
            assert len(message) == 1
            assert u"Digital Outcomes and Specialists will be open for applications soon" in \
                message[0].xpath('h3/text()')[0]
            assert u"We’ll email you when you can apply to Digital Outcomes and Specialists" in \
                message[0].xpath('p/text()')[0]
            assert u"Find out if your services are suitable" in message[0].xpath('p/a/text()')[0]

    def test_shows_gcloud_7_application_button(self, get_current_suppliers_users, data_api_client):
        data_api_client.get_framework_interest.return_value = {'frameworks': []}
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    'status': 'expired',
                    'slug': 'digital-outcomes-and-specialists',
                    'name': 'Digital Outcomes and Specialists'
                },
                {
                    'status': 'open',
                    'slug': 'g-cloud-7',
                    'name': 'G-Cloud 7'
                }
            ]
        }
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))

            assert res.status_code == 200
            assert 'Apply to G-Cloud 7' in doc.xpath('//h2[@class="summary-item-heading"]/text()')[0]
            assert doc.xpath('//input[@class="button-save"]/@value')[0] == 'Start application'

    def test_shows_gcloud_7_continue_link(self, get_current_suppliers_users, data_api_client):
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {'frameworkSlug': 'g-cloud-7'}
            ]
        }
        data_api_client.find_frameworks.return_value = find_frameworks_return_value
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))

            assert res.status_code == 200
            assert doc.xpath('//a[@href="/suppliers/frameworks/g-cloud-7"]/text()')[0] == \
                "Continue your G-Cloud 7 application"

    def test_shows_gcloud_7_closed_message_if_pending_and_no_interest(self, get_current_suppliers_users, data_api_client):  # noqa
        data_api_client.get_framework.return_value = self.framework('pending')
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_supplier_frameworks.return_value = {'frameworkInterest': []}
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    'status': 'pending',
                    'slug': 'g-cloud-7',
                    'name': 'G-Cloud 7'
                }
            ]
        }
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))

            message = doc.xpath('//aside[@class="temporary-message"]')
            assert len(message) > 0
            assert u"G-Cloud 7 is closed for applications" in message[0].xpath('h2/text()')[0]
            assert len(message[0].xpath('p[1]/a[@href="https://digitalmarketplace.blog.gov.uk/"]')) > 0

    def test_shows_gcloud_7_closed_message_if_pending_and_no_application(self, get_current_suppliers_users, data_api_client):  # noqa
        data_api_client.get_framework.return_value = self.framework('pending')
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {
                    'frameworkSlug': 'g-cloud-7',
                    'declaration': {'status': 'started'},
                    'drafts_count': 1,
                    'complete_drafts_count': 0
                }
            ]
        }
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    'status': 'pending',
                    'slug': 'g-cloud-7',
                    'name': 'G-Cloud 7'
                }
            ]
        }
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))

            message = doc.xpath('//aside[@class="temporary-message"]')
            assert len(message) > 0
            assert u"G-Cloud 7 is closed for applications" in message[0].xpath('h2/text()')[0]
            assert u"You didn’t submit an application" in message[0].xpath('p[1]/text()')[0]
            assert len(message[0].xpath('p[2]/a[contains(@href, "suppliers/frameworks/g-cloud-7")]')) > 0

    def test_shows_gcloud_7_closed_message_if_pending_and_application_done(
        self, get_current_suppliers_users, data_api_client
    ):
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {
                    'frameworkSlug': 'g-cloud-7',
                    'declaration': {'status': 'complete'},
                    'drafts_count': 0,
                    'complete_drafts_count': 99
                }
            ]
        }
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    'status': 'pending',
                    'slug': 'g-cloud-7',
                    'name': 'G-Cloud 7'
                }
            ]
        }

        with self.app.test_client():
            self.login()
            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))
            headings = doc.xpath('//h2[@class="summary-item-heading"]')
            assert len(headings) > 0
            assert u"G-Cloud 7 is closed for applications" in headings[0].xpath('text()')[0]
            assert u"You submitted 99 services for consideration" in headings[0].xpath('../p[1]/text()')[0]
            assert len(headings[0].xpath('../p[1]/a[contains(@href, "suppliers/frameworks/g-cloud-7")]')) > 0
            assert u"View your submitted application" in headings[0].xpath('../p[1]/a/text()')[0]

    @mock.patch("app.main.views.suppliers.content_loader")
    def test_shows_gcloud_7_in_standstill_application_passed_with_message(
        self, content_loader, get_current_suppliers_users, data_api_client
    ):
        content_loader.get_message.return_value = {'framework_live_date': '23 November 2015'}
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_supplier_frameworks.return_value = {
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
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    'status': 'standstill',
                    'slug': 'g-cloud-7',
                    'name': 'G-Cloud 7'
                }
            ]
        }

        with self.app.test_client():
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
            assert u"Live from 23 November 2015" in first_row
            assert u"99 services" in first_row
            assert u"99 services" in first_row
            assert u"You must sign the framework agreement to sell these services" in first_row

    @mock.patch("app.main.views.suppliers.content_loader")
    def test_shows_gcloud_7_in_standstill_application_passed_without_live_date(
        self, content_loader, get_current_suppliers_users, data_api_client
    ):
        content_loader.get_message.return_value = {'framework_live_date': ''}
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_supplier_frameworks.return_value = {
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
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    'status': 'standstill',
                    'slug': 'g-cloud-7',
                    'name': 'G-Cloud 7'
                }
            ]
        }

        with self.app.test_client():
            self.login()
            res = self.client.get("/suppliers")
            assert res.status_code == 200
            doc = html.fromstring(res.get_data(as_text=True))

            first_table = doc.xpath(
                '//table[@class="summary-item-body"]'
            )

            assert u"Pending services" in first_table[0].xpath('caption/text()')[0]

            first_row = "".join(first_table[0].xpath('tbody/descendant::*/text()'))
            assert u"G-Cloud 7" in first_row
            assert u"Live from" not in first_row

    def test_shows_gcloud_7_in_standstill_fw_agreement_returned(
        self, get_current_suppliers_users, data_api_client
    ):
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_supplier_frameworks.return_value = {
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
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    'status': 'standstill',
                    'slug': 'g-cloud-7',
                    'name': 'G-Cloud 7'
                }
            ]
        }

        with self.app.test_client():
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
            assert u"Live from 23 November 2015" in first_row
            assert u"99 services" in first_row
            assert u"You must sign the framework agreement to sell these services" not in first_row

    def test_shows_gcloud_7_in_standstill_no_application(
        self, get_current_suppliers_users, data_api_client
    ):
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': []
        }
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    'status': 'standstill',
                    'slug': 'g-cloud-7',
                    'name': 'G-Cloud 7'
                }
            ]
        }

        with self.app.test_client():
            self.login()
            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))

            assert not doc.xpath('//h2[normalize-space(string())=$t]', t="Pending services")

    def test_shows_gcloud_7_in_standstill_application_failed(
        self, get_current_suppliers_users, data_api_client
    ):
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_supplier_frameworks.return_value = {
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
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    'status': 'standstill',
                    'slug': 'g-cloud-7',
                    'name': 'G-Cloud 7'
                }
            ]
        }

        with self.app.test_client():
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
            assert u"Live from 23 November 2015" not in first_row
            assert u"99 services submitted" in first_row
            assert u"You must sign the framework agreement to sell these services" not in first_row
            assert u"View your documents" in first_row

    def test_shows_gcloud_7_in_standstill_application_passed(
        self, get_current_suppliers_users, data_api_client
    ):
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_supplier_frameworks.return_value = {
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
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    'status': 'standstill',
                    'slug': 'g-cloud-7',
                    'name': 'G-Cloud 7'
                }
            ]
        }

        with self.app.test_client():
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
            assert u"Live from 23 November 2015" in first_row
            assert u"99 services" in first_row
            assert u"You must sign the framework agreement to sell these services" not in first_row

    def test_shows_register_for_dos_button(self, get_current_suppliers_users, data_api_client):
        data_api_client.get_framework.return_value = self.framework(status='other')
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    'status': 'open',
                    'slug': 'digital-outcomes-and-specialists',
                    'name': 'Digital Outcomes and Specialists'
                },
                {
                    'status': 'live',
                    'slug': 'g-cloud-7',
                    'name': 'G-Cloud 7'
                }
            ]
        }
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))

            assert res.status_code == 200

            assert "Apply to Digital Outcomes and Specialists" in doc.xpath(
                '//div[@class="summary-item-lede"]//h2[@class="summary-item-heading"]/text()'
            )[0]
            assert doc.xpath('//div[@class="summary-item-lede"]//input/@value')[0] == "Start application"

    def test_shows_continue_with_dos_link(self, get_current_suppliers_users, data_api_client):
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {'frameworkSlug': 'digital-outcomes-and-specialists'}
            ]
        }
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    'status': 'open',
                    'slug': 'digital-outcomes-and-specialists',
                    'name': 'Digital Outcomes and Specialists'
                },
                {
                    'status': 'live',
                    'slug': 'g-cloud-7',
                    'name': 'G-Cloud 7'
                }
            ]
        }
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))

            assert res.status_code == 200
            assert "Continue your Digital Outcomes and Specialists application" in doc.xpath(
                '//a[@class="browse-list-item-link"]/text()'
            )[0]


@mock.patch("app.main.views.suppliers.data_api_client", autospec=True)
class TestSupplierDetails(BaseApplicationTest):
    def test_shows_supplier_info(self, data_api_client):
        data_api_client.get_supplier.side_effect = get_supplier
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers/details")
            assert res.status_code == 200
            page_html = res.get_data(as_text=True)
            document = html.fromstring(page_html)

            assert document.xpath(
                "//a[normalize-space(string())=$t][@href=$u][contains(@class, $c)]",
                t="Edit",
                u="/suppliers/details/edit",
                c="summary-change-link",
            )

            for property_str in (
                # "Supplier details" section at the top
                "Supplier Person",  # Contact name
                "supplier@user.dmdev",  # Contact email
                "0800123123",  # Phone number
                "1 Street",  # Address: "2 Building" and "Supplierland" are not shown, even though in contactInformation
                "Supplierville",  # Town or City
                "11 AB",  # Postcode
                "Supplier Description",  # Supplier summary
                # "Registration information" section
                "Official Name Inc",  # Registered company name
                "CH123456",  # Companies House number
                "987654321",  # DUNS number
                "12345678",  # VAT number
                "Open for business",  # Trading status
                "Small",  # Size
            ):
                assert document.xpath("//*[normalize-space(string())=$t]", t=property_str), property_str

            # Registration country and registration number not shown if Companies House ID exists
            for property_str in ("bz", "BEL153",):
                assert property_str not in page_html

            data_api_client.get_supplier.assert_called_once_with(1234)

    def test_shows_overseas_supplier_info_if_no_companies_house_number(self, data_api_client):
        data_api_client.get_supplier.return_value = get_supplier(companiesHouseNumber=None)
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers/details")
            assert res.status_code == 200
            page_html = res.get_data(as_text=True)
            document = html.fromstring(page_html)
            for property_str in ("BZ", "BEL153",):
                assert document.xpath("//*[normalize-space(string())=$t]", t=property_str), property_str

    def test_does_not_show_overseas_supplier_number_if_uk_company(self, data_api_client):
        data_api_client.get_supplier.return_value = get_supplier(companiesHouseNumber=None, registrationCountry="gb")
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers/details")
            assert res.status_code == 200
            page_html = res.get_data(as_text=True)
            document = html.fromstring(page_html)
            assert document.xpath("//*[normalize-space(string())='GB']")  # Country GB is shown
            assert "BEL153" not in page_html  # But overseas registration field isn't


@mock.patch("app.main.views.suppliers.data_api_client", autospec=True)
@mock.patch("app.main.views.suppliers.get_current_suppliers_users", autospec=True)
class TestSupplierOpportunitiesDashboardLink(BaseApplicationTest):
    def setup_method(self, method):
        super(TestSupplierOpportunitiesDashboardLink, self).setup_method(method)
        self.get_supplier_frameworks_response = {
            'agreementReturned': True,
            'complete_drafts_count': 2,
            'declaration': {'status': 'complete'},
            'frameworkSlug': 'digital-outcomes-and-specialists-2',
            'onFramework': True,
            'services_count': 2,
            'supplierId': 1234
        }
        self.find_frameworks_response = {
            'framework': 'digital-outcomes-and-specialists',
            'name': 'Digital Outcomes and Specialists 2',
            'slug': 'digital-outcomes-and-specialists-2',
            'status': 'live'
        }

    def test_opportunities_dashboard_link(self, get_current_suppliers_users, data_api_client):
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [self.get_supplier_frameworks_response]}
        data_api_client.find_frameworks.return_value = {"frameworks": [self.find_frameworks_response]}

        with self.client:
            self.login()
            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))

            # note how this also tests the ordering of the links
            assert doc.xpath(
                "//h3[normalize-space(string())=$f]"
                "[(following::a)[1][normalize-space(string())=$t1][@href=$u1]]"
                "[(following::a)[2][normalize-space(string())=$t2][@href=$u2]]"
                "[(following::a)[3][normalize-space(string())=$t3][@href=$u3]]",
                f="Digital Outcomes and Specialists 2",
                t1="View your opportunities",
                u1="/suppliers/opportunities/frameworks/digital-outcomes-and-specialists-2",
                t2="View services",
                u2="/suppliers/frameworks/digital-outcomes-and-specialists-2/services",
                t3="View documents and ask a question",
                u3="/suppliers/frameworks/digital-outcomes-and-specialists-2",
            )

    @pytest.mark.parametrize(
        'incorrect_data',
        (
            {'onFramework': False},
            {'services_count': 0},
            {'frameworkSlug': 'not-dos'}
        )
    )
    def test_opportunities_dashboard_link_fails_with_incomplete_data(
            self,
            get_current_suppliers_users,
            data_api_client,
            incorrect_data
    ):
        self.get_supplier_frameworks_response.update(incorrect_data)

        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [self.get_supplier_frameworks_response]}
        data_api_client.find_frameworks.return_value = {"frameworks": [self.find_frameworks_response]}

        with self.client:
            self.login()
            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))

            unexpected_link = "/suppliers/frameworks/digital-outcomes-and-specialists-2/opportunities"

            assert not any(filter(lambda i: i[2] == unexpected_link, doc.iterlinks()))


class TestSupplierDashboardLogin(BaseApplicationTest):
    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
    def test_should_show_supplier_dashboard_logged_in(
            self, get_current_suppliers_users, data_api_client
    ):
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
            self.login()
            data_api_client.authenticate_user.return_value = self.user(
                123, "email@email.com", 1234, u'Supplier NĀme', u'Năme')

            data_api_client.get_user.return_value = self.user(
                123, "email@email.com", 1234, u'Supplier NĀme', u'Năme')

            data_api_client.find_frameworks.return_value = find_frameworks_return_value

            data_api_client.get_supplier.side_effect = get_supplier

            res = self.client.get("/suppliers")

            assert res.status_code == 200

            assert self.strip_all_whitespace(u"<h1>Supplier NĀme</h1>") in \
                self.strip_all_whitespace(res.get_data(as_text=True))
            assert self.strip_all_whitespace("email@email.com") in \
                self.strip_all_whitespace(res.get_data(as_text=True))

    def test_should_redirect_to_login_if_not_logged_in(self):
        res = self.client.get("/suppliers")
        assert res.status_code == 302
        assert res.location == "http://localhost/user/login?next=%2Fsuppliers"


@mock.patch("app.main.views.suppliers.data_api_client")
class TestSupplierUpdate(BaseApplicationTest):
    def post_supplier_edit(self, data=None, **kwargs):
        if data is None:
            data = {
                "description": "New Description",
                "contact_id": 2,
                "contact_email": "supplier@user.dmdev",
                "contact_contactName": "Supplier Person",
                "contact_phoneNumber": "0800123123",
                "contact_address1": "1 Street",
                "contact_city": "Supplierville",
                "contact_postcode": "11 AB",
            }
        data.update(kwargs)
        res = self.client.post("/suppliers/details/edit", data=data)
        return res.status_code, res.get_data(as_text=True)

    def test_should_render_edit_page_with_minimum_data(self, data_api_client):
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

        data_api_client.get_supplier.side_effect = limited_supplier

        response = self.client.get("/suppliers/details/edit")
        assert response.status_code == 200

    def test_update_all_supplier_fields(self, data_api_client):
        self.login()

        status, _ = self.post_supplier_edit()

        assert status == 302

        data_api_client.update_supplier.assert_called_once_with(
            1234,
            {
                'description': u'New Description'
            },
            'email@email.com'
        )
        data_api_client.update_contact_information.assert_called_once_with(
            1234, 2,
            {
                'city': u'Supplierville',
                'address1': u'1 Street',
                'email': u'supplier@user.dmdev',
                'phoneNumber': u'0800123123',
                'postcode': u'11 AB',
                'contactName': u'Supplier Person',
                'id': 2
            },
            'email@email.com'
        )

    def test_should_strip_whitespace_surrounding_supplier_update_all_fields(self, data_api_client):
        self.login()

        data = {
            "description": "  New Description  ",
            "contact_id": 2,
            "contact_email": "  supplier@user.dmdev  ",
            "contact_contactName": "  Supplier Person  ",
            "contact_phoneNumber": "  0800123123  ",
            "contact_address1": "  1 Street  ",
            "contact_city": "  Supplierville  ",
            "contact_postcode": "  11 AB  "
        }

        status, _ = self.post_supplier_edit(data=data)

        assert status == 302

        data_api_client.update_supplier.assert_called_once_with(
            1234,
            {
                'description': u'New Description'
            },
            'email@email.com'
        )
        data_api_client.update_contact_information.assert_called_once_with(
            1234, 2,
            {
                'city': u'Supplierville',
                'address1': u'1 Street',
                'email': u'supplier@user.dmdev',
                'phoneNumber': u'0800123123',
                'postcode': u'11 AB',
                'contactName': u'Supplier Person',
                'id': 2
            },
            'email@email.com'
        )

    def test_missing_required_supplier_fields(self, data_api_client):
        self.login()

        status, resp = self.post_supplier_edit({
            "description": "New Description",
            "contact_id": 2,
            "contact_contactName": "Supplier Person",
            "contact_phoneNumber": "0800123123",
            "contact_address1": "1 Street",
            "contact_city": "Supplierville",
            "contact_postcode": "11 AB",
        })

        assert status == 200
        assert 'You must provide an email address' in resp

        assert data_api_client.update_supplier.called is False
        assert data_api_client.update_contact_information.called is False

        assert "New Description" in resp
        assert 'value="2"' in resp
        assert 'value="Supplier Person"' in resp
        assert 'value="0800123123"' in resp
        assert 'value="1 Street"' in resp
        assert 'value="Supplierville"' in resp
        assert 'value="11 AB"' in resp

    def test_description_below_word_length(self, data_api_client):
        self.login()

        status, resp = self.post_supplier_edit(
            description="DESCR " * 49
        )

        assert status == 302

        assert data_api_client.update_supplier.called is True
        assert data_api_client.update_contact_information.called is True

    def test_description_above_word_length(self, data_api_client):
        self.login()

        status, resp = self.post_supplier_edit(
            description="DESCR " * 51
        )

        assert status == 200
        assert 'must not be more than 50' in resp

        assert data_api_client.update_supplier.called is False
        assert data_api_client.update_contact_information.called is False

    def test_should_redirect_to_login_if_not_logged_in(self, data_api_client):
        res = self.client.get("/suppliers/details/edit")
        assert res.status_code == 302
        assert res.location == "http://localhost/user/login?next=%2Fsuppliers%2Fdetails%2Fedit"


class TestCreateSupplier(BaseApplicationTest):
    def test_should_be_an_error_if_no_duns_number(self):
        res = self.client.post(
            "/suppliers/duns-number",
            data={}
        )
        assert res.status_code == 400
        assert "You must enter a DUNS number with 9 digits." in res.get_data(as_text=True)

    def test_should_be_an_error_if_no_duns_number_is_letters(self):
        res = self.client.post(
            "/suppliers/duns-number",
            data={
                'duns_number': "invalid"
            }
        )
        assert res.status_code == 400
        assert "You must enter a DUNS number with 9 digits." in res.get_data(as_text=True)

    def test_should_be_an_error_if_no_duns_number_is_less_than_nine_digits(self):
        res = self.client.post(
            "/suppliers/duns-number",
            data={
                'duns_number': "12345678"
            }
        )
        assert res.status_code == 400
        assert "You must enter a DUNS number with 9 digits." in res.get_data(as_text=True)

    def test_should_be_an_error_if_no_duns_number_is_more_than_nine_digits(self):
        res = self.client.post(
            "/suppliers/duns-number",
            data={
                'duns_number': "1234567890"
            }
        )
        assert res.status_code == 400
        assert "You must enter a DUNS number with 9 digits." in res.get_data(as_text=True)

    @mock.patch("app.main.suppliers.data_api_client")
    def test_should_be_an_error_if_duns_number_in_use(self, data_api_client):
        data_api_client.find_suppliers.return_value = {
            "suppliers": [
                "one supplier", "two suppliers"
            ]
        }
        res = self.client.post(
            "/suppliers/duns-number",
            data={
                'duns_number': "123456789"
            }
        )
        assert res.status_code == 400
        page = res.get_data(as_text=True)
        assert "A supplier account already exists with that DUNS number" in page
        assert "DUNS number already used" in page

    @mock.patch("app.main.suppliers.data_api_client")
    def test_should_allow_nine_digit_duns_number(self, data_api_client):
        data_api_client.find_suppliers.return_value = {"suppliers": []}
        res = self.client.post(
            "/suppliers/duns-number",
            data={
                'duns_number': "123456789"
            }
        )
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/company-name'

    @mock.patch("app.main.suppliers.data_api_client")
    def test_should_allow_duns_numbers_that_start_with_zero(self, data_api_client):
        data_api_client.find_suppliers.return_value = {"suppliers": []}
        res = self.client.post(
            "/suppliers/duns-number",
            data={
                'duns_number': "012345678"
            }
        )
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/company-name'

    @mock.patch("app.main.suppliers.data_api_client")
    def test_should_strip_whitespace_surrounding_duns_number_field(self, data_api_client):
        data_api_client.find_suppliers.return_value = {"suppliers": []}
        with self.client as c:
            c.post(
                "/suppliers/duns-number",
                data={
                    'duns_number': "  012345678  "
                }
            )
            assert "duns_number" in session
            assert session.get("duns_number") == "012345678"

    def test_should_not_be_an_error_if_no_companies_house_number(self):
        res = self.client.post(
            "/suppliers/companies-house-number",
            data={}
        )
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/details'

    def test_should_be_an_error_if_companies_house_number_is_not_8_characters_short(self):
        res = self.client.post(
            "/suppliers/companies-house-number",
            data={
                'companies_house_number': "1234567"
            }
        )
        assert res.status_code == 400
        assert ("Companies House numbers must have either 8 digits or 2 letters followed by 6 digits."
                in
                res.get_data(as_text=True)
                )

    def test_should_be_an_error_if_companies_house_number_is_not_8_characters_long(self):
        res = self.client.post(
            "/suppliers/companies-house-number",
            data={
                'companies_house_number': "123456789"
            }
        )
        assert res.status_code == 400
        assert ("Companies House numbers must have either 8 digits or 2 letters followed by 6 digits."
                in
                res.get_data(as_text=True)
                )

    def test_should_be_an_error_if_companies_house_number_is_8_characters_but_invalid_format(self):
        res = self.client.post(
            "/suppliers/companies-house-number",
            data={
                'companies_house_number': "ABC12345"
            }
        )
        assert res.status_code == 400
        assert ("Companies House numbers must have either 8 digits or 2 letters followed by 6 digits."
                in
                res.get_data(as_text=True)
                )

    def test_should_allow_valid_companies_house_number(self):
        with self.client as c:
            res = c.post(
                "/suppliers/companies-house-number",
                data={
                    'companies_house_number': "SC001122"
                }
            )
            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/details'

    def test_should_strip_whitespace_surrounding_companies_house_number_field(self):
        with self.client as c:
            c.post(
                "/suppliers/companies-house-number",
                data={
                    'companies_house_number': "  SC001122  "
                }
            )
            assert "companies_house_number" in session
            assert session.get("companies_house_number") == "SC001122"

    def test_should_wipe_companies_house_number_if_not_supplied(self):
        with self.client as c:
            res = c.post(
                "/suppliers/companies-house-number",
                data={
                    'companies_house_number': ""
                }
            )
            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/details'
            assert "companies_house_number" not in session

    def test_should_allow_valid_company_name(self):
        res = self.client.post(
            "/suppliers/company-name",
            data={
                'company_name': "My Company"
            }
        )
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/company-contact-details'

    def test_should_strip_whitespace_surrounding_company_name_field(self):
        with self.client as c:
            c.post(
                "/suppliers/company-name",
                data={
                    'company_name': "  My Company  "
                }
            )
            assert "company_name" in session
            assert session.get("company_name") == "My Company"

    def test_should_be_an_error_if_no_company_name(self):
        res = self.client.post(
            "/suppliers/company-name",
            data={}
        )
        assert res.status_code == 400
        assert "You must provide a company name." in res.get_data(as_text=True)

    def test_should_be_an_error_if_company_name_too_long(self):
        twofiftysix = "a" * 256
        res = self.client.post(
            "/suppliers/company-name",
            data={
                'company_name': twofiftysix
            }
        )
        assert res.status_code == 400
        assert "You must provide a company name under 256 characters." in res.get_data(as_text=True)

    def test_should_allow_valid_company_contact_details(self):
        res = self.client.post(
            "/suppliers/company-contact-details",
            data={
                'contact_name': "Name",
                'email_address': "name@email.com",
                'phone_number': "999"
            }
        )
        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers/create-your-account'

    def test_should_strip_whitespace_surrounding_contact_details_fields(self):
        contact_details = {
            'contact_name': "  Name  ",
            'email_address': "  name@email.com  ",
            'phone_number': "  999  "
        }

        with self.client as c:
            c.post(
                "/suppliers/company-contact-details",
                data=contact_details
            )

            for key, value in contact_details.items():
                assert key in session
                assert session.get(key) == value.strip()

    def test_should_not_allow_contact_details_without_name(self):
        res = self.client.post(
            "/suppliers/company-contact-details",
            data={
                'email_address': "name@email.com",
                'phone_number': "999"
            }
        )
        assert res.status_code == 400
        assert "You must provide a contact name." in res.get_data(as_text=True)

    def test_should_not_allow_contact_details_with_too_long_name(self):
        twofiftysix = "a" * 256
        res = self.client.post(
            "/suppliers/company-contact-details",
            data={
                'contact_name': twofiftysix,
                'email_address': "name@email.com",
                'phone_number': "999"
            }
        )
        assert res.status_code == 400
        assert "You must provide a contact name under 256 characters." in res.get_data(as_text=True)

    def test_should_not_allow_contact_details_without_email(self):
        res = self.client.post(
            "/suppliers/company-contact-details",
            data={
                'contact_name': "Name",
                'phone_number': "999"
            }
        )
        assert res.status_code == 400
        assert "You must provide an email address." in res.get_data(as_text=True)

    def test_should_not_allow_contact_details_with_invalid_email(self):
        res = self.client.post(
            "/suppliers/company-contact-details",
            data={
                'contact_name': "Name",
                'email_address': "notrightatall",
                'phone_number': "999"
            }
        )
        assert res.status_code == 400
        assert "You must provide a valid email address." in res.get_data(as_text=True)

    def test_should_not_allow_contact_details_without_phone_number(self):
        res = self.client.post(
            "/suppliers/company-contact-details",
            data={
                'contact_name': "Name",
                'email_address': "name@email.com"
            }
        )
        assert res.status_code == 400
        assert "You must provide a phone number." in res.get_data(as_text=True)

    def test_should_not_allow_contact_details_with_invalid_phone_number(self):
        twentyone = "a" * 21
        res = self.client.post(
            "/suppliers/company-contact-details",
            data={
                'contact_name': "Name",
                'email_address': "name@email.com",
                'phone_number': twentyone
            }
        )
        assert res.status_code == 400
        assert "You must provide a phone number under 20 characters." in res.get_data(as_text=True)

    def test_should_show_multiple_errors(self):
        res = self.client.post(
            "/suppliers/company-contact-details",
            data={}
        )

        assert res.status_code == 400
        assert "You must provide a phone number." in res.get_data(as_text=True)
        assert "You must provide an email address." in res.get_data(as_text=True)
        assert "You must provide a contact name." in res.get_data(as_text=True)

    def test_should_populate_duns_from_session(self):
        with self.client.session_transaction() as sess:
            sess['duns_number'] = "999"
        res = self.client.get("/suppliers/duns-number")
        assert res.status_code == 200
        assert '<inputtype="text"name="duns_number"id="input-duns_number"class="text-box"value="999"' \
            in self.strip_all_whitespace(res.get_data(as_text=True))

    def test_should_populate_companies_house_from_session(self):
        with self.client.session_transaction() as sess:
            sess['companies_house_number'] = "999"
        res = self.client.get("/suppliers/companies-house-number")
        assert res.status_code == 200
        assert '<inputtype="text"name="companies_house_number"id="input-companies_house_number"' \
            'class="text-box"value="999"' in self.strip_all_whitespace(res.get_data(as_text=True))

    def test_should_populate_company_name_from_session(self):
        with self.client.session_transaction() as sess:
            sess['company_name'] = "Name"
        res = self.client.get("/suppliers/company-name")
        assert res.status_code == 200
        assert '<inputtype="text"name="company_name"id="input-company_name"class="text-box"value="Name"' \
            in self.strip_all_whitespace(res.get_data(as_text=True))

    def test_should_populate_contact_details_from_session(self):
        with self.client.session_transaction() as sess:
            sess['email_address'] = "email_address"
            sess['contact_name'] = "contact_name"
            sess['phone_number'] = "phone_number"
        res = self.client.get("/suppliers/company-contact-details")
        assert res.status_code == 200
        stripped_page = self.strip_all_whitespace(res.get_data(as_text=True))
        assert '<inputtype="text"name="email_address"id="input-email_address"class="text-box"value="email_address"' \
            in stripped_page

        assert '<inputtype="text"name="contact_name"id="input-contact_name"class="text-box"value="contact_name"' \
            in stripped_page

        assert '<inputtype="text"name="phone_number"id="input-phone_number"class="text-box"value="phone_number"' \
            in stripped_page

    def test_should_be_an_error_to_be_submit_company_with_incomplete_session(self):
        res = self.client.post("/suppliers/company-summary")
        assert res.status_code == 400
        assert 'You must answer all the questions' in res.get_data(as_text=True)

    @mock.patch("app.main.suppliers.data_api_client")
    @mock.patch("app.main.suppliers.send_user_account_email")
    def test_should_redirect_to_create_your_account_if_valid_session(self, send_user_account_email, data_api_client):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_address'] = "email_address"
                sess['phone_number'] = "phone_number"
                sess['contact_name'] = "contact_name"
                sess['duns_number'] = "duns_number"
                sess['company_name'] = "company_name"
                sess['account_email_address'] = "valid@email.com"

            data_api_client.create_supplier.return_value = self.supplier()
            res = c.post("/suppliers/company-summary")
            assert res.status_code == 302
            assert res.location == "http://localhost/suppliers/create-your-account-complete"
            data_api_client.create_supplier.assert_called_once_with({
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

    @mock.patch("app.main.suppliers.data_api_client")
    @mock.patch("app.main.suppliers.send_user_account_email")
    def test_should_allow_missing_companies_house_number(self, send_user_account_email, data_api_client):
        with self.client.session_transaction() as sess:
            sess['email_address'] = "email_address"
            sess['phone_number'] = "phone_number"
            sess['contact_name'] = "contact_name"
            sess['duns_number'] = "duns_number"
            sess['company_name'] = "company_name"
            sess['account_email_address'] = "account_email_address"

        data_api_client.create_supplier.return_value = self.supplier()
        res = self.client.post(
            "/suppliers/company-summary",
            data={
                'email_address': 'valid@email.com'
            }
        )
        assert res.status_code == 302
        assert res.location == "http://localhost/suppliers/create-your-account-complete"
        data_api_client.create_supplier.assert_called_once_with({
            "contactInformation": [{
                "email": "email_address",
                "phoneNumber": "phone_number",
                "contactName": "contact_name"
            }],
            "dunsNumber": "duns_number",
            "name": "company_name"
        })

    @mock.patch("app.main.suppliers.data_api_client")
    def test_should_be_an_error_if_missing_a_field_in_session(self, data_api_client):
        with self.client.session_transaction() as sess:
            sess['email_address'] = "email_address"
            sess['phone_number'] = "phone_number"
            sess['contact_name'] = "contact_name"
            sess['duns_number'] = "duns_number"

        data_api_client.create_supplier.return_value = True
        res = self.client.post("/suppliers/company-summary")
        assert res.status_code == 400
        assert data_api_client.create_supplier.called is False
        assert 'You must answer all the questions' in res.get_data(as_text=True)

    @mock.patch("app.main.suppliers.data_api_client")
    def test_should_return_503_if_api_error(self, data_api_client):
        with self.client.session_transaction() as sess:
            sess['email_address'] = "email_address"
            sess['phone_number'] = "phone_number"
            sess['contact_name'] = "contact_name"
            sess['duns_number'] = "duns_number"
            sess['company_name'] = "company_name"
            sess['account_email_address'] = "account_email_address"

        data_api_client.create_supplier.side_effect = HTTPError("gone bad")
        res = self.client.post("/suppliers/company-summary")
        assert res.status_code == 503

    def test_should_require_an_email_address(self):
        with self.client.session_transaction() as sess:
            sess['email_company_name'] = "company_name"
            sess['email_supplier_id'] = 1234
        res = self.client.post(
            "/suppliers/create-your-account",
            data={}
        )
        assert res.status_code == 400
        assert "You must provide an email address." in res.get_data(as_text=True)

    def test_should_not_allow_incorrect_email_address(self):
        with self.client.session_transaction() as sess:
            sess['email_company_name'] = "company_name"
            sess['email_supplier_id'] = 1234
        res = self.client.post(
            "/suppliers/create-your-account",
            data={
                'email_address': "bademail"
            }
        )
        assert res.status_code == 400
        assert "You must provide a valid email address." in res.get_data(as_text=True)

    @mock.patch("app.main.suppliers.data_api_client")
    @mock.patch("app.main.suppliers.send_user_account_email")
    def test_should_allow_correct_email_address(self, send_user_account_email, data_api_client):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_address'] = "email_address"
                sess['phone_number'] = "phone_number"
                sess['contact_name'] = "contact_name"
                sess['duns_number'] = "duns_number"
                sess['company_name'] = "company_name"
                sess['account_email_address'] = "valid@email.com"

            data_api_client.create_supplier.return_value = self.supplier()

            res = c.post("/suppliers/company-summary")

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
            assert res.location == 'http://localhost/suppliers/create-your-account-complete'

    @mock.patch("app.main.suppliers.data_api_client")
    @mock.patch('dmutils.email.user_account_email.DMNotifyClient')
    def test_should_correctly_store_email_address_in_session(self, DMNotifyClient, data_api_client):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_address'] = "email_address"
                sess['phone_number'] = "phone_number"
                sess['contact_name'] = "contact_name"
                sess['duns_number'] = "duns_number"
                sess['company_name'] = "company_name"
                sess['account_email_address'] = "valid@email.com"

            data_api_client.create_supplier.return_value = self.supplier()

            c.post("/suppliers/company-summary")

            assert session['email_sent_to'] == 'valid@email.com'

    @mock.patch("app.main.suppliers.send_user_account_email")
    def test_should_be_an_error_if_incomplete_session_on_account_creation(self, send_user_account_email):
        res = self.client.post(
            "/suppliers/company-summary"
        )

        assert send_user_account_email.called is False
        assert res.status_code == 400

    def test_should_show_email_address_on_create_account_complete(self):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_sent_to'] = "my@email.com"
                sess['other_stuff'] = True

            res = c.get("/suppliers/create-your-account-complete")

            assert res.status_code == 200
            assert 'An email has been sent to my@email.com' in res.get_data(as_text=True)
            assert 'other_stuff' not in session

    def test_should_show_email_address_even_when_refreshed(self):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_sent_to'] = 'my-email@example.com'

            res = c.get('/suppliers/create-your-account-complete')

            assert res.status_code == 200
            assert 'An email has been sent to my-email@example.com' in res.get_data(as_text=True)

            res = c.get('/suppliers/create-your-account-complete')

            assert res.status_code == 200
            assert 'An email has been sent to my-email@example.com' in res.get_data(as_text=True)


@mock.patch("app.main.suppliers.data_api_client")
class TestJoinOpenFrameworkNotificationMailingList(BaseApplicationTest):
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
        assert form.xpath(".//input[@type='submit'][@value='Subscribe']")

        return form

    @mock.patch("app.main.views.suppliers.DMMailChimpClient")
    def test_get(self, mailchimp_client_class, data_api_client):
        data_api_client.create_audit_event.side_effect = AssertionError("This should not be called")
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
            t="You must provide a valid email address.",
        )
        assert not doc.xpath(
            "//*[normalize-space(string())=$t]",
            t="You must provide an email address.",
        )
        assert not doc.xpath("//*[contains(@class, 'validation-message')]")

        form = self._common_page_asserts_and_get_form(doc)

        # we have already tested for the existence of input[@name='email_address']
        assert not any(inp.value for inp in form.xpath(".//input[@name='email_address']"))

        self.assert_no_flashes()

    @pytest.mark.parametrize("email_address_value,expected_validation_message", (
        ("pint@twopence", "You must provide a valid email address.",),
        ("", "You must provide an email address.",),
    ))
    @mock.patch("app.main.views.suppliers.DMMailChimpClient")
    def test_post_invalid_email(
        self,
        mailchimp_client_class,
        data_api_client,
        email_address_value,
        expected_validation_message,
    ):
        data_api_client.create_audit_event.side_effect = AssertionError("This should not be called")
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

    @pytest.mark.parametrize("mc_retval,expected_status", (
        (True, 400),
        (False, 503),
    ))
    @mock.patch("app.main.views.suppliers.DMMailChimpClient")
    def test_post_valid_email_failure(self, mailchimp_client_class, data_api_client, mc_retval, expected_status):
        data_api_client.create_audit_event.side_effect = AssertionError("This should not be called")
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
            t="You must provide a valid email address.",
        )
        assert not doc.xpath(
            "//*[normalize-space(string())=$t]",
            t="You must provide an email address.",
        )
        assert not doc.xpath("//*[contains(@class, 'validation-message')]")

        assert doc.xpath(
            "//*[contains(@class, 'banner-destructive-without-action')][contains(normalize-space(string()), $t)]//"
            "a[@href=$m][normalize-space(string())=$e]",
            t="The service is unavailable at the moment",
            m="mailto:enquiries@digitalmarketplace.service.gov.uk",
            e="enquiries@digitalmarketplace.service.gov.uk",
        )

        # flash message should have been consumed by view's own page rendering
        self.assert_no_flashes()

    @mock.patch("app.main.views.suppliers.DMMailChimpClient")
    def test_post_valid_email_success(self, mailchimp_client_class, data_api_client):
        data_api_client.create_audit_event.side_effect = assert_args_and_return(
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

        self.assert_flashes(
            "You will receive email notifications to qu&amp;rt@four.pence when applications are opening.",
            "success",
        )


@mock.patch("app.main.suppliers.data_api_client", autospec=True)
class TestBecomeASupplier(BaseApplicationTest):

    def test_become_a_supplier_page_loads_ok(self, data_api_client):
        res = self.client.get("/suppliers/supply")

        assert res.status_code == 200
        assert self.strip_all_whitespace(u"<h1>Become a supplier</h1>") in \
            self.strip_all_whitespace(res.get_data(as_text=True))

    def test_all_open_or_coming_frameworks(self, data_api_client):
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    "framework": "g-cloud",
                    "slug": "g-cloud-9",
                    "status": "open"
                },
                {
                    "framework": "g-cloud",
                    "slug": "g-cloud-8",
                    "status": "live"
                },
                {
                    "framework": "digital-outcomes-and-specialists",
                    "slug": "digital-outcomes-and-specialists-2",
                    "status": "coming"
                },
                {
                    "framework": "digital-outcomes-and-specialists",
                    "slug": "digital-outcomes-and-specialists",
                    "status": "live"
                },
            ]
        }

        with self.app.test_client():
            res = self.client.get("/suppliers/supply")
            data = res.get_data(as_text=True)

            data_api_client.find_frameworks.assert_called_once_with()

            # Check right headings are there
            assert u'Services you can apply to sell' in data
            assert u'Services you can’t apply to sell at the moment' not in data
            assert u'You can’t apply to sell anything at the moment' not in data

            # Check the right framework content is there
            assert u'Digital Outcomes and Specialists is opening for applications.' in data
            assert u'G-Cloud is open for applications.' in data

            # Check the right calls to action are there
            assert 'Create a supplier account' in data
            assert 'Get notifications when applications are opening' not in data

    def test_all_closed_frameworks(self, data_api_client):
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    "framework": "g-cloud",
                    "slug": "g-cloud-9",
                    "status": "live"
                },
                {
                    "framework": "g-cloud",
                    "slug": "g-cloud-8",
                    "status": "expired"
                },
                {
                    "framework": "digital-outcomes-and-specialists",
                    "slug": "digital-outcomes-and-specialists-2",
                    "status": "standstill"
                },
                {
                    "framework": "digital-outcomes-and-specialists",
                    "slug": "digital-outcomes-and-specialists",
                    "status": "live"
                },
            ]
        }

        with self.app.test_client():
            res = self.client.get("/suppliers/supply")
            data = res.get_data(as_text=True)

            data_api_client.find_frameworks.assert_called_once_with()

            # Check right headings are there
            assert u'You can’t apply to sell anything at the moment' in data
            assert u'Services you can apply to sell' not in data
            assert u'Services you can’t apply to sell at the moment' not in data

            # Check the right framework content is there
            assert u'Digital Outcomes and Specialists is closed for applications.' in data
            assert u'G-Cloud is closed for applications.' in data

            # Check the right calls to action are there
            assert 'Create a supplier account' not in data
            assert 'Get notifications when applications are opening' in data

    def test_one_open_one_closed_framework(self, data_api_client):
        data_api_client.find_frameworks.return_value = {
            "frameworks": [
                {
                    "framework": "g-cloud",
                    "slug": "g-cloud-9",
                    "status": "open"
                },
                {
                    "framework": "g-cloud",
                    "slug": "g-cloud-8",
                    "status": "live"
                },
                {
                    "framework": "digital-outcomes-and-specialists",
                    "slug": "digital-outcomes-and-specialists-2",
                    "status": "live"
                },
                {
                    "framework": "digital-outcomes-and-specialists",
                    "slug": "digital-outcomes-and-specialists",
                    "status": "expired"
                },
            ]
        }

        with self.app.test_client():
            res = self.client.get("/suppliers/supply")
            data = res.get_data(as_text=True)

            data_api_client.find_frameworks.assert_called_once_with()

            # Check right headings are there
            assert u'Services you can apply to sell' in data
            assert u'Services you can’t apply to sell at the moment' in data
            assert u'You can’t apply to sell anything at the moment' not in data

            # Check the right framework content is there
            assert u'Digital Outcomes and Specialists is closed for applications.' in data
            assert u'G-Cloud is open for applications.' in data

            # Check the right calls to action are there
            assert 'Create a supplier account' in data
            assert 'Get notifications when applications are opening' in data


@mock.patch("app.main.views.suppliers.data_api_client", autospec=True)
class TestSupplierEditOrganisationSize(BaseApplicationTest):
    def test_edit_organisation_size_page_loads(self, data_api_client):
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers/organisation-size/edit")
            assert res.status_code == 200, 'The edit organisation-size page has not loaded correctly.'

    def test_no_selection_triggers_input_required_validation(self, data_api_client):
        with self.app.test_client():
            self.login()

            res = self.client.post("/suppliers/organisation-size/edit")
            doc = html.fromstring(res.get_data(as_text=True))
            error = doc.xpath('//span[@id="error-organisation_size"]')

            assert len(error) == 1, \
                'Only one validation message should be shown.'

            assert error[0].text.strip() == 'You must choose an organisation size.', \
                'The validation message is not as anticipated.'

    @pytest.mark.parametrize('size', (None, 'micro', 'small', 'medium', 'large'))
    def test_post_choice_triggers_api_supplier_update_and_redirect(self, data_api_client, size):
        with self.app.test_client():
            self.login()

            self.client.post("/suppliers/organisation-size/edit", data={'organisation_size': size})

            call_args_list = data_api_client.update_supplier.call_args_list
            if size:
                assert call_args_list == [
                    mock.call(supplier_id=1234, supplier={'organisationSize': size}, user='email@email.com')
                ], 'update_supplier was called with the wrong arguments'

            else:
                assert call_args_list == [], 'update_supplier was called with the wrong arguments'

    @pytest.mark.parametrize('existing_size, expected_selection',
                             (
                                 (None, []),
                                 ('micro', ['micro']),
                                 ('small', ['small']),
                                 ('medium', ['medium']),
                                 ('large', ['large']),
                             ))
    def test_existing_org_size_sets_current_selection(self, data_api_client, existing_size, expected_selection):
        data = {'organisationSize': existing_size} if existing_size else {}
        data_api_client.get_supplier.return_value = {'suppliers': data}

        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers/organisation-size/edit")
            doc = html.fromstring(res.get_data(as_text=True))
            selected_value = doc.xpath('//input[@name="organisation_size" and @checked="checked"]/@value')
            assert selected_value == expected_selection, 'The organisation size has not pre-populated correctly.'
