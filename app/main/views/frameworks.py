# -*- coding: utf-8 -*-
from collections import OrderedDict
from datetime import datetime, timedelta

from dmutils.errors import render_error_page
from itertools import chain

from dateutil.parser import parse as date_parse
from flask import request, abort, flash, redirect, url_for, current_app, session
from flask_login import current_user

from dmapiclient import APIError, HTTPError
from dmapiclient.audit import AuditTypes
from dmcontent.questions import ContentQuestion
from dmcontent.errors import ContentNotFoundError
from dmcontent.utils import count_unanswered_questions
from dmutils import s3
from dmutils.dates import update_framework_with_formatted_dates
from dmutils.documents import (
    RESULT_LETTER_FILENAME, SIGNED_AGREEMENT_PREFIX, SIGNED_SIGNATURE_PAGE_PREFIX,
    SIGNATURE_PAGE_FILENAME, get_document_path, generate_timestamped_document_upload_path,
    degenerate_document_path_and_return_doc_name, get_signed_url, get_extension, file_is_less_than_5mb,
    file_is_image, file_is_pdf, sanitise_supplier_name, upload_declaration_documents
)
from dmutils.email.dm_notify import DMNotifyClient
from dmutils.email.exceptions import EmailError
from dmutils.email.helpers import hash_string
from dmutils.env_helpers import get_web_url_from_stage
from dmutils.flask import timed_render_template as render_template
from dmutils.formats import datetimeformat, displaytimeformat, monthyearformat, dateformat
from dmutils.forms.helpers import get_errors_from_wtform, remove_csrf_token, govuk_options
from dmutils.timing import logged_duration

from ... import data_api_client
from ...main import main, content_loader
from ..helpers import login_required
from ..helpers.frameworks import (
    check_agreement_is_related_to_supplier_framework_or_abort,
    count_drafts_by_lot,
    EnsureApplicationCompanyDetailsHaveBeenConfirmed,
    get_declaration_status,
    get_declaration_status_from_info,
    get_framework_and_lot_or_404,
    get_framework_for_reuse,
    get_framework_or_404,
    get_framework_or_500,
    get_last_modified_from_first_matching_file,
    get_statuses_for_lot,
    get_supplier_framework_info,
    get_supplier_on_framework_from_info,
    get_supplier_registered_name_from_declaration,
    register_interest_in_framework,
    return_supplier_framework_info_if_on_framework_or_abort,
    returned_agreement_email_recipients,
    return_404_if_applications_closed,
    check_framework_supports_e_signature_or_404,
    is_e_signature_supported_framework
)
from ..helpers.services import (
    get_drafts,
    get_lot_drafts,
    get_signed_document_url,
)
from ..helpers.suppliers import (
    supplier_company_details_are_complete,
    get_company_details_from_supplier,
    is_g12_recovery_supplier,
)
from ..helpers.validation import get_validator
from ..forms.frameworks import (SignerDetailsForm,
                                ContractReviewForm,
                                AcceptAgreementVariationForm,
                                ReuseDeclarationForm,
                                LegalAuthorityForm,
                                SignFrameworkAgreementForm)

CLARIFICATION_QUESTION_NAME = 'clarification_question'


MESSAGE_SENT_QS_OPEN_MESSAGE = (
    "Your clarification question has been sent. Answers to all clarification questions will be published on this page."
)

AGREEMENT_RETURNED_MESSAGE = (
    "Your framework agreement has been returned to the Crown Commercial Service to be countersigned."
)

CUSTOM_DIMENSION_IDENTIFIERS = {
    "supplierFrameworkApplicationStage": 29
}


@main.route('/frameworks/<framework_slug>', methods=['GET', 'POST'])
@login_required
def framework_dashboard(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug)
    framework_slug = framework['slug']  # cleaned slug from the API response that strips reserved characters
    update_framework_with_formatted_dates(framework)
    custom_dimensions, custom_dimension_stage = [], None
    if framework["status"] == "open":
        session["currently_applying_to"] = framework_slug

    framework_urls = content_loader.get_message(framework_slug, 'urls')

    if request.method == 'POST':
        register_interest_in_framework(data_api_client, framework_slug)
        supplier_users = data_api_client.find_users_iter(supplier_id=current_user.supplier_id)

        notify_client = DMNotifyClient()

        for address in [user['emailAddress'] for user in supplier_users if user['active']]:
            notify_client.send_email(
                to_email_address=address,
                template_name_or_id=notify_client.templates["framework-application-started"],
                personalisation={
                    'framework_name': framework['name'],
                    'framework_applications_close_date': framework['applicationsCloseAt'],
                    'framework_clarification_questions_close_date': framework['clarificationsCloseAt'],
                },
                reply_to_address_id=current_app.config['DM_ENQUIRIES_EMAIL_ADDRESS_UUID']
            )

    drafts, complete_drafts = get_drafts(data_api_client, framework_slug)

    supplier_framework_info = get_supplier_framework_info(data_api_client, framework_slug)
    declaration_status = get_declaration_status_from_info(supplier_framework_info)
    supplier_is_on_framework = get_supplier_on_framework_from_info(supplier_framework_info)
    supplier = data_api_client.get_supplier(current_user.supplier_id)['suppliers']

    # Do not show a framework dashboard for earlier G-Cloud iterations
    if declaration_status == 'unstarted' and framework['status'] == 'live':
        abort(404)

    application_company_details_confirmed = (
        supplier_framework_info and supplier_framework_info['applicationCompanyDetailsConfirmed']
    )
    application_made = (
        supplier_is_on_framework or (
            len(complete_drafts) > 0
            and declaration_status == 'complete'
            and application_company_details_confirmed
        )
    )
    lots_with_completed_drafts = [lot for lot in framework['lots'] if count_drafts_by_lot(complete_drafts, lot['slug'])]

    # GA custom dimension stages for the application
    if supplier_framework_info and not supplier_framework_info['applicationCompanyDetailsConfirmed']:
        custom_dimension_stage = "application_started"
    if application_company_details_confirmed:
        custom_dimension_stage = "company_details_confirmed"
    if declaration_status == 'complete':
        custom_dimension_stage = "declaration_confirmed"
    if complete_drafts:
        # At least one service has been confirmed
        custom_dimension_stage = "services_confirmed"
    if application_made:
        custom_dimension_stage = "application_confirmed"

    if custom_dimension_stage:
        custom_dimensions = [{
            'data_id': CUSTOM_DIMENSION_IDENTIFIERS['supplierFrameworkApplicationStage'],
            'data_value': custom_dimension_stage
        }]

    # filenames
    result_letter_filename = RESULT_LETTER_FILENAME

    countersigned_agreement_file = None
    if supplier_framework_info and supplier_framework_info['countersignedPath']:
        countersigned_agreement_file = degenerate_document_path_and_return_doc_name(
            supplier_framework_info['countersignedPath']
        )

    signed_agreement_document_name = None
    if supplier_is_on_framework and supplier_framework_info['agreementReturned']:
        # Frameworks supporting e-signature will not have agreementPath
        if supplier_framework_info['agreementPath']:
            signed_agreement_document_name = degenerate_document_path_and_return_doc_name(
                supplier_framework_info['agreementPath']
            )

    communications_folder = "{}/communications".format(framework_slug)
    key_list = s3.S3(current_app.config['DM_COMMUNICATIONS_BUCKET']).list(communications_folder, load_timestamps=True)
    key_list.reverse()

    base_communications_files = {
        "invitation": {
            "path": "communications/",
            "filename": "{}-invitation.pdf".format(framework_slug),
        },
        "proposed_agreement": {
            "path": "communications/",
            "filename": "{}-proposed-framework-agreement.pdf".format(framework_slug),
        },
        "final_agreement": {
            "path": "communications/",
            "filename": "{}-final-framework-agreement.pdf".format(framework_slug),
        },
        "proposed_call_off": {
            "path": "communications/",
            "filename": "{}-proposed-call-off.pdf".format(framework_slug),
        },
        "final_call_off": {
            "path": "communications/",
            "filename": "{}-final-call-off.pdf".format(framework_slug),
        },
        "reporting_template": {
            "path": "communications/",
            "filename": "{}-reporting-template.xls".format(framework_slug),
        },
        "supplier_updates": {
            "path": "communications/updates/",
        },
    }
    # now we annotate these with last_modified information which also tells us whether the file exists
    communications_files = {
        label: dict(
            d,
            last_modified=get_last_modified_from_first_matching_file(
                key_list,
                framework_slug,
                d["path"] + d.get("filename", ""),
            ),
        )
        for label, d in base_communications_files.items()
    }

    return render_template(
        "frameworks/dashboard.html",
        application_made=application_made,
        communications_files=communications_files,
        completed_lots=tuple(
            dict(lot, complete_count=count_drafts_by_lot(complete_drafts, lot['slug']))
            for lot in lots_with_completed_drafts
        ),
        countersigned_agreement_file=countersigned_agreement_file,
        counts={
            "draft": len(drafts),
            "complete": len(complete_drafts)
        },
        declaration_status=declaration_status,
        signed_agreement_document_name=signed_agreement_document_name,
        framework=framework,
        framework_urls=framework_urls,
        result_letter_filename=result_letter_filename,
        supplier_framework=supplier_framework_info,
        supplier_is_on_framework=supplier_is_on_framework,
        supplier_company_details_complete=supplier_company_details_are_complete(supplier),
        application_company_details_confirmed=application_company_details_confirmed,
        custom_dimensions=custom_dimensions,
        is_e_signature_supported_framework=is_e_signature_supported_framework(framework_slug)
    ), 200


