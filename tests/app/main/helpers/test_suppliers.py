from datetime import timedelta

import pytest
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import Length
from app.main.helpers.suppliers import get_country_name_from_country_code, supplier_company_details_are_complete, \
    is_g12_recovery_supplier, format_g12_recovery_time_remaining, get_g12_recovery_draft_ids

from dmtestutils.api_model_stubs import SupplierStub

from tests.app.helpers import BaseApplicationTest


class TestGetCountryNameFromCountryCode:
    @pytest.mark.parametrize(
        'code, name',
        (
            ('gb', 'United Kingdom'),
            ('country:GB', 'United Kingdom'),
            ('territory:UM-86', 'Jarvis Island'),
            (None, ''),
            ('notathing', ''),
        )
    )
    def test_returns_expected_name_for_different_codes(self, code, name):
        assert get_country_name_from_country_code(code) == name


class TestSupplierCompanyDetailsComplete:
    @pytest.mark.parametrize('supplier_data_from_api, expected_result',
                             (
                                 ({}, False),
                                 ({**SupplierStub().response(), 'dunsNumber': None}, False),
                                 ({**SupplierStub().response(), 'name': None}, False),
                                 ({**SupplierStub().response(), 'companiesHouseNumber': None}, False),
                                 ({**SupplierStub().response(), 'contactInformation': [{}]}, False),

                                 (SupplierStub().response(), True),
                                 ({**SupplierStub().response(), 'registrationCountry': 'gb'}, True),
                                 (SupplierStub(other_company_registration_number=12345).response(), True),
                             ))
    def test_returns_expected_value_for_input(self, supplier_data_from_api, expected_result):
        assert supplier_company_details_are_complete(supplier_data_from_api) is expected_result


class FormForTest(FlaskForm):
    field_one = StringField('Field one?', validators=[
        Length(max=5, message="Field one must be under 5 characters.")
    ])
    field_two = StringField('Field two?', validators=[
        Length(max=5, message="Field two must be under 5 characters.")
    ])
    field_three = StringField('Field three?', validators=[
        Length(max=5, message="Field three must be under 5 characters.")
    ])


class TestG12RecoverySupplier(BaseApplicationTest):
    @pytest.mark.parametrize(
        'g12_recovery_supplier_ids, expected_result',
        [
            (None, False),
            ('', False),
            (42, False),
            ('12:32', False),
            ([123456, 789012], False),
            ('123456', True),
            ('123456,789012', True),
            ('123456, 789012', True),
            ('123456,\n789012', True),
        ]
    )
    def test_returns_expected_value_for_input(self, g12_recovery_supplier_ids, expected_result):
        with self.app.app_context():
            self.app.config['DM_G12_RECOVERY_SUPPLIER_IDS'] = g12_recovery_supplier_ids
            assert is_g12_recovery_supplier('123456') is expected_result


class TestG12RecoveryDrafts(BaseApplicationTest):
    @pytest.mark.parametrize(
        'draft_ids_config, expected_result',
        [
            (None, set()),
            ('', set()),
            (42, set()),
            ('12:32', set()),
            ([123456, 789012], set()),
            ('123456', {123456}),
            ('123456,789012', {123456, 789012}),
            ('123456, 789012', {123456, 789012}),
            ('123456,\n789012', {123456, 789012}),
        ]
    )
    def test_returns_expected_value_for_input(self, draft_ids_config, expected_result):
        with self.app.app_context():
            self.app.config['DM_G12_RECOVERY_DRAFT_IDS'] = draft_ids_config
            assert get_g12_recovery_draft_ids() == expected_result


class TestG12TimeRemainingFormatting:
    @pytest.mark.parametrize(
        'time_to_deadline, expected_result', [
            (timedelta(days=10, hours=10), '10 days'),
            (timedelta(days=1, hours=10), '1 day'),
            (timedelta(hours=10, minutes=10), '10 hours'),
            (timedelta(hours=1, minutes=10), '1 hour'),
            (timedelta(minutes=10, seconds=10), '10 minutes'),
            (timedelta(minutes=1, seconds=10), '1 minute'),
            (timedelta(seconds=10), '10 seconds'),
            (timedelta(seconds=1), '1 second'),
            (timedelta(days=-1), '0 seconds'),
            (timedelta(days=-1, hours=10), '0 seconds'),
            (timedelta(hours=-1, minutes=10), '0 seconds'),
        ]
    )
    def test_returns_expected_value_for_input(self, time_to_deadline, expected_result):
        assert format_g12_recovery_time_remaining(time_to_deadline) == expected_result
