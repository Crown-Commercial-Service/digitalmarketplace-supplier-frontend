from __future__ import absolute_import
import six
from flask_login import current_user
from flask import current_app, flash, redirect, render_template, url_for, abort

from dmapiclient.audit import AuditTypes
from dmutils.email import generate_token, send_email
from dmutils.email.exceptions import EmailError

from .. import main
from ..forms.auth_forms import EmailAddressForm
from ..helpers import hash_email, login_required
from ... import data_api_client


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
        except EmailError as e:
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
