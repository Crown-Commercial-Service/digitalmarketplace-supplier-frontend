import six
from flask import render_template, request, url_for, current_app, abort, jsonify, redirect, Response
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
import os
from dmutils.file import s3_upload_file_from_request, s3_download_file
import mimetypes


S3_PATH = 'applications'


def can_user_view_application(application):
    return current_user.id == application['application']['user_id']


def is_application_submitted(application):
    return application['application'].get('status', 'saved') != 'saved'


@main.route('/signup', methods=['GET'])
def start_seller_signup(applicant={}, errors=None):
    rendered_component = render_component(
        'bundles/SellerRegistration/SignupWidget.js', {
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
    user = from_response(request)

    fields = ['name', 'email']
    errors = validate_form_data(user, fields)
    if errors:
        return start_seller_signup(user, errors)

    token = generate_application_invitation_token(user)
    url = url_for('main.render_create_application', token=token, _external=True)
    email_body = render_template(
        'emails/create_seller_user_email.html',
        url=url,
    )

    try:
        send_email(
            user['email'],
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

    return render_template('auth/seller-signup-email-sent.html', email_address=user['email'])


@main.route('/signup/create-user/<string:token>', methods=['GET'])
def render_create_application(token, data={}, errors=None):
    token_data = decode_user_token(token.encode())

    if not token_data.get('email'):
        abort(503, 'Invalid email address')

    user_json = data_api_client.get_user(email_address=token_data['email'])

    if not user_json:
        rendered_component = render_component(
            'bundles/SellerRegistration/EnterPasswordWidget.js', {
                'form_options': {
                    'errors': errors
                },
                'enterPasswordForm': dict(token_data.items() + data.items()),
            }
        )

        return render_template(
            '_react.html',
            component=rendered_component
        )

    user = User.from_json(user_json)
    return render_template(
        'auth/create_user_error.html',
        data=token_data,
        user=user), 400


@main.route('/signup/create-user/<string:token>', methods=['POST'])
def create_application(token):
    token_data = decode_user_token(token.encode())
    form_data = from_response(request)

    fields = [('password', 10)]
    errors = validate_form_data(form_data, fields)
    if errors:
        return render_create_application(token, form_data, errors)

    user = data_api_client.create_user({
        'name': token_data['name'],
        'password': form_data['password'],
        'emailAddress': token_data['email'],
        'role': 'applicant',
    })

    user = User.from_json(user)

    application = data_api_client.create_application(user.id, {'status': 'saved'})

    login_user(user)
    return redirect(url_for('main.render_application', id=application['application']['id'], step='start'))


@main.route('/application')
@applicant_login_required
def my_application():
    applications = data_api_client.find_applications(user_id=current_user.id)
    if applications['applications'][0]:
        application = applications['applications'][0]
        if application.get('status', 'saved') != 'saved':
            return redirect(url_for('.submit_application', id=application['id']))
        else:
            return redirect(url_for('.render_application', id=application['id'], step="start"))
    else:
        abort(404, "Application can not be found")


@main.route('/application/submit/<int:id>', methods=['GET'])
@applicant_login_required
def submit_application(id):
    application = data_api_client.get_application(id)
    if not can_user_view_application(application):
        abort(403, 'Not authorised to access application')

    data_api_client.update_application(id, {'status': 'submitted'})

    return render_template('suppliers/application_submitted.html')


@main.route('/application/<int:id>', methods=['GET'])
@main.route('/application/<int:id>/<path:step>', methods=['GET'])
@applicant_login_required
def render_application(id, step=None):
    application = data_api_client.get_application(id)
    if not can_user_view_application(application):
        abort(403, 'Not authorised to access application')
    if is_application_submitted(application):
        return redirect(url_for('.submit_application', id=id))

    props = dict(application)
    props['basename'] = url_for('.render_application', id=id, step=None)
    props['form_options'] = {
        'action': url_for('.render_application', id=id, step=step),
        'submit_url': url_for('.submit_application', id=id)
    }

    rendered_component = render_component('bundles/SellerRegistration/ApplicantSignupWidget.js', props)

    return render_template(
        '_react.html',
        component=rendered_component
    )


@main.route('/application/<int:id>', methods=['POST'])
@main.route('/application/<int:id>/<path:step>', methods=['POST'])
@applicant_login_required
def application_update(id, step=None):
    old_application = data_api_client.get_application(id)
    if not can_user_view_application(old_application):
        abort(403, 'Not authorised to access application')
    if is_application_submitted(old_application):
        return redirect(url_for('.submit_application', id=id))

    json = request.content_type == 'application/json'
    form_data = from_response(request)
    application = form_data['application'] if json else form_data

    if application.get('status'):
        del application['status']

    result = data_api_client.update_application(id, application)

    if json:
        return jsonify(result)
    else:
        return redirect(url_for('.render_application', id=id, step=form_data['next_step_slug']))


@main.route('/application/<int:id>/documents/<slug>', methods=['GET'])
@applicant_login_required
def download_single_file(id, slug):
    application = data_api_client.get_application(id)
    if not can_user_view_application(application):
        abort(403, 'Not authorised to access application')
    if is_application_submitted(application):
        abort(400, 'Application already submitted')

    file = s3_download_file(slug, os.path.join(S3_PATH, str(id)))

    mimetype = mimetypes.guess_type(slug)[0] or 'binary/octet-stream'
    return Response(file, mimetype=mimetype)


@main.route('/application/<int:id>/documents/<slug>', methods=['POST'])
@applicant_login_required
def upload_single_file(id, slug):
    application = data_api_client.get_application(id)
    if not can_user_view_application(application):
        abort(403, 'Not authorised to access application')
    if is_application_submitted(application):
        abort(400, 'Application already submitted')

    return s3_upload_file_from_request(request, slug, os.path.join(S3_PATH, str(id)))
