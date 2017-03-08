# coding=utf-8

import mock
from flask import session
from lxml import html

from dmapiclient import HTTPError
from dmutils.email.exceptions import EmailError

from tests.app.helpers import BaseApplicationTest

find_frameworks_return_value = {
    "frameworks": [
        {'status': 'live', 'slug': 'g-cloud-6', 'name': 'G-Cloud 6'},
        {'status': 'open', 'slug': 'digital-outcomes-and-specialists', 'name': 'Digital Outcomes and Specialists'},
        {'status': 'open', 'slug': 'g-cloud-7', 'name': 'G-Cloud 7'}
    ]
}


def get_supplier(*args, **kwargs):
    return {"suppliers": {
        "id": 1234,
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
    }}


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


class TestSuppliersDashboard(BaseApplicationTest):
    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
    def test_shows_supplier_info(self, get_current_suppliers_users, data_api_client):
        data_api_client.get_framework.return_value = self.framework('open')
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.find_audit_events.return_value = {
            "auditEvents": []
        }
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            assert res.status_code == 200

            data_api_client.get_supplier.assert_called_once_with(1234)

            resp_data = res.get_data(as_text=True)

            assert "Supplier Description" in resp_data
            assert "Client One" in resp_data
            assert "Client Two" in resp_data

            assert "1 Street" in resp_data
            assert "2 Building" in resp_data
            assert "supplier.dmdev" in resp_data
            assert "supplier@user.dmdev" in resp_data
            assert "Supplier Person" in resp_data
            assert "0800123123" in resp_data
            assert "Supplierville" in resp_data
            assert "Supplierland" in resp_data
            assert "11 AB" in resp_data

            # Check contributors table exists
            assert self.strip_all_whitespace('Contributors</h2>') in self.strip_all_whitespace(resp_data)
            assert self.strip_all_whitespace('User Name</span></td>') in self.strip_all_whitespace(resp_data)
            assert self.strip_all_whitespace('email@email.com</span></td>') in self.strip_all_whitespace(resp_data)

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
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

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
    def test_data_analytics_track_page_view_is_shown_if_account_created_flag_flash_message(
        self, get_current_suppliers_users, data_api_client
    ):
        with self.client.session_transaction() as session:
            session['_flashes'] = [('flag', 'account-created')]

        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            data = res.get_data(as_text=True)

            assert 'data-analytics="trackPageView" data-url="/suppliers/vpv/?account-created=true"' in data

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
    def test_data_analytics_track_page_view_is_not_shown_if_no_account_created_flag_flash_message(
        self, get_current_suppliers_users, data_api_client
    ):
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            data = res.get_data(as_text=True)

            assert 'data-analytics="trackPageView" data-url="/suppliers/vpv/?account-created=true"' not in data

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
    def test_shows_edit_buttons(self, get_current_suppliers_users, data_api_client):
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.find_frameworks.return_value = find_frameworks_return_value
        data_api_client.get_supplier_frameworks.return_value = {
            'frameworkInterest': [
                {'frameworkSlug': 'g-cloud-6', 'services_count': 99}
            ]
        }
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            assert res.status_code == 200

            assert '<a href="/suppliers/edit" class="summary-change-link">Edit</a>' in res.get_data(as_text=True)
            assert '<a href="/suppliers/services" class="summary-change-link">View</a>' in res.get_data(as_text=True)

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
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

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
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

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
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

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
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

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
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

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
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

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
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

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
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

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
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

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
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
            headings = doc.xpath('//h2[@class="summary-item-heading"]')

            assert u"Pending services" not in headings[0].xpath('text()')[0]

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
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

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
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

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
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

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
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
        assert res.location == "http://localhost/login?next=%2Fsuppliers"


