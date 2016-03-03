from flask import render_template, request, redirect, flash
from flask_login import current_user

from ..helpers import login_required
from ..helpers.briefs import (
    get_brief,
    ensure_supplier_is_eligible_for_brief,
    send_brief_clarification_question,
)
from ...main import main
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
