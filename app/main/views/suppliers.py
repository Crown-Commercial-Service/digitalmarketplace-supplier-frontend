# coding=utf-8
from itertools import chain

from flask import render_template, request, redirect, url_for, abort, session, Markup, flash
from flask_login import current_user, current_app

from dmapiclient import APIError
from dmapiclient.audit import AuditTypes
from dmcontent.content_loader import ContentNotFoundError
from dmutils.email import send_user_account_email
from dmutils.email.dm_mailchimp import DMMailChimpClient

from ...main import main, content_loader
from ... import data_api_client
from ..forms.suppliers import (
    AddCompanyRegisteredNameForm,
    AddCompanyRegistrationNumberForm,
    CompanyContactDetailsForm,
    CompanyNameForm,
    CompanyOrganisationSizeForm,
    CompanyTradingStatusForm,
    DunsNumberForm,
    EditContactInformationForm,
    EditRegisteredAddressForm,
    EditRegisteredCountryForm,
    EditSupplierForm,
    EmailAddressForm,
    VatNumberForm,
)
from ..helpers.frameworks import get_frameworks_by_status, get_frameworks_closed_and_open_for_applications
from ..helpers.suppliers import get_country_name_from_country_code, COUNTRY_TUPLE, \
    parse_form_errors_for_validation_masthead
from ..helpers import login_required
from .users import get_current_suppliers_users


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
        dates = {}
        try:
            dates = content_loader.get_message(framework['slug'], 'dates')
        except ContentNotFoundError:
            pass
        framework.update({
            'dates': dates,
            'deadline': Markup("Deadline: {}".format(dates.get('framework_close_date', ''))),
            'registered_interest': (framework['slug'] in supplier_frameworks),
            'made_application': (
                framework.get('declaration')
                and framework['declaration'].get('status') == 'complete'
                and framework.get('complete_drafts_count') > 0
            ),
            'needs_to_complete_declaration': (
                framework.get('onFramework') and framework.get('agreementReturned') is False
            )
        })
    return render_template(
        "suppliers/dashboard.html",
        supplier=supplier,
        users=get_current_suppliers_users(),
        frameworks={
            'coming': get_frameworks_by_status(all_frameworks, 'coming'),
            'open': get_frameworks_by_status(all_frameworks, 'open'),
            'pending': get_frameworks_by_status(all_frameworks, 'pending'),
            'standstill': get_frameworks_by_status(all_frameworks, 'standstill', 'made_application'),
            'live': get_frameworks_by_status(all_frameworks, 'live', 'services_count')
        }
    ), 200


@main.route('/details', methods=['GET'])
@login_required
def supplier_details():
    try:
        supplier = data_api_client.get_supplier(
            current_user.supplier_id
        )['suppliers']
    except APIError as e:
        abort(e.status_code)
    supplier['contact'] = supplier['contactInformation'][0]
    country_name = get_country_name_from_country_code(supplier.get('registrationCountry'))

    return render_template(
        "suppliers/details.html",
        supplier=supplier,
        country_name=country_name,
    ), 200


@main.route('/registered-address/edit', methods=['GET', 'POST'])
@login_required
def edit_registered_address():
    try:
        supplier = data_api_client.get_supplier(
            current_user.supplier_id
        )['suppliers']
    except APIError as e:
        abort(e.status_code)
    supplier['contact'] = supplier['contactInformation'][0]

    http_status = 200
    registered_address_form = EditRegisteredAddressForm()
    registered_country_form = EditRegisteredCountryForm()

    if request.method == 'POST':
        address_valid = registered_address_form.validate_on_submit()
        country_valid = registered_country_form.validate_on_submit()

        if address_valid and country_valid:
            try:
                data_api_client.update_supplier(
                    current_user.supplier_id,
                    registered_country_form.data,
                    current_user.email_address,
                )

                data_api_client.update_contact_information(
                    current_user.supplier_id,
                    supplier['contact']['id'],
                    registered_address_form.data,
                    current_user.email_address
                )

            except APIError as e:
                abort(e.status_code)

            return redirect(url_for(".supplier_details"))

        http_status = 400

    else:
        registered_address_form.address1.data = supplier['contact'].get('address1')
        registered_address_form.city.data = supplier['contact'].get('city')
        registered_address_form.postcode.data = supplier['contact'].get('postcode')

        registered_country_form.registrationCountry.data = supplier.get('registrationCountry')

    return render_template(
        "suppliers/registered_address.html",
        supplier=supplier,
        countries=COUNTRY_TUPLE,
        registered_address_form=registered_address_form,
        registered_country_form=registered_country_form,
        form_errors=parse_form_errors_for_validation_masthead([registered_address_form, registered_country_form]),
    ), http_status


