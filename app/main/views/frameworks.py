# -*- coding: utf-8 -*-
from collections import OrderedDict
from itertools import chain

from dateutil.parser import parse as date_parse
from flask import render_template, request, abort, flash, redirect, url_for, current_app, session
from flask_login import current_user
import flask_featureflags as feature

from dmapiclient import APIError, HTTPError
from dmapiclient.audit import AuditTypes
from dmcontent.formats import format_service_price
from dmcontent.questions import ContentQuestion
from dmcontent.errors import ContentNotFoundError
from dmutils import s3
from dmutils.documents import (
    RESULT_LETTER_FILENAME, AGREEMENT_FILENAME, SIGNED_AGREEMENT_PREFIX, SIGNED_SIGNATURE_PAGE_PREFIX,
    SIGNATURE_PAGE_FILENAME, get_document_path, generate_timestamped_document_upload_path,
    degenerate_document_path_and_return_doc_name, get_signed_url, get_extension, file_is_less_than_5mb,
    file_is_empty, file_is_image, file_is_pdf, sanitise_supplier_name
)
from dmutils.email import send_email
from dmutils.email.exceptions import EmailError
from dmutils.email.helpers import hash_string
from dmutils.formats import datetimeformat

from ... import data_api_client, flask_featureflags
from ...main import main, content_loader
from ..helpers import login_required
from ..helpers.frameworks import (
    get_declaration_status, get_last_modified_from_first_matching_file, register_interest_in_framework,
    get_supplier_on_framework_from_info, get_declaration_status_from_info, get_supplier_framework_info,
    get_framework_or_404, get_framework_and_lot_or_404, count_drafts_by_lot, get_statuses_for_lot,
    return_supplier_framework_info_if_on_framework_or_abort, returned_agreement_email_recipients,
    check_agreement_is_related_to_supplier_framework_or_abort, get_framework_for_reuse,
)
from ..helpers.validation import get_validator
from ..helpers.services import (
    get_signed_document_url, get_drafts, get_lot_drafts, count_unanswered_questions
)
from ..forms.frameworks import SignerDetailsForm, ContractReviewForm, AcceptAgreementVariationForm, ReuseDeclarationForm

CLARIFICATION_QUESTION_NAME = 'clarification_question'


@main.route('/frameworks/<framework_slug>', methods=['GET', 'POST'])
@login_required
def framework_dashboard(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug)
    if request.method == 'POST':
        register_interest_in_framework(data_api_client, framework_slug)
        supplier_users = data_api_client.find_users(supplier_id=current_user.supplier_id)

        try:
            email_body = render_template('emails/{}_application_started.html'.format(framework_slug))
            send_email(
                [user['emailAddress'] for user in supplier_users['users'] if user['active']],
                email_body,
                current_app.config['DM_MANDRILL_API_KEY'],
                'You started a {} application'.format(framework['name']),
                current_app.config['CLARIFICATION_EMAIL_FROM'],
                current_app.config['CLARIFICATION_EMAIL_NAME'],
                ['{}-application-started'.format(framework_slug)]
            )
        except EmailError as e:
            current_app.logger.error(
                "Application started email failed to send: {error}, supplier_id: {supplier_id}",
                extra={'error': str(e), 'supplier_id': current_user.supplier_id}
            )

    drafts, complete_drafts = get_drafts(data_api_client, framework_slug)

    supplier_framework_info = get_supplier_framework_info(data_api_client, framework_slug)
    declaration_status = get_declaration_status_from_info(supplier_framework_info)
    supplier_is_on_framework = get_supplier_on_framework_from_info(supplier_framework_info)

    # Do not show a framework dashboard for earlier G-Cloud iterations
    if declaration_status == 'unstarted' and framework['status'] == 'live':
        abort(404)

    application_made = supplier_is_on_framework or (len(complete_drafts) > 0 and declaration_status == 'complete')
    lots_with_completed_drafts = [lot for lot in framework['lots'] if count_drafts_by_lot(complete_drafts, lot['slug'])]

    framework_dates = content_loader.get_message(framework_slug, 'dates')
    framework_urls = content_loader.get_message(framework_slug, 'urls')

    try:
        framework_advice = content_loader.get_message(framework_slug, 'advice')
    except ContentNotFoundError:
        framework_advice = None

    # filenames
    result_letter_filename = RESULT_LETTER_FILENAME

    countersigned_agreement_file = None
    if supplier_framework_info and supplier_framework_info['countersignedPath']:
        countersigned_agreement_file = degenerate_document_path_and_return_doc_name(
            supplier_framework_info['countersignedPath']
        )

    signed_agreement_document_name = None
    if supplier_is_on_framework and supplier_framework_info['agreementReturned']:
        signed_agreement_document_name = degenerate_document_path_and_return_doc_name(
            supplier_framework_info['agreementPath']
        )

    key_list = s3.S3(current_app.config['DM_COMMUNICATIONS_BUCKET']).list(framework_slug, load_timestamps=True)
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
        framework_dates=framework_dates,
        framework_urls=framework_urls,
        result_letter_filename=result_letter_filename,
        supplier_framework=supplier_framework_info,
        supplier_is_on_framework=supplier_is_on_framework,
        framework_advice=framework_advice,
    ), 200


