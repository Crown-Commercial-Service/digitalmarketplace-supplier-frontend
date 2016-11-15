import six
from flask import render_template, request, url_for, current_app, abort, jsonify, redirect
from flask_login import current_user, login_user
from app.main import main
from react.render import render_component
from react.response import from_response, validate_form_data
from dmapiclient import HTTPError
from dmutils.email import EmailError, send_email
from dmutils.user import User
from app.main.helpers.users import generate_application_invitation_token, decode_user_token
from app import data_api_client
from ..helpers import applicant_login_required


@main.route('/signup', methods=['GET'])
def start_seller_signup(applicant={}, errors=None):
    rendered_component = render_component(
        'bundles/SellerRegistration/YourInfoWidget.js', {
            'form_options': {
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
    application = from_response(request)

    fields = ['representative', 'name', 'abn', 'phone', 'email']
    errors = validate_form_data(application, fields)
    if errors:
        return start_seller_signup(application, errors)

    token = generate_application_invitation_token(application)
    url = url_for('main.render_create_application', token=token, _external=True)
    email_body = render_template(
        'emails/create_seller_user_email.html',
        url=url,
    )

    try:
        send_email(
            application['email'],
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

    return render_template('auth/seller-signup-email-sent.html', email_address=application['email'])


@main.route('/signup/create-user/<string:token>', methods=['GET'])
def render_create_application(token, data={}, errors=None):
    application = decode_user_token(token.encode())

    if not application.get('email'):
        abort(503, 'Invalid email address')

    user_json = data_api_client.get_user(email_address=application['email'])

    if not user_json:
        form_data = dict(application.items() + data.items())
        rendered_component = render_component(
            'bundles/SellerRegistration/EnterPasswordWidget.js', {
                'form_options': {
                    'errors': errors
                },
                'enterPasswordForm': form_data,
            }
        )

        return render_template(
            '_react.html',
            component=rendered_component
        )

    user = User.from_json(user_json)
    return render_template(
        'auth/create_user_error.html',
        data=application,
        user=user), 400


@main.route('/signup/create-user/<string:token>', methods=['POST'])
def create_application(token):
    application_data = decode_user_token(token.encode())
    data = from_response(request)

    fields = [('password', 10)]
    errors = validate_form_data(data, fields)
    if errors:
        return render_create_application(token, data, errors)

    try:
        user = data_api_client.create_user({
            'name': application_data['name'],
            'password': data['password'],
            'emailAddress': application_data['email'],
            'role': 'applicant',
        })

        user = User.from_json(user)
        application = data_api_client.create_application(user.id, application_data)
        login_user(user)
        return redirect(url_for('main.render_application', id=application['application']['id'], step='start'))

    except HTTPError as e:
        return render_template(
            'auth/create_user_error.html',
            token=None), 400


@main.route('/application/<int:id>', methods=['GET'])
@main.route('/application/<int:id>/<path:step>', methods=['GET'])
@applicant_login_required
def render_application(id, step=None):
    application = data_api_client.get_application(id)

    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    if current_user.id != application['user_id']:
        abort(403, 'Not authorised to access application')

    props = dict(application)
    props['basename'] = url_for('.render_application', id=id, step=None)
    props['form_options'] = {
        'action': url_for('.render_application', id=id, step=step),
    }

    rendered_component = render_component('bundles/ApplicantSignup/ApplicantSignupWidget.js', props)

    return render_template(
        '_react.html',
        component=rendered_component
    )


@main.route('/application/<int:id>', methods=['POST'])
@main.route('/application/<int:id>/<path:step>', methods=['POST'])
@applicant_login_required
def application_update(id, step=None):
    old_application = data_api_client.get_application(id)

    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    if current_user.id != old_application['user_id']:
        abort(403, 'Not authorised to access application')

    json = request.content_type == 'application/json'
    form_data = from_response(request)
    application = form_data['application'] if json else form_data

    result = data_api_client.update_application(id, application)

    if json:
        return jsonify(result)
    else:
        return redirect(url_for('.render_application', id=id, step=form_data['next_step_slug']))
