import re
from datetime import datetime
from flask import abort, current_app
from flask_login import current_user

from dmutils.apiclient import APIError
from dmutils.service_attribute import Attribute

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


def get_drafts(apiclient, supplier_id, framework_slug):
    try:
        drafts = apiclient.find_draft_services(
            current_user.supplier_id,
            framework='g-cloud-7'
        )['services']

    except APIError as e:
        abort(e.status_code)

    # Hide drafts without service name
    drafts = [draft for draft in drafts if draft.get('serviceName')]

    complete_drafts = [draft for draft in drafts if draft['status'] == 'submitted']
    drafts = [draft for draft in drafts if draft['status'] == 'not-submitted']

    return drafts, complete_drafts


def count_unanswered_questions(service_attributes):
    unanswered_required, unanswered_optional = (0, 0)
    for section in service_attributes:
        for question in section['rows']:
            if question.answer_required:
                unanswered_required += 1
            elif question.value in ['', [], None]:
                unanswered_optional += 1

    return unanswered_required, unanswered_optional


def get_service_attributes(service_data, service_questions):
    return list(map(
        lambda section: {
            'name': section['name'],
            'rows': _get_rows(section, service_data),
            'editable': section['editable'],
            'id': section['id']
        },
        service_questions
    ))


def _get_rows(section, service_data):
    return list(
        map(
            lambda question: Attribute(
                value=service_data.get(question['id'], None),
                question_type=question['type'],
                label=question['question'],
                optional=question.get('optional', False)
            ),
            section['questions']
        )
    )


def is_service_associated_with_supplier(service):
    return service.get('supplierId') == current_user.supplier_id


def is_service_modifiable(service):
    return service.get('status') != 'disabled'


def get_draft_document_url(uploader, document_path):
    url = uploader.get_signed_url(document_path)
    if url is not None:
        url = urlparse.urlparse(url)
        base_url = urlparse.urlparse(current_app.config['DM_G7_DRAFT_DOCUMENTS_URL'])
        return url._replace(netloc=base_url.netloc, scheme=base_url.scheme).geturl()


def get_document_url(uploader, document_path):
    url = uploader.get_signed_url(document_path)
    if url is not None:
        if current_app.config['DM_ASSETS_URL'] is not None:
            url = urlparse.urlparse(url)
            base_url = urlparse.urlparse(current_app.config['DM_ASSETS_URL'])
            url = url._replace(netloc=base_url.netloc, scheme=base_url.scheme).geturl()
        return url


def parse_document_upload_time(data):
    match = re.search("(\d{4}-\d{2}-\d{2}-\d{2}\d{2})\..{2,3}$", data)
    if match:
        return datetime.strptime(match.group(1), "%Y-%m-%d-%H%M")


def get_next_section_name(content, current_section_id):
    if content.get_next_editable_section_id(current_section_id):
        return content.get_section(
            content.get_next_editable_section_id(current_section_id)
        ).name
