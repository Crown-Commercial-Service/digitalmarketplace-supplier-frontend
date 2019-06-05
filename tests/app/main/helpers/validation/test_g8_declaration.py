import pytest

from app.main.helpers.validation import get_validator, SharedValidator
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
        validator = SharedValidator(content, submission)
        assert validator.errors() == errors


MODERN_FRAMEWORK_SLUGS = [
    'g-cloud-8',
    'g-cloud-9',
    'g-cloud-10',
    'g-cloud-11',
    'digital-outcomes-and-specialists-2',
    'digital-outcomes-and-specialists-3',
    'digital-outcomes-and-specialists-4',
]


@pytest.mark.parametrize('framework_slug', MODERN_FRAMEWORK_SLUGS)
def test_get_validator_for_modern_frameworks(framework_slug):
    validator = get_validator({"slug": framework_slug}, None, None)
    assert isinstance(validator, SharedValidator)
    assert validator.character_limit == 5000


@pytest.mark.parametrize('licence_type', ['licensed', 'a member of a relevant organisation'])
@pytest.mark.parametrize('framework_slug', MODERN_FRAMEWORK_SLUGS)
def test_validator_includes_dependent_fields(framework_slug, licence_type):
    content = content_loader.get_builder(framework_slug, 'declaration')
    submission = {
        "tradingStatus": "other (please specify)",
        "establishedInTheUK": False,
        "appropriateTradeRegisters": True,
        "licenceOrMemberRequired": licence_type
    }

    validator = get_validator({"slug": framework_slug}, content, submission)
    required_fields = validator.get_required_fields()

    for expected_dependent_field in [
        "tradingStatusOther",
        "appropriateTradeRegisters",
        "appropriateTradeRegistersNumber",
        "licenceOrMemberRequiredDetails"
    ]:
        assert expected_dependent_field in required_fields


@pytest.mark.parametrize(
    'discretionary_field, expected_required_field',
    [
        ('misleadingInformation', 'mitigatingFactors'),
        ('confidentialInformation', 'mitigatingFactors'),
        ('influencedContractingAuthority', 'mitigatingFactors'),
        ('witheldSupportingDocuments', 'mitigatingFactors'),
        ('seriousMisrepresentation', 'mitigatingFactors'),
        ('significantOrPersistentDeficiencies', 'mitigatingFactors'),
        ('distortedCompetition', 'mitigatingFactors'),
        ('conflictOfInterest', 'mitigatingFactors'),
        ('distortingCompetition', 'mitigatingFactors'),
        ('graveProfessionalMisconduct', 'mitigatingFactors'),
        ('bankrupt', 'mitigatingFactors'),
        ('environmentalSocialLabourLaw', 'mitigatingFactors'),
        ('taxEvasion', 'mitigatingFactors'),
        ('unspentTaxConvictions', 'mitigatingFactors2'),
        ('GAAR', 'mitigatingFactors2'),
        ('modernSlaveryTurnover', 'modernSlaveryStatement'),
        ('modernSlaveryTurnover', 'modernSlaveryReportingRequirements'),
    ]
)
def test_validator_adds_dependency_for_discretionary_fields(discretionary_field, expected_required_field):
    g11_content = content_loader.get_builder('g-cloud-11', 'declaration')
    g11_submission = {discretionary_field: True}

    validator = get_validator({"slug": 'g-cloud-11'}, g11_content, g11_submission)

    required_fields = validator.get_required_fields()
    assert expected_required_field in required_fields


@pytest.mark.parametrize('framework_slug', ['g-cloud-11', 'digital-outcomes-and-specialists-4'])
def test_validator_handles_multiquestion_fields(framework_slug):
    # Currently only DOS4 and G11 have multiquestion declaration questions (for modernSlavery)
    g11_content = content_loader.get_builder(framework_slug, 'declaration')

    g11_submission = {
        "modernSlaveryTurnover": True,
        "modernSlaveryReportingRequirements": False,
    }

    validator = get_validator({"slug": framework_slug}, g11_content, g11_submission)
    required_fields = validator.get_required_fields()

    assert 'mitigatingFactors3' in required_fields
    assert 'modernSlaveryStatement' not in required_fields
