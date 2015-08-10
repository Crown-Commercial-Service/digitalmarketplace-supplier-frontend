from flask import render_template, request, abort, flash, redirect, url_for, escape, current_app
from flask_login import login_required, current_user

from dmutils.apiclient import APIError
from dmutils import flask_featureflags
from dmutils.email import send_email, MandrillException

from ...main import main, declaration_content
from ... import data_api_client
from ..helpers.services import get_draft_document_url


CLARIFICATION_QUESTION_NAME = 'clarification_question'


@main.route('/frameworks/g-cloud-7', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_dashboard():
    template_data = main.config['BASE_TEMPLATE_DATA']

    try:
        drafts = data_api_client.find_draft_services(
            current_user.supplier_id,
            framework='g-cloud-7'
        )['services']
    except APIError as e:
        abort(e.status_code)

    try:
        declaration_made = bool(data_api_client.get_selection_answers(
            current_user.supplier_id, 'g-cloud-7'))
    except APIError as e:
        if e.status_code == 404:
            declaration_made = False
        else:
            abort(e.status_code)

    return render_template(
        "frameworks/dashboard.html",
        counts={
            "draft": len(drafts),
            "complete": 1,
        },
        declaration_made=declaration_made,
        **template_data
    ), 200


@main.route('/frameworks/g-cloud-7/services', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_services():
    template_data = main.config['BASE_TEMPLATE_DATA']

    try:
        drafts = data_api_client.find_draft_services(
            current_user.supplier_id,
            framework='g-cloud-7'
        )['services']

    except APIError as e:
        abort(e.status_code)

    return render_template(
        "frameworks/services.html",
        drafts=drafts,
        **template_data
    ), 200


@main.route('/frameworks/g-cloud-7/declaration',
            methods=['GET', 'POST'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_supplier_declaration():
    template_data = main.config['BASE_TEMPLATE_DATA']

    if request.method == 'POST':
        answers = declaration_content.get_builder().get_all_data(request.form)
        try:
            data_api_client.answer_selection_questions(
                current_user.supplier_id,
                'g-cloud-7',
                answers,
                current_user.email_address
            )
            flash('questions_updated')
            return redirect(url_for('.framework_dashboard'))
        except APIError as e:
            abort(e.status_code)
    else:
        try:
            response = data_api_client.get_selection_answers(
                current_user.supplier_id, 'g-cloud-7')
            answers = response['selectionAnswers']['questionAnswers']
        except APIError as e:
            if e.status_code != 404:
                abort(e.status_code)
            answers = {}

    return render_template(
        "frameworks/edit_declaration_section.html",
        sections=declaration_content.get_builder(),
        service_data=answers,
        **template_data
    ), 200


@main.route('/frameworks/g-cloud-7/download-supplier-pack', methods=['GET', 'POST'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def download_supplier_pack():
    url = get_draft_document_url('g-cloud-7-supplier-pack.zip')
    if not url:
        abort(404)

    return redirect(url)


@main.route('/frameworks/g-cloud-7/updates', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_updates():
    return _framework_updates_page()


@main.route('/frameworks/g-cloud-7/updates', methods=['POST'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_updates_email_clarification_question():

    # Stripped input should not empty
    clarification_question = escape(request.form.get(CLARIFICATION_QUESTION_NAME, '')).strip()

    if not clarification_question:
        return _framework_updates_page("Question cannot be empty")
    elif len(clarification_question) > 5000:
        return _framework_updates_page("Question cannot be longer than 5000 characters")

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

    flash('message_sent', 'success')
    return _framework_updates_page()


def _framework_updates_page(error_message=None):

    template_data = main.config['BASE_TEMPLATE_DATA']
    status_code = 200 if not error_message else 400

    return render_template(
        "frameworks/updates.html",
        clarification_question_name=CLARIFICATION_QUESTION_NAME,
        error_message=error_message,
        **template_data
    ), status_code
