from __future__ import absolute_import
from itsdangerous import BadSignature, SignatureExpired
from datetime import datetime
from flask import current_app, flash, redirect, render_template, url_for, \
    request, abort
from flask_login import logout_user, login_user
from dmutils.user import user_has_role, User
from dmutils.formats import DATETIME_FORMAT
from dmutils.email import send_email, \
    generate_token, decode_token, MandrillException

from .. import main
from ..forms.auth_forms import LoginForm, EmailAddressForm, ChangePasswordForm
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
                main.config['SECRET_KEY'],
                main.config['RESET_PASSWORD_SALT']
            )

            url = url_for('main.reset_password', token=token, _external=True)

            email_body = render_template(
                "emails/reset_password_email.html",
                url=url,
                locked=user.locked)

            try:
                send_email(
                    user.id,
                    user.email_address,
                    email_body,
                    main.config['DM_MANDRILL_API_KEY'],
                    main.config['RESET_PASSWORD_EMAIL_SUBJECT'],
                    main.config['RESET_PASSWORD_EMAIL_FROM'],
                    main.config['RESET_PASSWORD_EMAIL_NAME'],
                    ["password-resets"]
                )
            except MandrillException as e:
                print e.message
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


@main.route('/invite-user', methods=["POST"])
def invite_user():
    return redirect(url_for('.dashboard'))


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
