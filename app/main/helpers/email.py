from flask import url_for, current_app, render_template
import mandrill
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime
from dmutils.formats import DATETIME_FORMAT

from .. import main


def send_password_email(user_id, email_address, locked):
    try:
        mandrill_client = mandrill.Mandrill(main.config['DM_MANDRILL_API_KEY'])
        url = generate_reset_url(user_id, email_address)
        body = render_template("emails/reset_password_email.html",
                               url=url, locked=locked)
        message = {'html': body,
                   'subject': main.config['RESET_PASSWORD_EMAIL_SUBJECT'],
                   'from_email': main.config['RESET_PASSWORD_EMAIL_FROM'],
                   'from_name': main.config['RESET_PASSWORD_EMAIL_NAME'],
                   'to': [{'email': email_address,
                           'name': 'Recipient Name',
                           'type': 'to'}],
                   'important': False,
                   'track_opens': None,
                   'track_clicks': None,
                   'auto_text': True,
                   'tags': ['password-resets'],
                   'headers': {'Reply-To': main.config['RESET_PASSWORD_EMAIL_FROM']},  # noqa
                   'recipient_metadata': [
                       {'rcpt': email_address,
                        'values': {'user_id': user_id}}]
        }
        result = mandrill_client.messages.send(message=message, async=False,
                                               ip_pool='Main Pool')
    except mandrill.Error as e:
        # Mandrill errors are thrown as exceptions
        current_app.logger.error("A mandrill error occurred: %s", e)
        return
    current_app.logger.info("Sent password email: %s", result)


def generate_reset_url(user_id, email_address):
    ts = URLSafeTimedSerializer(main.config["SECRET_KEY"])
    token = ts.dumps({"user": user_id, "email": email_address},
                     salt=main.config["RESET_PASSWORD_SALT"])
    url = url_for('main.reset_password', token=token, _external=True)
    current_app.logger.debug("Generated reset URL: %s", url)
    return url


def decode_email(token):
    ts = URLSafeTimedSerializer(main.config["SECRET_KEY"])
    decoded = ts.loads(token,
                       salt=main.config["RESET_PASSWORD_SALT"],
                       max_age=86400, return_timestamp=True)
    return decoded


def token_created_before_password_last_changed(token_timestamp, user):

        password_last_changed = datetime.strptime(
            user['users']['passwordChangedAt'], DATETIME_FORMAT)
        return token_timestamp < password_last_changed
