# -*- coding: utf-8 -*-
from collections import OrderedDict
from datetime import datetime, timedelta

from dmutils.errors import render_error_page
from itertools import chain

from dmutils.forms.errors import govuk_errors
from flask import Markup, request, abort, flash, redirect, url_for, current_app, session
from flask_login import current_user

from dmapiclient import APIError, HTTPError
from dmapiclient.audit import AuditTypes
from dmcontent import govuk_frontend
from dmcontent.questions import ContentQuestion
from dmcontent.errors import ContentNotFoundError
from dmcontent.html import to_summary_list_row
from dmcontent.utils import count_unanswered_questions
from dmutils import s3
from dmutils.dates import update_framework_with_formatted_dates
from dmutils.documents import (
    RESULT_LETTER_FILENAME, get_document_path, degenerate_document_path_and_return_doc_name, get_signed_url,
    upload_declaration_documents
)
from dmutils.email.dm_notify import DMNotifyClient
from dmutils.email.exceptions import EmailError
from dmutils.email.helpers import hash_string
from dmutils.flask import timed_render_template as render_template
from dmutils.formats import datetimeformat, displaytimeformat, monthyearformat, dateformat
from dmutils.forms.helpers import get_errors_from_wtform, govuk_options
from dmutils.timing import logged_duration

