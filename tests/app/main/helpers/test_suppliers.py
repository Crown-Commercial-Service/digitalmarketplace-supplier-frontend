import pytest
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import Length
from app.main.helpers.suppliers import get_country_name_from_country_code, parse_form_errors_for_validation_masthead, \
    supplier_company_details_are_complete
from ...helpers import BaseApplicationTest

from dmutils.api_stubs import supplier


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
                                 ({**supplier()['suppliers'], 'dunsNumber': None}, False),
                                 ({**supplier()['suppliers'], 'vatNumber': None}, False),
                                 ({**supplier()['suppliers'], 'companiesHouseNumber': None}, False),
                                 ({**supplier()['suppliers'], 'contactInformation': [{}]}, False),

                                 (supplier()['suppliers'], True),
                                 ({**supplier()['suppliers'], 'registrationCountry': 'gb'}, True),
                                 (supplier(other_company_registration_number=12345)['suppliers'], True),
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


class TestParseFormErrorsForValidationMasthead(BaseApplicationTest):
    def test_returns_formatted_list_of_errors_for_single_form(self):
        with self.app.test_request_context():
            form = FormForTest(field_one='Too long', field_two='Too long', field_three='Good')
            form.validate()

            masthead_errors = parse_form_errors_for_validation_masthead(form)
            assert masthead_errors == [
                {'question': 'Field one?', 'input_name': 'field_one'},
                {'question': 'Field two?', 'input_name': 'field_two'},
            ]

    def test_returns_formatted_list_of_errors_for_list_of_forms(self):
        with self.app.test_request_context():
            form_one = FormForTest(field_one='Good', field_two='Too long', field_three='Too long')
            form_two = FormForTest(field_one='Still too long', field_two='Yes!', field_three='Also too long')

            form_one.validate()
            form_two.validate()
            masthead_errors = parse_form_errors_for_validation_masthead([form_one, form_two])

            assert masthead_errors == [
                {'question': 'Field two?', 'input_name': 'field_two'},
                {'question': 'Field three?', 'input_name': 'field_three'},
                {'question': 'Field one?', 'input_name': 'field_one'},
                {'question': 'Field three?', 'input_name': 'field_three'},
            ]

    def test_returns_falsey_if_no_errors(self):
        with self.app.test_request_context():
            form = FormForTest(field_one='Good', field_two='Good', field_three='Good')
            form.validate()

            masthead_errors = parse_form_errors_for_validation_masthead(form)

            assert not masthead_errors
