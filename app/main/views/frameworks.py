from flask import render_template, request, abort, flash
from flask_login import login_required, current_user

from dmutils.apiclient import APIError
from dmutils import flask_featureflags

from ...main import main
from ... import data_api_client
from ..forms.frameworks import G7SelectionQuestions


@main.route('/frameworks/g-cloud-7', methods=['GET'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_dashboard():
    template_data = main.config['BASE_TEMPLATE_DATA']

    # get the framework
    # get the list of

    return render_template(
        "frameworks/dashboard.html",
        **template_data
    ), 200


@main.route('/frameworks/g-cloud-7/selection-questions',
            methods=['GET', 'POST'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_selection_questions():
    template_data = main.config['BASE_TEMPLATE_DATA']

    if request.method == 'POST':
        form = G7SelectionQuestions()
        if form.validate_on_submit():
            try:
                data_api_client.answer_selection_questions(
                    current_user.supplier_id,
                    'g-cloud-7',
                    form.data,
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
        form = G7SelectionQuestions(formdata=None, data=answers)

    return render_template(
        "frameworks/selection-questions.html",
        form=form,
        errors=[
            {'input_name': k,
             'question': v[0]} for k, v in form.errors.items()],
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
