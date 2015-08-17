import itertools

from flask import render_template, request, abort, flash, redirect, url_for, escape, current_app
from flask_login import login_required, current_user

from dmutils.apiclient import APIError
from dmutils.audit import AuditTypes
from dmutils import flask_featureflags
from dmutils.email import send_email, MandrillException
from dmutils.formats import format_service_price
from dmutils import s3

from ...main import main, declaration_content, new_service_content
from ..helpers.frameworks import get_error_messages_for_page, get_first_question_index, \
    get_error_messages, get_declaration_status

from ... import data_api_client
from ..helpers.services import (
    get_draft_document_url, get_service_attributes, get_drafts,
    count_unanswered_questions
)
from ..helpers.frameworks import register_interest_in_framework


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

    return render_template(
        "frameworks/dashboard.html",
        counts={
            "draft": len(drafts),
            "complete": len(complete_drafts),
        },
        declaration_status=declaration_status,
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
        **template_data
    ), 200


@main.route('/frameworks/g-cloud-7/declaration/<string:section_id>',
            methods=['GET', 'POST'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_supplier_declaration(section_id):
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
                    return redirect(url_for('.framework_dashboard'))
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
def framework_updates(error_message=None):
    current_app.logger.info("g7updates.viewed: user_id:%s supplier_id:%s",
                            current_user.email_address, current_user.supplier_id)

    template_data = main.config['BASE_TEMPLATE_DATA']

    uploader = s3.S3(current_app.config['DM_G7_DRAFT_DOCUMENTS_BUCKET'])
    file_list = uploader.list('g-cloud-7-updates/')

    sections = {
        'clarifications': {
            'heading': "G-Cloud 7 communications",
            'empty_message': "No communications have been sent out",
            'files': []
        },
        'communications': {
            'heading': "G-Cloud 7 clarification questions and answers",
            'empty_message': "No clarification questions exist",
            'files': []
        }
    }

    for key in sections:
        sections[key]['files'] = [file for file in file_list if key == file['path'].split('/')[1]]

    return render_template(
        "frameworks/updates.html",
        clarification_question_name=CLARIFICATION_QUESTION_NAME,
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
        return framework_updates("Question cannot be longer than 5000 characters")

    email_body = render_template(
        "emails/clarification_question.html",
        supplier_name=current_user.supplier_name,
        user_name=current_user.name,
        message=clarification_question
    )

    try:
        send_email(
            current_app.config['DM_CLARIFICATION_QUESTION_EMAIL'],
            email_body,
            current_app.config['DM_MANDRILL_API_KEY'],
            "Clarification question",
            "suppliers@digitalmarketplace.service.gov.uk",
            "G-Cloud 7 Supplier",
            ["clarification-question"]
        )
    except MandrillException as e:
        current_app.logger.error(
            "Clarification question email failed to send error {} supplier_id {} user_email_address {}".format(
                e, current_user.supplier_id, current_user.email_address))
        abort(503, "Clarification question email failed to send")

    data_api_client.create_audit_event(
        audit_type=AuditTypes.send_clarification_question,
        user=current_user.email_address,
        object_type="suppliers",
        object_id=current_user.supplier_id,
        data={"question": clarification_question})

    flash('message_sent', 'success')
    return framework_updates()