from ... import data_api_client
from ...main import main, content_loader
from ..helpers import login_required
from ..helpers.frameworks import (
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
    get_completed_lots, get_framework_contract_title,
    question_references,
)
from ..helpers.services import (
    get_drafts,
    get_lot_drafts,
    get_signed_document_url,
)
from ..helpers.suppliers import supplier_company_details_are_complete, get_company_details_from_supplier
from ..helpers.validation import get_validator
from ..forms.frameworks import (AcceptAgreementVariationForm,
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
    contract_title = get_framework_contract_title(framework)

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
        contract_title=contract_title
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
        "slug": lot['slug'],
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


@main.route('/frameworks/<framework_slug>/submissions/service-type', methods=['GET', 'POST'])
@login_required
@EnsureApplicationCompanyDetailsHaveBeenConfirmed(data_api_client)
def choose_draft_service_lot(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug)

    if framework['status'] not in ["open"]:
        abort(404)

    errors = {}
    status_code = 200

    lot_question = {
        option["value"]: option
        for option in ContentQuestion(content_loader.get_question(framework_slug, 'services', 'lot')).get('options')
    }

    lots = [
        {
            "text": lot_question[lot['slug']]['label'] if framework["status"] == "open" else lot["name"],
            "value": lot['slug'],
            "hint": {
                "html": lot_question[lot['slug']]['description']
            }
        } for lot in framework['lots']
        if framework["status"] == "open" or (lot['draft_count'] + lot['complete_count']) > 0
    ]

    if request.method == 'POST':
        if "lot_slug" in request.form:
            return redirect(
                url_for(
                    ".framework_submission_services",
                    framework_slug=framework['slug'],
                    lot_slug=request.form['lot_slug']
                )
            )
        else:
            errors = {
                "lot_slug": {
                    "text": "Select a type of service",
                    "href": "#lot_slug-1",
                    "errorMessage": "Select a type of service"
                }
            }
            status_code = 400

    return render_template(
        "frameworks/choose_service_lot.html",
        framework=framework,
        lots=lots,
        errors=errors
    ), status_code


@main.route('/frameworks/<framework_slug>/submissions/<lot_slug>', methods=['GET'])
@login_required
@EnsureApplicationCompanyDetailsHaveBeenConfirmed(data_api_client)
def framework_submission_services(framework_slug, lot_slug):
    framework, lot = get_framework_and_lot_or_404(data_api_client, framework_slug, lot_slug)

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
    if form.reuse.data == "yes":
        # They clicked 'Yes'! Check the POST data.
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

        # Create govukSummaryList-friendly fields
        section.summary_list = []
        for question in section.questions:
            if sf["prefillDeclarationFromFrameworkSlug"] and section.prefill:
                question.empty_message = "Review answer"
            else:
                question.empty_message = "Answer question"
            section.summary_list.append(
                to_summary_list_row(
                    question,
                    action_link=url_for(
                        ".framework_supplier_declaration_edit",
                        framework_slug=framework_slug,
                        section_id=section.id,
                        _anchor=question.id if section.questions[0].id != question.id else None
                    ) if framework["status"] == "open" and sections_errors else None
                )
            )

        # We need to parse key text for question references. This isn't optimal, but references only apply to
        # this app, so holding off on centralising this logic to the Content Loader.
        def label_question_reference(row):
            row["key"]["text"] = question_references(row.get("key", {}).get("text", ""), section.get_question)
            return row
        section.summary_list = list(map(label_question_reference, section.summary_list))

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
                errors = govuk_errors(section.get_error_messages(document_errors, question_descriptor_from="question"))
            else:
                submitted_answers.update(uploaded_documents)

        validator = get_validator(framework, content, submitted_answers)

        # TODO: combine document errors with other validation errors
        # If no document errors, look for other errors
        if not errors:
            errors = govuk_errors(validator.get_error_messages_for_page(section))
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

    if errors:
        # On this page only, we want to show the question name in the error summary banner rather than
        # the error message that instructs users what to do. This is because the declaration questions
        # have many radio buttons per page and all the error messages are the same. It is more useful
        # for the user to see the question name than for them to see 'You must answer this question'
        # repeated many times.
        # Replace the error text with the question name. This changes the text in the summary box
        # and keeps the error message with instructions by the question.
        updated_errors = OrderedDict()
        for key, value in errors.items():
            value["text"] = value["question"]
            updated_errors[key] = value

        errors = updated_errors

    # prepare the govuk-frontend macro calls for this page with some customizations
    form_html = []
    for question in section.questions:
        h = govuk_frontend.from_question(question, all_answers, errors, is_page_heading=False)

        # we want to use a class to style numbered questions
        if "fieldset" in h:
            label_or_legend = h["fieldset"]["legend"]
            h["fieldset"]["classes"] = "dm-numbered-question {}".format(h['fieldset'].get('classes', ''))
        else:
            label_or_legend = h["label"]
            h["label"]["classes"] = "dm-numbered-question {}".format(h['label'].get('classes', ''))

        params = h["params"]

        # we allow question references in the question label, hint, and error message
        label_or_legend["text"] = question_references(label_or_legend["text"], content.get_question)
        if "hint" in params:
            params["hint"]["text"] = question_references(params["hint"]["text"], content.get_question)
        if "errorMessage" in params:
            params["errorMessage"]["text"] = question_references(params["errorMessage"]["text"], content.get_question)

        # we want question numbers in the label
        label_or_legend["html"] = (
            Markup(f'<span class="dm-numbered-question__number">{question.number}</span> ')
            + label_or_legend["text"]
        )
        del label_or_legend["text"]

        # we add a 'message' to each question which is prefilled
        if (
            (question.id not in errors)
            and name_of_framework_that_section_has_been_prefilled_from
            and (question.id in all_answers)
        ):
            # this is a misuse of error message component but I can't think of a better way right now
            params["formGroup"] = {"classes": "dm-form-group--notice"}
            params["errorMessage"] = {
                "classes": "dm-error-message--notice",
                "text": "This answer is from your {} declaration".format(
                    name_of_framework_that_section_has_been_prefilled_from),
                "visuallyHiddenText": "Notice",
            }

        form_html.append(h)

    session_timeout = displaytimeformat(datetime.utcnow() + timedelta(hours=1))
    return render_template(
        "frameworks/edit_declaration_section.html",
        framework=framework,
        next_section=next_section,
        section=section,
        name_of_framework_that_section_has_been_prefilled_from=name_of_framework_that_section_has_been_prefilled_from,
        declaration_answers=all_answers,
        get_question=content.get_question,
        form_html=form_html,
        render=govuk_frontend.render,
        errors=errors,
        session_timeout=session_timeout,
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

    errors = {CLARIFICATION_QUESTION_NAME: {
        "text": error_message,
        "href": "#" + CLARIFICATION_QUESTION_NAME,
        "errorMessage": error_message,
    }} if error_message else {}

    return render_template(
        "frameworks/updates.html",
        framework=framework,
        framework_urls=content_loader.get_message(framework_slug, 'urls'),
        clarification_question_name=CLARIFICATION_QUESTION_NAME,
        clarification_question_value=default_textbox_value,
        error_message=error_message,
        errors=errors,
        error_title="There was a problem with your submitted question",
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
        return framework_updates(framework_slug, error_message="Add text if you want to ask a question.")
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
    check_framework_supports_e_signature_or_404(framework)
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
    check_framework_supports_e_signature_or_404(framework)
    supplier_framework = get_supplier_framework_info(data_api_client, framework_slug)
    if not get_supplier_on_framework_from_info(supplier_framework):
        return render_error_page(status_code=400, error_message="You must be on the framework to sign the agreement.")

    if not framework.get('frameworkAgreementVersion'):
        abort(404, error_message="The framework agreement was not found")

    supplier = data_api_client.get_supplier(current_user.supplier_id)["suppliers"]
    company_details = get_company_details_from_supplier(supplier)
    declaration = data_api_client.get_supplier_declaration(current_user.supplier_id, framework_slug).get('declaration')
    framework_urls = content_loader.get_message(framework_slug, 'urls')
    contract_title = content_loader.get_message(framework_slug, 'e-signature', 'framework_contract_title')
    framework_specific_labels = {
        'g-cloud-12': {'title': 'Sign agreement',
                       'include_govuk_link': False},
        'digital-outcomes-and-specialists-5': {'title': 'Sign contract',
                                               'include_govuk_link': True}
    }

    # TODO: can we derive this metadata programmatically or from framework content? https://trello.com/c/lctIBcq9
    framework_file_metadata = {
        'g-cloud-12': {'file_size': '487KB',
                       'page_count': 62,
                       'file_extension': 'PDF',
                       'file_format': 'Portable Document Format'},
        'digital-outcomes-and-specialists-5': {'file_size': '48KB',
                                               'page_count': 10,
                                               'file_extension': 'ODT',
                                               'file_format': 'OpenDocument Text'}
    }

    form = SignFrameworkAgreementForm(contract_title)

    completed_lots = get_completed_lots(data_api_client, framework['lots'], framework_slug, current_user.supplier_id)

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
        title=framework_specific_labels.get(framework_slug).get('title'),
        contract_title=contract_title,
        include_govuk_link=framework_specific_labels.get(framework_slug).get('include_govuk_link'),
        framework_govuk_url=framework_urls.get('framework_agreement_url'),
        framework_file_url=framework_urls.get('framework_agreement_pdf_url'),
        framework_file_metadata=framework_file_metadata.get(framework_slug),
        framework=framework,
        completed_lots=completed_lots,
        form=form,
        errors=errors
    ), 400 if errors else 200
