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
    dos5['contact'] = "Blah"
    dos5['subcontracting30DayPayments'] = True
    dos5['subcontractingInvoicesPaid'] = True
    dos5['contactEmail'] = 'Blah@example.com'

    return dos5


@pytest.fixture
def content():
    return content_loader.get_builder('digital-outcomes-and-specialists-5', 'declaration')


def test_no_error_if_correct(content, submission):
    assert DOS5Validator(content, submission).errors() == {}


def test_invalid_email_addresses_cause_errors(content, submission):
    submission['contactEmail'] = 'not an email'
    submission['contactEmailContractNotice'] = "not an email"

    assert DOS5Validator(content, submission).errors() == {
        'contactEmail': 'invalid_format',
        'contactEmailContractNotice': 'invalid_format',
    }
