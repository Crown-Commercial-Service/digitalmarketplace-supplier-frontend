import csv
import json
import logging
import requests
import sys

from flask import current_app, render_template, url_for

from dmapiclient import HTTPError
from dmutils.email import EmailError, send_email

from app import data_api_client
from app.main.helpers.users import generate_supplier_invitation_token


def send_supplier_invite(name, email_address, supplier_code, supplier_name):
    """Send invite email to new supplier from Marketplace admin and record in API's log.

    Raises EmailError if failed to send, or HTTPError if logging failed.
    """
    token = generate_supplier_invitation_token(name, email_address, supplier_code, supplier_name)
    activation_url = url_for('main.create_user', token=token)
    subject = current_app.config['NEW_SUPPLIER_INVITE_SUBJECT']
    email_body = render_template(
        'emails/new_supplier_invite_email.html',
        subject=subject,
        name=name,
        activation_url=activation_url
    )
    send_email(
        email_address,
        email_body,
        subject,
        current_app.config['DM_GENERIC_NOREPLY_EMAIL'],
        current_app.config['DM_GENERIC_ADMIN_NAME']
    )
    data_api_client.record_supplier_invite(
        supplier_code=supplier_code,
        email_address=email_address
    )


def send_supplier_invites(source=sys.stdin):
    """
    Read CSV list of suppliers to be invited and send invites.

    Required fields are user name, user email address, supplier code and supplier name.
    E.g.:
    Me,me@example.com,123,Example Supplier
    Someone Else,someone.else@example.com,456,Another Example Supplier
    """
    for supplier_record in csv.reader(source):
        name, email_address, supplier_code, supplier_name = supplier_record
        try:
            send_supplier_invite(name, email_address, int(supplier_code), supplier_name)
        except EmailError as e:
            logging.error('Failed to send invitation email to {}'.format(supplier_record))
        except HTTPError as e:
            logging.error('Failed to record invite for {}'.format(supplier_record))


def list_supplier_invite_candidates(sink=sys.stdout):
    """
    Output list of candidates for supplier account invites as CSV list.

    The format is the same as for send_supplier_invites.
    """
    response = data_api_client.list_supplier_account_invite_candidates()
    output = csv.writer(sink)
    for candidate in response['results']:
        contact = candidate['contact']
        name = contact['name']
        email_address = contact['email']
        supplier_code = candidate['supplierCode']
        supplier_name = candidate['supplierName']
        output.writerow((name, email_address, supplier_code, supplier_name))


def init_manager(manager):
    """Adds appropriate invite management commands to the Flask Script manager.

    These can be run from the command line.
    """

    manager.command(send_supplier_invites)
    manager.command(list_supplier_invite_candidates)
