from __future__ import absolute_import
from itsdangerous import BadSignature, SignatureExpired

from flask import current_app, flash, redirect, render_template, request, \
    Response, url_for
from flask_login import logout_user, login_required, login_user, current_user

from . import main
from .forms.login_form import LoginForm
from .. import api_client
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

        user = api_client.users_auth(
            form.email_address.data,
            form.password.data)

        if not user:
            flash(
                "Sorry, we couldn't find a supplier account with "
                "that username and password", "error")
            return render_template(
                "auth/login.html",
                form=form,
                **template_data), 403

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
    user = api_client.user_by_email(email_address)
    if user is not None:
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

    flash('If that Digital Marketplace supplier account exists, you will '
          'be sent an email containing a link to reset your password.')
    return redirect(url_for('.forgotten_password'))


@main.route('/change-password/<token>', methods=["GET"])
def change_password(token):
    try:
        decoded = email.decode_email(token)
        user_id = decoded["user"]
        email_address = decoded["email"]
    except SignatureExpired:
        current_app.logger.info("Password reset attempt with expired token.")
        flash('The token supplied has expired. Password reset links are only'
              ' valid for 24 hours. You can generate a new one using the form'
              ' below.', 'error')
        return redirect(url_for('.forgotten_password'))
    except BadSignature as e:
        current_app.logger.info("Error changing password: %s", e)
        flash('The token supplied was invalid. You can generate a new one'
              ' using the form below.', 'error')
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
        flash('Please enter a new password.', 'error')
        return redirect(email.generate_reset_url(user_id, email_address))
    if password != confirm:
        flash('The passwords you entered do not match.', 'error')
        return redirect(email.generate_reset_url(user_id, email_address))
    # TODO: Add any other password requirements here (e.g. min length = ?)

    if api_client.user_update_password(user_id, password):
        current_app.logger.info("User %s successfully changed their password",
                                user_id)
        flash('You have successfully changed your password.')
    else:
        flash('Could not update password due to an error.', 'error')
    return redirect(url_for('.render_login'))
