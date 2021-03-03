# -*- coding: utf-8 -*-
from datetime import datetime
from functools import wraps
from itertools import chain, islice, groupby
import re
from typing import Optional, Container, Dict, List

from flask import abort, current_app, render_template, request
from flask_login import current_user

from dmapiclient import DataAPIClient, APIError, HTTPError
from dmutils.dates import update_framework_with_formatted_dates
from dmutils.formats import DATETIME_FORMAT
from dmcontent.errors import ContentNotFoundError

from ...main import content_loader


def get_framework_or_404(client, framework_slug, allowed_statuses=None):
    if allowed_statuses is None:
        allowed_statuses = ['open', 'pending', 'standstill', 'live']
    framework = client.get_framework(framework_slug)['frameworks']

    if allowed_statuses and framework['status'] not in allowed_statuses:
        abort(404)

    return framework


def get_framework_or_500(client, framework_slug, logger=None):
    """Return a 500 if a framework is not found that we explicitly expect to be there"""
    try:
        return client.get_framework(framework_slug)['frameworks']
    except HTTPError as e:
        if e.status_code == 404:
            if logger:
                logger.error(
                    "Framework not found. Error: {error}, framework_slug: {framework_slug}",
                    extra={'error': str(e), 'framework_slug': framework_slug}
                )
            abort(500, f'Framework not found: {framework_slug}')
        else:
            raise


def get_framework_and_lot_or_404(client, framework_slug, lot_slug, allowed_statuses=None):
    framework = get_framework_or_404(client, framework_slug, allowed_statuses)
    return framework, get_framework_lot_or_404(framework, lot_slug)


def frameworks_by_slug(client):
    framework_list = client.find_frameworks().get("frameworks")
    frameworks = {}
    for framework in framework_list:
        frameworks[framework['slug']] = framework
    return frameworks


def get_completed_lots(client, lots, framework_slug, supplier_id):
    """Return an array of completed lot names for a supplier"""
    def has_submitted(lot):
        return client.find_draft_services_by_framework(framework_slug=framework_slug,
                                                       status="submitted",
                                                       supplier_id=supplier_id,
                                                       lot=lot['slug'],
                                                       page=1)['meta']['total'] > 0

    return [f"Lot {number}: {lot['name']}" for number, lot in enumerate(lots, start=1) if has_submitted(lot)]


def get_framework_lot_or_404(framework, lot_slug):
    try:
        return next(lot for lot in framework['lots'] if lot['slug'] == lot_slug)
    except StopIteration:
        abort(404)


def order_frameworks_for_reuse(frameworks):
    """Sort frameworks by reuse suitability.

    If a declaration has the reuse flag set and is the most recently closed framework then that's our framework.
    """
    return sorted(
        filter(lambda i: i['allowDeclarationReuse'] and i['applicationsCloseAtUTC'], frameworks),
        key=lambda i: datetime.strptime(i['applicationsCloseAtUTC'], DATETIME_FORMAT),
        reverse=True
    )


def register_interest_in_framework(client, framework_slug):
    client.register_framework_interest(current_user.supplier_id, framework_slug, current_user.email_address)


