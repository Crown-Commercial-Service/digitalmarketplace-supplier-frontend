from datetime import datetime
import re
import urllib.parse as urlparse

from dmapiclient import HTTPError
from flask import abort, current_app
from flask_login import current_user

from .frameworks import get_supplier_framework_info


def get_drafts(apiclient, framework_slug):
    drafts = apiclient.find_draft_services_iter(
        current_user.supplier_id,
        framework=framework_slug
    )
    complete_drafts, unsubmitted_drafts = [], []
    for draft in drafts:
        if draft['status'] in ('submitted', 'failed'):
            complete_drafts.append(draft)
        if draft['status'] == 'not-submitted':
            unsubmitted_drafts.append(draft)

    return unsubmitted_drafts, complete_drafts


def get_lot_drafts(apiclient, framework_slug, lot_slug):
    drafts, complete_drafts = get_drafts(apiclient, framework_slug)
    return (
        [draft for draft in drafts if draft['lotSlug'] == lot_slug],
        [draft for draft in complete_drafts if draft['lotSlug'] == lot_slug]
    )


def get_draft_service_or_404(data_api_client, service_id, framework_slug, lot_slug):
    try:
        draft = data_api_client.get_draft_service(service_id).get('services')
    except HTTPError as e:
        abort(e.status_code)

    if draft['lotSlug'] != lot_slug or draft['frameworkSlug'] != framework_slug:
        abort(404)

    if not is_service_associated_with_supplier(draft):
        abort(404)

    return draft


def is_service_associated_with_supplier(service):
    return service.get('supplierId') == current_user.supplier_id


def get_signed_document_url(uploader, document_path):
    url = uploader.get_signed_url(document_path)
    if url is not None:
        url = urlparse.urlparse(url)
        base_url = urlparse.urlparse(current_app.config['DM_ASSETS_URL'])
        return url._replace(netloc=base_url.netloc, scheme=base_url.scheme).geturl()


def parse_document_upload_time(data):
    match = re.search(r"(\d{4}-\d{2}-\d{2}-\d{2}\d{2})\..{2,3}$", data)
    if match:
        return datetime.strptime(match.group(1), "%Y-%m-%d-%H%M")


def get_next_section_name(content, current_section_id):
    if content.get_next_editable_section_id(current_section_id):
        return content.get_section(
            content.get_next_editable_section_id(current_section_id)
        ).name


def copy_service_from_previous_framework(data_api_client, content_loader, framework_slug, lot_slug, service_id):
    # Suppliers must have registered interest in a framework before they can edit draft services
    if not get_supplier_framework_info(data_api_client, framework_slug):
        abort(404)
    questions_to_exclude = content_loader.get_metadata(framework_slug, 'copy_services', 'questions_to_exclude')
    questions_to_copy = content_loader.get_metadata(framework_slug, 'copy_services', 'questions_to_copy')
    source_framework_slug = content_loader.get_metadata(framework_slug, 'copy_services', 'source_framework')

    previous_service = data_api_client.get_service(service_id)['services']
    if previous_service['lotSlug'] != lot_slug or previous_service['frameworkSlug'] != source_framework_slug \
            or previous_service['copiedToFollowingFramework']:
        abort(404)

    if not is_service_associated_with_supplier(previous_service):
        abort(404)

    copy_options = {
        'targetFramework': framework_slug,
        'status': 'not-submitted'
    }
    # Use questions_to_exclude if available in metadata, otherwise fall back to (deprecated) questions_to_copy
    if questions_to_exclude:
        copy_options['questionsToExclude'] = questions_to_exclude
    elif questions_to_copy:
        copy_options['questionsToCopy'] = questions_to_copy

    data_api_client.copy_draft_service_from_existing_service(
        previous_service['id'],
        current_user.email_address,
        copy_options,
    )