@main.route('/registered-company-name/edit', methods=['GET', 'POST'])
@login_required
def edit_supplier_registered_name():
    form = AddCompanyRegisteredNameForm()
    supplier = data_api_client.get_supplier(current_user.supplier_id)['suppliers']
    if supplier.get("registeredName"):
        return (
            render_template("suppliers/already_completed.html", completed_data_description="registered company name"),
            200 if request.method == 'GET' else 400
        )

    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                data_api_client.update_supplier(supplier_id=current_user.supplier_id,
                                                supplier={"registeredName": form.registered_company_name.data},
                                                user=current_user.email_address)
                return redirect(url_for('.supplier_details'))
            except APIError as e:
                abort(e.status_code)
        else:
            current_app.logger.warning(
                "supplieredit.fail: registered-name:{rname}, errors:{rname_errors}",
                extra={
                    'rname': form.registered_company_name.data,
                    'rname_errors': ",".join(form.registered_company_name.errors)
                })

            return render_template("suppliers/edit_registered_name.html", form=form), 400

    return render_template('suppliers/edit_registered_name.html', form=form)


@main.route('/registration-number/edit', methods=['GET', 'POST'])
@login_required
def edit_supplier_registration_number():
    form = AddCompanyRegistrationNumberForm()
    supplier = data_api_client.get_supplier(current_user.supplier_id)['suppliers']
    if supplier.get("companiesHouseNumber") or supplier.get("otherCompanyRegistrationNumber"):
        return (
            render_template(
                "suppliers/already_completed.html",
                completed_data_description="company registration number"
            ),
            200 if request.method == 'GET' else 400
        )

    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                if form.has_companies_house_number.data == "Yes":
                    data_api_client.update_supplier(
                        supplier_id=current_user.supplier_id,
                        supplier={"companiesHouseNumber": form.companies_house_number.data.upper()},
                        user=current_user.email_address
                    )
                else:
                    data_api_client.update_supplier(
                        supplier_id=current_user.supplier_id,
                        supplier={"otherCompanyRegistrationNumber": form.other_company_registration_number.data},
                        user=current_user.email_address
                    )
                return redirect(url_for('.supplier_details'))
            except APIError as e:
                abort(e.status_code)
        else:
            current_app.logger.warning(
                "supplieredit.fail: has-companies-house-number:{hasnum}, companies-house-number:{chnum}, "
                "other-registered-company-number:{rnumber}, errors:{errors}",
                extra={
                    'hasnum': form.has_companies_house_number.data,
                    'chnum': form.companies_house_number.data,
                    'rnumber': form.other_company_registration_number.data,
                    'rnumber_errors': ",".join(form.errors)
                })

            return render_template("suppliers/edit_company_registration_number.html", form=form), 400

    return render_template('suppliers/edit_company_registration_number.html', form=form)


@main.route('/edit', methods=['GET'])
@login_required
def edit_what_buyers_will_see_redirect():
    # redirect old route for this view
    return redirect(url_for('.edit_what_buyers_will_see'), 302)


