# -*- coding: utf-8 -*-
import itertools

from dateutil.parser import parse as date_parse
from flask import render_template, request, abort, flash, redirect, url_for, current_app
from flask_login import current_user
import six

from dmapiclient import APIError
from dmapiclient.audit import AuditTypes
from dmutils.email import send_email, MandrillException
from dmcontent.formats import format_service_price
from dmutils.formats import datetimeformat
from dmutils import s3
from dmutils.documents import (
    RESULT_LETTER_FILENAME, AGREEMENT_FILENAME, SIGNED_AGREEMENT_PREFIX, COUNTERSIGNED_AGREEMENT_FILENAME,
    get_agreement_document_path, get_signed_url, get_extension, file_is_less_than_5mb, file_is_empty,
    sanitise_supplier_name,
)

from ... import data_api_client
from ...main import main, content_loader
from ..helpers import hash_email, login_required
from ..helpers.frameworks import (
    get_declaration_status, get_last_modified_from_first_matching_file, register_interest_in_framework,
    get_supplier_on_framework_from_info, get_declaration_status_from_info, get_supplier_framework_info,
    get_framework, get_framework_and_lot, count_drafts_by_lot, get_statuses_for_lot,
    countersigned_framework_agreement_exists_in_bucket
)
from ..helpers.validation import get_validator
from ..helpers.services import (
    get_signed_document_url, get_drafts, get_lot_drafts, count_unanswered_questions
)

CLARIFICATION_QUESTION_NAME = 'clarification_question'


@main.route('/frameworks/<framework_slug>', methods=['GET', 'POST'])
@login_required
def framework_dashboard(framework_slug):
    framework = get_framework(data_api_client, framework_slug)

    if request.method == 'POST':
        register_interest_in_framework(data_api_client, framework_slug)
        supplier_users = data_api_client.find_users(supplier_id=current_user.supplier_id)

        try:
            email_body = render_template('emails/{}_application_started.html'.format(framework_slug))
            send_email(
                [user['emailAddress'] for user in supplier_users['users'] if user['active']],
                email_body,
                current_app.config['DM_MANDRILL_API_KEY'],
                'You have started your {} application'.format(framework['name']),
                current_app.config['CLARIFICATION_EMAIL_FROM'],
                current_app.config['CLARIFICATION_EMAIL_NAME'],
                ['{}-application-started'.format(framework_slug)]
            )
        except MandrillException as e:
            current_app.logger.error(
                "Application started email failed to send: {error}, supplier_id: {supplier_id}",
                extra={'error': six.text_type(e), 'supplier_id': current_user.supplier_id}
            )

    drafts, complete_drafts = get_drafts(data_api_client, framework_slug)

    supplier_framework_info = get_supplier_framework_info(data_api_client, framework_slug)
    declaration_status = get_declaration_status_from_info(supplier_framework_info)
    supplier_is_on_framework = get_supplier_on_framework_from_info(supplier_framework_info)

    # Do not show a framework dashboard for earlier G-Cloud iterations
    if declaration_status == 'unstarted' and framework['status'] == 'live':
        abort(404)

    key_list = s3.S3(current_app.config['DM_COMMUNICATIONS_BUCKET']).list(framework_slug, load_timestamps=True)
    key_list.reverse()

    first_page = content_loader.get_manifest(
        framework_slug, 'declaration'
    ).get_next_editable_section_id()

    # filenames
    supplier_pack_filename = '{}-supplier-pack.zip'.format(framework_slug)
    result_letter_filename = RESULT_LETTER_FILENAME
    countersigned_agreement_file = None
    if countersigned_framework_agreement_exists_in_bucket(framework_slug, current_app.config['DM_AGREEMENTS_BUCKET']):
        countersigned_agreement_file = COUNTERSIGNED_AGREEMENT_FILENAME

    return render_template(
        "frameworks/dashboard.html",
        application_made=supplier_is_on_framework or (len(complete_drafts) > 0 and declaration_status == 'complete'),
        completed_lots=[{
            'name': lot['name'],
            'complete_count': count_drafts_by_lot(complete_drafts, lot['slug']),
            'one_service_limit': lot['oneServiceLimit'],
            'unit': 'lab' if framework['slug'] == 'digital-outcomes-and-specialists' else 'service',
            'unit_plural': 'labs' if framework['slug'] == 'digital-outcomes-and-specialists' else 'service'
            # TODO: ^ make this dynamic, eg, lab, service, unit
        } for lot in framework['lots'] if count_drafts_by_lot(complete_drafts, lot['slug'])],
        counts={
            "draft": len(drafts),
            "complete": len(complete_drafts)
        },
        dates=content_loader.get_message(framework_slug, 'dates'),
        declaration_status=declaration_status,
        first_page_of_declaration=first_page,
        framework=framework,
        last_modified={
            'supplier_pack': get_last_modified_from_first_matching_file(
                key_list, framework_slug, "communications/{}".format(supplier_pack_filename)
            ),
            'supplier_updates': get_last_modified_from_first_matching_file(
                key_list, framework_slug, "communications/updates/"
            )
        },
        supplier_is_on_framework=supplier_is_on_framework,
        supplier_pack_filename=supplier_pack_filename,
        result_letter_filename=result_letter_filename,
        countersigned_agreement_file=countersigned_agreement_file
    ), 200


