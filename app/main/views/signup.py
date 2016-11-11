import six
from flask import render_template, request, url_for, current_app, abort, jsonify, redirect
from app.main import main
from react.render import render_component
from react.response import from_response, validate_form_data
from dmutils.forms import DmForm
from dmutils.email import EmailError, send_email
from app.main.helpers.users import generate_applicant_invitation_token
from ... import data_api_client


@main.route('/signup', methods=['GET'])
def start_seller_signup(applicant={}, errors=None):
    form = DmForm()

    rendered_component = render_component(
        'bundles/SellerRegistration/YourInfoWidget.js', {
            'form_options': {
                'csrf_token': form.csrf_token.current_token,
                'errors': errors
            },
            'yourInfoForm': applicant,
        }
    )

    return render_template(
        '_react.html',
        component=rendered_component
    )


@main.route('/signup', methods=['POST'])
def send_seller_signup_email():
    applicant = from_response(request)

    fields = ['representative', 'name', 'abn', 'phone', 'email']
    errors = validate_form_data(applicant, fields)
    if errors:
        start_seller_signup(applicant, errors)

    token = generate_applicant_invitation_token(applicant)
    url = url_for('main.create_user', token=token, _external=True)
    email_body = render_template(
        'emails/create_seller_user_email.html',
        url=url,
    )

    try:
        send_email(
            applicant['email'],
            email_body,
            current_app.config['INVITE_EMAIL_SUBJECT'],
            current_app.config['INVITE_EMAIL_FROM'],
            current_app.config['INVITE_EMAIL_NAME']
        )
    except EmailError as e:
        current_app.logger.error(
            'Invitation email failed to send. '
            'error {error}',
            extra={'error': six.text_type(e)}
        )
        abort(503, 'Failed to send user invite reset')

    return render_template('auth/seller-signup-email-sent.html', email_address=applicant['email'])


@main.route('/application/<int:id>', methods=['GET'])
@main.route('/application/<int:id>/<path:step>', methods=['GET'])
def application(id, step=None):

    form = DmForm()
    basename = url_for('.application', id=id, step=None)
    rendered_component = render_component('bundles/ApplicantSignup/ApplicantSignupWidget.js',
                                          {'form_options': {'csrf_token': form.csrf_token.current_token,
                                                            'mode': 'edit',
                                                            }, 'basename': basename})
    return render_template(
        '_react.html',
        component=rendered_component
    )


@main.route('/application/<int:id>', methods=['POST'])
@main.route('/application/<int:id>/<path:step>', methods=['POST'])
def application_update(id, step=None):
    json = request.content_type == 'application/json'
    application = from_response(request)

    result = data_api_client.update_application(id, application)

    if json:
        return jsonify(result)
    else:
        return redirect(url_for('.application', id=id, step=application['next_step']))