@main.route('/frameworks/<framework_slug>/submissions', methods=['GET'])
@login_required
@EnsureApplicationCompanyDetailsHaveBeenConfirmed(data_api_client)
def framework_submission_lots(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug)

    drafts, complete_drafts = get_drafts(data_api_client, framework_slug)
    declaration_status = get_declaration_status(data_api_client, framework_slug)
    application_made = len(complete_drafts) > 0 and declaration_status == 'complete'
    if framework['status'] not in ["open", "pending", "standstill"]:
        abort(404)

    lots = [
        dict(lot,
             draft_count=count_drafts_by_lot(drafts, lot['slug']),
             complete_count=count_drafts_by_lot(complete_drafts, lot['slug']))
        for lot in framework['lots']]

    lot_question = {
        option["value"]: option
        for option in ContentQuestion(content_loader.get_question(framework_slug, 'services', 'lot')).get('options')
    }

    lots = [{
        "title": lot_question[lot['slug']]['label'] if framework["status"] == "open" else lot["name"],
        'body': lot_question[lot['slug']]['description'],
        "link": url_for('.framework_submission_services', framework_slug=framework_slug, lot_slug=lot['slug']),
        "statuses": get_statuses_for_lot(
            lot['oneServiceLimit'],
            lot['draft_count'],
            lot['complete_count'],
            declaration_status,
            framework['status'],
            lot['name'],
            lot['unitSingular'],
            lot['unitPlural']
        ),
    } for lot in lots if framework["status"] == "open" or (lot['draft_count'] + lot['complete_count']) > 0]

    return render_template(
        "frameworks/submission_lots.html",
        complete_drafts=list(reversed(complete_drafts)),
        drafts=list(reversed(drafts)),
        declaration_status=declaration_status,
        framework=framework,
        lots=lots,
        application_made=application_made
    ), 200


@main.route('/frameworks/<framework_slug>/draft-services', methods=['GET'])
@login_required
@EnsureApplicationCompanyDetailsHaveBeenConfirmed(data_api_client)
def g12_recovery_draft_services(framework_slug):
    if framework_slug != "g-cloud-12":
        abort(404)

    framework = get_framework_or_404(data_api_client, framework_slug)

    drafts, complete_drafts = get_drafts(data_api_client, framework_slug)
    declaration_status = get_declaration_status(data_api_client, framework_slug)
    application_made = len(complete_drafts) > 0 and declaration_status == 'complete'
    if framework['status'] != 'live':
        abort(404)

    if not is_g12_recovery_supplier(current_user.supplier_id):
        abort(404)

    lots = [
        dict(lot,
             draft_count=count_drafts_by_lot(drafts, lot['slug']),
             complete_count=count_drafts_by_lot(complete_drafts, lot['slug']))
        for lot in framework['lots']
    ]

    lot_question = {
        option["value"]: option
        for option in ContentQuestion(content_loader.get_question(framework_slug, 'services', 'lot')).get('options')
    }

    lots = [{
        "title": lot_question[lot['slug']]['label'],
        'body': lot_question[lot['slug']]['description'],
        "link": url_for('.framework_submission_services', framework_slug=framework_slug, lot_slug=lot['slug']),
        "statuses": get_statuses_for_lot(
            lot['oneServiceLimit'],
            lot['draft_count'],
            lot['complete_count'],
            declaration_status,
            "open",  # we want the statuses as if the framework were open
            lot['name'],
            lot['unitSingular'],
            lot['unitPlural']
        ),
    } for lot in lots]

    return render_template(
        "frameworks/submission_lots.html",
        complete_drafts=list(reversed(complete_drafts)),
        drafts=list(reversed(drafts)),
        declaration_status=declaration_status,
        framework=framework,
        lots=lots,
        application_made=application_made
    ), 200


