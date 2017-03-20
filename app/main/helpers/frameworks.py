# -*- coding: utf-8 -*-
import re
from datetime import datetime

from dmutils.formats import DATETIME_FORMAT
from flask import abort
from flask_login import current_user
from dmapiclient import APIError


def get_framework(client, framework_slug, allowed_statuses=None):
    if allowed_statuses is None:
        allowed_statuses = ['open', 'pending', 'standstill', 'live']

    framework = client.get_framework(framework_slug)['frameworks']

    if allowed_statuses and framework['status'] not in allowed_statuses:
        abort(404)

    return framework


def get_framework_and_lot(client, framework_slug, lot_slug, allowed_statuses=None):
    framework = get_framework(client, framework_slug, allowed_statuses)
    return framework, get_framework_lot(framework, lot_slug)


def frameworks_by_slug(client):
    framework_list = client.find_frameworks().get("frameworks")
    frameworks = {}
    for framework in framework_list:
        frameworks[framework['slug']] = framework
    return frameworks


def get_framework_lot(framework, lot_slug):
    try:
        return next(lot for lot in framework['lots'] if lot['slug'] == lot_slug)
    except StopIteration:
        abort(404)


def order_frameworks_for_reuse(frameworks):
    """Sort frameworks by reuse suitability.

    If a declaration has the reuse flag set and is the most recently closed framework then that's our framework.
    """
    return sorted(
        filter(lambda i: i['allowDeclarationReuse'] and i['applicationCloseDate'], frameworks),
        key=lambda i: datetime.strptime(i['applicationCloseDate'], DATETIME_FORMAT),
        reverse=True
    )


def register_interest_in_framework(client, framework_slug):
    client.register_framework_interest(current_user.supplier_id, framework_slug, current_user.email_address)


def get_last_modified_from_first_matching_file(key_list, framework_slug, prefix):
    """
    Takes a list of file keys and a string.
    Returns the 'last_modified' timestamp for first file whose path starts with the passed-in string,
    or None if no matching file is found.

    :param key_list: list of file keys (from an s3 bucket)
    :param path_starts_with: check for file paths which start with this string
    :return: the timestamp of the first matching file key or None
    """
    path_starts_with = '{}/{}'.format(framework_slug, prefix)
    return next((key for key in key_list if key.get('path').startswith(path_starts_with)), {}).get('last_modified')


def get_first_question_index(content, section):
    questions_so_far = 0
    ind = content.sections.index(section)
    for i in range(0, ind):
        questions_so_far += len(content.sections[i].get_question_ids())
    return questions_so_far


def get_declaration_status(data_api_client, framework_slug):
    try:
        declaration = data_api_client.get_supplier_declaration(
            current_user.supplier_id, framework_slug
        )['declaration']
    except APIError as e:
        if e.status_code == 404:
            return 'unstarted'
        else:
            abort(e.status_code)

    if not declaration:
        return 'unstarted'
    else:
        return declaration.get('status', 'unstarted')


def get_framework_for_reuse(supplier_id, client, exclude_framework_slugs=None):
    """Given a list of declarations find the most suitable for reuse.

     :param supplier_id: supplier whose declarations we are inspecting
     :param client: data client if not frameworks
     :param exclude_framework_slugs: list of framework slugs to exclude from results
     :return: framework
     """
    exclude_framework_slugs = exclude_framework_slugs or []
    supplier_frameworks = client.find_supplier_declarations(supplier_id)['frameworkInterest']
    supplier_frameworks_on_framework = filter(
        lambda i: i['onFramework'],
        supplier_frameworks
    )
    declarations = {i['frameworkSlug']: i for i in supplier_frameworks_on_framework}
    frameworks = client.find_frameworks()['frameworks']
    for framework in order_frameworks_for_reuse(frameworks):
        if framework['slug'] in declarations and framework['slug'] not in exclude_framework_slugs:
            return framework
    return None


def get_supplier_framework_info(data_api_client, framework_slug):
    try:
        return data_api_client.get_supplier_framework_info(
            current_user.supplier_id, framework_slug
        )['frameworkInterest']
    except APIError as e:
        if e.status_code == 404:
            return None
        else:
            abort(e.status_code)


def get_declaration_status_from_info(supplier_framework_info):
    if not supplier_framework_info or not supplier_framework_info.get('declaration'):
        return 'unstarted'

    return supplier_framework_info['declaration'].get('status', 'unstarted')


def get_supplier_on_framework_from_info(supplier_framework_info):
    if not supplier_framework_info:
        return False

    return bool(supplier_framework_info.get('onFramework'))


def return_supplier_framework_info_if_on_framework_or_abort(data_api_client, framework_slug):
    supplier_framework = get_supplier_framework_info(data_api_client, framework_slug)

    if not get_supplier_on_framework_from_info(supplier_framework):
        abort(404)

    return supplier_framework