@mock.patch("app.main.views.suppliers.data_api_client")
class TestSupplierUpdate(BaseApplicationTest):
    def post_supplier_edit(self, data=None, **kwargs):
        if data is None:
            data = {
                "description": "New Description",
                "clients": ["ClientA", "ClientB"],
                "contact_id": 2,
                "contact_email": "supplier@user.dmdev",
                "contact_website": "supplier.dmdev",
                "contact_contactName": "Supplier Person",
                "contact_phoneNumber": "0800123123",
                "contact_address1": "1 Street",
                "contact_address2": "2 Building",
                "contact_city": "Supplierville",
                "contact_country": "Supplierland",
                "contact_postcode": "11 AB",
            }
        data.update(kwargs)
        res = self.client.post("/suppliers/edit", data=data)
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

        response = self.client.get("/suppliers/edit")
        assert response.status_code == 200

    def test_update_all_supplier_fields(self, data_api_client):
        self.login()

        status, _ = self.post_supplier_edit()

        assert status == 302

        data_api_client.update_supplier.assert_called_once_with(
            1234,
            {
                'clients': [u'ClientA', u'ClientB'],
                'description': u'New Description'
            },
            'email@email.com'
        )
        data_api_client.update_contact_information.assert_called_once_with(
            1234, 2,
            {
                'website': u'supplier.dmdev',
                'city': u'Supplierville',
                'country': u'Supplierland',
                'address1': u'1 Street',
                'address2': u'2 Building',
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
            "clients": ["  ClientA  ", "  ClientB  "],
            "contact_id": 2,
            "contact_email": "  supplier@user.dmdev  ",
            "contact_website": "  supplier.dmdev  ",
            "contact_contactName": "  Supplier Person  ",
            "contact_phoneNumber": "  0800123123  ",
            "contact_address1": "  1 Street  ",
            "contact_address2": "  2 Building  ",
            "contact_city": "  Supplierville  ",
            "contact_country": "  Supplierland  ",
            "contact_postcode": "  11 AB  "
        }

        status, _ = self.post_supplier_edit(data=data)

        assert status == 302

        data_api_client.update_supplier.assert_called_once_with(
            1234,
            {
                'clients': [u'ClientA', u'ClientB'],
                'description': u'New Description'
            },
            'email@email.com'
        )
        data_api_client.update_contact_information.assert_called_once_with(
            1234, 2,
            {
                'website': u'supplier.dmdev',
                'city': u'Supplierville',
                'country': u'Supplierland',
                'address1': u'1 Street',
                'address2': u'2 Building',
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
            "clients": ["ClientA", "", "ClientB"],
            "contact_id": 2,
            "contact_website": "supplier.dmdev",
            "contact_contactName": "Supplier Person",
            "contact_phoneNumber": "0800123123",
            "contact_address1": "1 Street",
            "contact_address2": "2 Building",
            "contact_city": "Supplierville",
            "contact_country": u"Supplierland",
            "contact_postcode": "11 AB",
        })

        assert status == 200
        assert 'You must provide an email address' in resp

        assert data_api_client.update_supplier.called is False
        assert data_api_client.update_contact_information.called is False

        assert "New Description" in resp
        assert 'value="ClientA"' in resp
        assert 'value="ClientB"' in resp
        assert 'value="2"' in resp
        assert 'value="supplier.dmdev"' in resp
        assert 'value="Supplier Person"' in resp
        assert 'value="0800123123"' in resp
        assert 'value="1 Street"' in resp
        assert 'value="2 Building"' in resp
        assert 'value="Supplierville"' in resp
        assert 'value="Supplierland"' in resp
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

    def test_clients_above_limit(self, data_api_client):
        self.login()

        status, resp = self.post_supplier_edit(
            clients=["", "A Client"] * 11
        )

        assert status == 200
        assert 'You must have 10 or fewer clients' in resp

    def test_should_redirect_to_login_if_not_logged_in(self, data_api_client):
        res = self.client.get("/suppliers/edit")
        assert res.status_code == 302
        assert res.location == "http://localhost/login?next=%2Fsuppliers%2Fedit"


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
        assert res.location == 'http://localhost/suppliers/companies-house-number'

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
        assert res.location == 'http://localhost/suppliers/companies-house-number'

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
        assert res.location == 'http://localhost/suppliers/company-name'

    def test_should_be_an_error_if_companies_house_number_is_not_8_characters_short(self):
        res = self.client.post(
            "/suppliers/companies-house-number",
            data={
                'companies_house_number': "short"
            }
        )
        assert res.status_code == 400
        assert "Companies House numbers must have 8 characters." in res.get_data(as_text=True)

    def test_should_be_an_error_if_companies_house_number_is_not_8_characters_long(self):
        res = self.client.post(
            "/suppliers/companies-house-number",
            data={
                'companies_house_number': "muchtoolongtobecompanieshouse"
            }
        )
        assert res.status_code == 400
        assert "Companies House numbers must have 8 characters." in res.get_data(as_text=True)

    def test_should_allow_valid_companies_house_number(self):
        with self.client as c:
            res = c.post(
                "/suppliers/companies-house-number",
                data={
                    'companies_house_number': "SC001122"
                }
            )
            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/company-name'

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
            assert res.location == 'http://localhost/suppliers/company-name'
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
        assert "You must provide a email address." in res.get_data(as_text=True)

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
        assert "You must provide a email address." in res.get_data(as_text=True)
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
    @mock.patch("app.main.suppliers.send_email")
    @mock.patch("app.main.suppliers.generate_token")
    def test_should_redirect_to_create_your_account_if_valid_session(self, generate_token, send_email, data_api_client):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_address'] = "email_address"
                sess['phone_number'] = "phone_number"
                sess['contact_name'] = "contact_name"
                sess['duns_number'] = "duns_number"
                sess['company_name'] = "company_name"
                sess['companies_house_number'] = "companies_house_number"
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
                "companiesHouseNumber": "companies_house_number",
            })
            assert 'email_address' not in session
            assert 'phone_number' not in session
            assert 'contact_name' not in session
            assert 'duns_number' not in session
            assert 'company_name' not in session
            assert 'companies_house_number' not in session
            assert session['email_supplier_id'] == 12345
            assert session['email_company_name'] == 'Supplier Name'

    @mock.patch("app.main.suppliers.data_api_client")
    @mock.patch("app.main.suppliers.send_email")
    @mock.patch("app.main.suppliers.generate_token")
    def test_should_allow_missing_companies_house_number(self, generate_token, send_email, data_api_client):
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
        assert "You must provide a email address." in res.get_data(as_text=True)

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
    @mock.patch("app.main.suppliers.send_email")
    @mock.patch("app.main.suppliers.generate_token")
    def test_should_allow_correct_email_address(self, generate_token, send_email, data_api_client):
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

            generate_token.assert_called_once_with(
                {
                    "email_address": "valid@email.com",
                    "supplier_id": 12345,
                    "supplier_name": "Supplier Name"
                },
                "KEY",
                "InviteEmailSalt"
            )

            send_email.assert_called_once_with(
                "valid@email.com",
                mock.ANY,
                "MANDRILL",
                "Create your Digital Marketplace account",
                "enquiries@digitalmarketplace.service.gov.uk",
                "Digital Marketplace Admin",
                ["user-creation"]
            )

            assert res.status_code == 302
            assert res.location == 'http://localhost/suppliers/create-your-account-complete'
            assert session['email_sent_to'] == 'valid@email.com'

    @mock.patch("app.main.suppliers.send_email")
    @mock.patch("app.main.suppliers.generate_token")
    def test_should_be_an_error_if_incomplete_session_on_account_creation(self, generate_token, send_email):
        res = self.client.post(
            "/suppliers/company-summary"
        )

        assert generate_token.called is False
        assert send_email.called is False
        assert res.status_code == 400

    @mock.patch("app.main.suppliers.data_api_client")
    @mock.patch("app.main.suppliers.send_email")
    @mock.patch("app.main.suppliers.generate_token")
    def test_should_be_a_503_if_mandrill_failure_on_creation_email(self, generate_token, send_email, data_api_client):
        with self.client.session_transaction() as sess:
            sess['email_address'] = "email_address"
            sess['phone_number'] = "phone_number"
            sess['contact_name'] = "contact_name"
            sess['duns_number'] = "duns_number"
            sess['company_name'] = "company_name"
            sess['account_email_address'] = "valid@email.com"

        send_email.side_effect = EmailError("Failed")
        data_api_client.create_supplier.return_value = self.supplier()

        res = self.client.post(
            "/suppliers/company-summary"
        )

        generate_token.assert_called_once_with(
            {
                "email_address": "valid@email.com",
                "supplier_id": 12345,
                "supplier_name": "Supplier Name"
            },
            "KEY",
            "InviteEmailSalt"
        )

        send_email.assert_called_once_with(
            "valid@email.com",
            mock.ANY,
            "MANDRILL",
            "Create your Digital Marketplace account",
            "enquiries@digitalmarketplace.service.gov.uk",
            "Digital Marketplace Admin",
            ["user-creation"]
        )

        assert res.status_code == 503

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
