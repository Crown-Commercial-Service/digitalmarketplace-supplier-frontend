import re
from datetime import datetime
from flask import abort, current_app
from flask_login import current_user

from dmapiclient import APIError

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


def get_drafts(apiclient, framework_slug):
    try:
        drafts = apiclient.find_draft_services(
            current_user.supplier_id,
            framework=framework_slug
        )['services']

    except APIError as e:
        abort(e.status_code)

    complete_drafts = [draft for draft in drafts if draft['status'] == 'submitted']
    drafts = [draft for draft in drafts if draft['status'] == 'not-submitted']

    return drafts, complete_drafts


def get_lot_drafts(apiclient, framework_slug, lot_slug):
    drafts, complete_drafts = get_drafts(apiclient, framework_slug)
    return (
        [draft for draft in drafts if draft['lotSlug'] == lot_slug],
        [draft for draft in complete_drafts if draft['lotSlug'] == lot_slug]
    )


def count_unanswered_questions(service_attributes):
    unanswered_required, unanswered_optional = (0, 0)
    for section in service_attributes:
        for question in section.questions:
            if question.answer_required:
                unanswered_required += 1
            elif question.value in ['', [], None]:
                unanswered_optional += 1

    return unanswered_required, unanswered_optional


def is_service_associated_with_supplier(service):
    return service.get('supplierId') == current_user.supplier_id


def get_signed_document_url(uploader, document_path):
    url = uploader.get_signed_url(document_path)
    if url is not None:
        url = urlparse.urlparse(url)
        base_url = urlparse.urlparse(current_app.config['DM_ASSETS_URL'])
        return url._replace(netloc=base_url.netloc, scheme=base_url.scheme).geturl()


def parse_document_upload_time(data):
    match = re.search("(\d{4}-\d{2}-\d{2}-\d{2}\d{2})\..{2,3}$", data)
    if match:
        return datetime.strptime(match.group(1), "%Y-%m-%d-%H%M")


def get_next_section_name(content, current_section_id):
    if content.get_next_editable_section_id(current_section_id):
        return content.get_section(
            content.get_next_editable_section_id(current_section_id)
        ).name
