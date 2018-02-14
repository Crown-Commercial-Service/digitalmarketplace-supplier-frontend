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
    CompaniesHouseNumberForm,
    CompanyContactDetailsForm,
    CompanyNameForm,
    CompanyOrganisationSizeForm,
    DunsNumberForm,
    EditContactInformationForm,
    EditSupplierForm,
    EmailAddressForm,
)
from ..helpers.frameworks import get_frameworks_by_status, get_frameworks_closed_and_open_for_applications
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

    return render_template(
        "suppliers/details.html",
        supplier=supplier,
    ), 200


@main.route('/edit', methods=['GET'])
@login_required
def edit_supplier_redirect():
    # redirect old route for this view
    return redirect(url_for('.edit_supplier'), 302)


@main.route('/details/edit', methods=['GET'])
@login_required
def edit_supplier(supplier_form=None, contact_form=None, error=None):
    try:
        supplier = data_api_client.get_supplier(
            current_user.supplier_id
        )['suppliers']
    except APIError as e:
        abort(e.status_code)

    if supplier_form is None:
        supplier_form = EditSupplierForm(
            description=supplier.get('description', None),
            clients=supplier.get('clients', None)
        )
        contact_form = EditContactInformationForm(
            prefix='contact_',
            **supplier['contactInformation'][0]
        )

    return render_template(
        "suppliers/edit_supplier.html",
        error=error,
        supplier_form=supplier_form,
        contact_form=contact_form
    ), 200


@main.route('/details/edit', methods=['POST'])
@login_required
def update_supplier():
    # FieldList expects post parameter keys to have number suffixes
    # (eg client-0, client-1 ...), which is incompatible with how
    # JS list-entry plugin generates input names. So instead of letting
    # the form search for request keys we pass in the values directly as data
    supplier_form = EditSupplierForm(
        formdata=None,
        description=request.form['description'],
    )

    contact_form = EditContactInformationForm(prefix='contact_')

    if not (supplier_form.validate_on_submit() and contact_form.validate_on_submit()):
        return edit_supplier(supplier_form=supplier_form, contact_form=contact_form)

    try:
        data_api_client.update_supplier(
            current_user.supplier_id,
            supplier_form.data,
            current_user.email_address
        )

        data_api_client.update_contact_information(
            current_user.supplier_id,
            contact_form.id.data,
            contact_form.data,
            current_user.email_address
        )
    except APIError as e:
        return edit_supplier(supplier_form=supplier_form,
                             contact_form=contact_form,
                             error=e.message)

    return redirect(url_for(".supplier_details"))


@main.route('/organisation-size/edit', methods=['GET', 'POST'])
@login_required
def edit_supplier_organisation_size():
    form = CompanyOrganisationSizeForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            data_api_client.update_supplier(supplier_id=current_user.supplier_id,
                                            supplier={"organisationSize": form.organisation_size.data},
                                            user=current_user.email_address)
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


@main.route('/companies-house-number', methods=['GET'])
def companies_house_number():
    form = CompaniesHouseNumberForm()

    if form.companies_house_number.name in session:
        form.companies_house_number.data = session[form.companies_house_number.name]

    return render_template(
        "suppliers/companies_house_number.html",
        form=form
    ), 200


@main.route('/companies-house-number', methods=['POST'])
def submit_companies_house_number():
    form = CompaniesHouseNumberForm()

    if form.validate_on_submit():
        if form.companies_house_number.data:
            # TODO: below should be a statement updating database with Company House Number
            session[form.companies_house_number.name] = form.companies_house_number.data
        else:
            session.pop(form.companies_house_number.name, None)
        return redirect(url_for(".supplier_details"))
    else:
        current_app.logger.warning(
            "suppliercreate.fail: duns:{duns} {duns_errors}",
            extra={
                'duns': session.get('duns_number'),
                'duns_errors': ",".join(chain.from_iterable(form.errors.values()))})
        return render_template(
            "suppliers/companies_house_number.html",
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
