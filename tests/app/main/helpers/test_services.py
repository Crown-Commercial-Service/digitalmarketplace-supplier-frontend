import mock
import pytest

from dmtestutils.api_model_stubs import SupplierFrameworkStub

from app.main.helpers.services import copy_service_from_previous_framework


class CustomAbortException(Exception):
    """
    Custom exception used in tests to mimick `aborts` behaviour of halting code execution. Catching this specific
    exception in the tests allows us to know an exception is being thrown for the expected reason.
    """
    pass


class TestCopyServiceFromPreviousFramework():
    def setup_method(self):
        self.abort_patch = mock.patch('app.main.helpers.services.abort')
        self.abort = self.abort_patch.start()
        self.abort.side_effect = CustomAbortException()

        self.get_supplier_framework_info_patch = mock.patch('app.main.helpers.services.get_supplier_framework_info')
        self.get_supplier_framework_info = self.get_supplier_framework_info_patch.start()
        self.get_supplier_framework_info.return_value = SupplierFrameworkStub(
            framework_slug='digital-outcomes-and-specialists-3'
        ).single_result_response()

        self.api_client_mock = mock.Mock()
        self.content_loader_mock = mock.Mock()
        self.content_loader_mock.get_metadata.side_effect = [
            ['list', 'of', 'questions', 'to', 'exclude'],
            ['list', 'of', 'questions', 'to', 'copy'],
            'dos-cloud-IX'
        ]

    def previous_service(self, **kwargs):
        service_data = {
            'id': 4444244,
            'lotSlug': 'digital-sausages',
            'frameworkSlug': 'dos-cloud-IX',
            'copiedToFollowingFramework': False,
            'supplierId': 1234,
        }
        service_data.update(kwargs)
        return {'services': service_data}

    def assert_404_and_no_copy(self, assertion_error=None):
        assert self.abort.call_args_list == [mock.call(404)], assertion_error
        assert self.api_client_mock.copy_draft_service_from_existing_service.call_args_list == []

    @mock.patch('app.main.helpers.services.current_user')
    def test_correctly_calls_api_client_for_excluded_questions(self, current_user):
        current_user.email_address = 'sausage@pink.net'
        current_user.supplier_id = 1234

        self.api_client_mock.get_service.return_value = self.previous_service()

        copy_service_from_previous_framework(
            self.api_client_mock, self.content_loader_mock, 'dos-cloud-X', 'digital-sausages', 4444244
        )

        assert self.api_client_mock.copy_draft_service_from_existing_service.call_args_list == [
            mock.call(
                4444244,
                "sausage@pink.net",
                {
                    'targetFramework': 'dos-cloud-X',
                    'status': 'not-submitted',
                    'questionsToExclude': ['list', 'of', 'questions', 'to', 'exclude']
                },
            )
        ]

    @mock.patch('app.main.helpers.services.current_user')
    def test_correctly_calls_api_client_for_copied_questions(self, current_user):
        self.content_loader_mock.get_metadata.side_effect = [
            None,  # Backwards compatibility for frameworks without excluded questions list
            ['list', 'of', 'questions', 'to', 'copy'],
            'dos-cloud-IX'
        ]
        current_user.email_address = 'sausage@pink.net'
        current_user.supplier_id = 1234

        self.api_client_mock.get_service.return_value = self.previous_service()

        copy_service_from_previous_framework(
            self.api_client_mock, self.content_loader_mock, 'dos-cloud-X', 'digital-sausages', 4444244
        )

        assert self.api_client_mock.copy_draft_service_from_existing_service.call_args_list == [
            mock.call(
                4444244,
                "sausage@pink.net",
                {
                    'targetFramework': 'dos-cloud-X',
                    'status': 'not-submitted',
                    'questionsToCopy': ['list', 'of', 'questions', 'to', 'copy']
                },
            )
        ]

    def test_404s_if_no_supplier_framework_info(self):
        self.get_supplier_framework_info.return_value = None

        with pytest.raises(CustomAbortException):
            copy_service_from_previous_framework(
                self.api_client_mock, self.content_loader_mock, 'dos-cloud-X', 'digital-sausages', 4444244
            )

        self.assert_404_and_no_copy(assertion_error='Suppliers must have registered interest in a framework')

    @pytest.mark.parametrize(
        ('reason', 'data'),
        (
            ('Target lot and source service lot should match', {'lotSlug': "You'll like it..."}),
            ('Source service should be on source framework', {'frameworkSlug': 'Sausage-Cloud-54'}),
            ('Source service should not have already been copied', {'copiedToFollowingFramework': True})
        )
    )
    def test_404s_for_various_data_mismatches(self, reason, data):
        self.api_client_mock.get_service.return_value = self.previous_service(**data)
        with pytest.raises(CustomAbortException):
            copy_service_from_previous_framework(
                self.api_client_mock, self.content_loader_mock, 'dos-cloud-X', 'digital-sausages', 4444244
            )

        self.assert_404_and_no_copy(assertion_error=reason)

    @mock.patch('app.main.helpers.services.is_service_associated_with_supplier')
    def test_404s_if_source_service_is_not_associated_with_supplier(self, is_service_associated_with_supplier):
        is_service_associated_with_supplier.return_value = False
        self.api_client_mock.get_service.return_value = self.previous_service()

        with pytest.raises(CustomAbortException):
            copy_service_from_previous_framework(
                self.api_client_mock, self.content_loader_mock, 'dos-cloud-X', 'digital-sausages', 4444244
            )

        self.assert_404_and_no_copy(assertion_error='Service being copied must belong to the current users supplier')