@main.route('/frameworks/<framework_slug>/submissions', methods=['GET'])
@login_required
def framework_submission_lots(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug)

    drafts, complete_drafts = get_drafts(data_api_client, framework_slug)
    declaration_status = get_declaration_status(data_api_client, framework_slug)
    application_made = len(complete_drafts) > 0 and declaration_status == 'complete'
    if framework['status'] not in ["open", "pending", "standstill"]:
        abort(404)
    if framework['status'] == 'pending' and not application_made:
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
    ), 200


@main.route('/frameworks/<framework_slug>/submissions/<lot_slug>', methods=['GET'])
@login_required
def framework_submission_services(framework_slug, lot_slug):
    framework, lot = get_framework_and_lot_or_404(data_api_client, framework_slug, lot_slug)

    drafts, complete_drafts = get_lot_drafts(data_api_client, framework_slug, lot_slug)
    declaration_status = get_declaration_status(data_api_client, framework_slug)
    if framework['status'] == 'pending' and declaration_status != 'complete':
        abort(404)

    if lot['oneServiceLimit']:
        draft = next(iter(drafts + complete_drafts), None)
        if not draft:
            draft = data_api_client.create_new_draft_service(
                framework_slug, lot_slug, current_user.supplier_id, {}, current_user.email_address,
            )['services']

        return redirect(
            url_for('.view_service_submission',
                    framework_slug=framework_slug, lot_slug=lot_slug, service_id=draft['id'])
        )

    for draft in chain(drafts, complete_drafts):
        draft['priceString'] = format_service_price(draft)
        content = content_loader.get_manifest(framework_slug, 'edit_submission').filter(draft)
        sections = content.summary(draft)

        unanswered_required, unanswered_optional = count_unanswered_questions(sections)
        draft.update({
            'unanswered_required': unanswered_required,
            'unanswered_optional': unanswered_optional,
        })

    return render_template(
        "frameworks/services.html",
        complete_drafts=list(reversed(complete_drafts)),
        drafts=list(reversed(drafts)),
        declaration_status=declaration_status,
        framework=framework,
        lot=lot,
    ), 200


@main.route('/frameworks/<framework_slug>/declaration/start', methods=['GET'])
@login_required
def framework_start_supplier_declaration(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['open'])
    framework_close_date = content_loader.get_message(framework_slug, 'dates', 'framework_close_date')

    return render_template("frameworks/start_declaration.html",
                           framework=framework,
                           framework_close_date=framework_close_date), 200


@main.route('/frameworks/<framework_slug>/declaration/reuse', methods=['GET'])
@login_required
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
        old_framework=old_framework,
        old_framework_application_close_date=date_parse(old_framework['applicationCloseDate']).strftime('%B %Y'),
    ), 200


