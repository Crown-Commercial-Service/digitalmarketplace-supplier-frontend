from __future__ import absolute_import
import six
from flask_login import login_required, current_user
from itsdangerous import BadSignature, SignatureExpired
from datetime import datetime
from flask import current_app, flash, redirect, render_template, url_for, \
    request, abort
from flask_login import logout_user, login_user
from dmutils.audit import AuditTypes
from dmutils.user import user_has_role, User
from dmutils.formats import DATETIME_FORMAT
from dmutils.email import send_email, \
    generate_token, decode_token, MandrillException
from .. import main
from ..forms.auth_forms import LoginForm, EmailAddressForm, ChangePasswordForm, CreateUserForm
from ..helpers import hash_email, is_existing_supplier_user
from ... import data_api_client


ONE_DAY_IN_SECONDS = 86400
SEVEN_DAYS_IN_SECONDS = 604800


@main.route('/login', methods=["GET"])
def render_login():
    next_url = request.args.get('next')
    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template(
        "auth/login.html",
        form=LoginForm(),
        next=next_url,
        **template_data), 200


@main.route('/login', methods=["POST"])
def process_login():
    form = LoginForm()
    next_url = request.args.get('next')
    template_data = main.config['BASE_TEMPLATE_DATA']
    if form.validate_on_submit():

        user_json = data_api_client.authenticate_user(
            form.email_address.data,
            form.password.data)

        if not user_has_role(user_json, 'supplier'):
            current_app.logger.info(
                "login.fail: failed to log in {email_hash}",
                extra={'email_hash': hash_email(form.email_address.data)})
            flash("no_account", "error")
            return render_template(
                "auth/login.html",
                form=form,
                next=next_url,
                **template_data), 403

        user = User.from_json(user_json)
        login_user(user)
        current_app.logger.info("login.success")
        if next_url and next_url.startswith('/suppliers'):
            return redirect(next_url)

        return redirect(url_for('.dashboard'))

    else:
        return render_template(
            "auth/login.html",
            form=form,
            next=next_url,
            **template_data), 400


@main.route('/logout', methods=["GET"])
def logout():
    logout_user()
    return redirect(url_for('.render_login'))


@main.route('/reset-password', methods=["GET"])
def request_password_reset():
    template_data = main.config['BASE_TEMPLATE_DATA']

    return render_template("auth/request-password-reset.html",
                           form=EmailAddressForm(),
                           **template_data), 200


@main.route('/reset-password', methods=["POST"])
def send_reset_password_email():
    form = EmailAddressForm()
    if form.validate_on_submit():
        email_address = form.email_address.data
        user_json = data_api_client.get_user(email_address=email_address)

        if user_json is not None:

            user = User.from_json(user_json)

            token = generate_token(
                {
                    "user": user.id,
                    "email": user.email_address
                },
                current_app.config['SECRET_KEY'],
                current_app.config['RESET_PASSWORD_SALT']
            )

            url = url_for('main.reset_password', token=token, _external=True)

            email_body = render_template(
                "emails/reset_password_email.html",
                url=url,
                locked=user.locked)

            try:
                send_email(
                    user.email_address,
                    email_body,
                    current_app.config['DM_MANDRILL_API_KEY'],
                    current_app.config['RESET_PASSWORD_EMAIL_SUBJECT'],
                    current_app.config['RESET_PASSWORD_EMAIL_FROM'],
                    current_app.config['RESET_PASSWORD_EMAIL_NAME'],
                    ["password-resets"]
                )
            except MandrillException as e:
                current_app.logger.error(
                    "Password reset email failed to send. "
                    "error {error} email_hash {email_hash}",
                    extra={'error': six.text_type(e),
                           'email_hash': hash_email(user.email_address)})
                abort(503, "Failed to send password reset")

            message = "login.reset-email.sent: " \
                      "Sending password reset email for supplier %d (%s)"

            params = dict(
                supplier_id=user.supplier_id,
                email_hash=hash_email(user.email_address))
            current_app.logger.info(
                "login.reset-email.sent: Sending password reset email for "
                "supplier_id {supplier_id} email_hash {email_hash}",
                extra={'supplier_id': user.supplier_id,
                       'email_hash': hash_email(user.email_address)})
        else:
            current_app.logger.info(
                "login.reset-email.invalid-email: "
                "Password reset request for invalid supplier email {email_hash}",
                extra={'email_hash': hash_email(email_address)})

        flash('email_sent')
        return redirect(url_for('.request_password_reset'))
    else:
        template_data = main.config['BASE_TEMPLATE_DATA']
        return render_template("auth/request-password-reset.html",
                               form=form,
                               **template_data), 400


