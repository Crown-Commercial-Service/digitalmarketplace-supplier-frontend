from __future__ import absolute_import
import six
import flask_featureflags

from flask_login import current_user, login_user
from flask import current_app, flash, make_response, redirect, render_template, request, url_for, abort

from dmapiclient import HTTPError
from dmapiclient.audit import AuditTypes
from dmutils.user import User
from dmutils.email import EmailError, generate_token, hash_email, InvalidToken, send_email
from dmutils.forms import render_template_with_csrf

from app import data_api_client
from app.main import main
from app.main.forms.auth_forms import EmailAddressForm, CreateUserForm
from app.main.helpers import login_required
from app.main.helpers.users import decode_supplier_invitation_token, generate_supplier_invitation_token


def get_create_user_data(token):
    if token == 'fake-token' and current_app.config['DEBUG']:
        data = {
            'name': 'Debug User',
            'emailAddress': 'debug@example.com',
            'supplierCode': 0,
            'supplierName': 'Example Pty Ltd',
        }
    else:
        try:
            data = decode_supplier_invitation_token(token.encode())
        except InvalidToken:
            current_app.logger.warning(
                'createuser.token_invalid: {token}',
                extra={'token': token})
            body = render_template(
                'auth/create_user_error.html',
                data=None
            )
            abort(make_response(body, 404))
    return data


@main.route('/create-user/<string:token>', methods=['GET'])
def create_user(token):
    data = get_create_user_data(token)

    user_json = data_api_client.get_user(email_address=data['emailAddress'])

    if not user_json:
        form = CreateUserForm(name=data['name'])
        return render_template_with_csrf(
            'auth/create_user.html',
            form=form,
            email_address=data['emailAddress'],
            supplier_name=data['supplierName'],
            token=token)

    user = User.from_json(user_json)
    return render_template(
        'auth/create_user_error.html',
        data=data,
        user=user), 400


@main.route('/create-user/<string:token>', methods=['POST'])
def submit_create_user(token):
    data = get_create_user_data(token)
    form = CreateUserForm(request.form)

    if not form.validate():
        current_app.logger.warning(
            'createuser.invalid: {form_errors}',
            extra={'form_errors': ', '.join(form.errors)})
        return render_template(
            'auth/create_user.html',
            form=form,
            token=token,
            email_address=data['emailAddress'],
            supplier_name=data['supplierName']), 400

    if token == 'fake-token':
        return redirect('/')

    try:
        user = data_api_client.create_user({
            'name': form.name.data,
            'password': form.password.data,
            'emailAddress': data['emailAddress'],
            'role': 'supplier',
            'supplierCode': data['supplierCode']
        })

        user = User.from_json(user)
        login_user(user)

    except HTTPError as e:
        if e.status_code != 409:
            raise

        return render_template(
            'auth/create_user_error.html',
            token=None), 400

    flash('account-created', 'flag')
    return redirect(url_for('.dashboard'))


@main.route('/invite-user', methods=['GET'])
@login_required
def invite_user():
    form = EmailAddressForm()

    return render_template_with_csrf(
        'auth/submit_email_address.html',
        form=form)


@main.route('/invite-user', methods=['POST'])
@login_required
def send_invite_user():
    form = EmailAddressForm(request.form)
    if form.validate():
        token = generate_supplier_invitation_token(
            name='',
            supplier_code=current_user.supplier_code,
            supplier_name=current_user.supplier_name,
            email_address=form.email_address.data
        )
        url = url_for('main.create_user', token=token, _external=True)
        email_body = render_template(
            'emails/invite_user_email.html',
            url=url,
            user=current_user.name,
            supplier=current_user.supplier_name)

        try:
            send_email(
                form.email_address.data,
                email_body,
                current_app.config['INVITE_EMAIL_SUBJECT'],
                current_app.config['INVITE_EMAIL_FROM'],
                current_app.config['INVITE_EMAIL_NAME']
            )
        except EmailError as e:
            current_app.logger.error(
                'Invitation email failed to send. '
                'error {error} supplier_code {supplier_code} email_hash {email_hash}',
                extra={'error': six.text_type(e),
                       'supplier_code': current_user.supplier_code,
                       'email_hash': hash_email(current_user.email_address)})
            abort(503, 'Failed to send user invite reset')

        data_api_client.create_audit_event(
            audit_type=AuditTypes.invite_user,
            user=current_user.email_address,
            object_type='suppliers',
            object_id=current_user.supplier_code,
            data={'invitedEmail': form.email_address.data},
        )

        flash('user_invited', 'success')
        return redirect(url_for('.list_users'))
    else:
        return render_template_with_csrf(
            'auth/submit_email_address.html',
            status_code=400,
            form=form)