@main.route('/frameworks/<framework_slug>/declaration/reuse', methods=['POST'])
@login_required
def reuse_framework_supplier_declaration_post(framework_slug):
    """Set the prefill preference if a reusable framework slug is provided and redirect to declaration."""

    form = ReuseDeclarationForm(request.form)

    # If the form isn't valid they likely didn't select either way.
    if not form.validate_on_submit():
        # Bail and re-render form with errors.
        current_framework = data_api_client.get_framework(framework_slug)['frameworks']
        old_framework = data_api_client.get_framework(form.old_framework_slug.data)['frameworks']
        form_errors = [{'question': form[key].label.text, 'input_name': key} for key in form.errors]
        return render_template(
            "frameworks/reuse_declaration.html",
            current_framework=current_framework,
            form=form,
            form_errors=form_errors,
            old_framework=old_framework,
            old_framework_application_close_date=date_parse(old_framework['applicationCloseDate']).strftime('%B %Y')
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
def framework_supplier_declaration_overview(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=[
        "open",
        "pending",
        "standstill",
        "live",
        "expired",
    ])

    sf = data_api_client.get_supplier_framework_info(current_user.supplier_id, framework_slug)["frameworkInterest"]
    # ensure our declaration is a a dict
    sf["declaration"] = sf.get("declaration") or {}

    if framework["status"] != "open" and sf["declaration"].get("status") != "complete":
        # 410 - the thinking here is that the user probably *used to* be able to access a page at this url but they
        # no longer can, so it's apparently "gone"
        abort(410)

    try:
        content = content_loader.get_manifest(framework_slug, 'declaration').filter(sf["declaration"])
    except ContentNotFoundError:
        abort(404)

    # generate an (ordered) dict of the form {section_slug: (section, section_errors)}.
    # we must perform an actual validation for each section rather than rely on .answer_required as the latter won't
    # take into account declarations custom question dependencies
    sections_errors = OrderedDict(
        (
            section.slug,
            (
                section,
                section.editable and get_validator(
                    framework,
                    content,
                    sf["declaration"],
                ).get_error_messages_for_page(section),
            ),
        )
        for section in content.summary(sf["declaration"])
    )

    return render_template(
        "frameworks/declaration_overview.html",
        framework=framework,
        supplier_framework=sf,
        sections_errors=sections_errors,
        validates=not any(errors for section, errors in sections_errors.values()),
        framework_dates=content_loader.get_message(framework_slug, "dates"),
    ), 200


@main.route('/frameworks/<framework_slug>/declaration', methods=['POST'])
@login_required
def framework_supplier_declaration_submit(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['open'])

    sf = data_api_client.get_supplier_framework_info(current_user.supplier_id, framework_slug)["frameworkInterest"]
    # ensure our declaration is at least a dict
    sf["declaration"] = sf.get("declaration") or {}

    content = content_loader.get_manifest(framework_slug, 'declaration').filter(sf["declaration"])

    validator = get_validator(framework, content, sf["declaration"])
    errors = validator.get_error_messages()
    if errors:
        abort(400, "This declaration has incomplete questions")

    sf["declaration"]["status"] = "complete"

    # unfortunately this can't be totally transactionally safe, but we can worry about that less because it should be
    # "impossible" to move a previously-"complete" declaration back to being non-"complete"

    try:
        data_api_client.set_supplier_declaration(
            current_user.supplier_id,
            framework["slug"],
            sf["declaration"],
            current_user.email_address,
        )
    except APIError as e:
        abort(e.status_code)

    # follow existing flash message passing pattern
    flash_key = "{}/declaration_complete".format(url_for('.framework_dashboard', framework_slug=framework['slug']))
    flash(flash_key, 'declaration_complete')
    return redirect(url_for('.framework_dashboard', framework_slug=framework['slug']))


@main.route('/frameworks/<framework_slug>/declaration/edit/<string:section_id>', methods=['GET', 'POST'])
@login_required
def framework_supplier_declaration_edit(framework_slug, section_id):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['open'])

    content = content_loader.get_manifest(framework_slug, 'declaration').filter({})
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

    if request.method == 'GET':
        errors = {}

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
        all_answers = dict(saved_declaration, **submitted_answers)

        validator = get_validator(framework, content, submitted_answers)
        errors = validator.get_error_messages_for_page(section)

        if len(errors) > 0:
            status_code = 400
        else:
            if not all_answers.get("status"):
                all_answers.update({"status": "started"})
            try:
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
            except APIError as e:
                abort(e.status_code)

    return render_template(
        "frameworks/edit_declaration_section.html",
        framework=framework,
        next_section=next_section,
        section=section,
        name_of_framework_that_section_has_been_prefilled_from=name_of_framework_that_section_has_been_prefilled_from,
        declaration_answers=all_answers,
        get_question=content.get_question,
        errors=errors
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


@main.route('/frameworks/<framework_slug>/updates', methods=['GET'])
@login_required
def framework_updates(framework_slug, error_message=None, default_textbox_value=None):
    framework = get_framework_or_404(data_api_client, framework_slug)
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
        clarification_question_name=CLARIFICATION_QUESTION_NAME,
        clarification_question_value=default_textbox_value,
        error_message=error_message,
        files=files,
        dates=content_loader.get_message(framework_slug, 'dates'),
        agreement_countersigned=bool(supplier_framework_info and supplier_framework_info['countersignedPath']),
    ), 200 if not error_message else 400


