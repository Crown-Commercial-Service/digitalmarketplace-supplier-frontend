# coding: utf-8
from __future__ import unicode_literals

from flask import render_template, redirect, url_for, request, flash, abort
from flask_login import current_user

from dmapiclient import HTTPError

from ..helpers import login_required
from ..helpers.briefs import (
    get_brief,
    ensure_supplier_is_eligible_for_brief,
    send_brief_clarification_question,
    supplier_has_a_brief_response
)
from ..helpers.frameworks import get_framework_and_lot
from ...main import main, content_loader
from ... import data_api_client


@main.route('/opportunities/<int:brief_id>/ask-a-question', methods=['GET', 'POST'])
@login_required
def ask_brief_clarification_question(brief_id):
    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live'])
    if brief['clarificationQuestionsAreClosed']:
        abort(404)
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
            send_brief_clarification_question(data_api_client, brief, clarification_question)
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

    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live'])
    ensure_supplier_is_eligible_for_brief(brief, current_user.supplier_id)

    if supplier_has_a_brief_response(data_api_client, current_user.supplier_id, brief_id):
        # TODO redirect to summary of brief response page with flash message
        abort(404)

    framework, lot = get_framework_and_lot(
        data_api_client, brief['frameworkSlug'], brief['lotSlug'], allowed_statuses=['live'])

    content = content_loader.get_manifest(framework['slug'], 'edit_brief_response').filter({'lot': lot['slug']})
    section = content.get_section(content.get_next_editable_section_id())

    # replace generic 'Apply to opportunity' title with title including the name of the brief
    section.name = "Apply to ‘{}’".format(brief['title'])
    section.inject_brief_questions_into_boolean_list_question(brief)

    return render_template(
        "services/edit_submission_section.html",
        framework=framework,
        service_data={},
        section=section,
        **dict(main.config['BASE_TEMPLATE_DATA'])
    ), 200


# Add a create route
@main.route('/opportunities/<int:brief_id>/responses/create', methods=['POST'])
@login_required
def create_new_brief_response(brief_id):
    """Hits up the data API to create a new brief response."""

    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live'])
    ensure_supplier_is_eligible_for_brief(brief, current_user.supplier_id)

    if supplier_has_a_brief_response(data_api_client, current_user.supplier_id, brief_id):
        # TODO redirect to summary of brief response page with flash message
        abort(404)

    framework, lot = get_framework_and_lot(
        data_api_client, brief['frameworkSlug'], brief['lotSlug'], allowed_statuses=['live'])

    content = content_loader.get_manifest(framework['slug'], 'edit_brief_response').filter({'lot': lot['slug']})
    section = content.get_section(content.get_next_editable_section_id())
    response_data = section.get_data(request.form)

    try:
        data_api_client.create_brief_response(
            brief_id, current_user.supplier_id, response_data, current_user.email_address
        )['briefResponses']
    except HTTPError as e:
        section.inject_brief_questions_into_boolean_list_question(brief)
        section_summary = section.summary(response_data)

        errors = section_summary.get_error_messages(e.message)

        return render_template(
            "services/edit_submission_section.html",
            framework=framework,
            service_data=response_data,
            section=section,
            errors=errors,
            **dict(main.config['BASE_TEMPLATE_DATA'])
        ), 400

    flash('Your response to &lsquo;{}&rsquo; has been submitted.'.format(brief['title']))

    return redirect(url_for(".dashboard"))
