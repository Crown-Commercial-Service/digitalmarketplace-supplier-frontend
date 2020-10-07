from app.main.helpers.validation import DOS5Validator
from app.main import content_loader
from .test_dos_declaration import FULL_DOS_SUBMISSION
import pytest


@pytest.fixture
def submission():
    dos5 = FULL_DOS_SUBMISSION.copy()

    dos5["mitigatingFactors3"] = ""
    dos5["modernSlaveryTurnover"] = True
    dos5["modernSlaveryReportingRequirements"] = True
    dos5["modernSlaveryStatement"] = "/path/to/document"
    dos5["dunsNumber"] = "123456789"
    dos5["conspiracy"] = False
    dos5["corruptionBribery"] = False
    dos5["helpBuyersComplyTechnologyCodesOfPractice"] = True
    dos5["outsideIR35"] = True
    dos5["employmentStatus"] = True
    dos5["incorrectTaxReturns"] = False
    dos5["safeguardingOfficialInformation"] = True
    dos5["employersLiabilityInsurance"] = True
    dos5['subcontracting'] = 'as a prime contractor, using third parties (subcontractors) to provide some services'
    dos5['subcontracting30DayPayments'] = True
    dos5['subcontractingInvoicesPaid'] = "100"

    return dos5


@pytest.fixture
def content():
    return content_loader.get_builder('digital-outcomes-and-specialists-5', 'declaration')


def test_no_error_if_correct(content, submission):
    assert DOS5Validator(content, submission).errors() == {}


@pytest.mark.parametrize("number_field_value", [
    "0",
    "100",
    "3.14159",
    "50%",
    40,
])
def test_subcontracting_payment_percent_is_valid(content, submission, number_field_value):
    submission['subcontractingInvoicesPaid'] = number_field_value
    assert DOS5Validator(content, submission).errors() == {}


@pytest.mark.parametrize("number_field_value", [
    "-42",
    "1000",
    "not a number",
])
def test_subcontracting_payment_percent_is_invalid(content, submission, number_field_value):
    submission['subcontractingInvoicesPaid'] = number_field_value
    assert DOS5Validator(content, submission).errors() == {'subcontractingInvoicesPaid': 'not_a_number'}


def test_subcontracting_payment_fails_when_absent_and_required(content, submission):
    submission['subcontracting30DayPayments'] = None
    submission['subcontractingInvoicesPaid'] = None
    assert DOS5Validator(content, submission).errors() == {
        'subcontractingInvoicesPaid': 'answer_required',
        'subcontracting30DayPayments': 'answer_required'
    }


def test_subcontracting_payment_passes_when_absent_and_not_required(content, submission):
    submission['subcontracting'] = 'yourself without the use of third parties (subcontractors)'
    submission['subcontracting30DayPayments'] = None
    submission['subcontractingInvoicesPaid'] = None
    assert DOS5Validator(content, submission).errors() == {}