@main.route('/frameworks/<framework_slug>/updates', methods=['POST'])
@login_required
def framework_updates_email_clarification_question(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug)

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

    # Submit email to Zendesk so the question can be answered
    # Fail if this email does not send
    if framework['clarificationQuestionsOpen']:
        subject = "{} clarification question".format(framework['name'])
        to_address = current_app.config['DM_CLARIFICATION_QUESTION_EMAIL']
        from_address = "suppliers+{}@digitalmarketplace.service.gov.uk".format(framework['slug'])
        email_body = render_template(
            "emails/clarification_question.html",
            supplier_id=current_user.supplier_id,
            message=clarification_question
        )
        tags = ["clarification-question"]
    else:
        subject = "{} application question".format(framework['name'])
        to_address = current_app.config['DM_FOLLOW_UP_EMAIL_TO']
        from_address = current_user.email_address
        email_body = render_template(
            "emails/follow_up_question.html",
            supplier_name=current_user.supplier_name,
            user_name=current_user.name,
            framework_name=framework['name'],
            message=clarification_question
        )
        tags = ["application-question"]
    try:
        send_email(
            to_address,
            email_body,
            current_app.config['DM_MANDRILL_API_KEY'],
            subject,
            current_app.config["DM_GENERIC_NOREPLY_EMAIL"],
            "{} Supplier".format(framework['name']),
            tags,
            reply_to=from_address,
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

    if framework['clarificationQuestionsOpen']:
        # Send confirmation email to the user who submitted the question
        # No need to fail if this email does not send
        subject = current_app.config['CLARIFICATION_EMAIL_SUBJECT']
        tags = ["clarification-question-confirm"]
        audit_type = AuditTypes.send_clarification_question
        email_body = render_template(
            "emails/clarification_question_submitted.html",
            user_name=current_user.name,
            framework_name=framework['name'],
            message=clarification_question
        )
        try:
            send_email(
                current_user.email_address,
                email_body,
                current_app.config['DM_MANDRILL_API_KEY'],
                subject,
                current_app.config['CLARIFICATION_EMAIL_FROM'],
                current_app.config['CLARIFICATION_EMAIL_NAME'],
                tags
            )
        except EmailError as e:
            current_app.logger.error(
                "{framework} clarification question confirmation email failed to send. "
                "error {error} supplier_id {supplier_id} email_hash {email_hash}",
                extra={'error': str(e),
                       'framework': framework['slug'],
                       'supplier_id': current_user.supplier_id,
                       'email_hash': hash_string(current_user.email_address)})
    else:
        # Do not send confirmation email to the user who submitted the question
        # Zendesk will handle this instead
        audit_type = AuditTypes.send_application_question

    data_api_client.create_audit_event(
        audit_type=audit_type,
        user=current_user.email_address,
        object_type="suppliers",
        object_id=current_user.supplier_id,
        data={"question": clarification_question, 'framework': framework['slug']})

    flash('message_sent', 'success')
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

    # if there's a frameworkAgreementVersion key, it means we're on G-Cloud 8 or higher
    if framework.get('frameworkAgreementVersion'):
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
            lots=[{
                'name': lot['name'],
                'result': lot_results[lot['slug']]
            } for lot in framework['lots']],
            supplier_framework=supplier_framework,
        ), 200

    return render_template(
        "frameworks/agreement.html",
        framework=framework,
        supplier_framework=supplier_framework,
        agreement_filename=AGREEMENT_FILENAME,
    ), 200