@main.route('/frameworks/<framework_slug>/signing', methods=['GET'])
@login_required
def framework_signing(framework_slug):
    framework = get_framework(data_api_client, framework_slug, allowed_statuses=("standstill", "live", "expired",))

    if not framework.get("frameworkAgreementVersion"):
        # presumably an old pre-g8 framework that we don't want to enable this feature for
        abort(404)

    supplier_framework_info = get_supplier_framework_info(data_api_client, framework_slug)
    if not get_supplier_on_framework_from_info(supplier_framework_info):
        abort(404)

    drafts, complete_drafts = get_drafts(data_api_client, framework_slug)
    applied_lot_slugs = frozenset(draft["lotSlug"] for draft in complete_drafts)

    return render_template(
        "frameworks/signing.html",
        framework=framework,
        applied_lots=tuple(lot for lot in framework["lots"] if lot["slug"] in applied_lot_slugs),
        supplier_framework_info=supplier_framework_info,
    ), 200


@main.route('/frameworks/<framework_slug>/submissions', methods=['GET'])
@login_required
def framework_submission_lots(framework_slug):
    framework = get_framework(data_api_client, framework_slug)

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
        for option in content_loader.get_question(framework_slug, 'services', 'lot')['options']
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
    framework, lot = get_framework_and_lot(data_api_client, framework_slug, lot_slug)

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

    for draft in itertools.chain(drafts, complete_drafts):
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
        lot=lot
    ), 200


@main.route('/frameworks/<framework_slug>/declaration', methods=['GET'])
@main.route('/frameworks/<framework_slug>/declaration/<string:section_id>', methods=['GET', 'POST'])
@login_required
def framework_supplier_declaration(framework_slug, section_id=None):
    framework = get_framework(data_api_client, framework_slug, allowed_statuses=['open'])

    content = content_loader.get_manifest(framework_slug, 'declaration')
    status_code = 200

    if section_id is None:
        return redirect(
            url_for('.framework_supplier_declaration',
                    framework_slug=framework_slug,
                    section_id=content.get_next_editable_section_id()))

    section = content.get_section(section_id)
    if section is None or not section.editable:
        abort(404)

    is_last_page = section_id == content.sections[-1]['id']
    saved_answers = {}

    try:
        response = data_api_client.get_supplier_declaration(current_user.supplier_id, framework_slug)
        if response['declaration']:
            saved_answers = response['declaration']
    except APIError as e:
        if e.status_code != 404:
            abort(e.status_code)

    if request.method == 'GET':
        errors = {}
        all_answers = saved_answers
    else:
        submitted_answers = section.get_data(request.form)
        all_answers = dict(saved_answers, **submitted_answers)

        validator = get_validator(framework, content, submitted_answers)
        errors = validator.get_error_messages_for_page(section)

        if len(errors) > 0:
            status_code = 400
        else:
            validator = get_validator(framework, content, all_answers)
            if validator.get_error_messages():
                all_answers.update({"status": "started"})
            else:
                all_answers.update({"status": "complete"})
            try:
                data_api_client.set_supplier_declaration(
                    current_user.supplier_id,
                    framework_slug,
                    all_answers,
                    current_user.email_address
                )
                saved_answers = all_answers

                next_section = content.get_next_editable_section_id(section_id)
                if next_section:
                    return redirect(
                        url_for('.framework_supplier_declaration',
                                framework_slug=framework['slug'],
                                section_id=next_section))
                else:
                    url = "{}/declaration_complete".format(
                        url_for('.framework_dashboard',
                                framework_slug=framework['slug']))
                    flash(url, 'declaration_complete')
                    return redirect(
                        url_for('.framework_dashboard',
                                framework_slug=framework['slug']))
            except APIError as e:
                abort(e.status_code)

    return render_template(
        "frameworks/edit_declaration_section.html",
        framework=framework,
        section=section,
        declaration_answers=all_answers,
        is_last_page=is_last_page,
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
    path = get_agreement_document_path(framework_slug, current_user.supplier_id, document_name)
    url = get_signed_url(agreements_bucket, path, current_app.config['DM_ASSETS_URL'])
    if not url:
        abort(404)

    return redirect(url)


@main.route('/frameworks/<framework_slug>/updates', methods=['GET'])
@login_required
def framework_updates(framework_slug, error_message=None, default_textbox_value=None):
    framework = get_framework(data_api_client, framework_slug)

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
        agreement_countersigned=countersigned_framework_agreement_exists_in_bucket(
            framework_slug, current_app.config['DM_AGREEMENTS_BUCKET'])
    ), 200 if not error_message else 400


