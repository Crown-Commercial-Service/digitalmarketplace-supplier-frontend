from flask import render_template
from flask_login import login_required

from dmutils import flask_featureflags

from ...main import main


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


@main.route('/frameworks/g-cloud-7/pre-qualification-questionnaire',
            methods=['GET', 'POST'])
@login_required
@flask_featureflags.is_active_feature('GCLOUD7_OPEN')
def framework_pqq():
    template_data = main.config['BASE_TEMPLATE_DATA']

    return render_template(
        "frameworks/pre-qualification-questionnaire.html",
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
