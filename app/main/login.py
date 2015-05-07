from __future__ import absolute_import
from itsdangerous import BadSignature, SignatureExpired

from flask import current_app, flash, redirect, render_template, request, \
    url_for
from flask_login import logout_user, login_user

from . import main
from .forms.login_form import LoginForm
from .. import data_api_client
from ..model import User
from .helpers import email


@main.route('/login', methods=["GET"])
def render_login():
    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template(
        "auth/login.html",
        form=LoginForm(),
        **template_data), 200


@main.route('/login', methods=["POST"])
def process_login():
    form = LoginForm()
    template_data = main.config['BASE_TEMPLATE_DATA']
    if form.validate_on_submit():

        user_json = data_api_client.authenticate_user(
            form.email_address.data,
            form.password.data)

        if not user_json:
            flash("no_account", "error")
            return render_template(
                "auth/login.html",
                form=form,
                **template_data), 403

        user = User.from_json(user_json)
        login_user(user)
        return redirect(url_for('.dashboard'))
    else:
        return render_template(
            "auth/login.html",
            form=form,
            **template_data), 400


@main.route('/logout', methods=["GET"])
def logout():
    logout_user()
    return redirect(url_for('.render_login'))


@main.route('/forgotten-password', methods=["GET"])
def forgotten_password():
    template_data = main.config['BASE_TEMPLATE_DATA']

    return render_template("auth/forgotten-password.html",
                           **template_data), 200


@main.route('/forgotten-password', methods=["POST"])
def send_reset_email():
    email_address = request.form['email-address']
    user_json = data_api_client.get_user(email_address=email_address)
    if user_json is not None:
        user = User.from_json(user_json)
        # Send a password reset email with token
        current_app.logger.info(
            "Sending password reset email for supplier %d (%s)",
            user.id, user.email_address
        )
        email.send_password_email(user.id, email_address)
        # TODO: Add to count in "forgotten password emails sent" metric
    else:
        current_app.logger.info(
            "Password reset request for invalid supplier email address %s",
            email_address
        )
        # TODO: Add to count in "forgotten password - invalid" metric

    flash('email_sent')
    return redirect(url_for('.forgotten_password'))


@main.route('/change-password/<token>', methods=["GET"])
def change_password(token):
    try:
        decoded = email.decode_email(token)
        user_id = decoded["user"]
        email_address = decoded["email"]
    except SignatureExpired:
        current_app.logger.info("Password reset attempt with expired token.")
        flash('token_expired', 'error')
        return redirect(url_for('.forgotten_password'))
    except BadSignature as e:
        current_app.logger.info("Error changing password: %s", e)
        flash('token_invalid', 'error')
        return redirect(url_for('.forgotten_password'))
    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template("auth/change-password.html", email=email_address,
                           user_id=user_id, **template_data), 200


@main.route('/change-password', methods=["POST"])
def update_password():
    email_address = request.form['email-address']
    user_id = request.form['user-id']
    password = request.form['password']
    confirm = request.form['confirm-password']

    if not password:
        flash('passwords_empty', 'error')
        return redirect(email.generate_reset_url(user_id, email_address))
    if password != confirm:
        flash('passwords_differ', 'error')
        return redirect(email.generate_reset_url(user_id, email_address))
    # TODO: Add any other password requirements here (e.g. min length = ?)

    if data_api_client.update_user_password(user_id, password):
        current_app.logger.info("User %s successfully changed their password",
                                user_id)
        flash('password_updated')
    else:
        flash('password_not_updated', 'error')
    return redirect(url_for('.render_login'))
