import pytest

from app.main.helpers.validation import DOSValidator, get_validator
from app.main import content_loader


FULL_DOS_SUBMISSION = {
    "tradingNames": "Blah",
    "witheldSupportingDocuments": False,
    "unspentTaxConvictions": False,
    "fraudAndTheft": True,
    "currentRegisteredCountry": "Finland",
    "environmentalSocialLabourLaw": False,
    "registeredAddress": "Blah",
    "canProvideFromDayOne": True,
    "technologyCodesOfPractice": True,
    "skillsAndResources": True,
    "establishedInTheUK": False,
    "firstRegistered": "Blah",
    "mitigatingFactors": "",
    "influencedContractingAuthority": False,
    "proofOfClaims": True,
    "cyberEssentialsPlus": True,
    "customerSatisfactionProcess": True,
    "fullAccountability": True,
    "skillsAndCapabilityAssessment": True,
    "subcontracting": "yourself without the use of third parties (subcontractors)",
    "licenceOrMemberRequired": "none of the above",
    "mitigatingFactors2": "",
    "accuratelyDescribed": True,
    "tradingStatus": "other (please specify)",
    "confidentialInformation": False,
    "registeredVATNumber": "Blah",
    "significantOrPersistentDeficiencies": False,
    "terrorism": True,
    "evidence": True,
    "bankrupt": False,
    "termsOfParticipation": True,
    "MI": True,
    "accurateInformation": True,
    "graveProfessionalMisconduct": False,
    "appropriateTradeRegisters": True,
    "licenceOrMemberRequiredDetails": "",
    "offerServicesYourselves": True,
    "conflictOfInterest": False,
    "understandTool": True,
    "companyRegistrationNumber": "Blah",
    "taxEvasion": False,
    "transparentContracting": True,
    "misleadingInformation": False,
    "informationChanges": True,
    "consistentDelivery": True,
    "organisedCrime": True,
    "requisiteAuthority": True,
    "ongoingEngagement": True,
    "understandHowToAskQuestions": True,
    "seriousMisrepresentation": False,
    "primaryContact": "Blah",
    "nameOfOrganisation": "Bla",
    "continuousProfessionalDevelopment": True,
    "environmentallyFriendly": True,
    "primaryContactEmail": "Blah@example.com",
    "distortingCompetition": False,
    "10WorkingDays": True,
    "termsAndConditions": True,
    "equalityAndDiversity": True,
    "serviceStandard": True,
    "distortedCompetition": False,
    "readUnderstoodGuidance": True,
    "tradingStatusOther": "blah",
    "cyberEssentials": True,
    "conspiracyCorruptionBribery": True,
    "publishContracts": True,
    "unfairCompetition": True,
    "organisationSize": "micro",
    "safeguardPersonalData": True,
    "appropriateTradeRegistersNumber": "Blah",
    "GAAR": False,
    "contactEmailContractNotice": "Blah@example.com",
    "status": "complete",
    "contactNameContractNotice": "Blah",
    "employersInsurance": "Yes \u2013 your organisation has, or will have in place, employer\u2019s liability insurance of at least \u00a35 million and you will provide certification prior to framework award.",  # noqa
    "civilServiceValues": True,
    "safeguardOfficialInformation": True
}


@pytest.fixture
def content():
    return content_loader.get_builder('digital-outcomes-and-specialists', 'declaration')


@pytest.fixture
def submission():
    return FULL_DOS_SUBMISSION.copy()


def test_error_if_required_field_is_missing(content, submission):
    del submission['termsAndConditions']

    validator = DOSValidator(content, submission)

    assert validator.errors() == {"termsAndConditions": "answer_required"}


def test_error_if_required_text_field_is_empty(content, submission):
    submission['primaryContact'] = ''

    validator = DOSValidator(content, submission)

    assert validator.errors() == {"primaryContact": "answer_required"}


def test_no_error_if_optional_field_is_missing(content, submission):
    del submission['mitigatingFactors2']

    validator = DOSValidator(content, submission)

    assert validator.errors() == {}


def test_error_if_mitigating_factors_not_provided_when_required(content, submission):
    del submission['mitigatingFactors']
    dependent_fields = [
        'misleadingInformation', 'confidentialInformation', 'influencedContractingAuthority',
        'witheldSupportingDocuments', 'seriousMisrepresentation', 'significantOrPersistentDeficiencies',
        'distortedCompetition', 'conflictOfInterest', 'distortedCompetition', 'graveProfessionalMisconduct',
        'bankrupt', 'environmentalSocialLabourLaw', 'taxEvasion'
    ]
    for field in dependent_fields:
        for other in dependent_fields:
            submission[other] = False
        submission[field] = True

        validator = DOSValidator(content, submission)
        assert validator.errors() == {"mitigatingFactors": "answer_required"}


