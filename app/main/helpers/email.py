from flask import url_for
import mandrill
from itsdangerous import URLSafeTimedSerializer

from .. import main


def send_password_email(email_address):
    try:
        mandrill_client = mandrill.Mandrill(main.config['MANDRILL_API_KEY'])
        url = generate_reset_url(email_address)
        body = main.config['FORGOT_PASSWORD_EMAIL_BODY'].format(url)
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
                        'values': {'user_id': 123456}}]
        }
        result = mandrill_client.messages.send(message=message, async=False,
                                               ip_pool='Main Pool')
        '''
        [{'_id': 'abc123abc123abc123abc123abc123',
          'email': 'recipient.email@example.com',
          'reject_reason': 'hard-bounce',
          'status': 'sent'}]
        '''
    except mandrill.Error as e:
        # Mandrill errors are thrown as exceptions
        print 'A mandrill error occurred: %s - %s' % (e.__class__, e)
        # A mandrill error occurred: <class 'mandrill.UnknownSubaccountError'>
        # - No subaccount exists with the id 'customer-123'
        raise
    print("Email result: " + str(result))


def generate_reset_url(email_address):
    ts = URLSafeTimedSerializer(main.config["SECRET_KEY"])
    token = ts.dumps(email_address, salt=main.config["SECRET_SALT"])
    url = url_for('.change_password', token=token, _external=True)
    print("Generated reset URL: " + url)
    return url


def decode_email(token):
    ts = URLSafeTimedSerializer(main.config["SECRET_KEY"])
    email = ts.loads(token, salt=main.config["SECRET_SALT"], max_age=86400)
    return email
