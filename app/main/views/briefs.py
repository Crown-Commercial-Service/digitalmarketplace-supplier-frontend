# coding: utf-8
from __future__ import unicode_literals

import re

from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
import flask_featureflags as feature

from dmapiclient import HTTPError
from dmutils.formats import DATETIME_FORMAT

from ..helpers import login_required, new_supplier_flow_active_for_datetime
from ..helpers.briefs import (
    get_brief,
    is_supplier_eligible_for_brief,
    send_brief_clarification_question,
    supplier_has_a_brief_response
)
from ..helpers.frameworks import get_framework_and_lot
from ...main import main, content_loader
from ... import data_api_client


@main.route('/opportunities/<int:brief_id>/question-and-answer-session', methods=['GET'])
@login_required
def question_and_answer_session(brief_id):
    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live'])

    if brief['clarificationQuestionsAreClosed']:
        abort(404)

    if not is_supplier_eligible_for_brief(data_api_client, current_user.supplier_id, brief):
        return _render_not_eligible_for_brief_error_page(brief, clarification_question=True)

    return render_template(
        "briefs/question_and_answer_session.html",
        brief=brief,
    ), 200


@main.route('/opportunities/<int:brief_id>/ask-a-question', methods=['GET', 'POST'])
@login_required
def ask_brief_clarification_question(brief_id):
    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live'])

    if brief['clarificationQuestionsAreClosed']:
        abort(404)

    if not is_supplier_eligible_for_brief(data_api_client, current_user.supplier_id, brief):
        return _render_not_eligible_for_brief_error_page(brief, clarification_question=True)

    error_message = None
    clarification_question_value = None

    if request.method == 'POST':
        clarification_question = request.form.get('clarification-question', '').strip()
        if not clarification_question:
            error_message = "Question cannot be empty"
        elif len(clarification_question) > 5000:
            clarification_question_value = clarification_question
            error_message = "Question cannot be longer than 5000 characters"
        elif not re.match("^$|(^(?:\\S+\\s+){0,99}\\S+$)", clarification_question):
            clarification_question_value = clarification_question
            error_message = "Question must be no more than 100 words"
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


@main.route('/opportunities/<int:brief_id>/responses/start', methods=['GET', 'POST'])
@feature.is_active_feature('NEW_SUPPLIER_FLOW')
@login_required
def start_brief_response(brief_id):
    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live'])
    brief_published_at = datetime.strptime(brief['publishedAt'], DATETIME_FORMAT)

    if not new_supplier_flow_active_for_datetime(brief_published_at):
        abort(404)

    if not is_supplier_eligible_for_brief(data_api_client, current_user.supplier_id, brief):
        return _render_not_eligible_for_brief_error_page(brief)

    brief_response = data_api_client.find_brief_responses(
        brief_id=brief_id,
        supplier_id=current_user.supplier_id,
        status='draft,submitted'
    )['briefResponses']

    if brief_response and brief_response[0]['status'] == 'submitted':
        flash('already_applied', 'error')
        return redirect(url_for(".view_response_result", brief_id=brief_id))

    if request.method == 'POST':
        if brief_response and brief_response[0]['status'] == 'draft':
            return redirect(
                url_for('.edit_brief_response', brief_id=brief_id, brief_response_id=brief_response[0]['id'])
            )
        else:
            brief_response = data_api_client.create_brief_response(
                brief_id,
                current_user.supplier_id,
                {},
                current_user.email_address,
            )['briefResponses']
            brief_response_id = brief_response['id']
            return redirect(url_for('.edit_brief_response', brief_id=brief_id, brief_response_id=brief_response_id))

    existing_draft_response = False
    if brief_response and brief_response[0]['status'] == 'draft':
        existing_draft_response = brief_response[0]

    return render_template(
        "briefs/start_brief_response.html",
        brief=brief,
        existing_draft_response=existing_draft_response
    )