def test_error_if_mitigating_factors2_not_provided_when_required(content, submission):
    del submission['mitigatingFactors2']
    dependent_fields = [
        "unspentTaxConvictions", "GAAR"
    ]
    for field in dependent_fields:
        for other in dependent_fields:
            submission[other] = False
        submission[field] = True

        validator = DOSValidator(content, submission)
        assert validator.errors() == {"mitigatingFactors2": "answer_required"}


def test_trading_status_details_error_depends_on_trading_status(content, submission):
    del submission['tradingStatusOther']

    submission['tradingStatus'] = "something"
    validator = DOSValidator(content, submission)
    assert validator.errors() == {}

    submission['tradingStatus'] = "other (please specify)"
    validator = DOSValidator(content, submission)
    assert validator.errors() == {"tradingStatusOther": "answer_required"}


def test_trade_registers_error_depends_on_established_in_uk(content, submission):
    del submission['appropriateTradeRegisters']

    submission['establishedInTheUK'] = True
    validator = DOSValidator(content, submission)
    assert validator.errors() == {}

    submission['establishedInTheUK'] = False
    validator = DOSValidator(content, submission)
    assert validator.errors() == {"appropriateTradeRegisters": "answer_required"}


def test_trade_register_number_error_depends_on_trade_registers(content, submission):
    del submission['appropriateTradeRegistersNumber']

    submission['establishedInTheUK'] = True
    del submission['appropriateTradeRegisters']
    validator = DOSValidator(content, submission)
    assert validator.errors() == {}

    submission['establishedInTheUK'] = False
    submission['appropriateTradeRegisters'] = False
    validator = DOSValidator(content, submission)
    assert validator.errors() == {}

    submission['establishedInTheUK'] = False
    submission['appropriateTradeRegisters'] = True
    validator = DOSValidator(content, submission)
    assert validator.errors() == {"appropriateTradeRegistersNumber": "answer_required"}


def test_licence_or_member_error_depends_on_established_in_uk(content, submission):
    del submission['licenceOrMemberRequired']

    submission['establishedInTheUK'] = True
    validator = DOSValidator(content, submission)
    assert validator.errors() == {}

    submission['establishedInTheUK'] = False
    validator = DOSValidator(content, submission)
    assert validator.errors() == {"licenceOrMemberRequired": "answer_required"}


def test_licence_or_member_details_error_depends_on_licence_or_member(content, submission):
    del submission['licenceOrMemberRequiredDetails']

    submission['establishedInTheUK'] = True
    del submission['licenceOrMemberRequired']
    validator = DOSValidator(content, submission)
    assert validator.errors() == {}

    submission['establishedInTheUK'] = False
    submission['licenceOrMemberRequired'] = 'none of the above'
    validator = DOSValidator(content, submission)
    assert validator.errors() == {}

    submission['establishedInTheUK'] = False
    submission['licenceOrMemberRequired'] = 'licensed'
    validator = DOSValidator(content, submission)
    assert validator.errors() == {"licenceOrMemberRequiredDetails": "answer_required"}


def test_invalid_email_addresses_cause_errors(content, submission):
    submission['primaryContactEmail'] = '@invalid.com'
    submission['contactEmailContractNotice'] = 'some.user.missed.their.at.com'

    validator = DOSValidator(content, submission)
    assert validator.errors() == {
        'primaryContactEmail': 'invalid_format',
        'contactEmailContractNotice': 'invalid_format'
    }


def test_character_limit_errors(content, submission):
    text_fields = [
        "appropriateTradeRegistersNumber",
        "companyRegistrationNumber",
        "contactNameContractNotice",
        "currentRegisteredCountry",
        "firstRegistered",
        "licenceOrMemberRequiredDetails",
        "mitigatingFactors",
        "mitigatingFactors2",
        "nameOfOrganisation",
        "primaryContact",
        "registeredAddress",
        "registeredVATNumber",
        "tradingNames",
        "tradingStatusOther",
    ]

    for field in text_fields:
        submission[field] = "a" * 5001
        validator = DOSValidator(content, submission)
        assert validator.errors() == {field: "under_character_limit"}

        submission[field] = "a" * 5000
        validator = DOSValidator(content, submission)
        assert validator.errors() == {}


def test_get_validator():
    validator = get_validator({"slug": "digital-outcomes-and-specialists"}, None, None)
    assert isinstance(validator, DOSValidator)
