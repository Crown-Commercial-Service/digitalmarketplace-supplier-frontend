import pytest

from app.main.helpers.validation import get_validator
from app.main import content_loader


def get_g12_declaration(**kwargs):
    declaration = {
        "10WorkingDays": True,
        "GAAR": False,
        "MI": True,
        "accurateInformation": True,
        "accuratelyDescribed": True,
        "bankrupt": False,
        "canProvideFromDayOne": True,
        "confidentialInformation": False,
        "conflictOfInterest": False,
        "conspiracy": False,
        "contactEmailContractNotice": "Test_Person-8@example.com",
        "contactNameContractNotice": "Test Person-8",
        "corruptionBribery": False,
        "distortedCompetition": False,
        "distortingCompetition": False,
        "dunsNumberCompanyRegistrationNumber": True,
        "dunsNumber": '123456789',
        "employersInsurance": (
            "Yes \u2013 your organisation has, or will have in place, "
            "employer\u2019s liability insurance of at least \u00a35 million and you will provide certification before "
            "the framework is awarded."
        ),
        "environmentalSocialLabourLaw": False,
        "environmentallyFriendly": True,
        "equalityAndDiversity": True,
        "fraudAndTheft": False,
        "fullAccountability": True,
        "graveProfessionalMisconduct": False,
        "helpBuyersComplyTechnologyCodesOfPractice": True,
        "influencedContractingAuthority": False,
        "informationChanges": True,
        "misleadingInformation": False,
        "mitigatingFactors3": (
            "The Modern Slavery Statement for 2019 is currently under review by OUR Senior Management Team and as "
            "such, has not yet been published. Should we be awarded, we, as an organisation, will ensure to be fully "
            "compliant with question 52b."
        ),
        "modernSlaveryReportingRequirements": False,
        "modernSlaveryStatement": (
            "https://www.digitalmarketplace.service.gov.uk/suppliers/assets/g-cloud-11"
            "/documents/586237/modern-slavery-statement-2019-05-13-1009.pdf"
        ),
        "modernSlaveryTurnover": True,
        "offerServicesYourselves": True,
        "organisedCrime": False,
        "primaryContact": "Test Person8B",
        "primaryContactEmail": "Test_Person8A@EXAMPLE.com",
        "proofOfClaims": True,
        "publishContracts": True,
        "readUnderstoodGuidance": True,
        "seriousMisrepresentation": False,
        "servicesDoNotInclude": True,
        "servicesHaveOrSupportCloudHostingCloudSoftware": "Yes",
        "servicesHaveOrSupportCloudSupport": "Yes",
        "significantOrPersistentDeficiencies": False,
        "status": "complete",
        "subcontracting": ["as a prime contractor, using third parties (subcontractors) to provide some services"],
        "supplierCompanyRegistrationNumber": "FC021012",
        "supplierDunsNumber": "611429481",
        "supplierOrganisationSize": "medium",
        "supplierRegisteredBuilding": "999 Buckingham Palace",
        "supplierRegisteredCountry": "country:GB",
        "supplierRegisteredName": "TEST COMPANY 8",
        "supplierRegisteredPostcode": "W1A 1AA",
        "supplierRegisteredTown": "LONDON NODNOL",
        "supplierTradingName": "TEST COMPANY 8 International Corp.,t/as TEST COMPANY8 UK",
        "supplierTradingStatus": "other",
        "taxEvasion": False,
        "termsAndConditions": True,
        "termsOfParticipation": True,
        "terrorism": False,
        "understandHowToAskQuestions": True,
        "understandTool": True,
        "unfairCompetition": True,
        "unspentTaxConvictions": False,
        "witheldSupportingDocuments": False
    }
    declaration.update(kwargs)
    return declaration