@main.route('/opportunities/<int:brief_id>/responses/<int:brief_response_id>', methods=['GET'])
@main.route(
    '/opportunities/<int:brief_id>/responses/<int:brief_response_id>/<string:question_id>',
    methods=['GET', 'POST']
)
@feature.is_active_feature('NEW_SUPPLIER_FLOW')
@login_required
def edit_brief_response(brief_id, brief_response_id, question_id=None):
    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live'])
    brief_response = data_api_client.get_brief_response(brief_response_id)['briefResponses']

    if brief_response['briefId'] != brief['id'] or brief_response['supplierId'] != current_user.supplier_id:
        abort(404)

    if not is_supplier_eligible_for_brief(data_api_client, current_user.supplier_id, brief):
        return _render_not_eligible_for_brief_error_page(brief)

    if supplier_has_a_brief_response(data_api_client, current_user.supplier_id, brief_id):
        flash('already_applied', 'error')
        return redirect(url_for(".view_response_result", brief_id=brief_id))

    framework, lot = get_framework_and_lot(
        data_api_client, brief['frameworkSlug'], brief['lotSlug'], allowed_statuses=['live', 'expired'])

    max_day_rate = None
    role = brief.get('specialistRole')
    if role:
        brief_service = data_api_client.find_services(
            supplier_id=current_user.supplier_id,
            framework=brief['frameworkSlug'],
            status="published",
            lot=brief["lotSlug"],
        )["services"][0]
        max_day_rate = brief_service.get(role + "PriceMax")

    content = content_loader.get_manifest(
        brief['frameworkSlug'], 'edit_brief_response'
    ).filter({'lot': lot['slug'], 'brief': brief, 'max_day_rate': max_day_rate})

    section = content.get_section(content.get_next_editable_section_id())
    if section is None or not section.editable:
        abort(404)

    # If a question in a brief is optional and is unanswered by the buyer, the brief will have the key but will have no
    # data. The question will be skipped in the brief response flow (see below). If a user attempts to access the
    # question by directly visiting the url, this check will return a 404. It has been created specifically for nice to
    # have requirements, and works because briefs and responses share the same key for this question/response.
    if question_id in brief.keys() and not brief[question_id]:
        abort(404)

    # If a question is to be skipped in the normal flow (due to the reason above), we update the next_question_id.
    next_question_id = section.get_next_question_id(question_id)
    if next_question_id in brief.keys() and not brief[next_question_id]:
        next_question_id = section.get_next_question_id(next_question_id)

    def redirect_to_next_page():
        return redirect(url_for(
            '.edit_brief_response',
            brief_id=brief_id,
            brief_response_id=brief_response_id,
            question_id=next_question_id
        ))

    # If no question_id in url then redirect to first question
    if question_id is None:
        return redirect_to_next_page()

    question = section.get_question(question_id)
    if question is None:
        abort(404)

    # Unformat brief response into data for form
    service_data = question.unformat_data(brief_response)

    status_code = 200
    errors = {}
    if request.method == 'POST':
        try:
            data_api_client.update_brief_response(
                brief_response_id,
                question.get_data(request.form),
                current_user.email_address,
                page_questions=[question.id]
            )

        except HTTPError as e:
            errors = question.get_error_messages(e.message)
            status_code = 400
            service_data = question.unformat_data(question.get_data(request.form))

        else:
            if next_question_id:
                return redirect_to_next_page()
            else:
                data_api_client.submit_brief_response(
                    brief_response_id,
                    current_user.email_address
                )

                return redirect(url_for('.view_response_result', brief_id=brief_id))

    previous_question_id = section.get_previous_question_id(question_id)
    # Skip previous question if the brief has no nice to have requirements
    if previous_question_id in brief.keys() and not brief[previous_question_id]:
        previous_question_id = section.get_previous_question_id(previous_question_id)

    previous_question_url = None
    if previous_question_id:
        previous_question_url = url_for(
            '.edit_brief_response',
            brief_id=brief_id,
            brief_response_id=brief_response_id,
            question_id=previous_question_id
        )

    return render_template(
        "briefs/edit_brief_response_question.html",
        brief=brief,
        errors=errors,
        is_last_page=False if next_question_id else True,
        previous_question_url=previous_question_url,
        question=question,
        service_data=service_data
    ), status_code


@main.route('/opportunities/<int:brief_id>/responses/result')
@login_required
def view_response_result(brief_id):
    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live', 'closed'])
    brief_published_at = datetime.strptime(brief['publishedAt'], DATETIME_FORMAT)
    if not is_supplier_eligible_for_brief(data_api_client, current_user.supplier_id, brief):
        return _render_not_eligible_for_brief_error_page(brief)

    brief_response = data_api_client.find_brief_responses(
        brief_id=brief_id,
        supplier_id=current_user.supplier_id
    )['briefResponses']

    legacy_brief = not new_supplier_flow_active_for_datetime(brief_published_at)
    if len(brief_response) == 0:
        if legacy_brief:
            abort(404)
        else:
            return redirect(url_for(".start_brief_response", brief_id=brief_id))
    elif brief_response[0].get('essentialRequirementsMet') or all(brief_response[0]['essentialRequirements']):
        result_state = 'submitted_ok'
        flash('submitted_ok', 'success')
    else:
        result_state = 'submitted_unsuccessful'
        flash('submitted_unsuccessful', 'error')

    brief_response = brief_response[0]
    framework, lot = get_framework_and_lot(
        data_api_client, brief['frameworkSlug'], brief['lotSlug'], allowed_statuses=['live', 'expired'])

    if brief_response.get('essentialRequirementsMet'):
        brief_response_display_manifest = 'display_brief_response'
    else:
        brief_response_display_manifest = 'legacy_display_brief_response'

    response_content = content_loader.get_manifest(
        framework['slug'], brief_response_display_manifest).filter({'lot': lot['slug'], 'brief': brief})
    for section in response_content:
        section.inject_brief_questions_into_boolean_list_question(brief)

    brief_content = content_loader.get_manifest(
        framework['slug'], 'edit_brief').filter({'lot': lot['slug']})
    brief_summary = brief_content.summary(brief)

    return render_template(
        'briefs/view_response_result.html',
        brief=brief,
        brief_summary=brief_summary,
        brief_response=brief_response,
        result_state=result_state,
        response_content=response_content
    )


def _render_not_eligible_for_brief_error_page(brief, clarification_question=False):
    common_kwargs = {
        "supplier_id": current_user.supplier_id,
        "framework": brief['frameworkSlug'],
        "status": "published",
    }

    if data_api_client.find_services(**common_kwargs)["services"]:
        if data_api_client.find_services(**dict(common_kwargs, lot=brief["lotSlug"]))["services"]:
            # deduce that the problem is that the roles don't match.
            reason = data_reason_slug = "supplier-not-on-role"
        else:
            reason = data_reason_slug = "supplier-not-on-lot"
    else:
        reason = "supplier-not-on-framework"
        data_reason_slug = "supplier-not-on-{}".format(brief['frameworkSlug'])

    return render_template(
        "briefs/not_is_supplier_eligible_for_brief_error.html",
        clarification_question=clarification_question,
        framework_name=brief['frameworkName'],
        lot=brief['lotSlug'],
        reason=reason,
        data_reason_slug=data_reason_slug
    ), 400