@main.route('/frameworks/<framework_slug>/submissions/<lot_slug>', methods=['GET'])
@login_required
@EnsureApplicationCompanyDetailsHaveBeenConfirmed(data_api_client)
def framework_submission_services(framework_slug, lot_slug):
    framework, lot = get_framework_and_lot_or_404(data_api_client, framework_slug, lot_slug)

    if (
        framework_slug == "g-cloud-12"
        and framework["status"] == "live"
        and is_g12_recovery_supplier(current_user.supplier_id)
    ):
        # we want this page to appear as it would if g12 were open
        framework["status"] = "open"

    drafts, complete_drafts = get_lot_drafts(data_api_client, framework_slug, lot_slug)
    declaration_status = get_declaration_status(data_api_client, framework_slug)

    try:
        previous_framework_slug = content_loader.get_metadata(framework['slug'], 'copy_services', 'source_framework')
    except ContentNotFoundError:
        previous_framework_slug = None
        previous_services = []
        previous_framework = {}

    if previous_framework_slug:
        previous_framework = get_framework_or_500(data_api_client, previous_framework_slug, logger=current_app.logger)
        previous_services = data_api_client.find_services(
            supplier_id=current_user.supplier_id,
            framework=previous_framework_slug,
            lot=lot_slug,
            status='published',
        )["services"]

    previous_services_still_to_copy = not all(
        service['copiedToFollowingFramework'] for service in previous_services
    )

    if lot['oneServiceLimit']:
        draft = next(chain(drafts, complete_drafts), None)
        if not draft and previous_services_still_to_copy:
            return redirect(
                url_for('.previous_services', framework_slug=framework_slug, lot_slug=lot_slug)
            )

        elif not draft:
            draft = data_api_client.create_new_draft_service(
                framework_slug, lot_slug, current_user.supplier_id, {}, current_user.email_address,
            )['services']

        return redirect(
            url_for('.view_service_submission',
                    framework_slug=framework_slug, lot_slug=lot_slug, service_id=draft['id'])
        )

    lot_service_sections = content_loader.get_manifest(
        framework_slug,
        'edit_submission',
    ).filter(context={'lot': lot_slug}, inplace_allowed=True)

    with logged_duration(message="Annotated draft details in {duration_real}s"):
        for draft in drafts:
            sections = lot_service_sections.summary(draft, inplace_allowed=True)

            unanswered_required, unanswered_optional = count_unanswered_questions(sections)
            draft.update({
                'unanswered_required': unanswered_required,
                'unanswered_optional': unanswered_optional,
            })

    return render_template(
        "frameworks/services.html",
        previous_framework=previous_framework if previous_services_still_to_copy else None,
        complete_drafts=list(reversed(complete_drafts)),
        drafts=list(reversed(drafts)),
        declaration_status=declaration_status,
        framework=framework,
        lot=lot,
    ), 200


@main.route('/frameworks/<framework_slug>/declaration/start', methods=['GET'])
@login_required
@EnsureApplicationCompanyDetailsHaveBeenConfirmed(data_api_client)
@return_404_if_applications_closed(lambda: data_api_client)
def framework_start_supplier_declaration(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['open'])
    update_framework_with_formatted_dates(framework)

    return render_template("frameworks/start_declaration.html",
                           framework=framework), 200


# TODO: refactor this view to combine with reuse_framework_supplier_declaration_post
@main.route('/frameworks/<framework_slug>/declaration/reuse', methods=['GET'])
@login_required
@EnsureApplicationCompanyDetailsHaveBeenConfirmed(data_api_client)
@return_404_if_applications_closed(lambda: data_api_client)
def reuse_framework_supplier_declaration(framework_slug):
    """Attempt to find a supplier framework declaration that we can reuse.

    :param: framework_slug
    :query_param: reusable_declaration_framework_slug
    :return: 404, redirect or reuse page (frameworks/reuse_declaration.html)
    """
    reusable_declaration_framework_slug = request.args.get('reusable_declaration_framework_slug', None)
    supplier_id = current_user.supplier_id
    # Get the current framework.
    current_framework = data_api_client.get_framework(framework_slug)['frameworks']
    if reusable_declaration_framework_slug:
        # If a framework slug is supplied in this URL parameter then use this for pre-filling if possible,
        # overriding the default framework selection logic.
        try:
            # Get their old declaration to make sure it exists. The api will raise if it doesn't exist.
            data_api_client.get_supplier_framework_info(
                supplier_id, reusable_declaration_framework_slug
            )['frameworkInterest']['onFramework']
            old_framework = data_api_client.get_framework(reusable_declaration_framework_slug)['frameworks']
        except APIError:
            abort(404)
    else:
        # Otherwise then attempt to determine if they have a declaration we can offer for reuse.
        old_framework = get_framework_for_reuse(
            supplier_id,
            data_api_client,
            exclude_framework_slugs=[framework_slug]
        )
        if not old_framework:
            # If not then redirect to the overview. They do not have a suitable reuse candidate.
            return redirect(url_for('.framework_supplier_declaration_overview', framework_slug=framework_slug))

    # Otherwise offer to prefill the declaration.
    return render_template(
        "frameworks/reuse_declaration.html",
        current_framework=current_framework,
        form=ReuseDeclarationForm(),
        errors={},
        old_framework=old_framework,
        old_framework_application_close_date=monthyearformat(old_framework['applicationsCloseAtUTC']),
    ), 200


@main.route('/frameworks/<framework_slug>/declaration/reuse', methods=['POST'])
@login_required
@EnsureApplicationCompanyDetailsHaveBeenConfirmed(data_api_client)
@return_404_if_applications_closed(lambda: data_api_client)
def reuse_framework_supplier_declaration_post(framework_slug):
    """Set the prefill preference if a reusable framework slug is provided and redirect to declaration."""

    form = ReuseDeclarationForm()

    # If the form isn't valid they likely didn't select either way.
    if not form.validate_on_submit():
        # Bail and re-render form with errors.
        current_framework = data_api_client.get_framework(framework_slug)['frameworks']
        old_framework = data_api_client.get_framework(form.old_framework_slug.data)['frameworks']
        return render_template(
            "frameworks/reuse_declaration.html",
            current_framework=current_framework,
            form=form,
            errors=get_errors_from_wtform(form),
            old_framework=old_framework,
            old_framework_application_close_date=monthyearformat(old_framework['applicationsCloseAtUTC']),
        ), 400
    if form.reuse.data:
        # They clicked OK! Check the POST data.
        try:
            framework_ok = data_api_client.get_framework(
                form.old_framework_slug.data
            )['frameworks']['allowDeclarationReuse']
            declaration_ok = False  # Default value

            if framework_ok:
                declaration_ok = data_api_client.get_supplier_framework_info(
                    current_user.supplier_id, form.old_framework_slug.data
                )['frameworkInterest']['onFramework']

        except HTTPError:
            framework_ok = False
            declaration_ok = False

        if framework_ok and declaration_ok:
            # If it's OK then Set reuse on supplier framework.
            data_api_client.set_supplier_framework_prefill_declaration(
                current_user.supplier_id,
                framework_slug,
                form.old_framework_slug.data,
                current_user.email_address
            )
        else:
            # If it's not then fail out.
            abort(404)
    else:
        # If they use the back button to change their mind we need to set this.
        data_api_client.set_supplier_framework_prefill_declaration(
            current_user.supplier_id,
            framework_slug,
            None,
            current_user.email_address
        )
    return redirect(url_for('.framework_supplier_declaration_overview', framework_slug=framework_slug))


