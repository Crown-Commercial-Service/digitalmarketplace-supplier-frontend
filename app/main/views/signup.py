import six
from flask import render_template, request, url_for, current_app, abort, jsonify, redirect
from flask_login import current_user, login_required
from app.main import main
from react.render import render_component
from react.response import from_response, validate_form_data
from dmutils.forms import DmForm
from dmutils.email import EmailError, send_email
from app.main.helpers.users import generate_applicant_invitation_token
from ... import data_api_client
from ..helpers import login_required


@main.route('/signup', methods=['GET'])
def start_seller_signup(applicant={}, errors=None):
    form = DmForm()

    rendered_component = render_component(
        'bundles/SellerRegistration/YourInfoWidget.js', {
            'form_options': {
                'csrf_token': form.csrf_token.current_token,
                'errors': errors
            },
            'yourInfoForm': applicant,
        }
    )

    return render_template(
        '_react.html',
        component=rendered_component
    )


@main.route('/signup', methods=['POST'])
def send_seller_signup_email():
    applicant = from_response(request)

    fields = ['representative', 'name', 'abn', 'phone', 'email']
    errors = validate_form_data(applicant, fields)
    if errors:
        start_seller_signup(applicant, errors)

    token = generate_applicant_invitation_token(applicant)
    url = url_for('main.create_user', token=token, _external=True)
    email_body = render_template(
        'emails/create_seller_user_email.html',
        url=url,
    )

    try:
        send_email(
            applicant['email'],
            email_body,
            current_app.config['INVITE_EMAIL_SUBJECT'],
            current_app.config['INVITE_EMAIL_FROM'],
            current_app.config['INVITE_EMAIL_NAME']
        )
    except EmailError as e:
        current_app.logger.error(
            'Invitation email failed to send. '
            'error {error}',
            extra={'error': six.text_type(e)}
        )
        abort(503, 'Failed to send user invite reset')

    return render_template('auth/seller-signup-email-sent.html', email_address=applicant['email'])


@main.route('/application/<int:id>', methods=['GET'])
@main.route('/application/<int:id>/<path:step>', methods=['GET'])
@login_required
def application(id, step=None):

    application = data_api_client.get_application(id)['application']

    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    if current_user.id != application['user_id']:
        return current_app.login_manager.unauthorized()

    application['basename'] = url_for('.application', id=id, step=None)

    rendered_component = render_component('bundles/ApplicantSignup/ApplicantSignupWidget.js', application)
    return render_template(
        '_react.html',
        component=rendered_component
    )


@main.route('/application/<int:id>', methods=['POST'])
@main.route('/application/<int:id>/<path:step>', methods=['POST'])
@login_required
def application_update(id, step=None):
    old_application = data_api_client.get_application(id)

    if not current_user.is_authenticated and current_user.id != old_application['application']['user_id']:
        return current_app.login_manager.unauthorized()

    json = request.content_type == 'application/json'
    application = from_response(request)

    result = data_api_client.update_application(id, application)

    if json:
        return jsonify(result)
    else:
        return redirect(url_for('.application', id=id, step=application['next_step']))
