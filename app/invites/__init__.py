import csv
import json
import logging
import requests
import sys

from flask import current_app, render_template, url_for
from flask_script import Manager

from dmapiclient import HTTPError
from dmutils.email import EmailError, send_email

from app import data_api_client
from app.main.helpers.users import generate_supplier_invitation_token


# This stuff is a bit kludgy.  If we did it all in the server, we'd have all the configuration and keys needed to send
# emails properly, but then it would be harder to handle the variety of special requests for invites that we get.
# These tools were created as a quick solution to an initial problem.  Maybe more of this code can be turned into
# server-side handlers after the use cases stabilise.
#
# To use these commands, first pull the environment variables from a production server using
# $ cf env <supplier-app-name>
# Export these variables inside your own shell.
#
# After that, this will produce a list of suppliers who haven't received invites:
# $ python application.py supplier_invites list_candidates > /tmp/invites
#
# And this will send the invites:
# $ python application.py supplier_invites send < /tmp/invites
#
# The invite list ultimately comes from data entered into a spreadsheet, so it's a good idea to check the list for
# obvious errors.  Before doing a live mailout, you can also test sending using the Example Pty Ltd supplier.
#
# Run this for more docs:
# $ python application.py supplier_invites -?


def send_supplier_invite(name, email_address, supplier_code, supplier_name):
    """Send invite email to new supplier from Marketplace admin and record in API's log.

    Raises EmailError if failed to send, or HTTPError if logging failed.
    """
    token = generate_supplier_invitation_token(name, email_address, supplier_code, supplier_name)
    activation_url = url_for(
        'main.create_user',
        token=token,
        _external=True,
        _scheme=current_app.config['DM_HTTP_PROTO']
    )
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


def format_potential_invites(contact_list, sink=sys.stdout):
    """
    Formats json contact/supplier info as CSV.

    Using CSV as a common format makes ad-hoc usage of these tools easier.
    """
    output = csv.writer(sink)
    for candidate in contact_list:
        contact = candidate['contact']
        name = contact['name']
        email_address = contact['email']
        supplier_code = candidate['supplierCode']
        supplier_name = candidate['supplierName']
        output.writerow((name, email_address, supplier_code, supplier_name))


def send(source=sys.stdin):
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


def list_candidates(sink=sys.stdout):
    """
    Output list of candidates for supplier account invites as CSV list.

    The format is the same as for send_supplier_invites.
    """
    response = data_api_client.list_supplier_account_invite_candidates()
    format_potential_invites(response['results'], sink)


def list_unclaimed(sink=sys.stdout):
    """
    Output list of unclaimed invitees in CSV format for resending invites.

    The format is the same as for send_supplier_invites.
    """
    response = data_api_client.list_unclaimed_supplier_account_invites()
    format_potential_invites(response['results'], sink)


def init_manager(manager):
    """Adds appropriate invite management commands to the Flask Script manager.

    These can be run from the command line.
    """
    sub_manager = Manager(
        description='Commands for managing supplier invites',
        usage='Run "python application.py supplier_invites -?" to see subcommand list'
    )

    sub_manager.command(send)
    sub_manager.command(list_candidates)
    sub_manager.command(list_unclaimed)
    manager.add_command('supplier_invites', sub_manager)
