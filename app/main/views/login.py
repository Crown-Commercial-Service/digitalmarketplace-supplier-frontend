from __future__ import absolute_import
import six
from flask_login import current_user
from flask import current_app, flash, redirect, render_template, url_for, abort
from flask_login import login_user

from dmapiclient import HTTPError
from dmapiclient.audit import AuditTypes
from dmutils.user import User
from dmutils.email import decode_invitation_token, generate_token, send_email, MandrillException

from .. import main
from ..forms.auth_forms import EmailAddressForm, CreateUserForm
from ..helpers import hash_email, login_required
from ... import data_api_client


@main.route('/create-user/<string:encoded_token>', methods=["GET"])
def create_user(encoded_token):
    form = CreateUserForm()

    token = decode_invitation_token(encoded_token)

    if token is None:
        current_app.logger.warning(
            "createuser.token_invalid: {encoded_token}",
            extra={'encoded_token': encoded_token})
        return render_template(
            "auth/create_user_error.html",
            token=None), 400

    user_json = data_api_client.get_user(email_address=token["email_address"])

    if not user_json:
        return render_template(
            "auth/create_user.html",
            form=form,
            email_address=token['email_address'],
            supplier_name=token['supplier_name'],
            token=encoded_token), 200

    user = User.from_json(user_json)
    return render_template(
        "auth/create_user_error.html",
        token=token,
        user=user), 400


@main.route('/create-user/<string:encoded_token>', methods=["POST"])
def submit_create_user(encoded_token):
    form = CreateUserForm()

    token = decode_invitation_token(encoded_token)
    if token is None:
        current_app.logger.warning("createuser.token_invalid: {encoded_token}",
                                   extra={'encoded_token': encoded_token})
        return render_template(
            "auth/create_user_error.html",
            token=None), 400

    else:
        if not form.validate_on_submit():
            current_app.logger.warning(
                "createuser.invalid: {form_errors}",
                extra={'form_errors': ", ".join(form.errors)})
            return render_template(
                "auth/create_user.html",
                form=form,
                token=encoded_token,
                email_address=token['email_address'],
                supplier_name=token['supplier_name']), 400

        try:
            user = data_api_client.create_user({
                'name': form.name.data,
                'password': form.password.data,
                'emailAddress': token['email_address'],
                'role': 'supplier',
                'supplierId': token['supplier_id']
            })

            user = User.from_json(user)
            login_user(user)

        except HTTPError as e:
            if e.status_code != 409:
                raise

            return render_template(
                "auth/create_user_error.html",
                token=None), 400

        flash('account-created', 'flag')
        return redirect(url_for('.dashboard'))


@main.route('/invite-user', methods=["GET"])
@login_required
def invite_user():
    form = EmailAddressForm()

    return render_template(
        "auth/submit_email_address.html",
        form=form), 200


@main.route('/invite-user', methods=["POST"])
@login_required
def send_invite_user():
    form = EmailAddressForm()

    if form.validate_on_submit():
        token = generate_token(
            {
                "supplier_id": current_user.supplier_id,
                "supplier_name": current_user.supplier_name,
                "email_address": form.email_address.data
            },
            current_app.config['SHARED_EMAIL_KEY'],
            current_app.config['INVITE_EMAIL_SALT']
        )
        url = url_for('main.create_user', encoded_token=token, _external=True)
        email_body = render_template(
            "emails/invite_user_email.html",
            url=url,
            user=current_user.name,
            supplier=current_user.supplier_name)

        try:
            send_email(
                form.email_address.data,
                email_body,
                current_app.config['DM_MANDRILL_API_KEY'],
                current_app.config['INVITE_EMAIL_SUBJECT'],
                current_app.config['INVITE_EMAIL_FROM'],
                current_app.config['INVITE_EMAIL_NAME'],
                ["user-invite"]
            )
        except MandrillException as e:
            current_app.logger.error(
                "Invitation email failed to send. "
                "error {error} supplier_id {supplier_id} email_hash {email_hash}",
                extra={'error': six.text_type(e),
                       'supplier_id': current_user.supplier_id,
                       'email_hash': hash_email(current_user.email_address)})
            abort(503, "Failed to send user invite reset")

        data_api_client.create_audit_event(
            audit_type=AuditTypes.invite_user,
            user=current_user.email_address,
            object_type='suppliers',
            object_id=current_user.supplier_id,
            data={'invitedEmail': form.email_address.data},
        )

        flash('user_invited', 'success')
        return redirect(url_for('.list_users'))
    else:
        return render_template(
            "auth/submit_email_address.html",
            form=form), 400
