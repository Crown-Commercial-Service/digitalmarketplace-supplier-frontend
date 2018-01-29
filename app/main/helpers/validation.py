from functools import reduce
from operator import add
import re

from werkzeug.datastructures import ImmutableOrderedMultiDict

EMAIL_REGEX = r'^[^@^\s]+@[^@^\.^\s]+(\.[^@^\.^\s]+)+$'


def get_validator(framework, content, answers):
    """
    Retrieves a validator by slug contained in the framework dictionary.
    """
    if framework is None:
        raise ValueError("a framework dictionary must be provided")
    if framework is not None:
        validator_cls = VALIDATORS.get(framework['slug'])
        return validator_cls(content, answers)


class DeclarationValidator(object):
    email_validation_fields = []
    number_string_fields = []
    character_limit = None
    optional_fields = set([])

    def __init__(self, content, answers):
        self.content = content
        self.answers = answers

    def get_error_messages_for_page(self, section):
        all_errors = self.get_error_messages()
        page_ids = section.get_question_ids()
        page_errors = ImmutableOrderedMultiDict(filter(lambda err: err[0] in page_ids, all_errors))
        return page_errors

    def get_error_messages(self):
        raw_errors_map = self.errors()
        errors_map = list()
        for question_id in self.all_fields():
            if question_id in raw_errors_map:
                question_number = self.content.get_question(question_id).get('number')
                validation_message = self.get_error_message(question_id, raw_errors_map[question_id])
                errors_map.append((question_id, {
                    'input_name': question_id,
                    'question': "Question {}".format(question_number)
                    if question_number else self.content.get_question(question_id).get('question'),
                    'message': validation_message,
                }))

        return errors_map

    def get_error_message(self, question_id, message_key):
        for validation in self.content.get_question(question_id).get('validations', []):
            if validation['name'] == message_key:
                return validation['message']
        default_messages = {
            'answer_required': 'You need to answer this question.',
            'under_character_limit': 'Your answer must be no more than {} characters.'.format(self.character_limit),
            'invalid_format': 'You must enter a valid email address.',
        }
        return default_messages.get(
            message_key, 'There was a problem with the answer to this question')

    def all_fields(self):
        return reduce(add, (section.get_question_ids() for section in self.content))

    def fields_with_values(self):
        return set(key for key, value in self.answers.items()
                   if value is not None and (not isinstance(value, str) or len(value) > 0))

    def errors(self):
        errors_map = {}
        errors_map.update(self.character_limit_errors())
        errors_map.update(self.formatting_errors(self.answers))
        errors_map.update(self.answer_required_errors())
        return errors_map

    def answer_required_errors(self):
        req_fields = self.get_required_fields()
        filled_fields = self.fields_with_values()
        errors_map = {}

        for field in req_fields - filled_fields:
            errors_map[field] = 'answer_required'

        return errors_map

    def character_limit_errors(self):
        errors_map = {}
        for question_id in self.all_fields():
            if self.content.get_question(question_id).get('type') in ['text', 'textbox_large']:
                answer = self.answers.get(question_id) or ''
                if self.character_limit is not None and len(answer) > self.character_limit:
                    errors_map[question_id] = "under_character_limit"

        return errors_map

    def formatting_errors(self, answers):
        errors_map = {}
        if self.email_validation_fields is not None and len(self.email_validation_fields) > 0:
            for field in self.email_validation_fields:
                if self.answers.get(field) is None or not re.match(EMAIL_REGEX, self.answers.get(field, '')):
                    errors_map[field] = 'invalid_format'

        if self.number_string_fields is not None and len(self.number_string_fields) > 0:
            for field, length in self.number_string_fields:
                if self.answers.get(field) is None or not re.match(
                        '^\d{{{0}}}$'.format(length), self.answers.get(field, '')
                ):
                    errors_map[field] = 'invalid_format'
        return errors_map

    def get_required_fields(self):
        try:
            req_fields = self.required_fields
        except AttributeError:
            req_fields = set(self.all_fields())

        #  Remove optional fields
        if self.optional_fields is not None:
            req_fields -= set(self.optional_fields)

        return req_fields


class G7Validator(DeclarationValidator):
    """
    Validator for G-Cloud 7.
    """
    optional_fields = set([
        "SQ1-1p-i", "SQ1-1p-ii", "SQ1-1p-iii", "SQ1-1p-iv",
        "SQ1-1q-i", "SQ1-1q-ii", "SQ1-1q-iii", "SQ1-1q-iv", "SQ1-1cii", "SQ1-1i-ii",
        "SQ1-1j-i", "SQ1-1j-ii", "SQ4-1c", "SQ3-1k", "SQ1-1i-i"
    ])
    email_validation_fields = set(['SQ1-1o', 'SQ1-2b'])
    character_limit = 5000

    def get_required_fields(self):
        req_fields = super(G7Validator, self).get_required_fields()

        #  If you answered other to question 19 (trading status)
        if self.answers.get('SQ1-1ci') == 'other (please specify)':
            req_fields.add('SQ1-1cii')

        #  If you answered yes to question 27 (non-UK business registered in EU)
        if self.answers.get('SQ1-1i-i', False):
            req_fields.add('SQ1-1i-ii')

        #  If you answered 'licensed' or 'a member of a relevant organisation' in question 29
        answer_29 = self.answers.get('SQ1-1j-i', [])
        if answer_29 and len(answer_29) > 0 and \
                ('licensed' in answer_29 or 'a member of a relevant organisation' in answer_29):
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
    optional_fields = set([
        "mitigatingFactors", "mitigatingFactors2", "tradingStatusOther",
        # Registered in UK = no
        "appropriateTradeRegisters", "appropriateTradeRegistersNumber",
        "licenceOrMemberRequired", "licenceOrMemberRequiredDetails",
    ])
    email_validation_fields = set(["contactEmailContractNotice", "primaryContactEmail"])
    character_limit = 5000

    def get_required_fields(self):
        req_fields = super(DOSValidator, self).get_required_fields()

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
        }
        for target_field, fields in dependent_fields.items():
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

        return req_fields


class G8Validator(DOSValidator):
    number_string_fields = [('dunsNumber', 9)]


class DOS2Validator(G8Validator):
    pass


VALIDATORS = {
    "g-cloud-7": G7Validator,
    "g-cloud-8": G8Validator,
    "digital-outcomes-and-specialists": DOSValidator,
    "digital-outcomes-and-specialists-2": DOS2Validator,
    "g-cloud-9": DOS2Validator,
    "g-cloud-10": DOS2Validator,
    "digital-outcomes-and-specialists-3": DOS2Validator,
}