@main.route('/frameworks/<framework_slug>/updates', methods=['POST'])
@login_required
def framework_updates_email_clarification_question(framework_slug):
    framework = get_framework(data_api_client, framework_slug)

    # Stripped input should not empty
    clarification_question = request.form.get(CLARIFICATION_QUESTION_NAME, '').strip()

    if not clarification_question:
        return framework_updates(framework_slug, "Question cannot be empty")
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
            supplier_name=current_user.supplier_name,
            user_name=current_user.name,
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
    except MandrillException as e:
        current_app.logger.error(
            "{framework} clarification question email failed to send. "
            "error {error} supplier_id {supplier_id} email_hash {email_hash}",
            extra={'error': six.text_type(e),
                   'framework': framework['slug'],
                   'supplier_id': current_user.supplier_id,
                   'email_hash': hash_email(current_user.email_address)})
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
        except MandrillException as e:
            current_app.logger.error(
                "{framework} clarification question confirmation email failed to send. "
                "error {error} supplier_id {supplier_id} email_hash {email_hash}",
                extra={'error': six.text_type(e),
                       'framework': framework['slug'],
                       'supplier_id': current_user.supplier_id,
                       'email_hash': hash_email(current_user.email_address)})
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
    framework = get_framework(data_api_client, framework_slug, allowed_statuses=['standstill', 'live'])

    supplier_framework = data_api_client.get_supplier_framework_info(
        current_user.supplier_id, framework_slug
    )['frameworkInterest']
    if not supplier_framework['onFramework']:
        abort(404)

    if supplier_framework['agreementReturned']:
        supplier_framework['agreementReturnedAt'] = datetimeformat(
            date_parse(supplier_framework['agreementReturnedAt'])
        )

    return render_template(
        "frameworks/agreement.html",
        framework=framework,
        supplier_framework=supplier_framework,
        agreement_filename=AGREEMENT_FILENAME
    ), 200


@main.route('/frameworks/<framework_slug>/agreement', methods=['POST'])
@login_required
def upload_framework_agreement(framework_slug):
    framework = get_framework(data_api_client, framework_slug, allowed_statuses=['standstill', 'live'])

    supplier_framework = data_api_client.get_supplier_framework_info(
        current_user.supplier_id, framework_slug
    )['frameworkInterest']
    if not supplier_framework or not supplier_framework['onFramework']:
        abort(404)

    upload_error = None
    if not file_is_less_than_5mb(request.files['agreement']):
        upload_error = "Document must be less than 5Mb"
    elif file_is_empty(request.files['agreement']):
        upload_error = "Document must not be empty"

    if upload_error is not None:
        return render_template(
            "frameworks/agreement.html",
            framework=framework,
            supplier_framework=supplier_framework,
            upload_error=upload_error,
            agreement_filename=AGREEMENT_FILENAME
        ), 400

    agreements_bucket = s3.S3(current_app.config['DM_AGREEMENTS_BUCKET'])
    extension = get_extension(request.files['agreement'].filename)

    path = get_agreement_document_path(
        framework_slug,
        current_user.supplier_id,
        '{}{}'.format(SIGNED_AGREEMENT_PREFIX, extension)
    )
    agreements_bucket.save(
        path,
        request.files['agreement'],
        acl='private',
        download_filename='{}-{}-{}{}'.format(
            sanitise_supplier_name(current_user.supplier_name),
            current_user.supplier_id,
            SIGNED_AGREEMENT_PREFIX,
            extension
        )
    )

    data_api_client.register_framework_agreement_returned(
        current_user.supplier_id, framework_slug, current_user.email_address)

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
    except MandrillException as e:
        current_app.logger.error(
            "Framework agreement email failed to send. "
            "error {error} supplier_id {supplier_id} email_hash {email_hash}",
            extra={'error': six.text_type(e),
                   'supplier_id': current_user.supplier_id,
                   'email_hash': hash_email(current_user.email_address)})
        abort(503, "Framework agreement email failed to send")

    return redirect(url_for('.framework_agreement', framework_slug=framework_slug))
