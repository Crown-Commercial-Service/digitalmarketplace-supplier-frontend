import pytest

from app.main.helpers.validation import get_validator, G8Validator
from app.main import content_loader


FULL_G8_SUBMISSION = {
    "termsAndConditions": False,
    "understandTool": True,
    "distortingCompetition": False,
    "skillsAndResources": True,
    "significantOrPersistentDeficiencies": False,
    "cyberEssentials": False,
    "companyRegistrationNumber": "N/A",
    "dunsNumber": "123456789",
    "registeredVATNumber": "N/A",
    "distortedCompetition": False,
    "conspiracyCorruptionBribery": True,
    "contactNameContractNotice": "Test G8 Supplier",
    "contactEmailContractNotice": "contact@email.com",
    "organisationSize": "micro",
    "graveProfessionalMisconduct": False,
    "GAAR": False,
    "canProvideCloudServices": True,
    "bankrupt": False,
    "confidentialInformation": False,
    "seriousMisrepresentation": False,
    "licenceOrMemberRequiredDetails": "I have a licence",
    "understandHowToAskQuestions": True,
    "primaryContactEmail": "primary@email.com",
    "tradingStatusOther": "Sole trader",
    "mitigatingFactors": "It wasn't me",
    "taxEvasion": False,
    "primaryContact": "The boss",
    "subcontracting": [
        "as a prime contractor, using third parties (subcontractors) to provide all services",
        "as part of a consortium or special purpose vehicle, using members only to provide all services"
    ],
    "tradingStatus": "other (please specify)",
    "terrorism": True,
    "conflictOfInterest": True,
    "proofOfClaims": False,
    "status": "complete",
    "witheldSupportingDocuments": False,
    "registeredAddressBuilding": "123 High Street",
    "registeredAddressTown": "Abergavenny",
    "registeredAddressPostcode": "AB1 2CD",
    "currentRegisteredCountry": "Wales",
    "misleadingInformation": True,
    "equalityAndDiversity": True,
    "nameOfOrganisation": "Test G8 supplier",
    "fraudAndTheft": False,
    "firstRegistered": "2005",
    "employersInsurance": "No",
    "unspentTaxConvictions": False,
    "establishedInTheUK": False,
    "servicesHaveOrSupport": False,
    "appropriateTradeRegisters": True,
    "appropriateTradeRegistersNumber": "12-34-ABC",
    "readUnderstoodGuidance": True,
    "environmentalSocialLabourLaw": False,
    "termsOfParticipation": True,
    "accuratelyDescribed": False,
    "licenceOrMemberRequired": "licensed",
    "influencedContractingAuthority": False,
    "organisedCrime": True,
    "MI": True,
    "cyberEssentialsPlus": True,
    "tradingNames": "Test G8 supplier"
}


@pytest.fixture
def submission():
    return FULL_G8_SUBMISSION.copy()


@pytest.fixture
def content():
    return content_loader.get_builder('g-cloud-8', 'declaration')


def test_duns_number_validation(content, submission):
    test_cases = [
        ('123456789', {}),
        ('12345678', {'dunsNumber': 'invalid_format'}),
        ('1234567890', {'dunsNumber': 'invalid_format'}),
        ('8-NO-DIG', {'dunsNumber': 'invalid_format'}),
        ('9-NON-DIG', {'dunsNumber': 'invalid_format'}),
        ('10-NON-DIG', {'dunsNumber': 'invalid_format'}),
    ]

    for val, errors in test_cases:
        submission['dunsNumber'] = val
        validator = G8Validator(content, submission)
        assert validator.errors() == errors


def test_get_validator():
    validator = get_validator({"slug": "g-cloud-8"}, None, None)
    assert isinstance(validator, G8Validator)
