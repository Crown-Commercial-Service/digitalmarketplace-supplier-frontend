# coding=utf-8
from itertools import chain

from flask import current_app, request, redirect, url_for, abort, session, Markup, flash
from flask_login import current_user

from dmapiclient.audit import AuditTypes
from dmcontent.content_loader import ContentNotFoundError
from dmutils.dates import update_framework_with_formatted_dates
from dmutils.direct_plus_client import (
    DirectPlusError, DUNSNumberNotFound, DUNSNumberInvalid,
)
from dmutils.email import send_user_account_email
from dmutils.email.dm_mailchimp import DMMailChimpClient
from dmutils.flask import timed_render_template as render_template
from dmutils.forms.helpers import get_errors_from_wtform, govuk_options
from dmutils.errors import render_error_page
from dmutils.dmp_so_status import are_new_frameworks_live

from ...main import main, content_loader, direct_plus_client
from ... import data_api_client
from ..forms.suppliers import (
    AddCompanyRegisteredNameForm,
    AddCompanyRegistrationNumberForm,
    CompanyOrganisationSizeForm,
    CompanyPublicContactInformationForm,
    CompanyTradingStatusForm,
    DunsNumberForm,
    EditRegisteredAddressForm,
    EditSupplierInformationForm,
    EmailAddressForm,
    ConfirmCompanyForm,
)
from ..helpers.frameworks import (
    get_frameworks_by_status,
    get_frameworks_closed_and_open_for_applications,
    get_most_recent_expired_dos_framework,
    get_unconfirmed_open_supplier_frameworks, get_framework_contract_title,
)
from ..helpers.suppliers import (
    COUNTRY_TUPLE,
    get_country_name_from_country_code,
    supplier_company_details_are_complete,
    get_company_details_from_supplier
)
from ..helpers import login_required

JOIN_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_SUCCESS_MESSAGE = (
    "You will receive email notifications to {email_address} when applications are opening."
)
JOIN_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_ERROR_MESSAGE = Markup("""
    The service is unavailable at the moment. If the problem continues please contact
    <a class="govuk-link" href="mailto:{support_email_address}">{support_email_address}</a>.
""")
JOIN_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_ALREADY_SUBSCRIBED_MESSAGE = Markup("""
    This email address has already been used to sign up for Digital Marketplace alerts. Please use a different
     email address or contact <a class="govuk-link" href="mailto:{support_email_address}">{support_email_address}</a>.
""")
JOIN_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_UNSUBSCRIBED_MESSAGE = Markup("""
    This email address cannot be used to sign up for Digital Marketplace alerts. Please use a different
     email address or contact <a class="govuk-link" href="mailto:{support_email_address}">{support_email_address}</a>.
""")


@main.route('')
@login_required
def dashboard():
    supplier = data_api_client.get_supplier(
        current_user.supplier_id
    )['suppliers']
    supplier['contact'] = supplier['contactInformation'][0]

    all_frameworks = sorted(
        data_api_client.find_frameworks()['frameworks'],
        key=lambda framework: framework['slug'],
        reverse=True
    )
    supplier_frameworks = {
        framework['frameworkSlug']: framework
        for framework in data_api_client.get_supplier_frameworks(current_user.supplier_id)['frameworkInterest']
    }

    for framework in all_frameworks:
        framework.update(
            supplier_frameworks.get(framework['slug'], {})
        )

        update_framework_with_formatted_dates(framework)
        framework.update({
            'deadline': Markup(f"Deadline: {framework['applicationsCloseAt']}"),
            'registered_interest': (framework['slug'] in supplier_frameworks),
            'made_application': (
                framework.get('declaration')
                and framework['declaration'].get('status') == 'complete'
                and framework.get('complete_drafts_count') > 0
            ),
            'needs_to_return_agreement': (
                framework.get('onFramework') and framework.get('agreementReturned') is False
            ),
            'contract_title': get_framework_contract_title(framework)
        })

    if "currently_applying_to" in session:
        del session["currently_applying_to"]

    g_cloud_framework_live = [
        framework for framework in get_frameworks_by_status(all_frameworks, 'live') if framework['family'] == 'g-cloud'
    ]

    return render_template(
        "suppliers/dashboard.html",
        supplier=supplier,
        frameworks={
            'coming': get_frameworks_by_status(all_frameworks, 'coming'),
            'open': get_frameworks_by_status(all_frameworks, 'open'),
            'pending': get_frameworks_by_status(all_frameworks, 'pending'),
            'standstill': get_frameworks_by_status(all_frameworks, 'standstill', 'made_application'),
            'live': get_frameworks_by_status(all_frameworks, 'live', 'onFramework'),
            'last_dos': get_most_recent_expired_dos_framework(all_frameworks),
        },
        g_cloud_framework_live=g_cloud_framework_live,
        are_new_frameworks_live=are_new_frameworks_live(request.args)
    ), 200