@main.route('/frameworks/<framework_slug>/declaration', methods=['GET'])
@login_required
@EnsureApplicationCompanyDetailsHaveBeenConfirmed(data_api_client)
def framework_supplier_declaration_overview(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=[
        "open",
        "pending",
        "standstill",
        "live",
        "expired",
    ])
    update_framework_with_formatted_dates(framework)

    sf = data_api_client.get_supplier_framework_info(current_user.supplier_id, framework_slug)["frameworkInterest"]
    # ensure our declaration is a a dict
    sf["declaration"] = sf.get("declaration") or {}

    if framework["status"] != "open" and sf["declaration"].get("status") != "complete":
        # 410 - the thinking here is that the user probably *used to* be able to access a page at this url but they
        # no longer can, so it's apparently "gone"
        abort(410)

    try:
        content = content_loader.get_manifest(
            framework_slug,
            'declaration',
        ).filter(sf["declaration"], inplace_allowed=True)
    except ContentNotFoundError:
        abort(404)

    # generate an (ordered) dict of the form {section_slug: (section, section_errors)}.
    # to perform validation per section.
    declaration_validator = get_validator(framework, content, sf["declaration"])

    sections_errors = OrderedDict()
    for section in content.summary(sf["declaration"]):
        errors = None
        if section.editable:
            errors = declaration_validator.get_error_messages_for_page(section)

        sections_errors[section.slug] = (section, errors)

    return render_template(
        "frameworks/declaration_overview.html",
        framework=framework,
        supplier_framework=sf,
        sections_errors=sections_errors,
        validates=not any(errors for section, errors in sections_errors.values()),
    ), 200


@main.route('/frameworks/<framework_slug>/declaration', methods=['POST'])
@login_required
@EnsureApplicationCompanyDetailsHaveBeenConfirmed(data_api_client)
@return_404_if_applications_closed(lambda: data_api_client)
def framework_supplier_declaration_submit(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['open'])

    sf = data_api_client.get_supplier_framework_info(current_user.supplier_id, framework_slug)["frameworkInterest"]
    # ensure our declaration is at least a dict
    sf["declaration"] = sf.get("declaration") or {}

    content = content_loader.get_manifest(
        framework_slug,
        'declaration',
    ).filter(sf["declaration"], inplace_allowed=True)

    validator = get_validator(framework, content, sf["declaration"])
    errors = validator.get_error_messages()
    if errors:
        abort(400, "This declaration has incomplete questions")

    sf["declaration"]["status"] = "complete"

    # unfortunately this can't be totally transactionally safe, but we can worry about that less because it should be
    # "impossible" to move a previously-"complete" declaration back to being non-"complete"

    data_api_client.set_supplier_declaration(
        current_user.supplier_id,
        framework["slug"],
        sf["declaration"],
        current_user.email_address,
    )

    return redirect(url_for('.framework_dashboard', framework_slug=framework['slug']))


@main.route('/frameworks/<framework_slug>/declaration/edit/<string:section_id>', methods=['GET', 'POST'])
@login_required
@EnsureApplicationCompanyDetailsHaveBeenConfirmed(data_api_client)
@return_404_if_applications_closed(lambda: data_api_client)
def framework_supplier_declaration_edit(framework_slug, section_id):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['open'])

    content = content_loader.get_manifest(framework_slug, 'declaration').filter({}, inplace_allowed=True)
    status_code = 200

    # Get and check the current section.
    section = content.get_section(section_id)
    if section is None or not section.editable:
        abort(404)
    # Do the same for the next section. This also implies whether or not we are on the last page of the declaration.
    next_section = content.get_section(content.get_next_section_id(section_id=section.id, only_editable=True))

    supplier_framework = data_api_client.get_supplier_framework_info(
        current_user.supplier_id, framework_slug)['frameworkInterest']
    saved_declaration = supplier_framework.get('declaration') or {}
    name_of_framework_that_section_has_been_prefilled_from = ""

    errors = {}
    if request.method == 'GET':
        section_errors = get_validator(
            framework,
            content,
            saved_declaration,
        ).get_error_messages_for_page(section)

        # If there are section_errors it means that this section has not previously been completed
        if section_errors and section.prefill and supplier_framework['prefillDeclarationFromFrameworkSlug']:
            # Fetch the old declaration to pre-fill from and pass it through
            # For now we pre-fill a whole section or none of the section
            # TODO: In future we may need to pre-fill individual questions and add a 'prefilled' flag to the questions
            try:
                prefill_from_slug = supplier_framework['prefillDeclarationFromFrameworkSlug']
                framework_to_reuse = data_api_client.get_framework(prefill_from_slug)['frameworks']
                declaration_to_reuse = data_api_client.get_supplier_declaration(
                    current_user.supplier_id,
                    prefill_from_slug
                )['declaration']
                all_answers = declaration_to_reuse
                name_of_framework_that_section_has_been_prefilled_from = framework_to_reuse['name']
            except APIError as e:
                if e.status_code != 404:
                    abort(e.status_code)
        else:
            all_answers = saved_declaration
    else:
        submitted_answers = section.get_data(request.form)

        # File fields won't be returned by `section.get_data` so handle these separately
        if request.files:
            documents_url = url_for('.dashboard', _external=True) + '/assets/'
            # This utils method filters out any empty documents and validates against service document rules
            uploaded_documents, document_errors = upload_declaration_documents(
                s3.S3(current_app.config['DM_DOCUMENTS_BUCKET']),
                'documents',
                documents_url,
                request.files,
                section,
                framework_slug,
                supplier_framework["supplierId"]
            )

            if document_errors:
                errors = section.get_error_messages(document_errors, question_descriptor_from="question")
            else:
                submitted_answers.update(uploaded_documents)

        validator = get_validator(framework, content, submitted_answers)

        # TODO: combine document errors with other validation errors
        # If no document errors, look for other errors
        if not errors:
            errors = validator.get_error_messages_for_page(section)
            # Handle bug for pre-existing files - the filepath value is not included in the POST data,
            # so this fails validation if the user has resubmitted without changes (or changed a different field).
            # If the user *does* change the file, any errors will be picked up by the 'document_errors' section above
            # (and this code won't be reached)
            if 'modernSlaveryStatement' in errors and saved_declaration.get('modernSlaveryStatement'):
                current_app.logger.info("Existing modern slavery statement file is unchanged")
                mutable_errors = {k: v for k, v in errors.items()}
                mutable_errors.pop('modernSlaveryStatement')
                errors = mutable_errors

        all_answers = dict(saved_declaration, **submitted_answers)

        if len(errors) > 0:
            status_code = 400
        else:
            if not all_answers.get("status"):
                all_answers.update({"status": "started"})

            data_api_client.set_supplier_declaration(
                current_user.supplier_id,
                framework_slug,
                all_answers,
                current_user.email_address
            )

            if next_section and not request.form.get('save_and_return_to_overview', False):
                # Go to the next section.
                return redirect(url_for(
                    '.framework_supplier_declaration_edit',
                    framework_slug=framework['slug'],
                    section_id=next_section.id
                ))
            else:
                # Otherwise they have reached the last page of their declaration.
                # Return to the overview.
                return redirect(url_for('.framework_supplier_declaration_overview', framework_slug=framework_slug))

    session_timeout = displaytimeformat(datetime.utcnow() + timedelta(hours=1))
    return render_template(
        "frameworks/edit_declaration_section.html",
        framework=framework,
        next_section=next_section,
        section=section,
        name_of_framework_that_section_has_been_prefilled_from=name_of_framework_that_section_has_been_prefilled_from,
        declaration_answers=all_answers,
        get_question=content.get_question,
        errors=errors,
        session_timeout=session_timeout
    ), status_code