def question_references(data, get_question):
    if not data:
        return data
    references = re.sub(
        r"\[\[([^\]]+)\]\]",  # anything that looks like [[nameOfQuestion]]
        lambda question_id: str(get_question(question_id.group(1))['number']),
        data
    )

    return data.__class__(references)


def get_frameworks_by_status(frameworks, status, extra_condition=False):
    return [
        framework for framework in frameworks
        if framework['status'] == status and
        (framework.get(extra_condition) if extra_condition else True)
    ]


def count_drafts_by_lot(drafts, lotSlug):
    return len([
        draft for draft in drafts if draft['lotSlug'] == lotSlug
    ])


def get_statuses_for_lot(
    has_one_service_limit,
    drafts_count,
    complete_drafts_count,
    declaration_status,
    framework_status,
    lot_name,
    unit,
    unit_plural
):

    if not drafts_count and not complete_drafts_count:
        return []

    framework_is_open = ('open' == framework_status)
    declaration_complete = ('complete' == declaration_status)

    if has_one_service_limit:
        return [get_status_for_one_service_lot(
            drafts_count, complete_drafts_count, declaration_complete, framework_is_open, lot_name, unit, unit_plural
        )]

    if not complete_drafts_count:
        return [get_status_for_multi_service_lot_and_service_type(
            drafts_count, 'draft', framework_is_open, declaration_complete, unit, unit_plural
        )] if framework_is_open else [{
            'title': 'No {} were marked as complete'.format(unit_plural),
            'type': 'quiet'
        }]

    if not drafts_count:
        return [get_status_for_multi_service_lot_and_service_type(
            complete_drafts_count, 'complete', framework_is_open, declaration_complete, unit, unit_plural
        )]

    return [
        get_status_for_multi_service_lot_and_service_type(
            complete_drafts_count, 'complete', framework_is_open, declaration_complete, unit, unit_plural
        ),
        get_status_for_multi_service_lot_and_service_type(
            drafts_count, 'draft', framework_is_open, declaration_complete, unit, unit_plural
        )
    ] if framework_is_open else [get_status_for_multi_service_lot_and_service_type(
        complete_drafts_count, 'complete', framework_is_open, declaration_complete, unit, unit_plural
    )]


def get_status_for_one_service_lot(
    drafts_count, complete_drafts_count, declaration_complete, framework_is_open, lot_name, unit, unit_plural
):
    if (drafts_count and framework_is_open) or (drafts_count and not complete_drafts_count):
        return {
            'title': u'Started but not complete' if framework_is_open else u'Not completed',
            'type': u'quiet'
        }

    if complete_drafts_count:
        if framework_is_open:
            return {
                'title': u'This will be submitted',
                'hint': u'You can edit it until the deadline',
                'type': u'happy'
            } if declaration_complete else {
                'title': u'Marked as complete',
                'hint': u'You can edit it until the deadline'
            }
        else:
            return {
                'title': u'Submitted',
                'type': u'happy'
            } if declaration_complete else {
                'title': u'Marked as complete'
            }


def get_status_for_multi_service_lot_and_service_type(
    count, services_status, framework_is_open, declaration_complete, unit, unit_plural
):

    singular = (1 == count)
    description_of_services = u'{} {} {}'.format(
        count, services_status, unit if singular else unit_plural
    )

    if services_status == 'draft':
        return {
            'title': description_of_services,
            'hint': u'Started but not complete',
            'type': u'quiet'
        } if framework_is_open else {
            'title': u'{} {} submitted'.format(
                description_of_services, u'wasn’t' if singular else u'weren’t'
            ),
            'type': u'quiet'
        }

    if framework_is_open:
        return {
            'title': u'{} {} will be submitted'.format(
                count, unit if singular else unit_plural
            ),
            'hint': u'You can edit {} until the deadline'.format(u'it' if singular else u'them'),
            'type': u'happy'
        } if declaration_complete else {
            'title': u'{} {} marked as complete'.format(
                count, unit if singular else unit_plural
            ),
            'hint': u'You can edit {} until the deadline'.format(u'it' if singular else u'them')
        }
    else:
        return {
            'title': u'{} {} submitted'.format(
                description_of_services, u'was' if singular else u'were'
            ),
            'type': u'happy'
        } if declaration_complete else {
            'title': u'{} {} submitted'.format(
                description_of_services, u'wasn’t' if singular else u'weren’t'
            ),
            'type': u'quiet'
        }


def returned_agreement_email_recipients(supplier_framework):
    email_recipients = [supplier_framework['declaration']['primaryContactEmail']]
    if supplier_framework['declaration']['primaryContactEmail'].lower() != current_user.email_address.lower():
        email_recipients.append(current_user.email_address)
    return email_recipients


def check_agreement_is_related_to_supplier_framework_or_abort(agreement, supplier_framework):
    if not agreement.get('supplierId') or agreement.get('supplierId') != supplier_framework.get('supplierId'):
        abort(404)
    if not agreement.get('frameworkSlug') or agreement.get('frameworkSlug') != supplier_framework.get('frameworkSlug'):
        abort(404)