@main.route('/details', methods=['GET'])
@login_required
def supplier_details():
    supplier = data_api_client.get_supplier(
        current_user.supplier_id
    )['suppliers']
    supplier['contact'] = supplier['contactInformation'][0]
    country_name = get_country_name_from_country_code(supplier.get('registrationCountry'))

    supplier_company_details_confirmed = supplier['companyDetailsConfirmed']
    application_company_details_confirmed = None

    unconfirmed_open_supplier_frameworks = get_unconfirmed_open_supplier_frameworks(data_api_client,
                                                                                    current_user.supplier_id)

    currently_applying_to_framework = (
        data_api_client.get_framework(session["currently_applying_to"])['frameworks']
        if "currently_applying_to" in session else
        None
    )

    return render_template(
        "suppliers/details.html",
        supplier=supplier,
        country_name=country_name,
        currently_applying_to=currently_applying_to_framework,
        supplier_company_details_complete=supplier_company_details_are_complete(supplier),
        supplier_company_details_confirmed=supplier_company_details_confirmed,
        application_company_details_confirmed=application_company_details_confirmed,
        unconfirmed_open_supplier_framework_names=[
            fw['frameworkName'] for fw in unconfirmed_open_supplier_frameworks
        ],
        company_details=get_company_details_from_supplier(supplier)
    ), 200


@main.route('/details', methods=['POST'])
@login_required
def confirm_supplier_details():
    supplier = data_api_client.get_supplier(
        current_user.supplier_id
    )['suppliers']

    unconfirmed_open_supplier_frameworks = get_unconfirmed_open_supplier_frameworks(data_api_client,
                                                                                    current_user.supplier_id)

    if not supplier_company_details_are_complete(supplier):
        return render_error_page(status_code=400, error_message="Some company details are not complete")

    else:
        data_api_client.update_supplier(
            supplier_id=current_user.supplier_id,
            supplier={"companyDetailsConfirmed": True},
            user=current_user.email_address
        )

        for supplier_framework in unconfirmed_open_supplier_frameworks:
            data_api_client.set_supplier_framework_application_company_details_confirmed(
                supplier_id=current_user.supplier_id,
                framework_slug=supplier_framework['frameworkSlug'],
                application_company_details_confirmed=True,
                user=current_user.email_address)

    if "currently_applying_to" in session:
        return redirect(url_for(".framework_dashboard", framework_slug=session["currently_applying_to"]))
    else:
        return redirect(url_for(".supplier_details"))


