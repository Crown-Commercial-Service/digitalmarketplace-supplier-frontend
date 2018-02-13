import pytest
from app.main.helpers.suppliers import get_country_name_from_country_code


class TestGetCountryNameFromCountryCode():
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
