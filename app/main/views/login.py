from __future__ import absolute_import
from flask_login import login_required, current_user
from itsdangerous import BadSignature, SignatureExpired
from datetime import datetime
from flask import current_app, flash, redirect, render_template, url_for, \
    request, abort
from flask_login import logout_user, login_user
from dmutils.user import user_has_role, User
from dmutils.formats import DATETIME_FORMAT
from dmutils.email import send_email, \
    generate_token, decode_token, MandrillException
from dmutils.apiclient.errors import HTTPError
from .. import main
from ..forms.auth_forms import LoginForm, EmailAddressForm, ChangePasswordForm, CreateUserForm
from ... import data_api_client


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
            message = "login.fail: " \
                      "Failed to log in: %s"
            current_app.logger.info(message, form.email_address.data)
            flash("no_account", "error")
            return render_template(
                "auth/login.html",
                form=form,
                next=next_url,
                **template_data), 403

        user = User.from_json(user_json)
        login_user(user)
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
                current_app.logger.error("Email failed to send {}".format(e.message))
                abort(503, "Failed to send password reset")

            message = "login.reset-email.sent: " \
                      "Sending password reset email for supplier %d (%s)"

            current_app.logger.info(message, user.id, user.email_address)
        else:
            message = "login.reset-email.invalid-email: " \
                      "Password reset request for invalid supplier email %s"
            current_app.logger.info(message, email_address)

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
        if data_api_client.update_user_password(user_id, password):
            current_app.logger.info(
                "User %s successfully changed their password", user_id)
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

    try:
        token, timestamp = decode_token(
            encoded_token,
            current_app.config['SECRET_KEY'],
            current_app.config['RESET_PASSWORD_SALT']
        )
        if not token.get('email_address', None):
            raise Exception('Missing email address from token')
        if not token.get('supplier_id', None):
            raise Exception('Missing supplier from token')
    except Exception as e:
        current_app.logger.error(e.message)
        flash('token_invalid', 'error')
        return render_template(
            "auth/create-user.html",
            valid_token=False,
            form=form,
            token=encoded_token,
            email_address=None,
            supplier=None,
            **template_data), 400

    try:
        data_api_client.get_user(email_address=token['email_address'])
    except HTTPError as e:
        current_app.logger.error(e.message)
    try:
        supplier = data_api_client.get_supplier(token['supplier_id'])
    except HTTPError as e:
        current_app.logger.error(e.message)
        abort(404, "Failed to find supplier")

    return render_template(
        "auth/create-user.html",
        valid_token=True,
        form=form,
        email_address=token['email_address'],
        supplier=supplier["suppliers"],
        token=token,
        **template_data), 200


@main.route('/create-user/<string:encoded_token>', methods=["POST"])
def submit_create_user(encoded_token):
    template_data = main.config['BASE_TEMPLATE_DATA']

    form = CreateUserForm()

    try:
        token, timestamp = decode_token(
            encoded_token,
            current_app.config['SECRET_KEY'],
            current_app.config['RESET_PASSWORD_SALT']
        )
        if not token.get('email_address', None):
            raise Exception('Missing email address from token')
        if not token.get('supplier_id', None):
            raise Exception('Missing supplier from token')
    except Exception as e:
        current_app.logger.error(e.message)
        flash('token_invalid', 'error')
        return render_template(
            "auth/create-user.html",
            valid_token=False,
            form=form,
            token=encoded_token,
            email_address=None,
            supplier=None,
            **template_data), 400

    user = None

    # does user exist
    try:
        user = data_api_client.get_user(token.get('email_address'))
        user = data_api_client.update_user({
            'role': 'supplier',
            'supplier_id': token.get('supplier_id')
        })
    except HTTPError as e:
        if e.status_code is 404:
            # Create user
            user = data_api_client.create_user({
                'name': form.name.data,
                'password': form.name.password,
                'email_address': token.get('email_address'),
                'role': 'supplier',
                'supplier_id': token.get('supplier_id')
            })

    user = User.from_json(user)
    login_user(user)

    return redirect(url_for('.dashboard'))


@main.route('/invite-user', methods=["GET"])
@login_required
def invite_user():
    form = CreateUserForm()

    template_data = main.config['BASE_TEMPLATE_DATA']

    return render_template(
        "auth/submit-email-address.html",
        form=form,
        **template_data), 200


@main.route('/invite-user', methods=["POST"])
@login_required
def send_invite_user():
    form = EmailAddressForm()

    if form.validate_on_submit():

        token = generate_token(
            {
                "supplier_id": current_user.supplier_id,
                "email_address": form.email_address.data
            },
            current_app.config['SECRET_KEY'],
            current_app.config['RESET_PASSWORD_SALT']
        )

        url = url_for('main.create_user', token=token, _external=True)

        email_body = render_template(
            "emails/invite_user_email.html",
            url=url,
            user=current_user.name,
            supplier=current_user.supplier_name)

        print current_app.config['DM_MANDRILL_API_KEY']

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
                "Invitation email failed to send error {} to {} suppluer {} supplier id {} ".format(
                    e.message,
                    form.email_address.data,
                    current_user.supplier_name,
                    current_user.supplier_id)
            )
            abort(503, "Failed to send user invite reset")

        flash('user_invited', 'success')
        return redirect(url_for('.invite_user'))
    else:
        template_data = main.config['BASE_TEMPLATE_DATA']
        return render_template(
            "auth/submit-email-address.html",
            form=form,
            **template_data), 400


def decode_password_reset_token(token):
    try:
        decoded, timestamp = decode_token(token, main.config["SECRET_KEY"], main.config["RESET_PASSWORD_SALT"])

    except SignatureExpired:
        current_app.logger.info("Password reset attempt with expired token.")
        flash('token_expired', 'error')
        return None
    except BadSignature as e:
        current_app.logger.info("Error changing password: %s", e)
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
        current_app.logger.info(
            "Error changing password: "
            + "Token generated earlier than password was last changed."
        )
        flash('token_invalid', 'error')
        return None

    return decoded


def token_created_before_password_last_changed(token_timestamp, user_timestamp):
    return token_timestamp < user_timestamp