@main.route("/registered-address/edit", methods=["GET", "POST"])
@login_required
def edit_registered_address():
    supplier = data_api_client.get_supplier(current_user.supplier_id)["suppliers"]
    contact = supplier["contactInformation"][0]

    prefill_data = {
        "street": contact.get("address1"),
        "city": contact.get("city"),
        "postcode": contact.get("postcode"),
        "country": supplier.get("registrationCountry"),
    }

    registered_address_form = EditRegisteredAddressForm(data=prefill_data)

    if registered_address_form.validate_on_submit():
        data_api_client.update_supplier(
            current_user.supplier_id,
            {
                "registrationCountry": registered_address_form.country.data,
            },
            current_user.email_address,
        )

        data_api_client.update_contact_information(
            current_user.supplier_id,
            contact["id"],
            {
                "address1": registered_address_form.street.data,
                "city": registered_address_form.city.data,
                "postcode": registered_address_form.postcode.data,
            },
            current_user.email_address
        )

        return redirect(url_for(".supplier_details"))

    errors = get_errors_from_wtform(registered_address_form)

    return render_template(
        "suppliers/registered_address.html",
        supplier=supplier,
        countries=COUNTRY_TUPLE,
        form=registered_address_form,
        errors=errors,
    ), 200 if not errors else 400


@main.route('/registered-company-name/edit', methods=['GET', 'POST'])
@login_required
def edit_supplier_registered_name():
    form = AddCompanyRegisteredNameForm()
    supplier = data_api_client.get_supplier(current_user.supplier_id)['suppliers']
    if supplier.get("registeredName") and supplier.get('companyDetailsConfirmed'):
        return (
            render_template(
                "suppliers/already_completed.html",
                completed_data_description="registered company name",
                company_details_change_email=current_app.config['DM_COMPANY_DETAILS_CHANGE_EMAIL'],
            ), 200 if request.method == 'GET' else 400
        )

    if request.method == 'POST':
        if form.validate_on_submit():
            data_api_client.update_supplier(supplier_id=current_user.supplier_id,
                                            supplier={"registeredName": form.registered_company_name.data},
                                            user=current_user.email_address)
            return redirect(url_for('.supplier_details'))
        else:
            current_app.logger.warning(
                "supplieredit.fail: registered-name:{rname}, errors:{rname_errors}",
                extra={
                    'rname': form.registered_company_name.data,
                    'rname_errors': ",".join(form.registered_company_name.errors)
                })

    else:
        form.registered_company_name.data = supplier.get("registeredName")

    errors = get_errors_from_wtform(form)

    return render_template(
        'suppliers/edit_registered_name.html',
        form=form,
        errors=errors,
        company_details_change_email=current_app.config['DM_COMPANY_DETAILS_CHANGE_EMAIL']
    ), 200 if not errors else 400


@main.route('/registration-number/edit', methods=['GET', 'POST'])
@login_required
def edit_supplier_registration_number():
    form = AddCompanyRegistrationNumberForm()
    supplier = data_api_client.get_supplier(current_user.supplier_id)['suppliers']
    if (supplier.get("companiesHouseNumber") or supplier.get("otherCompanyRegistrationNumber")) \
            and supplier.get('companyDetailsConfirmed'):
        return (
            render_template(
                "suppliers/already_completed.html",
                completed_data_description="registration number",
                company_details_change_email=current_app.config['DM_COMPANY_DETAILS_CHANGE_EMAIL'],
            ),
            200 if request.method == 'GET' else 400
        )

    if request.method == 'POST':
        if form.validate_on_submit():
            if form.has_companies_house_number.data == "Yes":
                data_api_client.update_supplier(
                    supplier_id=current_user.supplier_id,
                    supplier={"companiesHouseNumber": form.companies_house_number.data.upper(),
                              "otherCompanyRegistrationNumber": None},
                    user=current_user.email_address
                )
            else:
                data_api_client.update_supplier(
                    supplier_id=current_user.supplier_id,
                    supplier={"companiesHouseNumber": None,
                              "otherCompanyRegistrationNumber": form.other_company_registration_number.data},
                    user=current_user.email_address
                )
            return redirect(url_for('.supplier_details'))
        else:
            current_app.logger.warning(
                "supplieredit.fail: has-companies-house-number:{hasnum}, companies-house-number:{chnum}, "
                "other-registered-company-number:{rnumber}, errors:{rnumber_errors}",
                extra={
                    'hasnum': form.has_companies_house_number.data,
                    'chnum': form.companies_house_number.data,
                    'rnumber': form.other_company_registration_number.data,
                    'rnumber_errors': ",".join(form.errors)
                })

    else:
        if supplier.get('companiesHouseNumber'):
            form.has_companies_house_number.data = "Yes"
            form.companies_house_number.data = supplier.get('companiesHouseNumber')

        elif supplier.get('otherCompanyRegistrationNumber'):
            form.has_companies_house_number.data = "No"
            form.other_company_registration_number.data = supplier.get('otherCompanyRegistrationNumber')

    errors = get_errors_from_wtform(form)

    return render_template(
        'suppliers/edit_company_registration_number.html',
        form=form,
        errors=errors,
    ), 200 if not errors else 400