@main.route('/reset-password/<token>', methods=["GET"])
def reset_password(token):
    decoded = decode_password_reset_token(token)
    if not decoded:
        return redirect(url_for('.request_password_reset'))

    email_address = decoded["email"]

    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template("auth/reset-password.html",
                           email_address=email_address,
                           form=ChangePasswordForm(),
                           token=token,
                           **template_data), 200


@main.route('/reset-password/<token>', methods=["POST"])
def update_password(token):
    form = ChangePasswordForm()
    decoded = decode_password_reset_token(token)
    if not decoded:
        return redirect(url_for('.request_password_reset'))

    user_id = decoded["user"]
    email_address = decoded["email"]
    password = form.password.data

    if form.validate_on_submit():
        if data_api_client.update_user_password(user_id, password, email_address):
            current_app.logger.info(
                "User {user_id} successfully changed their password",
                extra={'user_id': user_id})
            flash('password_updated')
        else:
            flash('password_not_updated', 'error')
        return redirect(url_for('.render_login'))
    else:
        template_data = main.config['BASE_TEMPLATE_DATA']
        return render_template("auth/reset-password.html",
                               email_address=email_address,
                               form=form,
                               token=token,
                               **template_data), 400


@main.route('/create-user/<string:encoded_token>', methods=["GET"])
def create_user(encoded_token):
    form = CreateUserForm()
    template_data = main.config['BASE_TEMPLATE_DATA']

    token = decode_invitation_token(encoded_token)

    if token is None:
        current_app.logger.warning(
            "createuser.token_invalid: {encoded_token}",
            extra={'encoded_token': encoded_token})
        flash('token_invalid', 'error')
        return render_template(
            "auth/create-user.html",
            form=form,
            token=None,
            email_address=None,
            supplier_name=None,
            **template_data), 400

    else:
        user_json = data_api_client.get_user(email_address=token.get("email_address"))

        if not user_json:

            # account does not exist
            return render_template(
                "auth/create-user.html",
                form=form,
                email_address=token['email_address'],
                supplier_name=token['supplier_name'],
                token=encoded_token,
                **template_data), 200

        user = User.from_json(user_json)

        # locked or inactive
        is_inactive_or_locked = 'inactive' if not user.active else 'locked' if user.is_locked() else False

        # supplier account exists (wrong supplier)
        is_registered_to_another_supplier = False
        if user.role == 'supplier' and token.get("supplier_name") != user.supplier_name:
            is_registered_to_another_supplier = {
                'supplier_who_sent_the_invitation': token.get("supplier_name"),
                'supplier_registered_with_account': user.supplier_name,
            }

        # valid supplier account exists
        if user.role == 'supplier' and not is_registered_to_another_supplier and not is_inactive_or_locked:
            # valid supplier account exists and is logged in
            if not current_user.is_anonymous() and current_user.email_address == user.email_address:
                return redirect(url_for('.dashboard'))

            return redirect(url_for('.render_login'))

        return render_template(
            "auth/update-user.html",
            user=user_json["users"],
            form=form,
            email_address=token['email_address'],
            supplier_name=token['supplier_name'],
            token=encoded_token,
            is_inactive_or_locked=is_inactive_or_locked,
            is_registered_to_another_supplier=is_registered_to_another_supplier,
            **template_data), 200


@main.route('/update-user/<string:encoded_token>', methods=["POST"])
def submit_update_user(encoded_token):
    template_data = main.config['BASE_TEMPLATE_DATA']

    token = decode_invitation_token(encoded_token)
    if token is None:
        current_app.logger.warning(
            "createuser.token_invalid: {encoded_token}",
            extra={'encoded_token': encoded_token})
        flash('token_invalid', 'error')
        return render_template(
            "auth/update-user.html",
            token=None,
            email_address=None,
            supplier_name=None,
            **template_data), 400

    else:
        user_json = data_api_client.get_user(email_address=token.get("email_address"))

        user = User.from_json(user_json)
        if user.is_locked() or not user.is_active() or not user_has_role(user_json, 'buyer'):
            current_app.logger.warning(
                "createuser.user_invalid: "
                "user_id: {user_id} supplier_id: {supplier_id}",
                extra={'user_id': user.id,
                       'supplier_id': token.get('supplier_id')})
            abort(400, "should not update an existing supplier")

        if current_user.is_anonymous():
            updater = token.get("email_address")
        else:
            updater = current_user.email_address

        data_api_client.update_user(
            user_id=user.id,
            supplier_id=token.get("supplier_id"),
            role='supplier',
            updater=updater
        )
        login_user(user)
        return redirect(url_for('.dashboard'))