@main.route('/frameworks/<framework_slug>/files/<path:filepath>', methods=['GET'])
@login_required
def download_supplier_file(framework_slug, filepath):
    uploader = s3.S3(current_app.config['DM_COMMUNICATIONS_BUCKET'])
    url = get_signed_document_url(uploader, "{}/communications/{}".format(framework_slug, filepath))
    if not url:
        abort(404)

    return redirect(url)


@main.route('/frameworks/<framework_slug>/agreements/<document_name>', methods=['GET'])
@login_required
def download_agreement_file(framework_slug, document_name):
    supplier_framework_info = get_supplier_framework_info(data_api_client, framework_slug)
    if supplier_framework_info is None or not supplier_framework_info.get("declaration"):
        abort(404)

    agreements_bucket = s3.S3(current_app.config['DM_AGREEMENTS_BUCKET'])
    path = get_document_path(framework_slug, current_user.supplier_id, 'agreements', document_name)
    url = get_signed_url(agreements_bucket, path, current_app.config['DM_ASSETS_URL'])
    if not url:
        abort(404)

    return redirect(url)


@main.route('/assets/<framework_slug>/documents/<int:supplier_id>/<document_name>', methods=['GET'])
@login_required
@EnsureApplicationCompanyDetailsHaveBeenConfirmed(data_api_client)
def download_declaration_document(framework_slug, supplier_id, document_name):
    """
    Equivalent to services.service_submission_document for retrieving declaration files uploaded to S3
    """
    if current_user.supplier_id != supplier_id:
        abort(404)

    uploader = s3.S3(current_app.config['DM_DOCUMENTS_BUCKET'])
    s3_url = get_signed_document_url(uploader, "{}/documents/{}/{}".format(framework_slug, supplier_id, document_name))
    if not s3_url:
        abort(404)

    return redirect(s3_url)


@main.route('/frameworks/<framework_slug>/updates', methods=['GET'])
@login_required
def framework_updates(framework_slug, error_message=None, default_textbox_value=None):
    framework = get_framework_or_404(data_api_client, framework_slug)
    update_framework_with_formatted_dates(framework)
    supplier_framework_info = get_supplier_framework_info(data_api_client, framework_slug)

    current_app.logger.info("{framework_slug}-updates.viewed: user_id {user_id} supplier_id {supplier_id}",
                            extra={'framework_slug': framework_slug,
                                   'user_id': current_user.id,
                                   'supplier_id': current_user.supplier_id})

    communications_bucket = s3.S3(current_app.config['DM_COMMUNICATIONS_BUCKET'])
    file_list = communications_bucket.list('{}/communications/updates/'.format(framework_slug), load_timestamps=True)
    files = {
        'communications': [],
        'clarifications': [],
    }
    for file in file_list:
        path_parts = file['path'].split('/')
        file['path'] = '/'.join(path_parts[2:])
        files[path_parts[3]].append(file)

    return render_template(
        "frameworks/updates.html",
        framework=framework,
        framework_urls=content_loader.get_message(framework_slug, 'urls'),
        clarification_question_name=CLARIFICATION_QUESTION_NAME,
        clarification_question_value=default_textbox_value,
        error_message=error_message,
        files=files,
        agreement_countersigned=bool(supplier_framework_info and supplier_framework_info['countersignedPath']),
    ), 200 if not error_message else 400


@main.route('/frameworks/<framework_slug>/updates', methods=['POST'])
@login_required
def framework_updates_email_clarification_question(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug)

    if not framework['clarificationQuestionsOpen']:
        # As of June 2019 suppliers cannot ask questions through the site after the deadline - a link to
        # the support page is shown instead.
        current_app.logger.warning("Attempted to send a clarification question after the deadline.")
        abort(400)

    # Stripped input should not empty
    clarification_question = request.form.get(CLARIFICATION_QUESTION_NAME, '').strip()

    if not clarification_question:
        return framework_updates(framework_slug, "Add text if you want to ask a question.")
    elif len(clarification_question) > 5000:
        return framework_updates(
            framework_slug,
            error_message="Question cannot be longer than 5000 characters",
            default_textbox_value=clarification_question
        )

    # Submit clarification email to CCS so the question can be answered
    # Fail noisily if this email does not send
    to_address = current_app.config['DM_CLARIFICATION_QUESTION_EMAIL']
    supplier = data_api_client.get_supplier(current_user.supplier_id)['suppliers']

    # Construct a reference ID from the date (YYYY-MM-DD) and a 'unique' hash of the time + question text.
    # e.g. 2019-07-01-8A99B2
    # This is a bit of a fudge as the users want a dated, anonymous reference that isn't too long.
    # Recent rates of question-asking are around 20/day, so truncating the hash to 6 characters shouldn't introduce
    # too many collisions, and is more likely to be unique than anything we can come up with on our own. If the platform
    # scales up to a higher rate of question-asking then we should review how this reference is constructed.
    now = datetime.utcnow()
    suffix = hash_string(now.strftime("%H:%M:%S.%f") + clarification_question)[:6].replace("-", "Y").replace("_", "Z")
    supplier_reference = "{}-{}".format(now.strftime("%Y-%m-%d"), suffix).upper()

    current_app.logger.info(
        "Preparing to send clarification question with supplier_reference {supplier_reference}",
        extra={"supplier_reference": supplier_reference},
    )

    personalisation = {
        "framework_name": framework['name'],
        "supplier_id": current_user.supplier_id,
        "supplier_name": supplier['name'],
        "supplier_reference": supplier_reference,
        "clarification_question": clarification_question
    }
    template = 'framework-clarification-question'
    reference = "fw-clarification-question-{}-{}".format(
        hash_string(clarification_question),
        hash_string(to_address),
    )

    notify_client = DMNotifyClient()
    try:
        notify_client.send_email(
            to_email_address=to_address,
            template_name_or_id=template,
            personalisation=personalisation,
            reference=reference,
            allow_resend=True,  # don't risk message getting swallowed
        )
    except EmailError as e:
        current_app.logger.error(
            "{framework} clarification question email failed to send. "
            "error {error} supplier_id {supplier_id} email_hash {email_hash}",
            extra={'error': str(e),
                   'framework': framework['slug'],
                   'supplier_id': current_user.supplier_id,
                   'email_hash': hash_string(current_user.email_address)})
        abort(503, "Clarification question email failed to send")

    # Send confirmation email to the user who submitted the question
    # No need to fail if this email does not send
    confirmation_email_personalisation = {
        'user_name': current_user.name,
        'framework_name': framework['name'],
        "supplier_reference": supplier_reference,
        'clarification_question_text': clarification_question,
    }

    try:
        notify_client.send_email(
            current_user.email_address,
            template_name_or_id='confirmation_of_clarification_question',
            personalisation=confirmation_email_personalisation,
            reference="fw-clarification-question-confirm-{}-{}".format(
                hash_string(clarification_question),
                hash_string(current_user.email_address),
            ),
            reply_to_address_id=current_app.config['DM_ENQUIRIES_EMAIL_ADDRESS_UUID'],
        )
    except EmailError as e:
        current_app.logger.error(
            "{code}: Clarification question confirm email for email_hash {email_hash} failed to send. "
            "Error: {error}",
            extra={
                'error': str(e),
                'email_hash': hash_string(current_user.email_address),
                'code': 'clarification-question-confirm-email.fail'
            })

    data_api_client.create_audit_event(
        audit_type=AuditTypes.send_clarification_question,
        user=current_user.email_address,
        object_type="suppliers",
        object_id=current_user.supplier_id,
        data={"question": clarification_question, 'framework': framework['slug']})

    flash(MESSAGE_SENT_QS_OPEN_MESSAGE, 'success')
    return framework_updates(framework['slug'])