@main.route('/edit', methods=['GET'])
@login_required
def edit_what_buyers_will_see_redirect():
    # redirect old route for this view
    return redirect(url_for('.edit_what_buyers_will_see'), 302)


@main.route('/what-buyers-will-see/edit', methods=['GET', 'POST'])
@login_required
def edit_what_buyers_will_see():

    supplier = data_api_client.get_supplier(
        current_user.supplier_id
    )['suppliers']

    contact = supplier["contactInformation"][0]

    prefill_data = {
        "contactName": contact.get("contactName"),
        "phoneNumber": contact.get("phoneNumber"),
        "email": contact.get("email"),
        "description": supplier.get("description"),
    }

    form = EditSupplierInformationForm(data=prefill_data)

    if form.validate_on_submit():
        data_api_client.update_supplier(
            current_user.supplier_id,
            {
                "description": form.description.data,
            },
            current_user.email_address
        )

        data_api_client.update_contact_information(
            current_user.supplier_id,
            contact["id"],
            {
                "contactName": form.contactName.data,
                "phoneNumber": form.phoneNumber.data,
                "email": form.email.data,
            },
            current_user.email_address
        )
        return redirect(url_for(".supplier_details"))

    errors = get_errors_from_wtform(form)

    return render_template(
        "suppliers/edit_what_buyers_will_see.html",
        form=form,
        errors=errors,
    ), 200 if not errors else 400


@main.route('/organisation-size/edit', methods=['GET', 'POST'])
@login_required
def edit_supplier_organisation_size():
    prefill_data = {}
    if request.method == "GET":
        supplier = data_api_client.get_supplier(current_user.supplier_id)['suppliers']
        prefill_data = {"organisation_size": supplier.get("organisationSize")}

    form = CompanyOrganisationSizeForm(data=prefill_data)

    if request.method == 'POST':
        if form.validate_on_submit():
            data_api_client.update_supplier(supplier_id=current_user.supplier_id,
                                            supplier={"organisationSize": form.organisation_size.data},
                                            user=current_user.email_address)

            return redirect(url_for('.supplier_details'))

        # TODO: see if we can remove this
        current_app.logger.warning(
            "supplieredit.fail: organisation-size:{osize}, errors:{osize_errors}",
            extra={
                'osize': form.organisation_size.data,
                'osize_errors': ",".join(form.organisation_size.errors)
            })

    form.organisation_size.govuk_options = govuk_options(options=form.OPTIONS, data=form.organisation_size.data)

    errors = get_errors_from_wtform(form)

    return render_template(
        'suppliers/edit_supplier_organisation_size.html',
        form=form,
        errors=errors
    ), 200 if not errors else 400


@main.route('/trading-status/edit', methods=['GET', 'POST'])
@login_required
def edit_supplier_trading_status():
    prefill_data = {}
    if request.method == "GET":
        supplier = data_api_client.get_supplier(current_user.supplier_id)['suppliers']
        prefill_data = {"trading_status": supplier.get("tradingStatus")}

    form = CompanyTradingStatusForm(data=prefill_data)

    if request.method == 'POST':
        if form.validate_on_submit():
            data_api_client.update_supplier(supplier_id=current_user.supplier_id,
                                            supplier={"tradingStatus": form.trading_status.data},
                                            user=current_user.email_address)

            return redirect(url_for('.supplier_details'))

        current_app.logger.warning(
            "supplieredit.fail: trading-status:{tstatus}, errors:{tstatus_errors}",
            extra={
                'tstatus': form.trading_status.data,
                'tstatus_errors': ",".join(form.trading_status.errors)
            })

    form.trading_status.govuk_options = govuk_options(options=form.OPTIONS, data=form.trading_status.data)
    errors = get_errors_from_wtform(form)

    return render_template(
        'suppliers/edit_supplier_trading_status.html',
        form=form,
        errors=errors
    ), 200 if not errors else 400