@main.route('/what-buyers-will-see/edit', methods=['GET', 'POST'])
@login_required
def edit_what_buyers_will_see():
    try:
        supplier = data_api_client.get_supplier(
            current_user.supplier_id
        )['suppliers']
    except APIError as e:
        abort(e.status_code)

    supplier['contact'] = supplier['contactInformation'][0]
    http_status = 200

    supplier_form = EditSupplierForm()
    contact_form = EditContactInformationForm()

    if request.method == 'POST':
        supplier_info_valid = supplier_form.validate_on_submit()
        contact_info_valid = contact_form.validate_on_submit()

        if supplier_info_valid and contact_info_valid:
            try:
                data_api_client.update_supplier(
                    current_user.supplier_id,
                    supplier_form.data,
                    current_user.email_address
                )

                data_api_client.update_contact_information(
                    current_user.supplier_id,
                    supplier['contact']['id'],
                    contact_form.data,
                    current_user.email_address
                )
            except APIError as e:
                abort(e.status_code)
            else:
                return redirect(url_for(".supplier_details"))

        http_status = 400

    else:
        supplier_form.description.data = supplier.get('description', None)
        contact_form.contactName.data = supplier['contact'].get('contactName')
        contact_form.phoneNumber.data = supplier['contact'].get('phoneNumber')
        contact_form.email.data = supplier['contact'].get('email')

    return render_template(
        "suppliers/edit_what_buyers_will_see.html",
        supplier_form=supplier_form,
        contact_form=contact_form
    ), http_status


@main.route('/organisation-size/edit', methods=['GET', 'POST'])
@login_required
def edit_supplier_organisation_size():
    form = CompanyOrganisationSizeForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                data_api_client.update_supplier(supplier_id=current_user.supplier_id,
                                                supplier={"organisationSize": form.organisation_size.data},
                                                user=current_user.email_address)

            except APIError as e:
                abort(e.status_code)

            return redirect(url_for('.supplier_details'))

        current_app.logger.warning(
            "supplieredit.fail: organisation-size:{osize}, errors:{osize_errors}",
            extra={
                'osize': form.organisation_size.data,
                'osize_errors': ",".join(form.organisation_size.errors)
            })

        return render_template("suppliers/edit_supplier_organisation_size.html", form=form), 400

    supplier = data_api_client.get_supplier(current_user.supplier_id)['suppliers']
    form.organisation_size.data = supplier.get('organisationSize', None)

    return render_template('suppliers/edit_supplier_organisation_size.html', form=form)


@main.route('/trading-status/edit', methods=['GET', 'POST'])
@login_required
def edit_supplier_trading_status():
    form = CompanyTradingStatusForm()

    if request.method == 'POST':
        api_error = None
        if form.validate_on_submit():
            try:
                data_api_client.update_supplier(supplier_id=current_user.supplier_id,
                                                supplier={"tradingStatus": form.trading_status.data},
                                                user=current_user.email_address)

            except APIError as e:
                abort(e.status_code)

            return redirect(url_for('.supplier_details'))

        current_app.logger.warning(
            "supplieredit.fail: trading-status:{tstatus}, errors:{tstatus_errors}",
            extra={
                'tstatus': form.trading_status.data,
                'tstatus_errors': ",".join(form.trading_status.errors)
            })

        return render_template("suppliers/edit_supplier_trading_status.html", form=form, api_error=api_error), 400

    supplier = data_api_client.get_supplier(current_user.supplier_id)['suppliers']

    prefill_trading_status = None
    if supplier.get('tradingStatus'):
        if supplier['tradingStatus'] in map(lambda x: x['value'], form.OPTIONS):
            prefill_trading_status = supplier['tradingStatus']

    form.trading_status.data = prefill_trading_status

    return render_template('suppliers/edit_supplier_trading_status.html', form=form)


