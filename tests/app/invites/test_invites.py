from StringIO import StringIO
import textwrap

import mock

from app.invites import send_supplier_invites, list_supplier_invite_candidates

from tests.app.helpers import BaseApplicationTest


class TestSupplierInvites(BaseApplicationTest):

    @mock.patch('app.invites.data_api_client')
    @mock.patch('app.invites.send_email')
    def test_send_supplier_invites(self, send_email, data_api_client):
        data = textwrap.dedent("""\
            Me,me@example.com,123,Example Supplier
            Someone Else,someone.else@example.com,456,Another Example Supplier
        """)
        with self.app.app_context():
            send_supplier_invites(StringIO(data))

            send_email.assert_has_calls([
                mock.call('me@example.com', mock.ANY, mock.ANY, mock.ANY, mock.ANY),
                mock.call('someone.else@example.com', mock.ANY, mock.ANY, mock.ANY, mock.ANY),
            ])
            data_api_client.record_supplier_invite.assert_has_calls([
                mock.call(supplier_code=123, email_address='me@example.com'),
                mock.call(supplier_code=456, email_address='someone.else@example.com'),
            ])

    @mock.patch('app.invites.data_api_client')
    @mock.patch('app.invites.send_email')
    def test_list_candidates(self, send_email, data_api_client):
        with self.app.app_context():
            candidates = [{
                'contact': {
                    'email': 'info@alpha.com.au',
                    'name': 'Kris Kringle',
                    'phone': '02 8394 0000',
                },
                'supplierCode': 11,
                'supplierName': 'Mu Digital Consulting Group',
                }, {
                'contact': {
                    'email': 'info@alpha.com.au',
                    'name': 'Kris Kringle',
                    'phone': '02 8394 0000',
                },
                'supplierCode': 6,
                'supplierName': 'Eta Digital Consulting Group',
            }]
            data_api_client.list_supplier_account_invite_candidates.return_value = {'results': candidates}

            pipe = StringIO()

            list_supplier_invite_candidates(pipe)

            csv_data = pipe.getvalue()
            for candidate in candidates:
                assert str(candidate['supplierCode']) in csv_data
                assert candidate['supplierName'] in csv_data
                contact = candidate['contact']
                assert contact['email'] in csv_data
                assert contact['name'] in csv_data

            # Should be able to handle this data without errors
            send_supplier_invites(pipe)