@main.route('/frameworks/<framework_slug>/agreement', methods=['GET'])
@login_required
def framework_agreement(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['standstill', 'live'])
    supplier_framework = return_supplier_framework_info_if_on_framework_or_abort(data_api_client, framework_slug)

    if supplier_framework['agreementReturned']:
        supplier_framework['agreementReturnedAt'] = datetimeformat(
            date_parse(supplier_framework['agreementReturnedAt'])
        )

    def lot_result(drafts_for_lot):
        if any(draft['status'] == 'submitted' for draft in drafts_for_lot):
            return 'Successful'
        elif any(draft['status'] == 'failed' for draft in drafts_for_lot):
            return 'Unsuccessful'
        else:
            return 'No application'

    drafts, complete_drafts = get_drafts(data_api_client, framework_slug)
    complete_drafts_by_lot = {
        lot['slug']: [draft for draft in complete_drafts if draft['lotSlug'] == lot['slug']]
        for lot in framework['lots']
    }
    lot_results = {k: lot_result(v) for k, v in complete_drafts_by_lot.items()}

    return render_template(
        'frameworks/contract_start.html',
        signature_page_filename=SIGNATURE_PAGE_FILENAME,
        framework=framework,
        framework_urls=content_loader.get_message(framework_slug, 'urls'),
        lots=[{'name': lot['name'], 'result': lot_results[lot['slug']]} for lot in framework['lots']],
        supplier_framework=supplier_framework,
        supplier_registered_name=get_supplier_registered_name_from_declaration(supplier_framework['declaration']),
    ), 200


@main.route('/frameworks/<framework_slug>/create-agreement', methods=['POST'])
@login_required
def create_framework_agreement(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['standstill', 'live'])
    # if there's no frameworkAgreementVersion key it means we're pre-G-Cloud 8 and shouldn't be using this route
    if not framework.get('frameworkAgreementVersion'):
        abort(404)
    return_supplier_framework_info_if_on_framework_or_abort(data_api_client, framework_slug)

    agreement_id = data_api_client.create_framework_agreement(
        current_user.supplier_id, framework["slug"], current_user.email_address
    )["agreement"]["id"]

    return redirect(url_for('.signer_details', framework_slug=framework_slug, agreement_id=agreement_id))


@main.route('/frameworks/<framework_slug>/<int:agreement_id>/signer-details', methods=['GET', 'POST'])
@login_required
def signer_details(framework_slug, agreement_id):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['standstill', 'live'])
    # if there's no frameworkAgreementVersion key it means we're pre-G-Cloud 8 and shouldn't be using this route
    if not framework.get('frameworkAgreementVersion'):
        abort(404)

    supplier_framework = return_supplier_framework_info_if_on_framework_or_abort(data_api_client, framework_slug)
    agreement = data_api_client.get_framework_agreement(agreement_id)['agreement']
    check_agreement_is_related_to_supplier_framework_or_abort(agreement, supplier_framework)

    prefill_data = agreement.get("signedAgreementDetails", {})

    form = SignerDetailsForm(data=prefill_data)

    if form.validate_on_submit():
        agreement_details = {
            "signedAgreementDetails": remove_csrf_token(form.data)
        }
        data_api_client.update_framework_agreement(
            agreement_id, agreement_details, current_user.email_address
        )

        # If they have already uploaded a file then let them go to straight to the contract review
        # page as they are likely editing their signer details
        if agreement.get('signedAgreementPath'):
            return redirect(url_for(".contract_review", framework_slug=framework_slug, agreement_id=agreement_id))

        return redirect(url_for(".signature_upload", framework_slug=framework_slug, agreement_id=agreement_id))

    errors = get_errors_from_wtform(form)

    return render_template(
        "frameworks/signer_details.html",
        agreement=agreement,
        form=form,
        errors=errors,
        framework=framework,
        supplier_framework=supplier_framework,
        supplier_registered_name=get_supplier_registered_name_from_declaration(supplier_framework['declaration']),
    ), 400 if errors else 200