@main.route('/duns-number/edit', methods=['GET', 'POST'])
def edit_supplier_duns_number():
    return (
        render_template("suppliers/already_completed.html",
                        completed_data_description="DUNS number",
                        company_details_change_email=current_app.config['DM_COMPANY_DETAILS_CHANGE_EMAIL'],),
        200 if request.method == 'GET' else 400
    )


@main.route('/supply', methods=['GET'])
def become_a_supplier():

    try:
        frameworks = sorted(
            data_api_client.find_frameworks().get('frameworks'),
            key=lambda framework: framework['id'],
            reverse=True
        )
        displayed_frameworks = get_frameworks_closed_and_open_for_applications(frameworks)
        for fwk in displayed_frameworks:
            content_loader.load_messages(fwk.get('slug'), ['become-a-supplier'])

    #  if no message file is found (should never happen), die
    except ContentNotFoundError:
        current_app.logger.error(
            "contentloader.fail No 'become-a-supplier' message file found for framework."
        )
        abort(500)

    return render_template(
        "suppliers/become_a_supplier.html",
        open_fwks=[fwk for fwk in displayed_frameworks if fwk["status"] == "open"],
        opening_fwks=[fwk for fwk in displayed_frameworks if fwk["status"] == "coming"],
        closed_fwks=[fwk for fwk in displayed_frameworks if fwk["status"] not in ("open", "coming")],
        content_loader=content_loader
    ), 200


# Redirect added 23rd March 2018 - can probably remove it in 6 months or so
@main.route('/create', methods=['GET'])
def redirect_to_create_new_supplier():
    return redirect(url_for(".create_new_supplier")), 301


@main.route('/create/start', methods=['GET'])
def create_new_supplier():
    return render_template(
        "suppliers/create_new_supplier.html"
    ), 200


@main.route('/create/duns-number', methods=['GET', 'POST'])
def duns_number():
    form = DunsNumberForm()

    if request.method == 'GET':
        if request.args.get('retry', None) == 'true':
            # When redirected back from the confirm_company page
            form.duns_number.errors = ["Enter a different DUNS number"]
        elif form.duns_number.name in session:
            # Likely a back click or unexpected navigation, refill form data
            form.duns_number.data = session[form.duns_number.name]

    if form.validate_on_submit():
        # Valid duns number
        # Fail on existing account with this duns number first
        if len(data_api_client.find_suppliers(duns_number=form.duns_number.data)['suppliers']) > 0:
            form.duns_number.errors = ["DUNS number already used"]
        else:
            # Check for number in Direct Plus API
            # If we cannot contact the API then skip this step
            # If the client doesn't return an organization then there is not a record for that DUNs
            # Otherwise the number is good, add the 'primaryName' to the session and continue
            try:
                organization = direct_plus_client.get_organization_by_duns_number(form.duns_number.data)
                company_name = organization['primaryName']
            except (DUNSNumberInvalid, DUNSNumberNotFound):
                form.duns_number.errors = ["DUNS number not found"]
            except (DirectPlusError, KeyError, ValueError):
                # An unexpected error. Something other than supplier data in the response.
                # Allow the user to proceed with the entered duns numer and skip this part of sign up.
                session[form.duns_number.name] = form.duns_number.data
                return redirect(url_for(".company_details"))

            else:
                # Success
                session[form.duns_number.name] = form.duns_number.data
                session['company_name'] = company_name
                return redirect(url_for(".confirm_company"))

        current_app.logger.warning(
            "suppliercreate.fail: duns:{duns} {duns_errors}",
            extra={
                'duns': form.duns_number.data,
                'duns_errors': ",".join(form.duns_number.errors)})

    errors = get_errors_from_wtform(form)
    error_title = None
    error_description = None
    if errors.get("duns_number", {}).get("message", None) == 'DUNS number already used':
        error_title = "A supplier account already exists with that DUNS number"
        support_email_address = current_app.config['SUPPORT_EMAIL_ADDRESS']
        error_description = Markup(
            'If you no longer have your account details, or if you think this may be an error, '
            f'email <a class="govuk-link" href="mailto:{support_email_address}?subject=DUNS%20number%20question" '
            f'title="Please contact {support_email_address}">{support_email_address}</a>')

    return render_template(
        "suppliers/create_duns_number.html",
        form=form,
        errors=errors,
        error_title=error_title,
        error_description=error_description
    ), 200 if not errors else 400


