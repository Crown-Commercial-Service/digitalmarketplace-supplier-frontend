# coding=utf-8

from dmutils.apiclient import HTTPError
from dmutils.email import MandrillException
import mock
from flask import session
from nose.tools import assert_equal, assert_true, assert_in, assert_false
from tests.app.helpers import BaseApplicationTest
from lxml import html


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
            assert_equal(res.status_code, 200)

            data_api_client.get_supplier.assert_called_once_with(1234)

            resp_data = res.get_data(as_text=True)

            assert_in("Supplier Description", resp_data)
            assert_in("Client One", resp_data)
            assert_in("Client Two", resp_data)

            assert_in("1 Street", resp_data)
            assert_in("2 Building", resp_data)
            assert_in("supplier.dmdev", resp_data)
            assert_in("supplier@user.dmdev", resp_data)
            assert_in("Supplier Person", resp_data)
            assert_in("0800123123", resp_data)
            assert_in("Supplierville", resp_data)
            assert_in("Supplierland", resp_data)
            assert_in("11 AB", resp_data)

            # Check contributors table exists
            assert_in(
                self.strip_all_whitespace('Contributors</h2>'),
                self.strip_all_whitespace(resp_data)
            )
            assert_in(
                self.strip_all_whitespace('User Name</span></td>'),
                self.strip_all_whitespace(resp_data)
            )
            assert_in(
                self.strip_all_whitespace('email@email.com</span></td>'),
                self.strip_all_whitespace(resp_data)
            )

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
    def test_shows_edit_buttons(self, get_current_suppliers_users, data_api_client):
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.find_audit_events.return_value = {
            "auditEvents": []
        }
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            assert_equal(res.status_code, 200)

            assert_in('<a href="/suppliers/edit" class="summary-change-link">Edit</a>', res.get_data(as_text=True))
            assert_in('<a href="/suppliers/services" class="summary-change-link">View</a>', res.get_data(as_text=True))

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
    def test_shows_gcloud_7_application_link(self, get_current_suppliers_users, data_api_client):
        data_api_client.get_framework.return_value = self.framework('open')
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.find_audit_events.return_value = {
            "auditEvents": []
        }
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))

            assert_equal(res.status_code, 200)

            assert_equal(doc.xpath('//a[@href="/suppliers/frameworks/g-cloud-7"]/span/text()')[0],
                         "Register your interest in becoming a G-Cloud 7 supplier")

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
    def test_shows_gcloud_7_continue_link(self, get_current_suppliers_users, data_api_client):
        data_api_client.get_framework.return_value = self.framework('open')
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_framework_interest.return_value = {'frameworks': ['g-cloud-7']}
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))

            assert_equal(res.status_code, 200)
            assert_equal(doc.xpath('//a[@href="/suppliers/frameworks/g-cloud-7"]/span/text()')[0],
                         "Continue your G-Cloud 7 application")

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
    def test_shows_gcloud_7_closed_message_if_pending_and_no_interest(self, get_current_suppliers_users, data_api_client):  # noqa
        data_api_client.get_framework.return_value = self.framework('pending')
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.find_audit_events.return_value = {
            "auditEvents": []
        }
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))

            message = doc.xpath('//aside[@class="temporary-message"]')
            assert_true(len(message) > 0)
            assert_in(u"G‑Cloud 7 is closed for applications",
                      message[0].xpath('h2/text()')[0])
            assert_true(len(message[0].xpath('p[1]/a[@href="https://digitalmarketplace.blog.gov.uk/"]')) > 0)

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
    def test_shows_gcloud_7_closed_message_if_pending_and_no_application(self, get_current_suppliers_users, data_api_client):  # noqa
        data_api_client.get_framework.return_value = self.framework('pending')
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_framework_interest.return_value = {'frameworks': ['g-cloud-7']}
        data_api_client.find_draft_services.return_value = {
            "services": [
                {'serviceName': 'A service', 'status': 'not-submitted'}
            ]
        }
        get_current_suppliers_users.side_effect = get_user
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))

            message = doc.xpath('//aside[@class="temporary-message"]')
            assert_true(len(message) > 0)
            assert_in(u"G‑Cloud 7 is closed for applications",
                      message[0].xpath('h2/text()')[0])
            assert_in(u"You didn’t submit an application",
                      message[0].xpath('p[1]/text()')[0])
            assert_true(len(message[0].xpath('p[2]/a[contains(@href, "suppliers/frameworks/g-cloud-7")]')) > 0)

    @mock.patch("app.main.views.suppliers.data_api_client")
    @mock.patch("app.main.views.suppliers.get_current_suppliers_users")
    def test_shows_gcloud_7_closed_message_if_pending_and_application_done(self, get_current_suppliers_users, data_api_client):  # noqa
        data_api_client.get_framework.return_value = self.framework('pending')
        data_api_client.get_supplier.side_effect = get_supplier
        data_api_client.get_framework_interest.return_value = {'frameworks': ['g-cloud-7']}

        # an application is made if at least one draft is complete and the declaration is complete
        data_api_client.find_draft_services.return_value = {
            "services": [
                {'serviceName': 'A service', 'status': 'submitted'}
            ]
        }
        data_api_client.get_supplier_declaration.return_value = {
            "declaration": {'status': 'complete'}
        }
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            doc = html.fromstring(res.get_data(as_text=True))

            heading = doc.xpath('//div[@class="summary-item-lede"]//h2[@class="summary-item-heading"]')
            assert_true(len(heading) > 0)
            assert_in(u"G-Cloud 7 is closed for applications",
                      heading[0].xpath('text()')[0])
            assert_in(u"You submitted 1 service for consideration",
                      heading[0].xpath('../p[1]/text()')[0])
            assert_true(len(heading[0].xpath('../p[1]/a[contains(@href, "suppliers/frameworks/g-cloud-7")]')) > 0)
            assert_in(u"View your submitted application",
                      heading[0].xpath('../p[1]/a/text()')[0])


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
                123, "email@email.com", 1234, "Supplier Name", "Name")

            data_api_client.get_user.return_value = self.user(
                123, "email@email.com", 1234, "Supplier Name", "Name")

            data_api_client.get_supplier.side_effect = get_supplier

            self.client.post("/suppliers/login", data={
                "email_address": "valid@email.com",
                "password": "1234567890"
            })

            res = self.client.get("/suppliers")

            assert_equal(res.status_code, 200)

            assert_in(
                self.strip_all_whitespace("<h1>Supplier Name</h1>"),
                self.strip_all_whitespace(res.get_data(as_text=True))
            )
            assert_in(
                self.strip_all_whitespace("email@email.com"),
                self.strip_all_whitespace(res.get_data(as_text=True))
            )

    def test_should_redirect_to_login_if_not_logged_in(self):
        res = self.client.get("/suppliers")
        assert_equal(res.status_code, 302)
        assert_equal(res.location,
                     "http://localhost/suppliers/login"
                     "?next=%2Fsuppliers")


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
        assert_equal(response.status_code, 200)

    def test_update_all_supplier_fields(self, data_api_client):
        self.login()

        status, _ = self.post_supplier_edit()

        assert_equal(status, 302)

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

        assert_equal(status, 302)

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

        assert_equal(status, 200)
        assert_in('Email can not be empty', resp)

        assert_false(data_api_client.update_supplier.called)
        assert_false(
            data_api_client.update_contact_information.called
        )

        assert_in("New Description", resp)
        assert_in('value="ClientA"', resp)
        assert_in('value="ClientB"', resp)
        assert_in('value="2"', resp)
        assert_in('value="supplier.dmdev"', resp)
        assert_in('value="Supplier Person"', resp)
        assert_in('value="0800123123"', resp)
        assert_in('value="1 Street"', resp)
        assert_in('value="2 Building"', resp)
        assert_in('value="Supplierville"', resp)
        assert_in('value="Supplierland"', resp)
        assert_in('value="11 AB"', resp)

    def test_description_below_word_length(self, data_api_client):
        self.login()

        status, resp = self.post_supplier_edit(
            description="DESCR " * 49
        )

        assert_equal(status, 302)

        assert_true(data_api_client.update_supplier.called)
        assert_true(data_api_client.update_contact_information.called)

    def test_description_above_word_length(self, data_api_client):
        self.login()

        status, resp = self.post_supplier_edit(
            description="DESCR " * 51
        )

        assert_equal(status, 200)
        assert_in('must not be more than 50', resp)

        assert_false(data_api_client.update_supplier.called)
        assert_false(data_api_client.update_contact_information.called)

    def test_clients_above_limit(self, data_api_client):
        self.login()

        status, resp = self.post_supplier_edit(
            clients=["", "A Client"] * 11
        )

        assert_equal(status, 200)
        assert_in('You must have 10 or fewer clients', resp)

    def test_should_redirect_to_login_if_not_logged_in(self, data_api_client):
        res = self.client.get("/suppliers/edit")
        assert_equal(res.status_code, 302)
        assert_equal(
            res.location,
            "http://localhost/suppliers/login?next=%2Fsuppliers%2Fedit"
        )


