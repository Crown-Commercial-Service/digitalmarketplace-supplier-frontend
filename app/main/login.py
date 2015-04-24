from __future__ import absolute_import

from flask import flash, redirect, render_template, request, Response, url_for
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
                "Sorry, we couldn't find a user with "
                "that username and password")
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
    try:
        email_address = request.form['email-address']
        # TODO: Check in API that the user account exists

        # Send a password reset email with token
        email.send_password_email(email_address)

        flash('If that Digital Marketplace account exists, you will be sent '
              'an email containing a link to reset your password.')
        return redirect(url_for('.forgotten_password'))
    except Exception as e:
        return Response("Error: %s" % str(e), 500)


@main.route('/change-password/<token>', methods=["GET"])
@login_required
def change_password(token):
    try:
        email_address = email.decode_email(token)
    except Exception as e:
        flash('The token supplied was invalid or has expired. Password reset'
              ' links are only valid for 24 hours. You can generate a new one'
              ' using the form below.', 'error')
        return redirect(url_for('.forgotten_password'))
    print("Change password for: " + email_address)
    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template("auth/change-password.html", email=email_address,
                           **template_data), 200


@main.route('/change-password', methods=["POST"])
def update_password():
    email_address = request.form['email-address']
    password = request.form['password']
    confirm = request.form['confirm-password']

    if password != confirm:
        flash('The passwords you entered do not match.', 'error')
        return redirect(email.generate_reset_url(email_address))

    print("changing password for {0} to '{1}'".format(email_address, password))
    # TODO: send API call to update password
    return redirect(url_for('.password_changed'))


@main.route('/password-changed', methods=["GET"])
def password_changed():
    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template("auth/password-changed.html", **template_data), 200