@main.route('/vat-number/edit', methods=['GET', 'POST'])
@login_required
def edit_supplier_vat_number():
    form = VatNumberForm()
    try:
        supplier = data_api_client.get_supplier(current_user.supplier_id)['suppliers']
    except APIError as e:
        abort(e.status_code)

    if supplier.get("vatNumber"):
        return (
            render_template("suppliers/already_completed.html", completed_data_description="VAT number"),
            200 if request.method == 'GET' else 400
        )

    form_errors = None
    if request.method == 'POST':
        if form.validate_on_submit():
            vat_number = form.vat_number.data if form.vat_registered.data == 'Yes' else 'Not VAT registered'

            try:
                data_api_client.update_supplier(supplier_id=current_user.supplier_id,
                                                supplier={"vatNumber": vat_number},
                                                user=current_user.email_address)
            except APIError as e:
                abort(e.status_code)

            return redirect(url_for('.supplier_details'))

        current_app.logger.warning(
            "supplieredit.fail: vat-number:{vat_number}, vat-number-errors:{vat_number_errors}, "
            "vat-registered:{vat_registered}, vat-registered-errors{vat_registered_errors}",
            extra={
                "vat_number": form.vat_number.data,
                "vat_number_errors": ",".join(form.vat_number.errors),
                "vat_registered": form.vat_registered.data,
                "vat_registered_errors": ",".join(form.vat_registered.errors),
            })

        form_errors = [
            {'question': form[field].label.text, 'input_name': form[field].name} for field in form.errors.keys()
        ]

    return render_template(
        'suppliers/edit_vat_number.html',
        form=form,
        form_errors=form_errors
    ), 200 if request.method == 'GET' else 400