@main.route('/frameworks/<framework_slug>/<int:agreement_id>/signature-upload', methods=['GET', 'POST'])
@login_required
def signature_upload(framework_slug, agreement_id):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['standstill', 'live'])
    # if there's no frameworkAgreementVersion key it means we're pre-G-Cloud 8 and shouldn't be using this route
    if not framework.get('frameworkAgreementVersion'):
        abort(404)
    supplier_framework = return_supplier_framework_info_if_on_framework_or_abort(data_api_client, framework_slug)
    agreement = data_api_client.get_framework_agreement(agreement_id)['agreement']
    check_agreement_is_related_to_supplier_framework_or_abort(agreement, supplier_framework)

    agreements_bucket = s3.S3(current_app.config['DM_AGREEMENTS_BUCKET'])
    agreement_path = agreement.get('signedAgreementPath')
    existing_signature_page = agreements_bucket.get_key(agreement_path) if agreement_path else None
    upload_error = None
    if request.method == 'POST':
        fresh_signature_page = request.files.get('signature_page')

        # No file chosen for upload and file already exists on s3 so can use existing and progress
        if not (fresh_signature_page and fresh_signature_page.filename) and existing_signature_page:
            return redirect(url_for(".contract_review", framework_slug=framework_slug, agreement_id=agreement_id))

        # Validate file
        if not fresh_signature_page:
            upload_error = "You must choose a file to upload"
        elif not file_is_image(fresh_signature_page) and not file_is_pdf(fresh_signature_page):
            upload_error = "The file must be a PDF, JPG or PNG"
        elif not file_is_less_than_5mb(fresh_signature_page):
            upload_error = "The file must be less than 5MB"

        # If all looks good then upload the file and proceed to next step of signing
        if not upload_error:
            extension = get_extension(fresh_signature_page.filename)
            upload_path = generate_timestamped_document_upload_path(
                framework_slug,
                current_user.supplier_id,
                'agreements',
                '{}{}'.format(SIGNED_AGREEMENT_PREFIX, extension)
            )
            agreements_bucket.save(
                upload_path,
                fresh_signature_page,
                acl='bucket-owner-full-control',
                download_filename='{}-{}-{}{}'.format(
                    sanitise_supplier_name(current_user.supplier_name),
                    current_user.supplier_id,
                    SIGNED_SIGNATURE_PAGE_PREFIX,
                    extension
                ),
                disposition_type='inline'  # Embeddeding PDFs in admin pages requires 'inline' and not 'attachment'
            )

            data_api_client.update_framework_agreement(agreement_id, {"signedAgreementPath": upload_path},
                                                       current_user.email_address)

            session['signature_page'] = fresh_signature_page.filename

            return redirect(url_for(".contract_review", framework_slug=framework_slug, agreement_id=agreement_id))

    return render_template(
        "frameworks/signature_upload.html",
        agreement=agreement,
        framework=framework,
        signature_page=existing_signature_page,
        upload_error=upload_error,
    ), 400 if upload_error else 200


@main.route('/frameworks/<framework_slug>/<int:agreement_id>/contract-review', methods=['GET', 'POST'])
@login_required
def contract_review(framework_slug, agreement_id):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['standstill', 'live'])
    update_framework_with_formatted_dates(framework)
    # if there's no frameworkAgreementVersion key it means we're pre-G-Cloud 8 and shouldn't be using this route
    if not framework.get('frameworkAgreementVersion'):
        abort(404)
    supplier_framework = return_supplier_framework_info_if_on_framework_or_abort(data_api_client, framework_slug)
    agreement = data_api_client.get_framework_agreement(agreement_id)['agreement']
    check_agreement_is_related_to_supplier_framework_or_abort(agreement, supplier_framework)

    # if framework agreement doesn't have a name or a role or the agreement file, then 404
    if not (
        agreement.get('signedAgreementDetails')
        and agreement['signedAgreementDetails'].get('signerName')
        and agreement['signedAgreementDetails'].get('signerRole')
        and agreement.get('signedAgreementPath')
    ):
        abort(404)

    agreements_bucket = s3.S3(current_app.config['DM_AGREEMENTS_BUCKET'])
    signature_page = agreements_bucket.get_key(agreement['signedAgreementPath'])

    supplier_registered_name = get_supplier_registered_name_from_declaration(supplier_framework['declaration'])

    form = ContractReviewForm(supplier_registered_name=supplier_registered_name)

    if form.validate_on_submit():
        data_api_client.sign_framework_agreement(
            agreement_id, current_user.email_address, {'uploaderUserId': current_user.id}
        )

        notify_client = DMNotifyClient()
        for email_address in returned_agreement_email_recipients(supplier_framework):
            try:
                notify_client.send_email(
                    to_email_address=email_address,
                    template_name_or_id="framework_agreement_signature_page",
                    personalisation={
                        "framework_name": framework['name'],
                        "framework_slug": framework['slug'],
                        "framework_updates_url": (
                            get_web_url_from_stage(current_app.config["DM_ENVIRONMENT"])
                            + url_for(".framework_updates", framework_slug=framework["slug"])
                        ),
                    },
                    reference=f"contract-review-agreement-{hash_string(email_address)}"
                )
            except EmailError:
                # We don't need to handle this as the email is only informational,
                # and failures are already logged by DMNotifyClient
                pass

        session.pop('signature_page', None)

        flash(AGREEMENT_RETURNED_MESSAGE, "success")

        # Redirect to contract variation if it has not been signed
        if (framework.get('variations') and not supplier_framework['agreedVariations']):
            variation_slug = list(framework['variations'].keys())[0]
            return redirect(url_for(
                '.view_contract_variation',
                framework_slug=framework_slug,
                variation_slug=variation_slug
            ))

        return redirect(url_for(".framework_dashboard", framework_slug=framework_slug))

    errors = get_errors_from_wtform(form)

    return render_template(
        "frameworks/contract_review.html",
        agreement=agreement,
        form=form,
        errors=errors,
        framework=framework,
        signature_page=signature_page,
        supplier_framework=supplier_framework,
        supplier_registered_name=supplier_registered_name,
    ), 400 if errors else 200


@main.route('/frameworks/<framework_slug>/contract-variation/<variation_slug>', methods=['GET', 'POST'])
@login_required
def view_contract_variation(framework_slug, variation_slug):
    """
    This view asks suppliers to agree to a framework variation and then generates a confirmation email  when they do.
    """
    # TODO: create a variation template in Notify web UI before adding a variation to a framework in the API
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['live'])
    supplier_framework = return_supplier_framework_info_if_on_framework_or_abort(data_api_client, framework_slug)
    variation_details = framework.get('variations', {}).get(variation_slug)

    # 404 if framework doesn't have contract variation
    if not variation_details:
        abort(404)

    # 404 if agreement hasn't been returned yet
    if not supplier_framework['agreementReturned']:
        abort(404)

    agreed_details = supplier_framework['agreedVariations'].get(variation_slug, {})
    variation_content_name = 'contract_variation_{}'.format(variation_slug)
    content_loader.load_messages(framework_slug, [variation_content_name])
    form = AcceptAgreementVariationForm()

    supplier_name = get_supplier_registered_name_from_declaration(supplier_framework['declaration'])
    variation_content = content_loader.get_message(framework_slug, variation_content_name).filter(
        {'supplier_name': supplier_name}
    )

    # Do not call API or send email if already agreed to
    if not agreed_details.get("agreedAt") and form.validate_on_submit():
        # Set variation as agreed to in database
        data_api_client.agree_framework_variation(
            current_user.supplier_id,
            framework_slug,
            variation_slug,
            current_user.id,
            current_user.email_address
        )

        # Send email confirming accepted
        notify_client = DMNotifyClient()
        for address in returned_agreement_email_recipients(supplier_framework):
            notify_client.send_email(
                to_email_address=address,
                template_name_or_id=notify_client.templates[f'{framework_slug}_variation_{variation_slug}_agreed'],
                personalisation={'framework_name': framework_slug},
                reference=f"contract-variation-agreed-confirmation-{hash_string(address)}"
            )
        flash(variation_content.confirmation_message, "success")
        return redirect(url_for(".view_contract_variation",
                                framework_slug=framework_slug,
                                variation_slug=variation_slug)
                        )

    errors = get_errors_from_wtform(form)

    return render_template(
        "frameworks/contract_variation.html",
        form=form,
        errors=errors,
        framework=framework,
        supplier_framework=supplier_framework,
        variation_details=variation_details,
        variation=variation_content,
        agreed_details=agreed_details,
        supplier_name=supplier_name,
    ), 400 if errors else 200


