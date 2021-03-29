from functools import reduce
from operator import add
import re
from typing import Any, List, Dict, Set, Tuple, Optional

from werkzeug.datastructures import ImmutableOrderedMultiDict

EMAIL_REGEX = r'^[^@^\s]+@[^@^\.^\s]+(\.[^@^\.^\s]+)+$'


def get_validator(framework, content, answers):
    """
    Retrieves a validator by slug contained in the framework dictionary.
    """
    if framework is None:
        raise ValueError("a framework dictionary must be provided")
    if framework is not None:
        validator_cls = VALIDATORS.get(framework['slug'], SharedValidator)
        return validator_cls(content, answers)


class DeclarationValidator(object):
    email_validation_fields: Set[str] = set()
    number_string_fields: List[Tuple[str, int]] = []
    character_limit: Optional[int] = None
    word_limit: Optional[int] = None
    optional_fields: Set[str] = set()

    def __init__(self, content, answers):
        self.content = content
        self.answers = answers

    def get_error_messages_for_page(self, section) -> ImmutableOrderedMultiDict:
        all_errors = self.get_error_messages()
        page_ids = section.get_question_ids()
        return ImmutableOrderedMultiDict(filter(lambda err: err[0] in page_ids, all_errors))

    def get_error_messages(self) -> List[Tuple[str, dict]]:
        raw_errors_map = self.errors()
        errors_map = list()
        for question_id in self.all_fields():
            if question_id in raw_errors_map:
                question_number = self.content.get_question(question_id).get('number')
                validation_message = self.get_error_message(question_id, raw_errors_map[question_id])
                errors_map.append((question_id, {
                    'input_name': question_id,
                    'href': self.content.get_question(question_id).get('href') or None,
                    'question': "Question {}".format(question_number)
                    if question_number else self.content.get_question(question_id).get('question'),
                    'message': validation_message,
                }))

        return errors_map

    def get_error_message(self, question_id: str, message_key: str) -> str:
        for validation in self.content.get_question(question_id).get('validations', []):
            if validation['name'] == message_key:
                return validation['message']  # type: ignore
        default_messages = {
            'answer_required': 'You need to answer this question.',
            'under_character_limit': 'Your answer must be no more than {} characters.'.format(self.character_limit),
            'invalid_format': 'You must enter a valid email address.',
        }
        return default_messages.get(
            message_key, 'There was a problem with the answer to this question')

    def all_fields(self) -> List[str]:
        return reduce(add, (section.get_question_ids() for section in self.content))

    def fields_with_values(self) -> Set[str]:
        return set(key for key, value in self.answers.items()
                   if value is not None and (not isinstance(value, str) or len(value) > 0))

    def errors(self) -> Dict[str, str]:
        errors_map = {}
        errors_map.update(self.character_limit_errors())
        errors_map.update(self.word_limit_errors())
        errors_map.update(self.formatting_errors(self.answers))
        errors_map.update(self.answer_required_errors())
        return errors_map

    def answer_required_errors(self) -> Dict[str, str]:
        req_fields = self.get_required_fields()
        filled_fields = self.fields_with_values()
        errors_map = {}

        for field in req_fields - filled_fields:
            errors_map[field] = 'answer_required'

        return errors_map

    def character_limit_errors(self) -> Dict[str, str]:
        errors_map = {}
        for question_id in self.all_fields():
            if self.content.get_question(question_id).get('type') in ['text', 'textbox_large']:
                answer = self.answers.get(question_id) or ''
                if self.character_limit is not None and len(answer) > self.character_limit:
                    errors_map[question_id] = "under_character_limit"

        return errors_map

    def word_limit_errors(self) -> Dict[str, str]:
        errors_map = {}
        for question_id in self.all_fields():
            question = self.content.get_question(question_id)
            if question.get('type') in ['text', 'textbox_large']:
                # Get word limit from question content, fall back to class attribute
                word_limit = question.get('max_length_in_words', self.word_limit)
                answer = self.answers.get(question_id) or ''
                if word_limit is not None and len(answer.split()) > word_limit:
                    errors_map[question_id] = "under_word_limit"

        return errors_map

    def formatting_errors(self, answers) -> Dict[str, str]:
        errors_map = {}
        if self.email_validation_fields is not None and len(self.email_validation_fields) > 0:
            for field in self.email_validation_fields:
                if self.answers.get(field) is None or not re.match(EMAIL_REGEX, self.answers.get(field, '')):
                    errors_map[field] = 'invalid_format'

        if self.number_string_fields is not None and len(self.number_string_fields) > 0:
            for field, length in self.number_string_fields:
                if self.answers.get(field) is None or not re.match(
                        r'^\d{{{0}}}$'.format(length), self.answers.get(field, '')
                ):
                    errors_map[field] = 'invalid_format'
        return errors_map

    def get_required_fields(self) -> Set[str]:
        try:
            req_fields = self.required_fields  # type: ignore
        except AttributeError:
            req_fields = set(self.all_fields())

        #  Remove optional fields
        if self.optional_fields is not None:
            req_fields -= set(self.optional_fields)

        return req_fields  # type: ignore


