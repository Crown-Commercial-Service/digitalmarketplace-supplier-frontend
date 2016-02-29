# coding: utf-8
from __future__ import unicode_literals
from collections import OrderedDict

from flask import render_template, redirect, url_for, request, flash, abort
from flask_login import current_user

from dmapiclient import HTTPError

from ..helpers import login_required
from ..helpers.briefs import (
    get_brief,
    ensure_supplier_is_eligible_for_brief,
    send_brief_clarification_question,
    inject_yes_no_questions_into_section_questions,
    has_supplier_already_submitted_a_brief_response
)
from ..helpers.frameworks import get_framework_and_lot
from ...main import main, content_loader
from ... import data_api_client


@main.route('/opportunities/<int:brief_id>/ask-a-question', methods=['GET', 'POST'])
@login_required
def ask_brief_clarification_question(brief_id):
    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live'])
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

    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live'])
    ensure_supplier_is_eligible_for_brief(brief, current_user.supplier_id)

    if not has_supplier_already_submitted_a_brief_response(data_api_client, current_user.supplier_id, brief_id):
        # TODO redirect to summary of brief response page with flash message
        abort(404)

    framework, lot = get_framework_and_lot(
        data_api_client, brief['frameworkSlug'], brief['lotSlug'], allowed_statuses=['live'])

    content = content_loader.get_manifest(framework['slug'], 'edit_brief_response').filter({'lot': lot['slug']})
    section = content.get_section(content.get_next_editable_section_id())

    # replace generic 'Apply to opportunity' title with title including the name of the brief
    section.name = "Apply to ‘{}’".format(brief['title'])
    inject_yes_no_questions_into_section_questions(section, brief)

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

    if not has_supplier_already_submitted_a_brief_response(data_api_client, current_user.supplier_id, brief_id):
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
        # `errors` doesn't take into account error messages in (nested) boolean_list question fields
        errors = section.get_error_messages(e.message, lot['slug'])
        new_errors = OrderedDict()

        while len(errors):
            old_error = errors.popitem(last=False)
            question_id, error_message = old_error

            if section.get_question(question_id).type == 'boolean_list':
                # errors don't get passed into a boolean list (or, therefore, its nested questions)
                # unless a 'truthy' value exists for its parent id
                new_errors[question_id] = True

                for index, essential_question in enumerate(brief[question_id]):
                    try:
                        # check the response data for True/False values returned from boolean_list questions
                        value_we_want_to_be_true_or_false = response_data[question_id][index]
                    except (IndexError, KeyError):
                        value_we_want_to_be_true_or_false = None

                    if not isinstance(value_we_want_to_be_true_or_false, bool):
                        # Each non-boolean value is an error
                        boolean_question_id = "{}-{}".format(question_id, index)
                        new_errors[boolean_question_id] = {
                            'input_name': boolean_question_id,
                            'message': error_message['message'],
                            'question': essential_question
                        }
            else:
                new_errors[question_id] = error_message

        inject_yes_no_questions_into_section_questions(section, brief)

        return render_template(
            "services/edit_submission_section.html",
            framework=framework,
            service_data=request.form,
            section=section,
            errors=new_errors,
            **dict(main.config['BASE_TEMPLATE_DATA'])
        ), 400

    flash('Your response to &lsquo;{}&rsquo; has been submitted.'.format(brief['title']))

    return redirect(url_for(".dashboard"))
