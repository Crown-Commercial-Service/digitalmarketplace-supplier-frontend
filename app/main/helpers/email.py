from flask import url_for, current_app, render_template
import mandrill
from itsdangerous import URLSafeTimedSerializer

from .. import main


def send_password_email(user_id, email_address):
    try:
        mandrill_client = mandrill.Mandrill(main.config['MANDRILL_API_KEY'])
        url = generate_reset_url(user_id, email_address)
        body = render_template("emails/forgotten_password_email.html", url=url)
        message = {'html': body,
                   'subject': main.config['FORGOT_PASSWORD_EMAIL_SUBJECT'],
                   'from_email': main.config['FORGOT_PASSWORD_EMAIL_FROM'],
                   'from_name': main.config['FORGOT_PASSWORD_EMAIL_NAME'],
                   'to': [{'email': email_address,
                           'name': 'Recipient Name',
                           'type': 'to'}],
                   'important': False,
                   'track_opens': None,
                   'track_clicks': None,
                   'auto_text': True,
                   'tags': ['password-resets'],
                   'headers': {'Reply-To': main.config['FORGOT_PASSWORD_EMAIL_FROM']},  # noqa
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
    encoded_string = str(user_id) + " " + email_address
    ts = URLSafeTimedSerializer(main.config["SECRET_KEY"])
    token = ts.dumps(encoded_string, salt=main.config["SECRET_SALT"])
    url = url_for('.change_password', token=token, _external=True)
    current_app.logger.debug("Generated reset URL: %s", url)
    return url


def decode_email(token):
    ts = URLSafeTimedSerializer(main.config["SECRET_KEY"])
    decoded = ts.loads(token, salt=main.config["SECRET_SALT"], max_age=86400)
    return decoded
