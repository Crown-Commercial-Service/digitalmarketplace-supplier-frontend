from flask import render_template, request, abort, flash
from flask_login import login_required, current_user

from dmutils.apiclient import APIError
from dmutils import flask_featureflags
from dmutils.content_loader import ContentBuilder

from ...main import main, declaration_content
from ... import data_api_client


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

    return render_template(
        "frameworks/dashboard.html",
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
        "services/edit_declaration_section.html",
        sections=declaration_content.get_builder(),
        service_data=answers,
        **template_data
    ), 200


@main.route('/frameworks/g-cloud-7/ask-a-question', methods=['GET', 'POST'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_ask_a_question():
    template_data = main.config['BASE_TEMPLATE_DATA']

    return render_template(
        "frameworks/ask-a-question.html",
        **template_data
    ), 200


@main.route('/frameworks/g-cloud-7/communications', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_communications():
    template_data = main.config['BASE_TEMPLATE_DATA']

    return render_template(
        "frameworks/communications.html",
        **template_data
    ), 200