class G7Validator(DeclarationValidator):
    """
    Validator for G-Cloud 7.
    """
    optional_fields = {
        "SQ1-1p-i", "SQ1-1p-ii", "SQ1-1p-iii", "SQ1-1p-iv",
        "SQ1-1q-i", "SQ1-1q-ii", "SQ1-1q-iii", "SQ1-1q-iv", "SQ1-1cii", "SQ1-1i-ii",
        "SQ1-1j-i", "SQ1-1j-ii", "SQ4-1c", "SQ3-1k", "SQ1-1i-i"
    }
    email_validation_fields = {'SQ1-1o', 'SQ1-2b'}
    character_limit = 5000

    def get_required_fields(self) -> Set[str]:
        req_fields = super(G7Validator, self).get_required_fields()

        #  If you answered other to question 19 (trading status)
        if self.answers.get('SQ1-1ci') == 'other (please specify)':
            req_fields.add('SQ1-1cii')

        #  If you answered yes to question 27 (non-UK business registered in EU)
        if self.answers.get('SQ1-1i-i', False):
            req_fields.add('SQ1-1i-ii')

        #  If you answered 'licensed' or 'a member of a relevant organisation' in question 29
        answer_29 = self.answers.get('SQ1-1j-i', [])
        if answer_29 and len(answer_29) > 0 and (
            'licensed' in answer_29
            or 'a member of a relevant organisation' in answer_29
        ):
            req_fields.add('SQ1-1j-ii')

        # If you answered yes to either question 53 or 54 (tax returns)
        if self.answers.get('SQ4-1a', False) or self.answers.get('SQ4-1b', False):
            req_fields.add('SQ4-1c')

        # If you answered Yes to questions 39 - 51 (discretionary exclusion)
        dependent_fields = [
            'SQ2-2a', 'SQ3-1a', 'SQ3-1b', 'SQ3-1c', 'SQ3-1d', 'SQ3-1e', 'SQ3-1f', 'SQ3-1g',
            'SQ3-1h-i', 'SQ3-1h-ii', 'SQ3-1i-i', 'SQ3-1i-ii', 'SQ3-1j'
        ]
        if any(self.answers.get(field) for field in dependent_fields):
            req_fields.add('SQ3-1k')

        # If you answered No to question 26 (established in the UK)
        if 'SQ5-2a' in self.answers and not self.answers['SQ5-2a']:
            req_fields.add('SQ1-1i-i')
            req_fields.add('SQ1-1j-i')

        return req_fields