def get_last_modified_from_first_matching_file(key_list, framework_slug, prefix):
    """
    Takes a list of file keys, a framework slug and a string that is a whole or start of a filename.
    Returns the 'last_modified' timestamp for first file whose path starts with the framework slug and passed-in string,
    or None if no matching file is found.

    :param key_list: list of file keys (from an s3 bucket)
    :param framework_slug: the framework that we're looking up a document for (this is the first part of the file path)
    :param prefix: the first part of the filename to match (this could also be the complete filename for an exact match)
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


def get_framework_for_reuse(
    supplier_id: int,
    client: DataAPIClient,
    exclude_framework_slugs: Optional[Container[str]] = None,
) -> Optional[dict]:
    """Given a list of declarations find the most suitable for reuse.

     :param supplier_id: supplier whose declarations we are inspecting
     :param client: data client
     :param exclude_framework_slugs: list of framework slugs to exclude from results
     :return: framework
    """
    declarations = {
        sf['frameworkSlug']: sf
        for sf in client.find_supplier_declarations(supplier_id)['frameworkInterest']
        if sf['onFramework'] and sf.get('allowDeclarationReuse') is not False
    }
    return next((
        framework for framework in order_frameworks_for_reuse(client.find_frameworks()['frameworks'])
        if framework['slug'] in declarations and framework['slug'] not in (exclude_framework_slugs or ())
    ), None)


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
    """
    Replace placeholders for question references with the number of the referenced question

    e.g. "This is my question hint which references question [[anotherQuestion]]" becomes
    "This is my question hint which references question 7"

    :param data: Object to have placeholders replaced for example a string or Markup object
    :param get_question: ContentManifest.get_question function
    :return: Object with same type of original `data` object but with question references replaced
    """
    if not data:
        return data
    references = re.sub(
        r"\[\[([^\]]+)\]\]",  # anything that looks like [[nameOfQuestion]]
        lambda question_id: str(get_question(question_id.group(1))['number']),
        data
    )

    return data.__class__(references)


def get_frameworks_by_status(
        frameworks: List[Dict],
        status: str,
        extra_condition: Optional[str] = None
) -> List[Dict]:
    return list(
        filter(lambda i: i['status'] == status and (i.get(extra_condition) if extra_condition else True), frameworks)
    )


def get_most_recent_expired_dos_framework(all_frameworks: List[Dict]) -> List[Dict]:
    expired_dos = [
        f for f in get_frameworks_by_status(all_frameworks, 'expired', 'onFramework')
        if f['family'] == 'digital-outcomes-and-specialists'
    ]

    if expired_dos:
        return [sorted(expired_dos, key=lambda f: f['frameworkExpiresAtUTC'], reverse=True)[0]]

    return []


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


def get_frameworks_closed_and_open_for_applications(frameworks):
    # This will find one framework iteration per framework-family, open > coming > closed
    def status_priority(status):
        if status == "open":
            return 0
        elif status == "coming":
            return 1
        else:
            return 2

    return tuple(chain.from_iterable(
        islice(grp, 1)          # take the first framework
        for _, grp in groupby(  # from each framework_family
            sorted(             # listed in priority order
                (fw for fw in frameworks),
                key=lambda fw_sort: (fw_sort["framework"], status_priority(fw_sort["status"])),
            ),
            key=lambda fw_groupby: fw_groupby["framework"],
        )
    ))


def get_supplier_registered_name_from_declaration(declaration):
    return (
        declaration.get('supplierRegisteredName')  # G-Cloud 10 and later declaration key
        or declaration.get('nameOfOrganisation')  # G-Cloud 9 and earlier declaration key
    )


def get_unconfirmed_open_supplier_frameworks(data_api_client, supplier_id):
    frameworks = data_api_client.find_frameworks().get('frameworks')
    open_framework_slugs = [framework['slug'] for framework in frameworks if framework['status'] == 'open']
    unconfirmed_open_supplier_frameworks = [
        sf for sf in
        data_api_client.get_supplier_frameworks(supplier_id=supplier_id)['frameworkInterest']
        if sf['frameworkSlug'] in open_framework_slugs and sf['applicationCompanyDetailsConfirmed'] is not True
    ]

    framework_slug_map = {framework['slug']: framework for framework in frameworks}
    for fw in unconfirmed_open_supplier_frameworks:
        if 'frameworkName' not in fw:
            fw['frameworkName'] = framework_slug_map[fw['frameworkSlug']]['name']

    return unconfirmed_open_supplier_frameworks


class EnsureApplicationCompanyDetailsHaveBeenConfirmed:
    """A decorator for framework application views that should not be accessible before company details have
    been confirmed for that application.

    This is a class-based decorator primarily so that it's possible to mock out the validator for the majority of tests
    which aren't actively testing that the view requires suppliers to be in a certain application state."""

    def __init__(self, data_api_client):
        self.data_api_client = data_api_client

    def __call__(self, func):
        @wraps(func)
        def decorated_view(*args, **kwargs):
            if self.validator(*args, **kwargs):
                return func(*args, **kwargs)

            # Shouldn't be able to get here
            abort(500, "There was a problem accessing this page of your application. Please try again later.")

        return decorated_view

    def validator(self, *args, **kwargs):
        """Performs the actual validation that ensures the logged-in supplier has confirmed their company details
        are correct for this application"""
        if 'framework_slug' not in kwargs:
            current_app.logger.error("Required parameter `framework_slug` is undefined for the calling view.")
            abort(500, "There was a problem accessing this page of your application. Please try again later.")

        if current_user.is_authenticated and current_user.supplier_id:
            supplier_framework = self.data_api_client.get_supplier_framework_info(
                current_user.supplier_id, kwargs['framework_slug']
            )['frameworkInterest']

            if supplier_framework['applicationCompanyDetailsConfirmed'] is not True:
                return abort(400, "You cannot access this part of your application until you have confirmed your "
                                  "company details.")

        return True


def return_404_if_applications_closed(data_api_client_callable):
    def real_decorator(func):
        @wraps(func)
        def decorated_view(*args, **kwargs):
            data_api_client = data_api_client_callable()
            if 'framework_slug' not in kwargs:
                current_app.logger.error("Required parameter `framework_slug` is undefined for the calling view.")
                abort(500)

            framework_slug = kwargs['framework_slug']
            framework = get_framework_or_404(data_api_client, framework_slug)

            if not framework['status'] == 'open':
                current_app.logger.info(
                    'Supplier {supplier_id} requested "{method} {path}" after {framework_slug} applications closed.',
                    extra={
                        'supplier_id': current_user.supplier_id,
                        'method': request.method,
                        'path': request.path,
                        'framework_slug': framework_slug
                    }
                )

                update_framework_with_formatted_dates(framework)

                try:
                    following_framework_content = content_loader.get_metadata(
                        framework_slug, 'following_framework', 'framework'
                    )
                except ContentNotFoundError:
                    following_framework_content = None

                return render_template(
                    'errors/applications_closed.html',
                    framework=framework,
                    following_framework_content=following_framework_content,
                ), 404
            else:
                return func(*args, **kwargs)
        return decorated_view
    return real_decorator


def check_framework_supports_e_signature_or_404(framework):
    if not framework['isESignatureSupported']:
        abort(404)


def get_framework_contract_title(framework):
    if framework['isESignatureSupported']:
        return content_loader.get_message(framework['slug'], 'e-signature', 'framework_contract_title')
    else:
        return 'Framework Agreement'