@main.route('/frameworks/<framework_slug>/agreement', methods=['POST'])
@login_required
def upload_framework_agreement(framework_slug):
    """
    This is the route used to upload agreements for pre-G-Cloud 8 frameworks
    """
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['standstill', 'live'])
    # if there's a frameworkAgreementVersion key it means we're on G-Cloud 8 or higher and shouldn't be using this route
    if framework.get('frameworkAgreementVersion'):
        abort(404)

    supplier_framework = return_supplier_framework_info_if_on_framework_or_abort(data_api_client, framework_slug)

    upload_error = None
    if not file_is_less_than_5mb(request.files['agreement']):
        upload_error = "Document must be less than 5MB"
    elif file_is_empty(request.files['agreement']):
        upload_error = "Document must not be empty"

    if upload_error is not None:
        return render_template(
            "frameworks/agreement.html",
            framework=framework,
            supplier_framework=supplier_framework,
            upload_error=upload_error,
            agreement_filename=AGREEMENT_FILENAME,
        ), 400

    agreements_bucket = s3.S3(current_app.config['DM_AGREEMENTS_BUCKET'])
    extension = get_extension(request.files['agreement'].filename)

    path = generate_timestamped_document_upload_path(
        framework_slug,
        current_user.supplier_id,
        'agreements',
        '{}{}'.format(SIGNED_AGREEMENT_PREFIX, extension)
    )
    agreements_bucket.save(
        path,
        request.files['agreement'],
        acl='bucket-owner-full-control',
        download_filename='{}-{}-{}{}'.format(
            sanitise_supplier_name(current_user.supplier_name),
            current_user.supplier_id,
            SIGNED_AGREEMENT_PREFIX,
            extension
        )
    )

    agreement_id = data_api_client.create_framework_agreement(
        current_user.supplier_id, framework_slug, current_user.email_address
    )['agreement']['id']
    data_api_client.update_framework_agreement(
        agreement_id, {"signedAgreementPath": path}, current_user.email_address
    )
    data_api_client.sign_framework_agreement(
        agreement_id, current_user.email_address, {"uploaderUserId": current_user.id}
    )

    try:
        email_body = render_template(
            'emails/framework_agreement_uploaded.html',
            framework_name=framework['name'],
            supplier_name=current_user.supplier_name,
            supplier_id=current_user.supplier_id,
            user_name=current_user.name
        )
        send_email(
            current_app.config['DM_FRAMEWORK_AGREEMENTS_EMAIL'],
            email_body,
            current_app.config['DM_MANDRILL_API_KEY'],
            '{} framework agreement'.format(framework['name']),
            current_app.config["DM_GENERIC_NOREPLY_EMAIL"],
            '{} Supplier'.format(framework['name']),
            ['{}-framework-agreement'.format(framework_slug)],
            reply_to=current_user.email_address,
        )
    except EmailError as e:
        current_app.logger.error(
            "Framework agreement email failed to send. "
            "error {error} supplier_id {supplier_id} email_hash {email_hash}",
            extra={'error': str(e),
                   'supplier_id': current_user.supplier_id,
                   'email_hash': hash_string(current_user.email_address)})
        abort(503, "Framework agreement email failed to send")

    return redirect(url_for('.framework_agreement', framework_slug=framework_slug))


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

    form = SignerDetailsForm()

    question_keys = ['signerName', 'signerRole']
    form_errors = {}

    if request.method == 'POST':

        if form.validate_on_submit():
            agreement_details = {
                "signedAgreementDetails": {
                    question_key: form[question_key].data for question_key in question_keys
                }
            }
            data_api_client.update_framework_agreement(
                agreement_id, agreement_details, current_user.email_address
            )

            # If they have already uploaded a file then let them go to straight to the contract review
            # page as they are likely editing their signer details
            if agreement.get('signedAgreementPath'):
                return redirect(url_for(".contract_review", framework_slug=framework_slug, agreement_id=agreement_id))

            return redirect(url_for(".signature_upload", framework_slug=framework_slug, agreement_id=agreement_id))
        else:
            error_keys_in_order = [key for key in question_keys if key in form.errors.keys()]
            form_errors = [
                {'question': form[key].label.text, 'input_name': key} for key in error_keys_in_order
            ]

    # if the signer* keys exist, prefill them in the form
    if agreement.get('signedAgreementDetails'):
        for question_key in question_keys:
            if question_key in agreement['signedAgreementDetails']:
                form[question_key].data = agreement['signedAgreementDetails'][question_key]

    return render_template(
        "frameworks/signer_details.html",
        agreement=agreement,
        form=form,
        form_errors=form_errors,
        framework=framework,
        question_keys=question_keys,
        supplier_framework=supplier_framework,
    ), 400 if form_errors else 200


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
        elif file_is_empty(fresh_signature_page):
            upload_error = "The file must not be empty"

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

    form = ContractReviewForm()
    form_errors = None

    if request.method == 'POST':
        if form.validate_on_submit():
            data_api_client.sign_framework_agreement(
                agreement_id, current_user.email_address, {'uploaderUserId': current_user.id}
            )

            try:
                email_body = render_template(
                    'emails/framework_agreement_with_framework_version_returned.html',
                    framework_name=framework['name'],
                    framework_slug=framework['slug'],
                    framework_live_date=content_loader.get_message(framework_slug, 'dates')['framework_live_date'],  # noqa
                )

                send_email(
                    returned_agreement_email_recipients(supplier_framework),
                    email_body,
                    current_app.config['DM_MANDRILL_API_KEY'],
                    'Your {} signature page has been received'.format(framework['name']),
                    current_app.config["DM_GENERIC_NOREPLY_EMAIL"],
                    current_app.config["FRAMEWORK_AGREEMENT_RETURNED_NAME"],
                    ['{}-framework-agreement'.format(framework_slug)],
                )
            except EmailError as e:
                current_app.logger.error(
                    "Framework agreement email failed to send. "
                    "error {error} supplier_id {supplier_id} email_hash {email_hash}",
                    extra={'error': str(e),
                           'supplier_id': current_user.supplier_id,
                           'email_hash': hash_string(current_user.email_address)})
                abort(503, "Framework agreement email failed to send")

            session.pop('signature_page', None)

            flash(
                'Your framework agreement has been returned to the Crown Commercial Service to be countersigned.',
                'success'
            )

            if feature.is_active('CONTRACT_VARIATION'):
                # Redirect to contract variation if it has not been signed
                if (framework.get('variations') and not supplier_framework['agreedVariations']):
                    variation_slug = list(framework['variations'].keys())[0]
                    return redirect(url_for(
                        '.view_contract_variation',
                        framework_slug=framework_slug,
                        variation_slug=variation_slug
                    ))

            return redirect(url_for(".framework_dashboard", framework_slug=framework_slug))

        else:
            form_errors = [
                {'question': form['authorisation'].label.text, 'input_name': 'authorisation'}
            ]

    form.authorisation.description = u"I have the authority to return this agreement on behalf of {}.".format(
        supplier_framework['declaration']['nameOfOrganisation']
    )

    return render_template(
        "frameworks/contract_review.html",
        agreement=agreement,
        form=form,
        form_errors=form_errors,
        framework=framework,
        signature_page=signature_page,
        supplier_framework=supplier_framework,
    ), 400 if form_errors else 200


