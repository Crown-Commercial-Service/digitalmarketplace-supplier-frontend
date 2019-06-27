from app.main.helpers.validation import SharedValidator
from app.main import content_loader
from .test_dos_declaration import FULL_DOS_SUBMISSION
import pytest


@pytest.fixture
def dos4_submission():
    dos4 = FULL_DOS_SUBMISSION.copy()
    dos4["mitigatingFactors3"] = ""
    dos4["modernSlaveryTurnover"] = True
    dos4["modernSlaveryReportingRequirements"] = True
    dos4["modernSlaveryStatement"] = "/path/to/document"
    dos4["dunsNumber"] = "123456789"
    dos4["conspiracy"] = False
    dos4["corruptionBribery"] = False
    dos4["helpBuyersComplyTechnologyCodesOfPractice"] = True
    dos4["outsideIR35"] = True
    dos4["employmentStatus"] = True
    return dos4


def test_word_limit_errors(dos4_submission):
    content = content_loader.get_builder('digital-outcomes-and-specialists-4', 'declaration')

    textbox_fields = [
        "mitigatingFactors",
        "mitigatingFactors2",
    ]

    for field in textbox_fields:
        dos4_submission[field] = "a " * 501
        validator = SharedValidator(content, dos4_submission)
        assert validator.errors() == {field: "under_word_limit"}

        dos4_submission[field] = "a " * 500
        validator = SharedValidator(content, dos4_submission)
        assert validator.errors() == {}
