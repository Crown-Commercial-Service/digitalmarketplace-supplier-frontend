import itertools

from flask import render_template, request, abort, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
import six

from dmutils.apiclient import APIError
from dmutils.audit import AuditTypes
from dmutils import flask_featureflags
from dmutils.email import send_email, MandrillException
from dmutils.formats import format_service_price
from dmutils import s3

from ... import data_api_client
from ...main import main, declaration_content, new_service_content
from ..helpers import hash_email
from ..helpers.frameworks import get_error_messages_for_page, get_first_question_index, \
    get_error_messages, get_declaration_status, get_last_modified_from_first_matching_file, \
    g_cloud_7_is_open_or_404, register_interest_in_framework
from ..helpers.services import (
    get_draft_document_url, get_service_attributes, get_drafts,
    count_unanswered_questions
)


CLARIFICATION_QUESTION_NAME = 'clarification_question'


@main.route('/frameworks/g-cloud-7', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_dashboard():
    template_data = main.config['BASE_TEMPLATE_DATA']

    try:
        register_interest_in_framework(data_api_client, 'g-cloud-7')
    except APIError as e:
        abort(e.status_code)

    drafts, complete_drafts = get_drafts(data_api_client, current_user.supplier_id, 'g-cloud-7')
    declaration_status = get_declaration_status(data_api_client)

    key_list = s3.S3(current_app.config['DM_G7_DRAFT_DOCUMENTS_BUCKET']).list('g-cloud-7-')
    # last_modified files will be first
    key_list.reverse()

    return render_template(
        "frameworks/dashboard.html",
        counts={
            "draft": len(drafts),
            "complete": len(complete_drafts),
        },
        declaration_status=declaration_status,
        deadline=current_app.config['G7_CLOSING_DATE'],
        g7_status=data_api_client.get_framework_status('g-cloud-7').get('status', None),
        last_modified={
            'supplier_pack': get_last_modified_from_first_matching_file(key_list, 'g-cloud-7-supplier-pack.zip'),
            'supplier_updates': get_last_modified_from_first_matching_file(key_list, 'g-cloud-7-updates/')
        },

        **template_data
    ), 200


@main.route('/frameworks/g-cloud-7/services', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_services():
    template_data = main.config['BASE_TEMPLATE_DATA']

    drafts, complete_drafts = get_drafts(data_api_client, current_user.supplier_id, 'g-cloud-7')

    for draft in itertools.chain(drafts, complete_drafts):
        draft['priceString'] = format_service_price(draft)
        content = new_service_content.get_builder().filter(draft)
        sections = get_service_attributes(draft, content)

        unanswered_required, unanswered_optional = count_unanswered_questions(sections)
        draft.update({
            'unanswered_required': unanswered_required,
            'unanswered_optional': unanswered_optional,
        })

    return render_template(
        "frameworks/services.html",
        complete_drafts=list(reversed(complete_drafts)),
        drafts=list(reversed(drafts)),
        declaration_status=get_declaration_status(data_api_client),
        g7_status=data_api_client.get_framework_status('g-cloud-7').get('status', None),
        **template_data
    ), 200


@main.route('/frameworks/g-cloud-7/declaration/<string:section_id>',
            methods=['GET', 'POST'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_supplier_declaration(section_id):
    g_cloud_7_is_open_or_404(data_api_client)

    template_data = main.config['BASE_TEMPLATE_DATA']
    content = declaration_content.get_builder()
    status_code = 200

    section = content.get_section(section_id)
    if section is None or not section.editable:
        abort(404)

    is_last_page = section_id == content.sections[-1]['id']

    try:
        response = data_api_client.get_selection_answers(
            current_user.supplier_id, 'g-cloud-7')
        latest_answers = response['selectionAnswers']['questionAnswers']
    except APIError as e:
        if e.status_code != 404:
            abort(e.status_code)
        latest_answers = {}

    if request.method == 'POST':
        answers = content.get_all_data(request.form)
        errors = get_error_messages_for_page(content, answers, section)
        if len(errors) > 0:
            status_code = 400
        else:
            latest_answers.update(answers)
            if get_error_messages(content, latest_answers):
                latest_answers.update({"status": "started"})
            else:
                latest_answers.update({"status": "complete"})
            try:
                data_api_client.answer_selection_questions(
                    current_user.supplier_id,
                    'g-cloud-7',
                    latest_answers,
                    current_user.email_address
                )

                next_section = content.get_next_editable_section_id(section_id)
                if next_section:
                    return redirect(url_for('.framework_supplier_declaration', section_id=next_section))
                else:
                    return redirect(url_for('.framework_dashboard', declaration_completed='true'))
            except APIError as e:
                abort(e.status_code)
    else:
        answers = latest_answers
        errors = {}

    return render_template(
        "frameworks/edit_declaration_section.html",
        section=section,
        service_data=answers,
        is_last_page=is_last_page,
        first_question_index=get_first_question_index(content, section),
        errors=errors,
        **template_data
    ), status_code


@main.route('/frameworks/g-cloud-7/<path:filepath>', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def download_supplier_file(filepath):
    url = get_draft_document_url(filepath)
    if not url:
        abort(404)

    return redirect(url)


@main.route('/frameworks/g-cloud-7/updates', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_updates(error_message=None, default_textbox_value=None):

    current_app.logger.info("g7updates.viewed: user_id {user_id} supplier_id {supplier_id}",
                            extra={'user_id': current_user.id,
                                   'supplier_id': current_user.supplier_id})

    template_data = main.config['BASE_TEMPLATE_DATA']

    file_list = s3.S3(current_app.config['DM_G7_DRAFT_DOCUMENTS_BUCKET']).list('g-cloud-7-updates/')

    sections = [
        {
            'section': 'communications',
            'heading': "G-Cloud 7 communications",
            'empty_message': "No communications have been sent out",
            'files': []
        },
        {
            'section': 'clarifications',
            'heading': "G-Cloud 7 clarification questions and answers",
            'empty_message': "No clarification questions and answers have been posted yet",
            'files': []
        }
    ]

    for section in sections:
        section['files'] = [file for file in file_list if section['section'] == file['path'].split('/')[1]]

    return render_template(
        "frameworks/updates.html",
        clarification_question_name=CLARIFICATION_QUESTION_NAME,
        clarification_question_value=default_textbox_value,
        error_message=error_message,
        sections=sections,
        **template_data
    ), 200 if not error_message else 400


@main.route('/frameworks/g-cloud-7/updates', methods=['POST'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_updates_email_clarification_question():

    # Stripped input should not empty
    clarification_question = request.form.get(CLARIFICATION_QUESTION_NAME, '').strip()

    if not clarification_question:
        return framework_updates("Question cannot be empty")
    elif len(clarification_question) > 5000:
        return framework_updates(
            error_message="Question cannot be longer than 5000 characters",
            default_textbox_value=clarification_question
        )

    # Submit email to Zendesk so the question can be answered
    # Fail if this email does not send
    if flask_featureflags.is_active('G7_CLARIFICATIONS_CLOSED'):
        subject = "G-Cloud 7 application question"
        to_address = current_app.config['DM_G7_FOLLOW_UP_EMAIL_TO']
        from_address = current_user.email_address
        email_body = render_template(
            "emails/g7_follow_up_question.html",
            supplier_name=current_user.supplier_name,
            user_name=current_user.name,
            message=clarification_question
        )
        tags = ["g7-application-question"]
    else:
        subject = "Clarification question"
        to_address = current_app.config['DM_CLARIFICATION_QUESTION_EMAIL']
        from_address = "suppliers@digitalmarketplace.service.gov.uk"
        email_body = render_template(
            "emails/clarification_question.html",
            supplier_name=current_user.supplier_name,
            user_name=current_user.name,
            message=clarification_question
        )
        tags = ["clarification-question"]
    try:
        send_email(
            to_address,
            email_body,
            current_app.config['DM_MANDRILL_API_KEY'],
            subject,
            from_address,
            "G-Cloud 7 Supplier",
            tags
        )
    except MandrillException as e:
        current_app.logger.error(
            "Clarification question email failed to send. "
            "error {error} supplier_id {supplier_id} email_hash {email_hash}",
            extra={'error': six.text_type(e),
                   'supplier_id': current_user.supplier_id,
                   'email_hash': hash_email(current_user.email_address)})
        abort(503, "Clarification question email failed to send")

    if flask_featureflags.is_active('G7_CLARIFICATIONS_CLOSED'):
        # Do not send confirmation email to the user who submitted the question
        # Zendesk will handle this instead
        audit_type = AuditTypes.send_g7_application_question
    else:
        # Send confirmation email to the user who submitted the question
        # No need to fail if this email does not send
        subject = current_app.config['CLARIFICATION_EMAIL_SUBJECT']
        tags = ["clarification-question-confirm"]
        audit_type = AuditTypes.send_clarification_question
        email_body = render_template(
            "emails/clarification_question_submitted.html",
            user_name=current_user.name,
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
                "Clarification question confirmation email failed to send. "
                "error {error} supplier_id {supplier_id} email_hash {email_hash}",
                extra={'error': six.text_type(e),
                       'supplier_id': current_user.supplier_id,
                       'email_hash': hash_email(current_user.email_address)})

    data_api_client.create_audit_event(
        audit_type=audit_type,
        user=current_user.email_address,
        object_type="suppliers",
        object_id=current_user.supplier_id,
        data={"question": clarification_question})

    flash('message_sent', 'success')
    return framework_updates()