@main.route('/frameworks/<framework_slug>/contract-variation/<variation_slug>', methods=['GET', 'POST'])
@flask_featureflags.is_active_feature('CONTRACT_VARIATION')
@login_required
def view_contract_variation(framework_slug, variation_slug):
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
    form_errors = None

    # Do not call API or send email if already agreed to
    if request.method == 'POST' and not agreed_details.get("agreedAt"):
        if form.validate_on_submit():
            # Set variation as agreed to in database
            data_api_client.agree_framework_variation(
                current_user.supplier_id,
                framework_slug,
                variation_slug,
                current_user.id,
                current_user.email_address
            )

            # Send email confirming accepted
            try:
                email_body = render_template(
                    'emails/{}_variation_{}_agreed.html'.format(framework_slug, variation_slug)
                )
                send_email(
                    returned_agreement_email_recipients(supplier_framework),
                    email_body,
                    current_app.config['DM_MANDRILL_API_KEY'],
                    '{}: you have accepted the proposed contract variation'.format(framework['name']),
                    current_app.config['CLARIFICATION_EMAIL_FROM'],
                    current_app.config['CLARIFICATION_EMAIL_NAME'],
                    ['{}-variation-accepted'.format(framework_slug)]
                )
            except EmailError as e:
                current_app.logger.error(
                    "Variation agreed email failed to send: {error}, supplier_id: {supplier_id}",
                    extra={'error': str(e), 'supplier_id': current_user.supplier_id}
                )
            flash('variation_accepted')
            return redirect(url_for(".view_contract_variation",
                                    framework_slug=framework_slug,
                                    variation_slug=variation_slug)
                            )
        else:
            form_errors = [
                {'question': form['accept_changes'].label.text, 'input_name': 'accept_changes'}
            ]

    supplier_name = supplier_framework['declaration']['nameOfOrganisation']
    variation_content = content_loader.get_message(framework_slug, variation_content_name).filter(
        {'supplier_name': supplier_name}
    )

    return render_template(
        "frameworks/contract_variation.html",
        form=form,
        form_errors=form_errors,
        framework=framework,
        supplier_framework=supplier_framework,
        variation_details=variation_details,
        variation=variation_content,
        agreed_details=agreed_details,
        supplier_name=supplier_name,
    ), 400 if form_errors else 200


@main.route('/frameworks/<framework_slug>/opportunities', methods=['GET'])
@login_required
def opportunities_dashboard_deprecated(framework_slug):
    return redirect(url_for('external.opportunities_dashboard', framework_slug=framework_slug), code=301)