@main.route('/create/confirm-company', methods=['GET', 'POST'])
def confirm_company():
    form = ConfirmCompanyForm()
    duns_number = session.get('duns_number', None)
    if request.method == 'GET':
        if not duns_number:
            # We require users to enter a duns_number to use this page
            # Users could otherwise navigate to this page via URL
            return redirect(url_for(".duns_number"))

    if form.validate_on_submit():
        # If this isn't the right company get them to enter a new duns number.
        if form.confirmed.data is False:
            for field in ('duns_number', 'company_name'):
                session.pop(field, None)
            return redirect(url_for(".duns_number", retry='true'))
        return redirect(url_for(".company_details"))

    errors = get_errors_from_wtform(form)

    return render_template(
        "suppliers/create_confirm_company.html",
        form=form,
        errors=errors,
    ), 200 if not errors else 400


@main.route('/create/company-details', methods=['GET', 'POST'])
def company_details():
    form = CompanyPublicContactInformationForm()

    if request.method == "POST":
        if form.validate_on_submit():
            session[form.company_name.name] = form.company_name.data
            session[form.email_address.name] = form.email_address.data
            session[form.phone_number.name] = form.phone_number.data
            session[form.contact_name.name] = form.contact_name.data
            return redirect(url_for(".create_your_account"))
        else:
            current_app.logger.warning(
                "suppliercreate.fail: duns:{duns} {form_errors}",
                extra={
                    'duns': session.get('duns_number'),
                    'form_errors': ",".join(chain.from_iterable(form.errors.values()))})

    else:
        if form.company_name.name in session:
            form.company_name.data = session[form.company_name.name]

        if form.contact_name.name in session:
            form.contact_name.data = session[form.contact_name.name]

        if form.email_address.name in session:
            form.email_address.data = session[form.email_address.name]

        if form.phone_number.name in session:
            form.phone_number.data = session[form.phone_number.name]

    errors = get_errors_from_wtform(form)

    return render_template(
        "suppliers/create_company_details.html",
        form=form,
        errors=errors,
    ), 200 if not errors else 400


@main.route('/create/account', methods=['GET', 'POST'])
def create_your_account():
    current_app.logger.info("suppliercreate: {} create-your-account supplier_id:{}".format(
        request.method,
        session.get('email_supplier_id', 'unknown'))
    )

    form = EmailAddressForm()
    if form.validate_on_submit():
        session['account_email_address'] = form.email_address.data
        return redirect(url_for(".company_summary"))

    errors = get_errors_from_wtform(form)

    return render_template(
        "suppliers/create_your_account.html",
        form=form,
        errors=errors,
        email_address=form.email_address.data if form.email_address.data else session.get('account_email_address', '')
    ), 200 if not errors else 400


@main.route('/create/company-summary', methods=['GET'])
def company_summary():
    return render_template(
        "suppliers/create_company_summary.html"
    ), 200