@main.route('/frameworks/<framework_slug>/opportunities', methods=['GET'])
@login_required
def opportunities_dashboard_deprecated(framework_slug):
    return redirect(url_for('external.opportunities_dashboard', framework_slug=framework_slug), code=301)


@main.route('/frameworks/<framework_slug>/start-framework-agreement-signing', methods=['GET', 'POST'])
@login_required
def legal_authority(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['standstill', 'live'])
    check_framework_supports_e_signature_or_404(framework_slug)
    supplier_framework = get_supplier_framework_info(data_api_client, framework_slug)
    if not get_supplier_on_framework_from_info(supplier_framework):
        return render_error_page(status_code=400, error_message="You must be on the framework to sign the agreement.")
    form = LegalAuthorityForm()
    if form.validate_on_submit():
        response = form.legal_authority.data
        if response == 'no':
            return render_template("frameworks/legal_authority_no.html",
                                   framework=framework)
        if response == 'yes':
            return redirect(url_for('.sign_framework_agreement', framework_slug=framework_slug))
    errors = get_errors_from_wtform(form)
    field_name = "legal_authority"
    legal_authority_gov_uk_radios = {
        "fieldset":
            {"legend": {
                "text": LegalAuthorityForm.HEADING,
                "isPageHeading": "true",
                "classes": "govuk-fieldset__legend--l"
            }
            },
        "idPrefix": f"input-{field_name}",
        "name": field_name,
        "hint": {"text": LegalAuthorityForm.HINT},
        "classes": "govuk-radios--inline",
        "items": govuk_options(LegalAuthorityForm.OPTIONS),
        "errorMessage": errors.get(field_name)['errorMessage'] if errors else None
    }
    return render_template(
        "frameworks/legal_authority.html",
        framework_slug=framework_slug,
        framework=framework,
        form=form,
        errors=errors,
        legal_authority_gov_uk_radios=legal_authority_gov_uk_radios
    ), 400 if errors else 200


@main.route('/frameworks/<framework_slug>/sign-framework-agreement', methods=['GET', 'POST'])
@login_required
def sign_framework_agreement(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['standstill', 'live'])
    check_framework_supports_e_signature_or_404(framework_slug)
    supplier_framework = get_supplier_framework_info(data_api_client, framework_slug)
    if not get_supplier_on_framework_from_info(supplier_framework):
        return render_error_page(status_code=400, error_message="You must be on the framework to sign the agreement.")

    if not framework.get('frameworkAgreementVersion'):
        abort(404, error_message="The framework agreement was not found")

    supplier = data_api_client.get_supplier(current_user.supplier_id)["suppliers"]
    company_details = get_company_details_from_supplier(supplier)
    declaration = data_api_client.get_supplier_declaration(current_user.supplier_id, framework_slug)
    form = SignFrameworkAgreementForm()
    framework_pdf_url = content_loader.get_message(framework_slug, 'urls').get('framework_agreement_pdf_url')
    contract_titles = {
        'g-cloud-12': 'Framework Agreement',
        'digital-outcomes-and-specialists-5': 'Framework Agreement Form'
    }
    contract_title = contract_titles.get(framework_slug)

    # TODO: can we derive this metadata programmatically?
    framework_pdf_metadata = {
        'g-cloud-12': {'file_size': '487KB', 'page_count': 62}
    }
    lots = framework['lots']
    completed_lots = []
    for lot in lots:
        has_submitted = data_api_client.find_draft_services_by_framework(framework_slug=framework_slug,
                                                                         status="submitted",
                                                                         supplier_id=current_user.supplier_id,
                                                                         lot=lot['slug'],
                                                                         page=1)['meta']['total'] > 0
        if has_submitted:
            completed_lots.append(lot['name'])

    if form.validate_on_submit():
        # For an e-signature we create, update and sign the agreement immediately following submission
        agreement_id = data_api_client.create_framework_agreement(
            current_user.supplier_id, framework["slug"], current_user.email_address
        )["agreement"]["id"]

        signed_agreement_details = {k: v for k, v in form.data.items() if k in ['signerRole', 'signerName']}
        agreement_details = {
            "signedAgreementDetails": signed_agreement_details
        }

        data_api_client.update_framework_agreement(
            agreement_id, agreement_details, current_user.email_address
        )

        data_api_client.sign_framework_agreement(
            agreement_id, current_user.email_address, {'uploaderUserId': current_user.id}
        )

        # Send confirmation email
        supplier_users = data_api_client.find_users_iter(supplier_id=current_user.supplier_id)
        framework_dashboard_url = url_for('.framework_dashboard', framework_slug=framework_slug, _external=True)
        framework_live_date = dateformat(framework.get('frameworkLiveAtUTC'))
        notify_client = DMNotifyClient()
        for address in [user['emailAddress'] for user in supplier_users if user['active']]:
            notify_client.send_email(
                to_email_address=address,
                template_name_or_id="sign_framework_agreement_confirmation",
                personalisation={
                    "framework_name": framework['name'],
                    "signer_name": form.data.get('signerName'),
                    "company_name": company_details.get('registered_name'),
                    "contract_title": contract_title,
                    "submitted_datetime": datetimeformat(datetime.utcnow()),
                    "framework_dashboard_url": framework_dashboard_url,
                    "framework_live_date": framework_live_date
                },
            )

        return render_template("frameworks/sign_framework_agreement_confirmation.html",
                               framework=framework,
                               contract_title=contract_title)

    errors = get_errors_from_wtform(form)
    return render_template(
        "frameworks/sign_framework_agreement.html",
        company_details=company_details,
        declaration=declaration,
        framework_slug=framework_slug,
        contract_title=contract_title,
        framework_pdf_url=framework_pdf_url,
        framework_pdf_metadata=framework_pdf_metadata.get(framework_slug),
        framework=framework,
        completed_lots=completed_lots,
        form=form,
        errors=errors
    ), 400 if errors else 200
