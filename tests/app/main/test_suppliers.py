import mock
from mock import Mock
from nose.tools import assert_equal, assert_true, assert_in, assert_false
from tests.app.helpers import BaseApplicationTest


def get_supplier(*args, **kwargs):
    return {"suppliers": {
        "id": 1234,
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


class TestSuppliersDashboard(BaseApplicationTest):
    @mock.patch("app.main.views.suppliers.data_api_client")
    def test_shows_supplier_info(self, data_api_client):
        data_api_client.get_supplier.side_effect = get_supplier
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

    @mock.patch("app.main.views.suppliers.data_api_client")
    def test_shows_edit_buttons(self, data_api_client):
        data_api_client.get_supplier.side_effect = get_supplier
        with self.app.test_client():
            self.login()

            res = self.client.get("/suppliers")
            assert_equal(res.status_code, 200)

            assert_true("/suppliers/edit" in res.get_data(as_text=True))
            assert_true("/suppliers/services" in res.get_data(as_text=True))


class TestSupplierDashboardLogin(BaseApplicationTest):
    @mock.patch("app.main.views.suppliers.data_api_client")
    def test_should_show_supplier_dashboard_logged_in(self, data_api_client):
        with self.app.test_client():
            data_api_client.authenticate_user = Mock(
                return_value=(self.user(
                    123, "email@email.com", 1234, "Supplier Name")))

            data_api_client.get_user = Mock(
                return_value=(self.user(
                    123, "email@email.com", 1234, "Supplier Name")))

            data_api_client.get_supplier = Mock(side_effect=get_supplier)

            self.client.post("/suppliers/login", data={
                "email_address": "valid@email.com",
                "password": "1234567890"
            })

            res = self.client.get("/suppliers")

            assert_equal(res.status_code, 200)

            assert_true(
                self.strip_all_whitespace("<h1>Supplier Name</h1>")
                in self.strip_all_whitespace(res.get_data(as_text=True))
            )
            assert_true(
                self.strip_all_whitespace("email@email.com")
                in self.strip_all_whitespace(res.get_data(as_text=True))
            )

    def test_should_redirect_to_login_if_not_logged_in(self):
        res = self.client.get("/suppliers")
        assert_equal(res.status_code, 302)
        assert_equal(res.location,
                     "http://localhost/suppliers/login"
                     "?next=%2Fsuppliers")


@mock.patch("app.main.suppliers.data_api_client")
class TestSupplierUpdate(BaseApplicationTest):

    def _login(self, data_api_client):

        data_api_client.authenticate_user.return_value = self.user(
            123, "email@email.com", 1234, "name"
        )

        data_api_client.get_user.return_value = self.user(
            123, "email@email.com", 1234, "name"
        )

        data_api_client.get_supplier.side_effect = get_supplier

        self.client.post("/suppliers/login", data={
            "email_address": "email@email.com",
            "password": "1234567890"
        })

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

    def test_update_all_supplier_fields(self, data_api_client):
        self._login(data_api_client)

        status, resp = self.post_supplier_edit()

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
        self._login(data_api_client)

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
        self._login(data_api_client)

        status, resp = self.post_supplier_edit(
            description="DESCR " * 49
        )

        assert_equal(status, 302)

        assert_true(data_api_client.update_supplier.called)
        assert_true(data_api_client.update_contact_information.called)

    def test_description_above_word_length(self, data_api_client):
        self._login(data_api_client)

        status, resp = self.post_supplier_edit(
            description="DESCR " * 51
        )

        assert_equal(status, 200)
        assert_in('must not be more than 50', resp)

        assert_false(data_api_client.update_supplier.called)
        assert_false(data_api_client.update_contact_information.called)

    def test_clients_above_limit(self, data_api_client):
        self._login(data_api_client)

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