def test_dependent_questions_both_error_when_both_negative():
    content = content_loader.get_builder('g-cloud-12', 'declaration')

    g12_declaration = get_g12_declaration(
        servicesHaveOrSupportCloudHostingCloudSoftware=(
            "My organisation isn't submitting cloud hosting (lot 1) or cloud software (lot 2) services"
        ),
        servicesHaveOrSupportCloudSupport="My organisation isn't submitting cloud support (lot 3) services",
    )
    errors = get_validator({'slug': 'g-cloud-12'}, content, g12_declaration).errors()

    assert errors['servicesHaveOrSupportCloudHostingCloudSoftware'] == 'dependent_question_error'
    assert errors['servicesHaveOrSupportCloudSupport'] == 'dependent_question_error'


@pytest.mark.parametrize(
    'values',
    (
        {
            'servicesHaveOrSupportCloudHostingCloudSoftware': "Yes",
            'servicesHaveOrSupportCloudSupport': "My organisation isn't submitting cloud support (lot 3) services"
        },
        {
            'servicesHaveOrSupportCloudHostingCloudSoftware': (
                "My organisation isn't submitting cloud hosting (lot 1) or cloud software (lot 2) services"
            ),
            'servicesHaveOrSupportCloudSupport': "Yes"
        },
        {
            'servicesHaveOrSupportCloudHostingCloudSoftware': "Yes",
            'servicesHaveOrSupportCloudSupport': "Yes"
        },
    )
)
def test_dependent_questions_do_not_error_when_at_least_one_positive(values):
    content = content_loader.get_builder('g-cloud-12', 'declaration')

    g12_declaration = get_g12_declaration(**values)

    errors = get_validator({'slug': 'g-cloud-12'}, content, g12_declaration).errors()

    with pytest.raises(KeyError, match='servicesHaveOrSupportCloudHostingCloudSoftware'):
        errors['servicesHaveOrSupportCloudHostingCloudSoftware']
    with pytest.raises(KeyError, match='servicesHaveOrSupportCloudSupport'):
        errors['servicesHaveOrSupportCloudSupport']


@pytest.mark.parametrize(
    'values',
    (
        {
            'servicesHaveOrSupportCloudHostingCloudSoftware': None,
            'servicesHaveOrSupportCloudSupport': "My organisation isn't submitting cloud support (lot 3) services"
        },
        {
            'servicesHaveOrSupportCloudHostingCloudSoftware': None,
            'servicesHaveOrSupportCloudSupport': "Yes"
        },
        {
            'servicesHaveOrSupportCloudHostingCloudSoftware': (
                "My organisation isn't submitting cloud hosting (lot 1) or cloud software (lot 2) services"
            ),
            'servicesHaveOrSupportCloudSupport': None
        },
        {
            'servicesHaveOrSupportCloudHostingCloudSoftware': "Yes",
            'servicesHaveOrSupportCloudSupport': None
        },
        {
            'servicesHaveOrSupportCloudHostingCloudSoftware': None,
            'servicesHaveOrSupportCloudSupport': None
        },
    )
)
def test_dependent_questions_still_error_with_answer_required(values):
    content = content_loader.get_builder('g-cloud-12', 'declaration')

    g12_declaration = get_g12_declaration(**values)

    errors = get_validator({'slug': 'g-cloud-12'}, content, g12_declaration).errors()

    assert 'dependent_question_error' not in errors.values()
    assert 'answer_required' in errors.values()


def test_other_field_validation_still_works():

    content = content_loader.get_builder('g-cloud-12', 'declaration')

    g12_declaration = get_g12_declaration(
        servicesHaveOrSupportCloudHostingCloudSoftware=(
            "My organisation isn't submitting cloud hosting (lot 1) or cloud software (lot 2) services"
        ),
        servicesHaveOrSupportCloudSupport="My organisation isn't submitting cloud support (lot 3) services",
        servicesDoNotInclude=None,
    )
    errors = get_validator({'slug': 'g-cloud-12'}, content, g12_declaration).errors()

    assert errors['servicesDoNotInclude'] == 'answer_required'
