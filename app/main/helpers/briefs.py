import six

from flask import abort, current_app, render_template
from flask_login import current_user

from dmutils.email import send_email, hash_email, MandrillException


def get_brief(data_api_client, brief_id, live_only=True):
    brief = data_api_client.get_brief(brief_id)['briefs']
    if live_only and brief['status'] != 'live':
        abort(404)

    return brief


def check_supplier_is_eligible_for_brief(brief, supplier_id):
    # TODO connect this with the API endpoint once it exists
    # Should abort or render an error page if the check fails
    pass


def send_brief_clarification_question(brief, clarification_question):
    # Email the question to brief owners
    email_body = render_template(
        "emails/brief_clarification_question.html",
        brief_name=brief['title'],
        message=clarification_question
    )
    try:
        send_email(
            to_email_addresses=get_brief_user_emails(brief),
            email_body=email_body,
            api_key=current_app.config['DM_MANDRILL_API_KEY'],
            subject="{} clarification question".format(brief['title']),
            from_email=current_app.config['CLARIFICATION_EMAIL_FROM'],
            from_name="{} Supplier".format(brief['frameworkName']),
            tags=["brief-clarification-question"]
        )
    except MandrillException as e:
        current_app.logger.error(
            "Brief question email failed to send. error={error} supplier_id={supplier_id} brief_id={brief_id}",
            extra={'error': six.text_type(e), 'supplier_id': current_user.supplier_id, 'brief_id': brief['id']}
        )

        abort(503, "Clarification question email failed to send")

    # Send the supplier a copy of the question
    supplier_email_body = render_template(
        "emails/brief_clarification_question_confirmation.html",
        brief_name=brief['title'],
        message=clarification_question
    )
    try:
        send_email(
            to_email_addresses=[current_user.email_address],
            email_body=supplier_email_body,
            api_key=current_app.config['DM_MANDRILL_API_KEY'],
            subject="Your {} clarification question".format(brief['title']),
            from_email=current_app.config['CLARIFICATION_EMAIL_FROM'],
            from_name=current_app.config['CLARIFICATION_EMAIL_NAME'],
            tags=["brief-clarification-question-confirmation"]
        )
    except MandrillException as e:
        current_app.logger.error(
            "Brief question supplier email failed to send. error={error} supplier_id={supplier_id} brief_id={brief_id}",
            extra={'error': six.text_type(e), 'supplier_id': current_user.supplier_id, 'brief_id': brief['id']}
        )


def get_brief_user_emails(brief):
    return [user['emailAddress'] for user in brief['users'] if user['active']]
