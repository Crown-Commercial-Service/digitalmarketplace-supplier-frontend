from flask import flash, redirect, url_for, current_app
from flask_login import current_user

from dmapiclient.audit import AuditTypes
from dmutils.email import send_user_account_email
from dmutils.flask import timed_render_template as render_template
from dmutils.forms.helpers import get_errors_from_wtform

from .. import main
from ..forms.auth_forms import EmailAddressForm
from ..helpers import login_required
from ... import data_api_client


USER_INVITED_FLASH_MESSAGE = "Contributor invited"


@main.route('/invite-user', methods=["GET", "POST"])
@login_required
def invite_user():
    form = EmailAddressForm()

    if form.validate_on_submit():
        send_user_account_email(
            'supplier',
            form.email_address.data,
            current_app.config['NOTIFY_TEMPLATES']['invite_contributor'],
            extra_token_data={
                'supplier_id': current_user.supplier_id,
                'supplier_name': current_user.supplier_name
            },
            personalisation={
                'user': current_user.name,
                'supplier': current_user.supplier_name
            }
        )

        data_api_client.create_audit_event(
            audit_type=AuditTypes.invite_user,
            user=current_user.email_address,
            object_type='suppliers',
            object_id=current_user.supplier_id,
            data={'invitedEmail': form.email_address.data},
        )

        flash(USER_INVITED_FLASH_MESSAGE, "success")
        return redirect(url_for('.list_users'))

    errors = get_errors_from_wtform(form)

    return render_template(
        "auth/submit_email_address.html",
        form=form,
        errors=errors
    ), 200 if not errors else 400
