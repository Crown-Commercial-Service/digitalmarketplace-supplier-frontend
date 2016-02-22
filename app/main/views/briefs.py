from flask import render_template, abort, request, redirect, flash
from flask_login import current_user

from ..helpers import login_required
from ..helpers.briefs import (
    get_brief,
    ensure_supplier_is_eligible_for_brief,
    send_brief_clarification_question,
)
from ..helpers.frameworks import get_framework_and_lot
from ...main import main, content_loader
from ... import data_api_client


@main.route('/opportunities/<int:brief_id>/ask-a-question', methods=['GET', 'POST'])
@login_required
def ask_brief_clarification_question(brief_id):
    brief = get_brief(data_api_client, brief_id)
    ensure_supplier_is_eligible_for_brief(brief, current_user.supplier_id)

    error_message = None
    clarification_question_value = None

    if request.method == 'POST':
        clarification_question = request.form.get('clarification-question', '').strip()
        if not clarification_question:
            error_message = "Question cannot be empty"
        elif len(clarification_question) > 5000:
            clarification_question_value = clarification_question
            error_message = "Question cannot be longer than 5000 characters"
        else:
            send_brief_clarification_question(brief, clarification_question)
            flash('message_sent', 'success')

    return render_template(
        "briefs/clarification_question.html",
        brief=brief,
        error_message=error_message,
        clarification_question_name='clarification-question',
        clarification_question_value=clarification_question_value
    ), 200 if not error_message else 400


@main.route('/opportunities/<int:brief_id>/responses/create', methods=['GET'])
@login_required
def submit_brief_response(brief_id):

    brief = data_api_client.get_brief(brief_id)['briefs']
    if brief['status'] != 'live':
        abort(404)

    framework_slug = brief['frameworkSlug']
    lot_slug = brief['lotSlug']

    framework, lot = get_framework_and_lot(data_api_client, framework_slug, lot_slug, open_only=False)

    content = content_loader.get_manifest(framework_slug, 'edit_brief_response').filter(
        {'lot': lot_slug}
    )
    section = content.get_section(content.get_next_editable_section_id())

    # pass all of the brief yes/no questions into the ContentQuestion
    for question in section.questions:
        if question.type == 'boolean_list':
            question.boolean_list_questions = brief[question.id]

    return render_template(
        "services/edit_submission_section.html",
        framework=framework,
        service_data={},
        section=section,
        **dict(main.config['BASE_TEMPLATE_DATA'])
    ), 200