class TestCreateSupplier(BaseApplicationTest):
    def test_should_be_an_error_if_no_duns_number(self):
        res = self.client.post(
            "/suppliers/duns-number",
            data={}
        )
        assert_equal(res.status_code, 400)
        assert_in("You must enter a DUNS number with 9 digits.", res.get_data(as_text=True))

    def test_should_be_an_error_if_no_duns_number_is_letters(self):
        res = self.client.post(
            "/suppliers/duns-number",
            data={
                'duns_number': "invalid"
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("You must enter a DUNS number with 9 digits.", res.get_data(as_text=True))

    def test_should_be_an_error_if_no_duns_number_is_less_than_nine_digits(self):
        res = self.client.post(
            "/suppliers/duns-number",
            data={
                'duns_number': "12345678"
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("You must enter a DUNS number with 9 digits.", res.get_data(as_text=True))

    def test_should_be_an_error_if_no_duns_number_is_more_than_nine_digits(self):
        res = self.client.post(
            "/suppliers/duns-number",
            data={
                'duns_number': "1234567890"
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("You must enter a DUNS number with 9 digits.", res.get_data(as_text=True))

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
        assert_equal(res.status_code, 400)
        page = res.get_data(as_text=True)
        assert_in("A supplier account already exists with that DUNS number", page)
        assert_in("DUNS number already used", page)

    @mock.patch("app.main.suppliers.data_api_client")
    def test_should_allow_nine_digit_duns_number(self, data_api_client):
        data_api_client.find_suppliers.return_value = {"suppliers": []}
        res = self.client.post(
            "/suppliers/duns-number",
            data={
                'duns_number': "123456789"
            }
        )
        assert_equal(res.status_code, 302)
        assert_equal(res.location, 'http://localhost/suppliers/companies-house-number')

    @mock.patch("app.main.suppliers.data_api_client")
    def test_should_allow_duns_numbers_that_start_with_zero(self, data_api_client):
        data_api_client.find_suppliers.return_value = {"suppliers": []}
        res = self.client.post(
            "/suppliers/duns-number",
            data={
                'duns_number': "012345678"
            }
        )
        assert_equal(res.status_code, 302)
        assert_equal(res.location, 'http://localhost/suppliers/companies-house-number')

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
            assert_true("duns_number" in session)
            assert_equal(session.get("duns_number"), "012345678")

    def test_should_not_be_an_error_if_no_companies_house_number(self):
        res = self.client.post(
            "/suppliers/companies-house-number",
            data={}
        )
        assert_equal(res.status_code, 302)
        assert_equal(res.location, 'http://localhost/suppliers/company-name')

    def test_should_be_an_error_if_companies_house_number_is_not_8_characters_short(self):
        res = self.client.post(
            "/suppliers/companies-house-number",
            data={
                'companies_house_number': "short"
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("Companies House numbers must have 8 characters.", res.get_data(as_text=True))

    def test_should_be_an_error_if_companies_house_number_is_not_8_characters_long(self):
        res = self.client.post(
            "/suppliers/companies-house-number",
            data={
                'companies_house_number': "muchtoolongtobecompanieshouse"
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("Companies House numbers must have 8 characters.", res.get_data(as_text=True))

    def test_should_allow_valid_companies_house_number(self):
        with self.client as c:
            res = c.post(
                "/suppliers/companies-house-number",
                data={
                    'companies_house_number': "SC001122"
                }
            )
            assert_equal(res.status_code, 302)
            assert_equal(res.location, 'http://localhost/suppliers/company-name')

    def test_should_strip_whitespace_surrounding_companies_house_number_field(self):
        with self.client as c:
            c.post(
                "/suppliers/companies-house-number",
                data={
                    'companies_house_number': "  SC001122  "
                }
            )
            assert_true("companies_house_number" in session)
            assert_equal(session.get("companies_house_number"), "SC001122")

    def test_should_wipe_companies_house_number_if_not_supplied(self):
        with self.client as c:
            res = c.post(
                "/suppliers/companies-house-number",
                data={
                    'companies_house_number': ""
                }
            )
            assert_equal(res.status_code, 302)
            assert_equal(res.location, 'http://localhost/suppliers/company-name')
            assert_false("companies_house_number" in session)

    def test_should_allow_valid_company_name(self):
        res = self.client.post(
            "/suppliers/company-name",
            data={
                'company_name': "My Company"
            }
        )
        assert_equal(res.status_code, 302)
        assert_equal(res.location, 'http://localhost/suppliers/company-contact-details')

    def test_should_strip_whitespace_surrounding_company_name_field(self):
        with self.client as c:
            c.post(
                "/suppliers/company-name",
                data={
                    'company_name': "  My Company  "
                }
            )
            assert_true("company_name" in session)
            assert_equal(session.get("company_name"), "My Company")

    def test_should_be_an_error_if_no_company_name(self):
        res = self.client.post(
            "/suppliers/company-name",
            data={}
        )
        assert_equal(res.status_code, 400)
        assert_in("You must provide a company name.", res.get_data(as_text=True))

    def test_should_be_an_error_if_company_name_too_long(self):
        twofiftysix = "a" * 256
        res = self.client.post(
            "/suppliers/company-name",
            data={
                'company_name': twofiftysix
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("You must provide a company name under 256 characters.", res.get_data(as_text=True))

    def test_should_allow_valid_company_contact_details(self):
        res = self.client.post(
            "/suppliers/company-contact-details",
            data={
                'contact_name': "Name",
                'email_address': "name@email.com",
                'phone_number': "999"
            }
        )
        assert_equal(res.status_code, 302)
        assert_equal(res.location, 'http://localhost/suppliers/create-your-account')

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
                assert_true(key in session)
                assert_equal(session.get(key), value.strip())

    def test_should_not_allow_contact_details_without_name(self):
        res = self.client.post(
            "/suppliers/company-contact-details",
            data={
                'email_address': "name@email.com",
                'phone_number': "999"
            }
        )
        assert_equal(res.status_code, 400)
        assert_true("You must provide a contact name." in res.get_data(as_text=True))

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
        assert_equal(res.status_code, 400)
        assert_true("You must provide a contact name under 256 characters." in res.get_data(as_text=True))

    def test_should_not_allow_contact_details_without_email(self):
        res = self.client.post(
            "/suppliers/company-contact-details",
            data={
                'contact_name': "Name",
                'phone_number': "999"
            }
        )
        assert_equal(res.status_code, 400)
        assert_true("You must provide a email address." in res.get_data(as_text=True))

    def test_should_not_allow_contact_details_with_invalid_email(self):
        res = self.client.post(
            "/suppliers/company-contact-details",
            data={
                'contact_name': "Name",
                'email_address': "notrightatall",
                'phone_number': "999"
            }
        )
        assert_equal(res.status_code, 400)
        assert_true("You must provide a valid email address." in res.get_data(as_text=True))

    def test_should_not_allow_contact_details_without_phone_number(self):
        res = self.client.post(
            "/suppliers/company-contact-details",
            data={
                'contact_name': "Name",
                'email_address': "name@email.com"
            }
        )
        assert_equal(res.status_code, 400)
        assert_true("You must provide a phone number." in res.get_data(as_text=True))

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
        assert_equal(res.status_code, 400)
        assert_true("You must provide a phone number under 20 characters." in res.get_data(as_text=True))

    def test_should_show_multiple_errors(self):
        res = self.client.post(
            "/suppliers/company-contact-details",
            data={}
        )
        assert_equal(res.status_code, 400)
        assert_true("You must provide a phone number." in res.get_data(as_text=True))
        assert_true("You must provide a email address." in res.get_data(as_text=True))
        assert_true("You must provide a contact name." in res.get_data(as_text=True))

    def test_should_populate_duns_from_session(self):
        with self.client.session_transaction() as sess:
            sess['duns_number'] = "999"
        res = self.client.get("/suppliers/duns-number")
        assert_equal(res.status_code, 200)
        assert_equal(
            '<input type="text" name="duns_number" id="input-duns_number" class="text-box" value="999" />'
            in res.get_data(as_text=True),
            True)

    def test_should_populate_companies_house_from_session(self):
        with self.client.session_transaction() as sess:
            sess['companies_house_number'] = "999"
        res = self.client.get("/suppliers/companies-house-number")
        assert_equal(res.status_code, 200)
        assert_true('<input type="text" name="companies_house_number" id="input-companies_house_number" class="text-box" value="999" />' in res.get_data(as_text=True))  # noqa

    def test_should_populate_company_name_from_session(self):
        with self.client.session_transaction() as sess:
            sess['company_name'] = "Name"
        res = self.client.get("/suppliers/company-name")
        assert_equal(res.status_code, 200)
        assert_true('<input type="text" name="company_name" id="input-company_name" class="text-box" value="Name" />' in res.get_data(as_text=True))  # noqa

    def test_should_populate_contact_details_from_session(self):
        with self.client.session_transaction() as sess:
            sess['email_address'] = "email_address"
            sess['contact_name'] = "contact_name"
            sess['phone_number'] = "phone_number"
        res = self.client.get("/suppliers/company-contact-details")
        assert_equal(res.status_code, 200)
        assert_true('<input type="text" name="email_address" id="input-email_address" class="text-box" value="email_address" />' in res.get_data(as_text=True))  # noqa

        assert_true('<input type="text" name="contact_name" id="input-contact_name" class="text-box" value="contact_name" />' in res.get_data(as_text=True))  # noqa

        assert_true('<input type="text" name="phone_number" id="input-phone_number" class="text-box" value="phone_number" />' in res.get_data(as_text=True))  # noqa

    def test_should_be_an_error_to_be_submit_company_with_incomplete_session(self):
        res = self.client.post("/suppliers/company-summary")
        assert_equal(res.status_code, 400)
        assert_equal(
            'You must answer all the questions' in res.get_data(as_text=True),
            True)

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
            assert_equal(res.status_code, 302)
            assert_equal(res.location, "http://localhost/suppliers/create-your-account-complete")
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
            assert_false('email_address' in session)
            assert_false('phone_number' in session)
            assert_false('contact_name' in session)
            assert_false('duns_number' in session)
            assert_false('company_name' in session)
            assert_false('companies_house_number' in session)
            assert_equal(session['email_supplier_id'], 12345)
            assert_equal(session['email_company_name'], 'Supplier Name')

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
        assert_equal(res.status_code, 302)
        assert_equal(res.location, "http://localhost/suppliers/create-your-account-complete")
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
        assert_equal(res.status_code, 400)
        assert_equal(data_api_client.create_supplier.called, False)
        assert_equal(
            'You must answer all the questions' in res.get_data(as_text=True),
            True)

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
        assert_equal(res.status_code, 503)

    def test_should_require_an_email_address(self):
        with self.client.session_transaction() as sess:
            sess['email_company_name'] = "company_name"
            sess['email_supplier_id'] = 1234
        res = self.client.post(
            "/suppliers/create-your-account",
            data={}
        )
        assert_equal(res.status_code, 400)
        assert_true("You must provide a email address." in res.get_data(as_text=True))

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
        assert_equal(res.status_code, 400)
        assert_true("You must provide a valid email address." in res.get_data(as_text=True))

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

            assert_equal(res.status_code, 302)
            assert_equal(res.location, 'http://localhost/suppliers/create-your-account-complete')
            assert_equal(session['email_sent_to'], 'valid@email.com')

    @mock.patch("app.main.suppliers.send_email")
    @mock.patch("app.main.suppliers.generate_token")
    def test_should_be_an_error_if_incomplete_session_on_account_creation(self, generate_token, send_email):
        res = self.client.post(
            "/suppliers/company-summary"
        )

        assert_false(generate_token.called)
        assert_false(send_email.called)
        assert_equal(res.status_code, 400)

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

        send_email.side_effect = MandrillException("Failed")
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

        assert_equal(res.status_code, 503)

    def test_should_show_email_address_on_create_account_complete(self):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_sent_to'] = "my@email.com"
                sess['other_stuff'] = True

            res = c.get("/suppliers/create-your-account-complete")

            assert_equal(res.status_code, 200)
            assert_true('An email has been sent to my@email.com' in res.get_data(as_text=True))
            assert_false('other_stuff' in session)

    def test_should_show_email_address_even_when_refreshed(self):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_sent_to'] = 'my-email@example.com'

            res = c.get('/suppliers/create-your-account-complete')

            assert_equal(res.status_code, 200)
            assert_true('An email has been sent to my-email@example.com' in res.get_data(as_text=True))

            res = c.get('/suppliers/create-your-account-complete')

            assert_equal(res.status_code, 200)
            assert_true('An email has been sent to my-email@example.com' in res.get_data(as_text=True))
