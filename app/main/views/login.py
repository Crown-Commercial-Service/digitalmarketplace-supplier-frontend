from __future__ import absolute_import
from flask_login import current_user
from flask import flash, redirect, render_template, url_for

from dmapiclient.audit import AuditTypes
from dmutils.email import InviteUser

from .. import main
from ..forms.auth_forms import EmailAddressForm
from ..helpers import login_required
from ... import data_api_client


# Any invites sent before the new user-frontend becomes active will be linking to this route. We need to maintain it
# for seven days after the user-frontend goes live.
@main.route('/create-user/<string:encoded_token>', methods=['GET'])
def create_user(encoded_token):
    return redirect(url_for('external.create_user', encoded_token=encoded_token), 301)


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
        token_data = {
            "role": "supplier",
            "supplier_id": current_user.supplier_id,
            "supplier_name": current_user.supplier_name,
            "email_address": form.email_address.data
        }

        user_invite = InviteUser(token_data)
        invite_link = url_for('external.create_user', encoded_token=user_invite.token, _external=True)
        user_invite.send_invite_email(invite_link)

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
