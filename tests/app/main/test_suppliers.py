# coding=utf-8

from dmapiclient import HTTPError
from dmutils.email import EmailError
from dmutils.forms import FakeCsrf
import mock
from flask import session
from nose.tools import assert_equal, assert_true, assert_in, assert_false, assert_greater, assert_not_in
from tests.app.helpers import BaseApplicationTest, csrf_only_request
from lxml import html
import pytest


find_frameworks_return_value = {
    "frameworks": [
        {'status': 'live', 'slug': 'g-cloud-6', 'name': 'G-Cloud 6'},
        {'status': 'open', 'slug': 'digital-outcomes-and-specialists', 'name': 'Digital Outcomes and Specialists'},
        {'status': 'open', 'slug': 'g-cloud-7', 'name': 'G-Cloud 7'}
    ]
}


def limited_supplier(self):
    return {
        'supplier': {
            'contacts': [
                {
                    'phoneNumber': '099887',
                    'id': 1234,
                    'contactName': 'contact name',
                    'email': 'email@email.com'
                }
            ],
            'website': 'www.com',
            'summary': 'supplier summary',
            'dunsNumber': '999999999',
            'id': 12345,
            'name': 'Supplier Name',
            'prices': {}
        }
    }


def get_supplier(*args, **kwargs):
    return {'supplier': {
        "id": 1234,
        "name": "Supplier Name",
        "description": "Supplier Description",
        "clients": ["Client One", "Client Two"],
        "contacts": [{
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
            'supplierCode': 1234
        }
    }]


class TestSuppliersDashboard(BaseApplicationTest):
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

            res = self.client.get(self.url_for('main.dashboard'))
            data = self.strip_all_whitespace(res.get_data(as_text=True))

            assert_in('<pclass="banner-message">Thisisanerror</p>', data)
            assert_in('<pclass="banner-message">Thisisasuccess</p>', data)
            assert_not_in('<pclass="banner-message">account-created</p>', data)


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

            data_api_client.find_frameworks.return_value = find_frameworks_return_value

            data_api_client.get_supplier.side_effect = get_supplier

            res = self.client.get(self.url_for('main.dashboard'))

            assert_equal(res.status_code, 200)

            assert self.strip_all_whitespace('>Supplier Name</h1>') in \
                self.strip_all_whitespace(res.get_data(as_text=True))

            assert_in(
                self.strip_all_whitespace("email@email.com"),
                self.strip_all_whitespace(res.get_data(as_text=True))
            )

    def test_should_redirect_to_login_if_not_logged_in(self):
        dashboard_url = self.url_for('main.dashboard')
        res = self.client.get(dashboard_url)
        assert_equal(res.status_code, 302)
        assert_equal(res.location, self.get_login_redirect_url(dashboard_url))


@mock.patch("app.main.views.suppliers.data_api_client")
class TestSupplierApplication(BaseApplicationTest):
    def test_update_create_application(self, data_api_client):
        self.login()

        response = self.client.get(self.url_for('main.supplier_update', id=1234))
        assert_equal(response.status_code, 302)

        args, kwargs = data_api_client.req.suppliers().application().post.call_args
        assert kwargs == {'data': {'current_user': {'email_address': 'email@email.com', 'name': 'Name'},
                                   'framework': 'digital-marketplace'}}


@mock.patch('app.main.suppliers.render_component')
@mock.patch("app.main.views.suppliers.data_api_client")
class TestSupplierEdit(BaseApplicationTest):

    def post_supplier_edit(self, data=None, csrf_token=FakeCsrf.valid_token, **kwargs):
        if data is None:
            data = {
                "summary": "New Description",
                "website": "www.com"
            }
        data.update(kwargs)
        if csrf_token is not None:
            data['csrf_token'] = csrf_token
        res = self.client.post(self.url_for('main.supplier_edit_save'), data=data)
        return res.status_code, res.get_data(as_text=True)

    def test_should_render_edit_page_with_minimum_data(self, data_api_client, render_component):
        self.login()
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        data_api_client.get_supplier.side_effect = limited_supplier

        response = self.client.get(self.url_for('main.supplier_edit'))
        assert_equal(response.status_code, 302)

    @pytest.mark.skip(reason="edit supplier through application")
    def test_update_all_supplier_fields(self, data_api_client, render_component):
        self.login()

        data_api_client.get_supplier.side_effect = limited_supplier
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        status, _ = self.post_supplier_edit()

        assert_equal(status, 302)

        data_api_client.update_supplier.assert_called_once_with(
            1234,
            {'website': u'www.com', 'summary': u'New Description'},
            user='email@email.com'
        )

    @pytest.mark.skip(reason="edit supplier through application")
    def test_should_strip_whitespace_surrounding_supplier_update_all_fields(self, data_api_client, render_component):
        self.login()

        data_api_client.get_supplier.side_effect = limited_supplier
        render_component.return_value.get_props.return_value = {}
        render_component.return_value.get_slug.return_value = 'slug'

        data = {
            'csrf_token': FakeCsrf.valid_token,
            "summary": "  New Description  ",
            "website": "www.com"
        }

        status, _ = self.post_supplier_edit(data=data)

        assert_equal(status, 302)

        data_api_client.update_supplier.assert_called_once_with(
            1234,
            {'website': u'www.com', 'summary': u'New Description'},
            user='email@email.com'
        )

    @pytest.mark.skip(reason="edit supplier through application")
    def test_description_below_word_length(self, data_api_client, render_component):
        self.login()

        status, resp = self.post_supplier_edit(
            description="DESCR " * 49
        )

        assert_equal(status, 302)

        assert_true(data_api_client.update_supplier.called)

    @pytest.mark.skip(reason="edit supplier through application")
    def test_description_above_word_length(self, data_api_client, render_component):
        self.login()

        status, resp = self.post_supplier_edit(
            summary="DESCR " * 51
        )

        assert_equal(status, 302)

    @pytest.mark.skip(reason="edit supplier through application")
    def test_should_redirect_to_login_if_not_logged_in(self, data_api_client, render_component):
        edit_url = self.url_for('main.supplier_edit_save')
        res = self.client.get(edit_url)
        assert_equal(res.status_code, 302)
        assert_equal(res.location, self.get_login_redirect_url(edit_url))


class TestCreateSupplier(BaseApplicationTest):
    def test_should_be_an_error_if_no_duns_number(self):
        res = self.client.post(
            self.url_for('main.submit_duns_number'),
            data=csrf_only_request,
        )
        assert_equal(res.status_code, 400)
        assert_in("You must enter a DUNS number with 9 digits.", res.get_data(as_text=True))

    def test_should_be_an_error_if_no_duns_number_is_letters(self):
        res = self.client.post(
            self.url_for('main.submit_duns_number'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'duns_number': "invalid"
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("You must enter a DUNS number with 9 digits.", res.get_data(as_text=True))

    def test_should_be_an_error_if_no_duns_number_is_less_than_nine_digits(self):
        res = self.client.post(
            self.url_for('main.submit_duns_number'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'duns_number': "12345678"
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("You must enter a DUNS number with 9 digits.", res.get_data(as_text=True))

    def test_should_be_an_error_if_no_duns_number_is_more_than_nine_digits(self):
        res = self.client.post(
            self.url_for('main.submit_duns_number'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'duns_number': "1234567890"
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("You must enter a DUNS number with 9 digits.", res.get_data(as_text=True))

    @mock.patch("app.main.suppliers.data_api_client")
    def test_should_be_an_error_if_duns_number_in_use(self, data_api_client):
        data_api_client.find_suppliers.return_value = {
            'suppliers': [
                "one supplier", "two suppliers"
            ]
        }
        res = self.client.post(
            self.url_for('main.submit_duns_number'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'duns_number': "123456789"
            }
        )
        assert_equal(res.status_code, 400)
        page = res.get_data(as_text=True)
        assert_in("A supplier account already exists with that DUNS number", page)
        assert_in("DUNS number already used", page)

    @mock.patch("app.main.suppliers.data_api_client")
    def test_should_allow_nine_digit_duns_number(self, data_api_client):
        data_api_client.find_suppliers.return_value = {'suppliers': []}
        res = self.client.post(
            self.url_for('main.submit_duns_number'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'duns_number': "123456789"
            }
        )
        assert_equal(res.status_code, 302)
        assert_equal(res.location, self.url_for('main.companies_house_number', _external=True))

    @mock.patch("app.main.suppliers.data_api_client")
    def test_should_allow_duns_numbers_that_start_with_zero(self, data_api_client):
        data_api_client.find_suppliers.return_value = {'suppliers': []}
        res = self.client.post(
            self.url_for('main.submit_duns_number'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'duns_number': "012345678"
            }
        )
        assert_equal(res.status_code, 302)
        assert_equal(res.location, self.url_for('main.companies_house_number', _external=True))

    def test_should_not_be_an_error_if_no_companies_house_number(self):
        res = self.client.post(
            self.url_for('main.submit_companies_house_number'),
            data=csrf_only_request,
        )
        assert_equal(res.status_code, 302)
        assert_equal(res.location, self.url_for('main.company_name', _external=True))

    def test_should_be_an_error_if_companies_house_number_is_not_8_characters_short(self):
        res = self.client.post(
            self.url_for('main.submit_companies_house_number'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'companies_house_number': 'short',
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("Companies House numbers must have 8 characters.", res.get_data(as_text=True))

    def test_should_be_an_error_if_companies_house_number_is_not_8_characters_long(self):
        res = self.client.post(
            self.url_for('main.submit_companies_house_number'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'companies_house_number': 'muchtoolongtobecompanieshouse',
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("Companies House numbers must have 8 characters.", res.get_data(as_text=True))

    def test_should_allow_valid_companies_house_number(self):
        with self.client as c:
            res = c.post(
                self.url_for('main.submit_companies_house_number'),
                data={
                    'csrf_token': FakeCsrf.valid_token,
                    'companies_house_number': 'SC001122',
                }
            )
            assert_equal(res.status_code, 302)
            assert_equal(res.location, self.url_for('main.company_name', _external=True))

    def test_should_strip_whitespace_surrounding_companies_house_number_field(self):
        with self.client as c:
            c.post(
                self.url_for('main.submit_companies_house_number'),
                data={
                    'csrf_token': FakeCsrf.valid_token,
                    'companies_house_number': '  SC001122  '
                }
            )
            assert_in("companies_house_number", session)
            assert_equal(session.get("companies_house_number"), "SC001122")

    def test_should_wipe_companies_house_number_if_not_supplied(self):
        with self.client as c:
            res = c.post(
                self.url_for('main.submit_companies_house_number'),
                data={
                    'csrf_token': FakeCsrf.valid_token,
                    'companies_house_number': '',
                }
            )
            assert_equal(res.status_code, 302)
            assert_equal(res.location, self.url_for('main.company_name', _external=True))
            assert_false("companies_house_number" in session)

    def test_should_allow_valid_company_name(self):
        res = self.client.post(
            self.url_for('main.submit_company_name'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'company_name': 'My Company',
            }
        )
        assert_equal(res.status_code, 302)
        assert_equal(res.location, self.url_for('main.company_contact_details', _external=True))

    def test_should_strip_whitespace_surrounding_company_name_field(self):
        with self.client as c:
            c.post(
                self.url_for('main.submit_company_name'),
                data={
                    'csrf_token': FakeCsrf.valid_token,
                    'company_name': '  My Company  ',
                }
            )
            assert_in("company_name", session)
            assert_equal(session.get("company_name"), "My Company")

    def test_should_be_an_error_if_no_company_name(self):
        res = self.client.post(
            self.url_for('main.submit_company_name'),
            data=csrf_only_request,
        )
        assert_equal(res.status_code, 400)
        assert_in("You must provide a company name.", res.get_data(as_text=True))

    def test_should_be_an_error_if_company_name_too_long(self):
        twofiftysix = "a" * 256
        res = self.client.post(
            self.url_for('main.submit_company_name'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'company_name': twofiftysix
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("You must provide a company name under 256 characters.", res.get_data(as_text=True))

    def test_should_allow_valid_company_contact_details(self):
        res = self.client.post(
            self.url_for('main.submit_company_contact_details'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'contact_name': "Name",
                'email_address': "name@email.com",
                'phone_number': "999"
            }
        )
        assert_equal(res.status_code, 302)
        assert_equal(res.location, self.url_for('main.create_your_account', _external=True))

    def test_should_strip_whitespace_surrounding_contact_details_fields(self):
        contact_details = {
            'csrf_token': FakeCsrf.valid_token,
            'contact_name': "  Name  ",
            'email_address': "  name@email.com  ",
            'phone_number': "  999  "
        }

        with self.client as c:
            c.post(
                self.url_for('main.submit_company_contact_details'),
                data=contact_details
            )

            contact_details.pop('csrf_token')
            for key, value in contact_details.items():
                assert_in(key, session)
                assert_equal(session.get(key), value.strip())

    def test_should_not_allow_contact_details_without_name(self):
        res = self.client.post(
            self.url_for('main.submit_company_contact_details'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'email_address': "name@email.com",
                'phone_number': "999"
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("You must provide a contact name.", res.get_data(as_text=True))

    def test_should_not_allow_contact_details_with_too_long_name(self):
        twofiftysix = "a" * 256
        res = self.client.post(
            self.url_for('main.submit_company_contact_details'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'contact_name': twofiftysix,
                'email_address': "name@email.com",
                'phone_number': "999"
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("You must provide a contact name under 256 characters.", res.get_data(as_text=True))

    def test_should_not_allow_contact_details_without_email(self):
        res = self.client.post(
            self.url_for('main.submit_company_contact_details'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'contact_name': "Name",
                'phone_number': "999"
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("You must provide a email address.", res.get_data(as_text=True))

    def test_should_not_allow_contact_details_with_invalid_email(self):
        res = self.client.post(
            self.url_for('main.submit_company_contact_details'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'contact_name': "Name",
                'email_address': "notrightatall",
                'phone_number': "999"
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("You must provide a valid email address.", res.get_data(as_text=True))

    def test_should_not_allow_contact_details_without_phone_number(self):
        res = self.client.post(
            self.url_for('main.submit_company_contact_details'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'contact_name': "Name",
                'email_address': "name@email.com"
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("You must provide a phone number.", res.get_data(as_text=True))

    def test_should_not_allow_contact_details_with_invalid_phone_number(self):
        twentyone = "a" * 21
        res = self.client.post(
            self.url_for('main.submit_company_contact_details'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'contact_name': "Name",
                'email_address': "name@email.com",
                'phone_number': twentyone
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("You must provide a phone number under 20 characters.", res.get_data(as_text=True))

    def test_should_show_multiple_errors(self):
        res = self.client.post(
            self.url_for('main.submit_company_contact_details'),
            data=csrf_only_request,
        )
        assert_equal(res.status_code, 400)
        assert_in("You must provide a phone number.", res.get_data(as_text=True))
        assert_in("You must provide a email address.", res.get_data(as_text=True))
        assert_in("You must provide a contact name.", res.get_data(as_text=True))

    def test_should_populate_companies_house_from_session(self):
        with self.client.session_transaction() as sess:
            sess['companies_house_number'] = "999"
        res = self.client.get(self.url_for('main.companies_house_number'))
        assert res.status_code == 200
        assert '<inputtype="text"name="companies_house_number"id="input-companies_house_number"' \
            'class="text-box"value="999"' in self.strip_all_whitespace(res.get_data(as_text=True))

    def test_should_populate_company_name_from_session(self):
        with self.client.session_transaction() as sess:
            sess['company_name'] = "Name"
        res = self.client.get(self.url_for('main.company_name'))
        assert res.status_code == 200
        assert '<inputtype="text"name="company_name"id="input-company_name"class="text-box"value="Name"' \
            in self.strip_all_whitespace(res.get_data(as_text=True))

    def test_should_populate_contact_details_from_session(self):
        with self.client.session_transaction() as sess:
            sess['email_address'] = "email_address"
            sess['contact_name'] = "contact_name"
            sess['phone_number'] = "phone_number"
        res = self.client.get(self.url_for('main.company_contact_details'))
        assert res.status_code == 200
        stripped_page = self.strip_all_whitespace(res.get_data(as_text=True))
        assert '<inputtype="text"name="email_address"id="input-email_address"class="text-box"value="email_address"' \
            in stripped_page

        assert '<inputtype="text"name="contact_name"id="input-contact_name"class="text-box"value="contact_name"' \
            in stripped_page

        assert '<inputtype="text"name="phone_number"id="input-phone_number"class="text-box"value="phone_number"' \
            in stripped_page

    def test_should_be_an_error_to_be_submit_company_with_incomplete_session(self):
        res = self.client.post(self.url_for('main.submit_company_summary'), data=csrf_only_request)
        assert res.status_code == 400
        assert_in('You must answer all the questions', res.get_data(as_text=True))

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
            res = c.post(self.url_for('main.submit_company_summary'), data=csrf_only_request)
            assert_equal(res.status_code, 302)
            assert_equal(res.location, self.url_for('main.create_your_account_complete', _external=True))
            data_api_client.create_supplier.assert_called_once_with({
                "contacts": [{
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
            assert_equal(session['email_supplier_code'], 12345)
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
            self.url_for('main.submit_company_summary'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'email_address': 'valid@email.com'
            }
        )
        assert_equal(res.status_code, 302)
        assert_equal(res.location, self.url_for('main.create_your_account_complete', _external=True))
        data_api_client.create_supplier.assert_called_once_with({
            "contacts": [{
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
        res = self.client.post(self.url_for('main.submit_company_summary'), data=csrf_only_request)
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
        res = self.client.post(self.url_for('main.submit_company_summary'), data=csrf_only_request)
        assert_equal(res.status_code, 503)

    def test_should_require_an_email_address(self):
        with self.client.session_transaction() as sess:
            sess['email_company_name'] = "company_name"
            sess['email_supplier_code'] = 1234
        res = self.client.post(
            self.url_for('main.submit_create_your_account'),
            data=csrf_only_request,
        )
        assert_equal(res.status_code, 400)
        assert_in("You must provide a email address.", res.get_data(as_text=True))

    def test_should_not_allow_incorrect_email_address(self):
        with self.client.session_transaction() as sess:
            sess['email_company_name'] = "company_name"
            sess['email_supplier_code'] = 1234
        res = self.client.post(
            self.url_for('main.submit_create_your_account'),
            data={
                'csrf_token': FakeCsrf.valid_token,
                'email_address': "bademail"
            }
        )
        assert_equal(res.status_code, 400)
        assert_in("You must provide a valid email address.", res.get_data(as_text=True))

    @mock.patch("app.main.suppliers.data_api_client")
    @mock.patch("app.main.suppliers.send_email")
    def test_should_allow_correct_email_address(self, send_email, data_api_client):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_address'] = "email_address"
                sess['phone_number'] = "phone_number"
                sess['contact_name'] = "contact_name"
                sess['duns_number'] = "duns_number"
                sess['company_name'] = "company_name"
                sess['account_email_address'] = "valid@email.com"

            data_api_client.create_supplier.return_value = self.supplier()

            res = c.post(self.url_for('main.submit_company_summary'), data=csrf_only_request)

            send_email.assert_called_once_with(
                "valid@email.com",
                mock.ANY,
                "Create your Digital Marketplace account",
                self.app.config['RESET_PASSWORD_EMAIL_FROM'],
                "Digital Marketplace Admin",
                ["user-creation"]
            )

            assert_equal(res.status_code, 302)
            assert_equal(res.location, self.url_for('main.create_your_account_complete', _external=True))
            assert_equal(session['email_sent_to'], 'valid@email.com')

    @mock.patch("app.main.suppliers.send_email")
    @mock.patch("app.main.suppliers.generate_token")
    def test_should_be_an_error_if_incomplete_session_on_account_creation(self, generate_token, send_email):
        res = self.client.post(self.url_for('main.submit_company_summary'), data=csrf_only_request)

        assert_false(generate_token.called)
        assert_false(send_email.called)
        assert_equal(res.status_code, 400)

    @mock.patch('app.main.suppliers.data_api_client')
    @mock.patch('app.main.suppliers.send_email')
    def test_return_503_response_if_server_error_sending_email(self, send_email, data_api_client):
        with self.client.session_transaction() as sess:
            sess['email_address'] = "email_address"
            sess['phone_number'] = "phone_number"
            sess['contact_name'] = "contact_name"
            sess['duns_number'] = "duns_number"
            sess['company_name'] = "company_name"
            sess['account_email_address'] = "valid@email.com"

        send_email.side_effect = EmailError("Failed")
        data_api_client.create_supplier.return_value = self.supplier()

        res = self.client.post(self.url_for('main.submit_company_summary'), data=csrf_only_request)

        send_email.assert_called_once_with(
            "valid@email.com",
            mock.ANY,
            "Create your Digital Marketplace account",
            self.app.config['RESET_PASSWORD_EMAIL_FROM'],
            "Digital Marketplace Admin",
            ["user-creation"]
        )

        assert_equal(res.status_code, 503)

    def test_should_show_email_address_on_create_account_complete(self):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_sent_to'] = "my@email.com"
                sess['other_stuff'] = True

            res = c.get(self.url_for('main.create_your_account_complete'))

            assert_equal(res.status_code, 200)
            assert_in('An email has been sent to my@email.com', res.get_data(as_text=True))
            assert_false('other_stuff' in session)

    def test_should_show_email_address_even_when_refreshed(self):
        with self.client as c:
            with c.session_transaction() as sess:
                sess['email_sent_to'] = 'my-email@example.com'

            res = c.get(self.url_for('main.create_your_account_complete'))

            assert_equal(res.status_code, 200)
            assert_in('An email has been sent to my-email@example.com', res.get_data(as_text=True))

            res = c.get(self.url_for('main.create_your_account_complete'))

            assert_equal(res.status_code, 200)
            assert_in('An email has been sent to my-email@example.com', res.get_data(as_text=True))