@main.route('/supply', methods=['GET'])
def become_a_supplier():

    try:
        frameworks = sorted(
            data_api_client.find_frameworks().get('frameworks'),
            key=lambda framework: framework['slug'],
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


@main.route('/create', methods=['GET'])
def create_new_supplier():
    return render_template(
        "suppliers/create_new_supplier.html"
    ), 200


@main.route('/duns-number', methods=['GET'])
def duns_number():
    form = DunsNumberForm()

    if form.duns_number.name in session:
        form.duns_number.data = session[form.duns_number.name]

    return render_template(
        "suppliers/duns_number.html",
        form=form
    ), 200


@main.route('/duns-number', methods=['POST'])
def submit_duns_number():
    form = DunsNumberForm()

    if form.validate_on_submit():

        suppliers = data_api_client.find_suppliers(duns_number=form.duns_number.data)
        if len(suppliers["suppliers"]) > 0:
            form.duns_number.errors = ["DUNS number already used"]
            current_app.logger.warning(
                "suppliercreate.fail: duns:{duns} {duns_errors}",
                extra={
                    'duns': form.duns_number.data,
                    'duns_errors': ",".join(form.duns_number.errors)})
            return render_template(
                "suppliers/duns_number.html",
                form=form
            ), 400
        session[form.duns_number.name] = form.duns_number.data
        return redirect(url_for(".company_name"))
    else:
        current_app.logger.warning(
            "suppliercreate.fail: duns:{duns} {duns_errors}",
            extra={
                'duns': form.duns_number.data,
                'duns_errors': ",".join(form.duns_number.errors)})
        return render_template(
            "suppliers/duns_number.html",
            form=form
        ), 400


@main.route('/company-name', methods=['GET'])
def company_name():
    form = CompanyNameForm()

    if form.company_name.name in session:
        form.company_name.data = session[form.company_name.name]

    return render_template(
        "suppliers/company_name.html",
        form=form
    ), 200


@main.route('/company-name', methods=['POST'])
def submit_company_name():
    form = CompanyNameForm()

    if form.validate_on_submit():
        session[form.company_name.name] = form.company_name.data
        return redirect(url_for(".company_contact_details"))
    else:
        current_app.logger.warning(
            "suppliercreate.fail: duns:{duns} company_name:{company_name} {duns_errors}",
            extra={
                'duns': session.get('duns_number'),
                'company_name': session.get('company_name'),
                'duns_errors': ",".join(chain.from_iterable(form.errors.values()))})
        return render_template(
            "suppliers/company_name.html",
            form=form
        ), 400


@main.route('/company-contact-details', methods=['GET'])
def company_contact_details():
    form = CompanyContactDetailsForm()

    if form.email_address.name in session:
        form.email_address.data = session[form.email_address.name]

    if form.phone_number.name in session:
        form.phone_number.data = session[form.phone_number.name]

    if form.contact_name.name in session:
        form.contact_name.data = session[form.contact_name.name]

    return render_template(
        "suppliers/company_contact_details.html",
        form=form
    ), 200


@main.route('/company-contact-details', methods=['POST'])
def submit_company_contact_details():
    form = CompanyContactDetailsForm()

    if form.validate_on_submit():
        session[form.email_address.name] = form.email_address.data
        session[form.phone_number.name] = form.phone_number.data
        session[form.contact_name.name] = form.contact_name.data
        return redirect(url_for(".create_your_account"))
    else:
        current_app.logger.warning(
            "suppliercreate.fail: duns:{duns} company_name:{company_name} {duns_errors}",
            extra={
                'duns': session.get('duns_number'),
                'company_name': session.get('company_name'),
                'duns_errors': ",".join(chain.from_iterable(form.errors.values()))})
        return render_template(
            "suppliers/company_contact_details.html",
            form=form
        ), 400


@main.route('/create-your-account', methods=['GET'])
def create_your_account():
    current_app.logger.info(
        "suppliercreate: get create-your-account supplier_id:{}".format(
            session.get('email_supplier_id', 'unknown')))
    form = EmailAddressForm()

    return render_template(
        "suppliers/create_your_account.html",
        form=form,
        email_address=session.get('account_email_address', '')
    ), 200


@main.route('/create-your-account', methods=['POST'])
def submit_create_your_account():
    current_app.logger.info(
        "suppliercreate: post create-your-account supplier_id:{}".format(
            session.get('email_supplier_id', 'unknown')))
    form = EmailAddressForm()

    if form.validate_on_submit():
        session['account_email_address'] = form.email_address.data
        return redirect(url_for(".company_summary"))
    else:
        return render_template(
            "suppliers/create_your_account.html",
            form=form,
            email_address=form.email_address.data
        ), 400


@main.route('/company-summary', methods=['GET'])
def company_summary():
    return render_template(
        "suppliers/company_summary.html"
    ), 200


@main.route('/company-summary', methods=['POST'])
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
            "suppliers/company_summary.html",
            missing_fields=missing_fields
        ), 400


@main.route('/create-your-account-complete', methods=['GET'])
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
    if request.method == "POST":
        form = EmailAddressForm(request.form)
        if form.validate():
            dmmc_client = DMMailChimpClient(
                current_app.config["DM_MAILCHIMP_USERNAME"],
                current_app.config["DM_MAILCHIMP_API_KEY"],
                current_app.logger,
            )

            mc_response = dmmc_client.subscribe_new_email_to_list(
                current_app.config["DM_MAILCHIMP_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_ID"],
                form.data["email_address"],
            )

            # note we're signalling our flash messages in two separate ways here
            if mc_response not in (True, False,):
                # success
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

                # this message will be consumed by the buyer app which has been converted to display raw "literal"
                # content from the session
                flash(Markup(render_template(
                    "flashmessages/join_open_framework_notification_mailing_list_success.html",
                    email_address=form.data["email_address"],
                )), "success")

                return redirect("/")
            else:
                # failure
                flash("mailing_list_signup_error", "error")
                if mc_response:
                    # this is a case where we think the error is *probably* the user's fault in some way
                    status = 400
                else:
                    # this is a case where we have no idea so should probably be alert to it
                    status = 503
                # fall through to re-display form with error
        else:
            status = 400
            # fall through to re-display form with errors
    else:
        form = EmailAddressForm()

    return render_template(
        "suppliers/join_open_framework_notification_mailing_list.html",
        form=form,
    ), status