@main.route('/create/company-summary', methods=['POST'])
def submit_company_summary():

    required_fields = [
        "email_address",
        "phone_number",
        "contact_name",
        "duns_number",
        "company_name",
        "account_email_address"
    ]

    missing_fields = [field for field in required_fields if field not in session]

    if not missing_fields:
        supplier = {
            "name": session["company_name"],
            "dunsNumber": str(session["duns_number"]),
            "contactInformation": [{
                "email": session["email_address"],
                "phoneNumber": session["phone_number"],
                "contactName": session["contact_name"]
            }]
        }

        account_email_address = session.get("account_email_address", None)

        supplier = data_api_client.create_supplier(supplier)
        session.clear()
        session['email_company_name'] = supplier['suppliers']['name']
        session['email_supplier_id'] = supplier['suppliers']['id']

        send_user_account_email(
            'supplier',
            account_email_address,
            current_app.config['NOTIFY_TEMPLATES']['create_user_account'],
            extra_token_data={
                "supplier_id": session['email_supplier_id'],
                "supplier_name": session['email_company_name']
            }
        )

        data_api_client.create_audit_event(
            audit_type=AuditTypes.invite_user,
            object_type='suppliers',
            object_id=session['email_supplier_id'],
            data={'invitedEmail': account_email_address})

        return redirect(url_for('.create_your_account_complete'), 302)
    else:
        return render_template(
            "suppliers/create_company_summary.html",
            missing_fields=missing_fields
        ), 400


@main.route('/create/complete', methods=['GET'])
def create_your_account_complete():
    if 'email_sent_to' in session:
        email_address = session['email_sent_to']
    else:
        email_address = "the email address you supplied"
    session.clear()
    session['email_sent_to'] = email_address
    return render_template(
        "suppliers/create_your_account_complete.html",
        email_address=email_address
    ), 200


@main.route('/mailing-list', methods=["GET", "POST"])
def join_open_framework_notification_mailing_list():
    status = 200

    form = EmailAddressForm()
    if form.validate_on_submit():
        dmmc_client = DMMailChimpClient(
            current_app.config["DM_MAILCHIMP_USERNAME"],
            current_app.config["DM_MAILCHIMP_API_KEY"],
            current_app.logger,
        )

        mc_response = dmmc_client.subscribe_new_email_to_list(
            current_app.config["DM_MAILCHIMP_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_ID"],
            form.data["email_address"],
        )
        if mc_response.get('status') == 'success':
            data_api_client.create_audit_event(
                audit_type=AuditTypes.mailing_list_subscription,
                data={
                    "subscribedEmail": form.data["email_address"],
                    "mailchimp": {k: mc_response.get(k) for k in (
                        "id",
                        "unique_email_id",
                        "timestamp_opt",
                        "last_changed",
                        "list_id",
                    )},
                },
            )

            flash(JOIN_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_SUCCESS_MESSAGE.format(
                email_address=form.data["email_address"],
            ), "success")

            return redirect("/")
        else:
            if mc_response.get('error_type') == 'already_subscribed':
                flash(JOIN_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_ALREADY_SUBSCRIBED_MESSAGE.format(
                    support_email_address=current_app.config['SUPPORT_EMAIL_ADDRESS']
                ), "error")
            elif mc_response.get('error_type') in ['deleted_user', 'invalid_email']:
                flash(JOIN_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_UNSUBSCRIBED_MESSAGE.format(
                    support_email_address=current_app.config['SUPPORT_EMAIL_ADDRESS']
                ), "error")
            else:
                flash(JOIN_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_ERROR_MESSAGE.format(
                    support_email_address=current_app.config['SUPPORT_EMAIL_ADDRESS']
                ), "error")
            # If no status code supplied, something has probably gone wrong
            status = mc_response.get('status_code', 503)
            # fall through to re-display form with error
    elif request.method == "POST":
        status = 400
        # fall through to re-display form with errors

    return render_template(
        "suppliers/join_open_framework_notification_mailing_list.html",
        form=form,
        errors=get_errors_from_wtform(form),
    ), status