class DOSValidator(DeclarationValidator):
    optional_fields = {
        "mitigatingFactors", "mitigatingFactors2", "mitigatingFactors3", "tradingStatusOther",
        "modernSlaveryStatement", "modernSlaveryStatementOptional", "modernSlaveryReportingRequirements",
        # Registered in UK = no
        "appropriateTradeRegisters", "appropriateTradeRegistersNumber",
        "licenceOrMemberRequired", "licenceOrMemberRequiredDetails",
    }

    dependent_fields = {
        # If you responded yes to any of questions 22 to 34
        "mitigatingFactors": [
            'misleadingInformation', 'confidentialInformation', 'influencedContractingAuthority',
            'witheldSupportingDocuments', 'seriousMisrepresentation', 'significantOrPersistentDeficiencies',
            'distortedCompetition', 'conflictOfInterest', 'distortingCompetition', 'graveProfessionalMisconduct',
            'bankrupt', 'environmentalSocialLabourLaw', 'taxEvasion'
        ],
        # If you responded yes to either 36 or 37
        "mitigatingFactors2": [
            "unspentTaxConvictions", "GAAR"
        ],
        # If you responded yes to 50 (Modern Slavery)
        "modernSlaveryStatement": [
            "modernSlaveryTurnover",
        ],
        "modernSlaveryReportingRequirements": [
            "modernSlaveryTurnover"
        ],
    }

    email_validation_fields = {"contactEmailContractNotice", "primaryContactEmail"}
    character_limit = 5000

    def get_required_fields(self) -> Set[str]:
        req_fields = super(DOSValidator, self).get_required_fields()

        for target_field, fields in self.dependent_fields.items():
            if any(self.answers.get(field) for field in fields):
                req_fields.add(target_field)

        # Describe your trading status
        if self.answers.get('tradingStatus') == "other (please specify)":
            req_fields.add('tradingStatusOther')

        # If your company was not established in the UK
        if self.answers.get('establishedInTheUK') is False:
            req_fields.add('appropriateTradeRegisters')
            # If yes to appropriate trade registers
            if self.answers.get('appropriateTradeRegisters') is True:
                req_fields.add('appropriateTradeRegistersNumber')

            req_fields.add('licenceOrMemberRequired')
            # If not 'none of the above' to licenceOrMemberRequired
            if self.answers.get('licenceOrMemberRequired') in ['licensed', 'a member of a relevant organisation']:
                req_fields.add('licenceOrMemberRequiredDetails')

        # If supplier doesn't meet the Modern Slavery reporting requirements, they don't need to upload a statement
        # but must have mitigatingFactors3 explanation
        if self.answers.get('modernSlaveryReportingRequirements') is False:
            req_fields.add('mitigatingFactors3')
            req_fields.remove('modernSlaveryStatement')

        return req_fields


class SharedValidator(DOSValidator):
    # From DOS2 and G8 onwards, validate DUNS number length
    number_string_fields = [('dunsNumber', 9)]
    word_limit = 500


class G12Validator(SharedValidator):

    def errors(self) -> Dict[str, str]:

        errors_map = super().errors()

        q1_answer = self.answers.get('servicesHaveOrSupportCloudHostingCloudSoftware')
        q2_answer = self.answers.get('servicesHaveOrSupportCloudSupport')

        q1_negative = "My organisation isn't submitting cloud hosting (lot 1) or cloud software (lot 2) services"
        q2_negative = "My organisation isn't submitting cloud support (lot 3) services"

        if q1_answer == q1_negative and q2_answer == q2_negative:
            errors_map.update({
                'servicesHaveOrSupportCloudHostingCloudSoftware': 'dependent_question_error',
                'servicesHaveOrSupportCloudSupport': 'dependent_question_error',
            })

        return errors_map


def is_valid_percentage(value: Any) -> bool:
    # Design System guidance is that we should allow users to provide answers with or without units.
    if isinstance(value, str):
        value = value.rstrip('%')

    try:
        number = float(value)
    except ValueError:
        return False
    else:
        return 0 <= number <= 100


class DOS5Validator(SharedValidator):
    """Following an accessibility review, a number of questions and answers were changed for DOS 5"""
    percentage_fields = ["subcontractingInvoicesPaid"]

    optional_fields = SharedValidator.optional_fields.union({
        "subcontracting30DayPayments",
        "subcontractingInvoicesPaid"}
    )

    def get_required_fields(self) -> Set[str]:
        req_fields = super(DOS5Validator, self).get_required_fields()

        # as per subcontracting configuration on digitalmarketplace-frameworks
        if self.answers.get("subcontracting") in [
            "as a prime contractor, using third parties (subcontractors) to provide some services",
            "as part of a consortium or special purpose vehicle, using third parties (subcontractors) to provide some "
            "services"
        ]:
            req_fields.add("subcontracting30DayPayments")
            req_fields.add("subcontractingInvoicesPaid")

        return req_fields

    def formatting_errors(self, answers) -> Dict[str, str]:
        error_map = super(DOS5Validator, self).formatting_errors(answers)

        for field in self.percentage_fields:
            value = self.answers.get(field)
            if value is not None and not is_valid_percentage(value):
                error_map[field] = 'not_a_number'

        return error_map


VALIDATORS = {
    "g-cloud-7": G7Validator,
    "g-cloud-8": SharedValidator,
    "digital-outcomes-and-specialists": DOSValidator,
    "digital-outcomes-and-specialists-2": SharedValidator,
    "g-cloud-9": SharedValidator,
    "g-cloud-10": SharedValidator,
    "digital-outcomes-and-specialists-3": SharedValidator,
    "g-cloud-11": SharedValidator,
    "digital-outcomes-and-specialists-4": SharedValidator,
    "g-cloud-12": G12Validator,
    "digital-outcomes-and-specialists-5": DOS5Validator,
}
