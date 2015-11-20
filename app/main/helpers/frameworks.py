# -*- coding: utf-8 -*-
import re

from flask import abort
from flask_login import current_user
from dmutils.apiclient import APIError


def get_framework(client, framework_slug, open_only=True):
    framework = client.get_framework(framework_slug)['frameworks']
    allowed_statuses = ['open'] if open_only else ['open', 'pending', 'standstill', 'live']
    if framework['status'] not in allowed_statuses:
        abort(404)

    return framework


def get_framework_and_lot(client, framework_slug, lot_slug, open_only=True):
    framework = get_framework(client, framework_slug, open_only)
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


def register_interest_in_framework(client, framework_slug):
    client.register_framework_interest(current_user.supplier_id, framework_slug, current_user.email_address)


def get_last_modified_from_first_matching_file(key_list, path_starts_with):
    """
    Takes a list of file keys and a string.
    Returns the 'last_modified' timestamp for first file whose path starts with the passed-in string,
    or None if no matching file is found.

    :param key_list: list of file keys (from an s3 bucket)
    :param path_starts_with: check for file paths which start with this string
    :return: the timestamp of the first matching file key or None
    """
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
    if not (supplier_framework_info or {}).get('declaration'):
        return 'unstarted'
    else:
        return supplier_framework_info['declaration'].get('status', 'unstarted')


def get_supplier_on_framework_from_info(supplier_framework_info):
    if supplier_framework_info is None:
        return False
    else:
        return bool(supplier_framework_info.get('onFramework'))


def question_references(data, get_question):
    return re.sub(
        r"\[\[([^\]]+)\]\]",  # anything that looks like [[nameOfQuestion]]
        lambda question_id: str(get_question(question_id.group(1))['number']),
        data
    )


def get_frameworks_by_status(frameworks, status, extra_condition=False):
    return [
        framework for framework in frameworks
        if framework['status'] == status and
        (framework.get(extra_condition) if extra_condition else True)
    ]


def count_drafts_by_lot(drafts, lot):
    return len([
        draft for draft in drafts if draft['lot'] == lot
    ])


def get_statuses_for_lot(
    has_one_service_limit, drafts_count, complete_drafts_count, declaration_status, framework_status, lot_name
):

    framework_is_open = 'open' == framework_status
    declaration_complete = 'complete' == declaration_status

    if not drafts_count and not complete_drafts_count:
        if framework_is_open:
            return [{
                'title': u'You haven’t applied to provide {}'.format(lot_name),
                'type': u'quiet'
            }]
        else:
            return [{
                'title': u'You didn’t apply to provide {}'.format(lot_name),
                'type': u'quiet'
            }]

    if has_one_service_limit:
        one_service_lot_status = get_status_for_one_service_lot(
            drafts_count, complete_drafts_count, declaration_complete, framework_is_open, lot_name
        )
        if one_service_lot_status:
            return [one_service_lot_status]

    if not complete_drafts_count:
        return [
            get_status_for_multi_service_lot_and_service_type(
                drafts_count, 'draft', framework_is_open, declaration_complete
            ) or None
        ]

    if not drafts_count:
        return [
            get_status_for_multi_service_lot_and_service_type(
                complete_drafts_count, 'complete', framework_is_open, declaration_complete
            )
        ]

    return [
        get_status_for_multi_service_lot_and_service_type(
            complete_drafts_count, 'complete', framework_is_open, declaration_complete
        ),
        get_status_for_multi_service_lot_and_service_type(
            drafts_count, 'draft', framework_is_open, declaration_complete
        )
    ]


def get_status_for_one_service_lot(
    drafts_count, complete_drafts_count, declaration_complete, framework_is_open, lot_name
):

    if drafts_count:
        if framework_is_open:
            return {
                'title': u'You’ve started your application',
                'type': u'quiet'
            }
        else:
            return {
                'title': u'You started your application',
                'type': u'quiet'
            }
    if complete_drafts_count:
        if framework_is_open:
            if declaration_complete:
                return {
                    'title': u'You’re submitting this service',
                    'hint': u'You can edit it until the deadline',
                    'type': u'happy'
                }
            else:
                return {
                    'title': u'You’ve completed this service',
                    'hint': u'You can edit it until the deadline'
                }
        else:
            if declaration_complete:
                return {
                    'title': u'You submitted this service',
                    'type': u'happy'
                }
            else:
                return {
                    'title': u'You marked this service as complete'
                }


def get_status_for_multi_service_lot_and_service_type(count, services_status, framework_is_open, declaration_complete):

    singular = 1 == count
    description_of_services = u'{} {} service{}'.format(
        count, services_status, u'' if singular else u's'
    )

    if framework_is_open:
        if services_status == 'complete':
            return {
                'title': u'{}{}'.format(
                    description_of_services, u' will be submitted' if declaration_complete else u''
                ),
                'hint': u'You can edit {} until the deadline'.format(u'it' if singular else u'them'),
                'type': u'happy' if declaration_complete else None
            }
        else:
            return {
                'title': u'{}{}'.format(
                    description_of_services, u' won’t be submitted' if declaration_complete else ''
                ),
                'type': u'quiet'
            }
    else:
        if services_status == 'complete':
            if declaration_complete:
                return {
                    'title': u'{} {} submitted'.format(
                        description_of_services, u'was' if singular else u'were'
                    ),
                    'type': u'happy' if declaration_complete else None
                }
            else:
                return {
                    'title': u'{} {} submitted'.format(
                        description_of_services, u'wasn’t' if singular else u'weren’t'
                    ),
                    'type': u'quiet'
                }
        else:
            return {
                'title': u'{} {} submitted'.format(
                    description_of_services, u'wasn’t' if singular else u'weren’t'
                ),
                'type': u'quiet'
            }