@main.route('/create-user/<string:encoded_token>', methods=["POST"])
def submit_create_user(encoded_token):
    template_data = main.config['BASE_TEMPLATE_DATA']
    form = CreateUserForm()

    token = decode_invitation_token(encoded_token)
    if token is None:
        current_app.logger.warning("createuser.token_invalid: {encoded_token}",
                                   extra={'encoded_token': encoded_token})
        flash('token_invalid', 'error')
        return render_template(
            "auth/create-user.html",
            form=form,
            token=None,
            email_address=None,
            supplier_name=None,
            **template_data), 400

    else:
        if not form.validate_on_submit():
            current_app.logger.warning(
                "createuser.invalid: {form_errors}",
                extra={'form_errors': ", ".join(form.errors)})
            return render_template(
                "auth/create-user.html",
                valid_token=False,
                form=form,
                token=encoded_token,
                email_address=token.get('email_address'),
                supplier_name=token.get('supplier_name'),
                **template_data), 400

        user = data_api_client.create_user({
            'name': form.name.data,
            'password': form.password.data,
            'emailAddress': token.get('email_address'),
            'role': 'supplier',
            'supplierId': token.get('supplier_id')
        })
        user = User.from_json(user)
        login_user(user)

        return redirect(url_for('.dashboard'))


@main.route('/invite-user', methods=["GET"])
@login_required
def invite_user():
    form = EmailAddressForm()

    template_data = main.config['BASE_TEMPLATE_DATA']

    return render_template(
        "auth/submit-email-address.html",
        form=form,
        **template_data), 200


@main.route('/invite-user', methods=["POST"])
@login_required
def send_invite_user():
    form = EmailAddressForm()

    user = data_api_client.get_user(
        email_address=form.email_address.data
    )

    if form.validate_on_submit() and not is_existing_supplier_user(user):
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
        if is_existing_supplier_user(user):
            form.email_address.errors.append('An account already exists with this email address.')
        template_data = main.config['BASE_TEMPLATE_DATA']
        return render_template(
            "auth/submit-email-address.html",
            form=form,
            **template_data), 400


def decode_password_reset_token(token):
    try:
        decoded, timestamp = decode_token(
            token,
            main.config["SECRET_KEY"],
            main.config["RESET_PASSWORD_SALT"],
            ONE_DAY_IN_SECONDS
        )
    except SignatureExpired:
        current_app.logger.info("Password reset attempt with expired token.")
        flash('token_expired', 'error')
        return None
    except BadSignature as e:
        current_app.logger.info("Error changing password: {error}", extra={'error': six.text_type(e)})
        flash('token_invalid', 'error')
        return None

    user = data_api_client.get_user(decoded["user"])
    user_last_changed_password_at = datetime.strptime(
        user['users']['passwordChangedAt'],
        DATETIME_FORMAT
    )

    if token_created_before_password_last_changed(
            timestamp,
            user_last_changed_password_at
    ):
        current_app.logger.info("Error changing password: Token generated earlier than password was last changed.")
        flash('token_invalid', 'error')
        return None

    return decoded


def decode_invitation_token(encoded_token):
    try:
        token, timestamp = decode_token(
            encoded_token,
            current_app.config['SHARED_EMAIL_KEY'],
            current_app.config['INVITE_EMAIL_SALT'],
            SEVEN_DAYS_IN_SECONDS
        )
        if all(field in token for field in ("email_address", 'supplier_id', 'supplier_name')):
            return token
        else:
            raise ValueError('Missing invalid invitation token')
    except SignatureExpired as e:
        current_app.logger.info("Invitation attempt with expired token. error {error}",
                                extra={'error': six.text_type(e)})
        return None
    except BadSignature as e:
        current_app.logger.info("Invitation reset attempt with expired token. error {error}",
                                extra={'error': six.text_type(e)})
        return None
    except ValueError as e:
        current_app.logger.info("error {error}",
                                extra={'error': six.text_type(e)})
        return None


def token_created_before_password_last_changed(token_timestamp, user_timestamp):
    return token_timestamp < user_timestamp
