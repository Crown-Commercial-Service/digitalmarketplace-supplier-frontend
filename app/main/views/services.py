from flask import render_template, request, redirect, url_for, abort, flash, current_app, Markup
from flask_login import current_user

from dmapiclient import HTTPError
from dmcontent.content_loader import ContentNotFoundError
from dmutils import s3
from dmutils.dates import update_framework_with_formatted_dates
from dmutils.documents import upload_service_documents

from ... import data_api_client, flask_featureflags
from ...main import main, content_loader
from ..helpers import login_required
from ..helpers.services import (
    copy_service_from_previous_framework,
    count_unanswered_questions,
    get_lot_drafts,
    get_signed_document_url,
    is_service_associated_with_supplier,
)
from ..helpers.frameworks import (
    get_framework_and_lot_or_404,
    get_declaration_status,
    get_supplier_framework_info,
    get_framework_or_404,
    get_framework_or_500,
)
from ..forms.frameworks import OneServiceLimitCopyServiceForm


# TODO make these more consistent, content-wise
SERVICE_REMOVED_MESSAGE = "{service_name} has been removed."
SERVICE_UPDATED_MESSAGE = "You’ve edited your service. The changes are now live on the Digital Marketplace."
SERVICE_COMPLETED_MESSAGE = Markup("<strong>{service_name}</strong> was marked as complete")
SERVICE_DELETED_MESSAGE = Markup("<strong>{service_name}</strong> was deleted")
REMOVE_LAST_SUBSECTION_ERROR_MESSAGE = Markup(
    "You must offer one of the {section_name} to be eligible.<br>"
    "If you don’t want to offer {service_name}, delete this service."
)
SINGLE_SERVICE_ADDED_MESSAGE = (
    "You've added a service to your {framework_name} drafts. You'll need to review it before it can be completed."
)
ALL_SERVICES_ADDED_MESSAGE = (
    "You've added {draft_count} services to your {framework_name} drafts. "
    "You'll need to review them before they can be completed."
)


@main.route("/frameworks/<string:framework_slug>/services")
@login_required
def list_services(framework_slug):
    framework = get_framework_or_404(data_api_client, framework_slug, allowed_statuses=['live'])

    suppliers_services = data_api_client.find_services(
        supplier_id=current_user.supplier_id,
        framework=framework_slug,
    )["services"]

    return render_template(
        "services/list_services.html",
        services=suppliers_services,
        framework=framework,
    ), 200


#  #######################  EDITING LIVE SERVICES #############################


@main.route("/frameworks/<string:framework_slug>/services/<string:service_id>", methods=['GET'])
@login_required
def edit_service(framework_slug, service_id):
    service = data_api_client.get_service(service_id)
    if not service:
        abort(404)

    service_unavailability_information = service.get('serviceMadeUnavailableAuditEvent')
    service = service.get('services')

    if not is_service_associated_with_supplier(service):
        abort(404)

    if service["frameworkSlug"] != framework_slug:
        abort(404)

    framework = get_framework_or_404(data_api_client, service['frameworkSlug'], allowed_statuses=['live'])

    try:
        content = content_loader.get_manifest(framework['slug'], 'edit_service').filter(service)
    except ContentNotFoundError:
        abort(404)
    remove_requested = bool(request.args.get('remove_requested'))

    return render_template(
        "services/service.html",
        service_id=service.get('id'),
        service_data=service,
        service_unavailability_information=service_unavailability_information,
        framework=framework,
        sections=content.summary(service),
        remove_requested=remove_requested,
    )


@main.route("/frameworks/<string:framework_slug>/services/<string:service_id>/remove", methods=['POST'])
@login_required
def remove_service(framework_slug, service_id):
    service = data_api_client.get_service(service_id).get('services')

    if not is_service_associated_with_supplier(service):
        abort(404)

    if service["frameworkSlug"] != framework_slug:
        abort(404)

    # dos services should not be removable
    if service["frameworkFramework"] == 'digital-outcomes-and-specialists':
        abort(404)

    # we don't actually need the framework here; using this to 404 if framework for the service is not live
    get_framework_or_404(data_api_client, service['frameworkSlug'], allowed_statuses=['live'])

    # we don't actually need the content here, we're just probing to see whether service editing should be allowed for
    # this framework (signalled by the existence of the edit_service manifest
    try:
        content_loader.get_manifest(service["frameworkSlug"], 'edit_service')
    except ContentNotFoundError:
        abort(404)

    # suppliers can't un-remove a service
    if service.get('status') != 'published':
        abort(400)

    if request.form.get('remove_confirmed'):

        updated_service = data_api_client.update_service_status(
            service.get('id'),
            'enabled',
            current_user.email_address)

        updated_service = updated_service.get('services')

        flash(SERVICE_REMOVED_MESSAGE.format(service_name=updated_service.get('serviceName')), 'remove_service')

        return redirect(url_for(".list_services", framework_slug=service["frameworkSlug"]))

    return redirect(url_for(
        ".edit_service",
        service_id=service_id,
        framework_slug=service["frameworkSlug"],
        remove_requested=True))


@main.route(
    "/frameworks/<string:framework_slug>/services/<string:service_id>/edit/<string:section_id>",
    methods=['GET'],
)
@login_required
@flask_featureflags.is_active_feature('EDIT_SECTIONS')
def edit_section(framework_slug, service_id, section_id):
    service = data_api_client.get_service(service_id)
    if service is None:
        abort(404)
    service = service['services']

    if not is_service_associated_with_supplier(service):
        abort(404)

    if service["frameworkSlug"] != framework_slug:
        abort(404)

    # we don't actually need the framework here; using this to 404 if framework for the service is not live
    get_framework_or_404(data_api_client, service['frameworkSlug'], allowed_statuses=['live'])

    try:
        content = content_loader.get_manifest(service["frameworkSlug"], 'edit_service').filter(service)
    except ContentNotFoundError:
        abort(404)
    section = content.get_section(section_id)
    if section is None or not section.editable:
        abort(404)

    return render_template(
        "services/edit_section.html",
        section=section,
        service_data=service,
        service_id=service_id,
    )


@main.route(
    "/frameworks/<string:framework_slug>/services/<string:service_id>/edit/<string:section_id>",
    methods=['POST'],
)
@login_required
@flask_featureflags.is_active_feature('EDIT_SECTIONS')
def update_section(framework_slug, service_id, section_id):
    service = data_api_client.get_service(service_id)
    if service is None:
        abort(404)
    service = service['services']

    if not is_service_associated_with_supplier(service):
        abort(404)

    if service["frameworkSlug"] != framework_slug:
        abort(404)

    # we don't actually need the framework here; using this to 404 if framework for the service is not live
    get_framework_or_404(data_api_client, service['frameworkSlug'], allowed_statuses=['live'])

    try:
        content = content_loader.get_manifest(service["frameworkSlug"], 'edit_service').filter(service)
    except ContentNotFoundError:
        abort(404)
    section = content.get_section(section_id)
    if section is None or not section.editable:
        abort(404)

    posted_data = section.get_data(request.form)

    errors = None
    # This utils method filters out any empty documents and validates against service document rules
    uploaded_documents, document_errors = upload_service_documents(
        s3.S3(current_app.config['DM_DOCUMENTS_BUCKET']),
        'documents',
        current_app.config['DM_ASSETS_URL'],
        service,
        request.files,
        section,
    )
    if document_errors:
        errors = section.get_error_messages(document_errors)
    else:
        posted_data.update(uploaded_documents)

    if not errors and section.has_changes_to_save(service, posted_data):
        try:
            data_api_client.update_service(
                service_id,
                posted_data,
                current_user.email_address)
        except HTTPError as e:
            errors = section.get_error_messages(e.message)
            # If the service name is empty the final breadcrumb will disappear, so re-populate with the current name
            if not posted_data.get('serviceName', None):
                posted_data['serviceName'] = service.get('serviceName', '')

    if errors:
        return render_template(
            "services/edit_section.html",
            section=section,
            service_data=posted_data,
            service_id=service_id,
            errors=errors,
        ), 400
    flash(SERVICE_UPDATED_MESSAGE, "success")
    return redirect(url_for(".edit_service", service_id=service_id, framework_slug=service["frameworkSlug"]))


# we have to split these route definitions in two because without a fixed "/" separating the service_id and
# trailing_path it's not clearly defined where flask should start capturing trailing_path
@main.route("/services/<string:service_id>", defaults={"trailing_path": ""})
@main.route("/services/<string:service_id>/<path:trailing_path>")
@login_required
def redirect_direct_service_urls(service_id, trailing_path):
    service_response = data_api_client.get_service(service_id)
    if service_response is None:
        abort(404)
    service = service_response["services"]

    # technically we could rely on the target view to do the access restriction, but this would still allow a
    # user from a different supplier to sniff the existence & framework of a service id
    if not is_service_associated_with_supplier(service):
        abort(404)

    # note this relies on the views beneath /services/<service_id>/... remaining beneath
    # /frameworks/<framework_slug>/services/<service_id>/..., but allows us to build one redirector to work for a number
    # of views
    return redirect(url_for(
        ".edit_service",
        framework_slug=service["frameworkSlug"],
        service_id=service_id,
    ) + (trailing_path and ("/" + trailing_path)))


#  ####################  CREATING NEW DRAFT SERVICES ##########################


@main.route('/frameworks/<framework_slug>/submissions/<lot_slug>/create', methods=['GET', 'POST'])
@login_required
def start_new_draft_service(framework_slug, lot_slug):
    """Page to kick off creation of a new service."""

    framework, lot = get_framework_and_lot_or_404(data_api_client, framework_slug, lot_slug, allowed_statuses=['open'])

    # Suppliers must have registered interest in a framework before they can create draft services
    if not get_supplier_framework_info(data_api_client, framework_slug):
        abort(404)

    content = content_loader.get_manifest(framework_slug, 'edit_submission').filter(
        {'lot': lot['slug']}
    )

    section = content.get_section(content.get_next_editable_section_id())
    if section is None:
        section = content.get_section(content.get_next_edit_questions_section_id(None))
        if section is None:
            abort(404)

        section = section.get_question_as_section(section.get_next_question_slug())

    if request.method == 'POST':
        update_data = section.get_data(request.form)

        try:
            draft_service = data_api_client.create_new_draft_service(
                framework_slug, lot['slug'], current_user.supplier_id, update_data,
                current_user.email_address, page_questions=section.get_field_names()
            )['services']
        except HTTPError as e:
            update_data = section.unformat_data(update_data)
            errors = section.get_error_messages(e.message)

            return render_template(
                "services/edit_submission_section.html",
                framework=framework,
                section=section,
                service_data=update_data,
                errors=errors
            ), 400

        return redirect(
            url_for(
                ".view_service_submission",
                framework_slug=framework['slug'],
                lot_slug=draft_service['lotSlug'],
                service_id=draft_service['id'],
            )
        )

    return render_template(
        "services/edit_submission_section.html",
        framework=framework,
        lot=lot,
        service_data={},
        section=section,
        force_continue_button=True,
    ), 200


@main.route('/frameworks/<framework_slug>/submissions/<lot_slug>/<service_id>/copy', methods=['POST'])
@login_required
def copy_draft_service(framework_slug, lot_slug, service_id):
    framework, lot = get_framework_and_lot_or_404(data_api_client, framework_slug, lot_slug, allowed_statuses=['open'])

    # Suppliers must have registered interest in a framework before they can edit draft services
    if not get_supplier_framework_info(data_api_client, framework_slug):
        abort(404)

    draft = data_api_client.get_draft_service(service_id).get('services')

    if draft['lotSlug'] != lot_slug or draft['frameworkSlug'] != framework_slug:
        abort(404)

    if not is_service_associated_with_supplier(draft):
        abort(404)

    content = content_loader.get_manifest(framework_slug, 'edit_submission').filter(
        {'lot': lot['slug']}
    )

    draft_copy = data_api_client.copy_draft_service(
        service_id,
        current_user.email_address
    )['services']

    # Get the first section or question to edit.
    section_id_to_edit = content.get_next_editable_section_id()
    if section_id_to_edit is None:
        section_id_to_edit = content.get_next_edit_questions_section_id()
        question_slug_to_edit = content.get_section(section_id_to_edit).get_next_question_slug()
        if question_slug_to_edit is None:
            abort(404)
    else:
        question_slug_to_edit = None

    return redirect(url_for(".edit_service_submission",
                            framework_slug=framework['slug'],
                            lot_slug=draft['lotSlug'],
                            service_id=draft_copy['id'],
                            section_id=section_id_to_edit,
                            question_slug=question_slug_to_edit,
                            force_continue_button=1
                            ))


@main.route('/frameworks/<framework_slug>/submissions/<lot_slug>/<service_id>/complete', methods=['POST'])
@login_required
def complete_draft_service(framework_slug, lot_slug, service_id):
    framework, lot = get_framework_and_lot_or_404(data_api_client, framework_slug, lot_slug, allowed_statuses=['open'])

    # Suppliers must have registered interest in a framework before they can complete draft services
    if not get_supplier_framework_info(data_api_client, framework_slug):
        abort(404)

    draft = data_api_client.get_draft_service(service_id).get('services')

    if draft['lotSlug'] != lot_slug or draft['frameworkSlug'] != framework_slug:
        abort(404)

    if not is_service_associated_with_supplier(draft):
        abort(404)

    data_api_client.complete_draft_service(
        service_id,
        current_user.email_address
    )

    flash(SERVICE_COMPLETED_MESSAGE.format(service_name=draft.get('serviceName') or draft.get('lotName')), "success")
    flash("/".join((
        url_for(".framework_submission_lots", framework_slug=framework['slug']),
        lot_slug,
        "complete",
    )), "track-page-view")

    if lot['oneServiceLimit']:
        return redirect(url_for(".framework_submission_lots", framework_slug=framework['slug']))
    else:
        return redirect(url_for(".framework_submission_services",
                                framework_slug=framework['slug'],
                                lot_slug=lot_slug,
                                lot=lot_slug))


@main.route('/frameworks/<framework_slug>/submissions/<lot_slug>/<service_id>/delete', methods=['POST'])
@login_required
def delete_draft_service(framework_slug, lot_slug, service_id):
    framework, lot = get_framework_and_lot_or_404(data_api_client, framework_slug, lot_slug, allowed_statuses=['open'])

    # Suppliers must have registered interest in a framework before they can delete draft services
    if not get_supplier_framework_info(data_api_client, framework_slug):
        abort(404)

    draft = data_api_client.get_draft_service(service_id).get('services')

    if draft['lotSlug'] != lot_slug or draft['frameworkSlug'] != framework_slug:
        abort(404)

    if not is_service_associated_with_supplier(draft):
        abort(404)

    if request.form.get('delete_confirmed') == 'true':
        data_api_client.delete_draft_service(
            service_id,
            current_user.email_address
        )

        flash(SERVICE_DELETED_MESSAGE.format(service_name=draft.get('serviceName', draft['lotName'])), "success")
        if lot['oneServiceLimit']:
            return redirect(url_for(".framework_submission_lots", framework_slug=framework['slug']))
        else:
            return redirect(url_for(".framework_submission_services",
                                    framework_slug=framework['slug'],
                                    lot_slug=lot_slug))
    else:
        return redirect(url_for(".view_service_submission",
                                framework_slug=framework['slug'],
                                lot_slug=draft['lotSlug'],
                                service_id=service_id,
                                delete_requested=True))


@main.route('/assets/<framework_slug>/submissions/<int:supplier_id>/<document_name>', methods=['GET'])
@login_required
def service_submission_document(framework_slug, supplier_id, document_name):
    if current_user.supplier_id != supplier_id:
        abort(404)

    uploader = s3.S3(current_app.config['DM_SUBMISSIONS_BUCKET'])
    s3_url = get_signed_document_url(uploader,
                                     "{}/submissions/{}/{}".format(framework_slug, supplier_id, document_name))
    if not s3_url:
        abort(404)

    return redirect(s3_url)


@main.route('/frameworks/<framework_slug>/submissions/<lot_slug>/<service_id>', methods=['GET'])
@login_required
def view_service_submission(framework_slug, lot_slug, service_id):
    framework, lot = get_framework_and_lot_or_404(data_api_client, framework_slug, lot_slug)
    update_framework_with_formatted_dates(framework)

    try:
        data = data_api_client.get_draft_service(service_id)
        draft, last_edit, validation_errors = data['services'], data['auditEvents'], data['validationErrors']
    except HTTPError as e:
        abort(e.status_code)

    if draft['lotSlug'] != lot_slug or draft['frameworkSlug'] != framework_slug:
        abort(404)

    if not is_service_associated_with_supplier(draft):
        abort(404)

    content = content_loader.get_manifest(framework['slug'], 'edit_submission').filter(draft)

    sections = content.summary(draft)

    unanswered_required, unanswered_optional = count_unanswered_questions(sections)
    delete_requested = True if request.args.get('delete_requested') else False

    return render_template(
        "services/service_submission.html",
        framework=framework,
        lot=lot,
        confirm_remove=request.args.get("confirm_remove", None),
        service_id=service_id,
        service_data=draft,
        last_edit=last_edit,
        sections=sections,
        unanswered_required=unanswered_required,
        unanswered_optional=unanswered_optional,
        can_mark_complete=not validation_errors,
        delete_requested=delete_requested,
        declaration_status=get_declaration_status(data_api_client, framework['slug'])
    ), 200


@main.route('/frameworks/<framework_slug>/submissions/<lot_slug>/<service_id>/edit/<section_id>',
            methods=('GET', 'POST',))
@main.route('/frameworks/<framework_slug>/submissions/<lot_slug>/<service_id>/edit/<section_id>/<question_slug>',
            methods=('GET', 'POST',))
@login_required
def edit_service_submission(framework_slug, lot_slug, service_id, section_id, question_slug=None):
    """
        Also accepts URL parameter `force_continue_button` which will allow rendering of a 'Save and continue' button,
        used for when copying services.
    """
    framework, lot = get_framework_and_lot_or_404(data_api_client, framework_slug, lot_slug, allowed_statuses=['open'])

    # Suppliers must have registered interest in a framework before they can edit draft services
    if not get_supplier_framework_info(data_api_client, framework_slug):
        abort(404)

    force_return_to_summary = framework['framework'] == "digital-outcomes-and-specialists"
    force_continue_button = request.args.get('force_continue_button')
    next_question = None

    try:
        draft = data_api_client.get_draft_service(service_id)['services']
    except HTTPError as e:
        abort(e.status_code)

    if draft['lotSlug'] != lot_slug or draft['frameworkSlug'] != framework_slug:
        abort(404)

    if not is_service_associated_with_supplier(draft):
        abort(404)

    content = content_loader.get_manifest(framework_slug, 'edit_submission').filter(draft)
    section = content.get_section(section_id)
    if section and (question_slug is not None):
        next_question = section.get_question_by_slug(section.get_next_question_slug(question_slug))
        section = section.get_question_as_section(question_slug)

    if section is None or not section.editable:
        abort(404)

    errors = None
    if request.method == "POST":
        update_data = section.get_data(request.form)

        if request.files:
            uploader = s3.S3(current_app.config['DM_SUBMISSIONS_BUCKET'])
            documents_url = url_for('.dashboard', _external=True) + '/assets/'
            # This utils method filters out any empty documents and validates against service document rules
            uploaded_documents, document_errors = upload_service_documents(
                uploader, 'submissions', documents_url, draft, request.files, section,
                public=False)

            if document_errors:
                errors = section.get_error_messages(document_errors, question_descriptor_from="question")
            else:
                update_data.update(uploaded_documents)

        if not errors and section.has_changes_to_save(draft, update_data):
            try:
                data_api_client.update_draft_service(
                    service_id,
                    update_data,
                    current_user.email_address,
                    page_questions=section.get_field_names()
                )
            except HTTPError as e:
                update_data = section.unformat_data(update_data)
                errors = section.get_error_messages(e.message, question_descriptor_from="question")

        if not errors:
            if next_question and not force_return_to_summary:
                return redirect(url_for(".edit_service_submission",
                                        framework_slug=framework['slug'],
                                        lot_slug=draft['lotSlug'],
                                        service_id=service_id,
                                        section_id=section_id,
                                        question_slug=next_question.slug))
            else:
                return redirect(url_for(".view_service_submission",
                                        framework_slug=framework['slug'],
                                        lot_slug=draft['lotSlug'],
                                        service_id=service_id,
                                        _anchor=section_id))

        update_data.update(
            (k, draft[k]) for k in ('serviceName', 'lot', 'lotName',) if k in draft and k not in update_data
        )
        service_data = update_data
        # fall through to regular GET path to display errors
    else:
        service_data = section.unformat_data(draft)

    return render_template(
        "services/edit_submission_section.html",
        section=section,
        framework=framework,
        lot=lot,
        next_question=next_question,
        service_data=service_data,
        service_id=service_id,
        force_return_to_summary=force_return_to_summary,
        force_continue_button=force_continue_button,
        errors=errors,
    )


@main.route('/frameworks/<framework_slug>/submissions/<lot_slug>/<service_id>/remove/<section_id>/<question_slug>',
            methods=['GET', 'POST'])
@login_required
def remove_subsection(framework_slug, lot_slug, service_id, section_id, question_slug):
    # Suppliers must have registered interest in a framework before they can edit draft services
    if not get_supplier_framework_info(data_api_client, framework_slug):
        abort(404)

    try:
        draft = data_api_client.get_draft_service(service_id)['services']
    except HTTPError as e:
        abort(e.status_code)

    if not is_service_associated_with_supplier(draft):
        abort(404)

    content = content_loader.get_manifest(framework_slug, 'edit_submission').filter(draft)
    section = content.get_section(section_id)
    containing_section = section
    if section and (question_slug is not None):
        section = section.get_question_as_section(question_slug)
    if section is None or not section.editable:
        abort(404)

    question_to_remove = content.get_question_by_slug(question_slug)
    fields_to_remove = question_to_remove.form_fields

    # simply defining this as an inner function so we can avoid having to manually pass around the umpteen variables
    # it depends on instead pulling them from the outer scope
    def set_remove_last_subsection_error_message():
        flash(REMOVE_LAST_SUBSECTION_ERROR_MESSAGE.format(
            section_name=containing_section.name.lower(),
            service_name=(draft.get("serviceName") or draft.get("lotName")).lower(),
        ), "error")
        flash("/".join((
            url_for(
                ".remove_subsection",
                framework_slug=framework_slug,
                lot_slug=lot_slug,
                service_id=service_id,
                section_id=section_id,
                question_slug=question_slug,
            ),
            "remove-last-subsection-attempt",
        )), "track-page-view")

    if request.args.get("confirm") and request.method == "POST":
        # Remove the section
        update_json = {field: None for field in fields_to_remove}
        try:
            data_api_client.update_draft_service(
                service_id,
                update_json,
                current_user.email_address
            )
            flash(SERVICE_DELETED_MESSAGE.format(service_name=question_to_remove.label), "success")
        except HTTPError as e:
            if e.status_code == 400:
                # You can't remove the last one
                set_remove_last_subsection_error_message()
            else:
                abort(e.status_code)

    else:
        section_responses = [field for field in containing_section.get_field_names() if field in draft]
        fields_remaining_after_removal = [field for field in section_responses if field not in fields_to_remove]

        if draft['status'] == 'not-submitted' or len(fields_remaining_after_removal) > 0:
            # Show page with "Are you sure?" message and button
            return redirect(
                url_for('.view_service_submission',
                        framework_slug=framework_slug,
                        lot_slug=lot_slug,
                        service_id=service_id,
                        confirm_remove=question_slug,
                        section_id=section_id
                        )
            )
        else:
            # You can't remove the last one
            set_remove_last_subsection_error_message()

    return redirect(
        url_for('.view_service_submission',
                framework_slug=framework_slug,
                lot_slug=lot_slug,
                service_id=service_id,
                confirm_remove=None
                ))


@main.route('/frameworks/<framework_slug>/submissions/<lot_slug>/previous-services', methods=['GET', 'POST'])
@login_required
def previous_services(framework_slug, lot_slug):
    framework, lot = get_framework_and_lot_or_404(data_api_client, framework_slug, lot_slug)
    if framework['status'] != 'open':
        abort(404)

    form = OneServiceLimitCopyServiceForm(lot['name'].lower()) if lot.get('oneServiceLimit') else None
    source_framework_slug = content_loader.get_metadata(framework['slug'], 'copy_services', 'source_framework')
    source_framework = get_framework_or_500(data_api_client, source_framework_slug, logger=current_app.logger)

    previous_services_list = data_api_client.find_services(
        supplier_id=current_user.supplier_id,
        framework=source_framework_slug,
        lot=lot_slug,
        status='published',
    )["services"]

    previous_services_still_to_copy = [
        service for service in previous_services_list if not service['copiedToFollowingFramework']
    ]

    if not previous_services_still_to_copy:
        return redirect(url_for(".framework_submission_services", framework_slug=framework_slug, lot_slug=lot_slug))

    if request.method == 'POST':
        if lot.get('oneServiceLimit'):
            # Don't copy a service if the lot has a one service limit and the supplier already has a draft for that lot
            drafts, complete_drafts = get_lot_drafts(data_api_client, framework_slug, lot_slug)
            if drafts or complete_drafts:
                abort(400)
            if form.validate_on_submit():
                if form.copy_service.data is True:
                    copy_service_from_previous_framework(
                        data_api_client,
                        content_loader,
                        framework_slug,
                        lot_slug,
                        previous_services_still_to_copy[0]['id'],
                    )
                    flash(SINGLE_SERVICE_ADDED_MESSAGE.format(framework_name=framework['name']), "success")
                else:
                    data_api_client.create_new_draft_service(
                        framework_slug, lot_slug, current_user.supplier_id, {}, current_user.email_address,
                    )
                return redirect(
                    url_for('.framework_submission_services', framework_slug=framework_slug, lot_slug=lot_slug)
                )
        else:
            # Should not be POSTing to this view if not a one service lot
            abort(400)

    copy_all = request.args.get('copy_all', None)
    supplier = data_api_client.get_supplier(current_user.supplier_id)['suppliers']

    return render_template(
        "services/previous_services.html",
        framework=framework,
        lot=lot,
        source_framework=source_framework,
        previous_services_still_to_copy=previous_services_still_to_copy,
        copy_all=copy_all,
        declaration_status=get_declaration_status(data_api_client, framework_slug),
        company_details_complete=supplier['companyDetailsConfirmed'],
        form=form,
        form_errors=[{'question': form[key].label.text, 'input_name': key} for key in form.errors] if form else None,
    )


@main.route('/frameworks/<framework_slug>/submissions/<lot_slug>/copy-previous-framework-service/<service_id>',
            methods=['POST'])
@login_required
def copy_previous_service(framework_slug, lot_slug, service_id):
    framework, lot = get_framework_and_lot_or_404(
        data_api_client, framework_slug, lot_slug, allowed_statuses=['open']
    )
    copy_service_from_previous_framework(data_api_client, content_loader, framework_slug, lot_slug, service_id)
    flash(SINGLE_SERVICE_ADDED_MESSAGE.format(framework_name=framework['name']), "success")

    return redirect(url_for(".previous_services", framework_slug=framework_slug, lot_slug=lot_slug))


@main.route('/frameworks/<framework_slug>/submissions/<lot_slug>/copy-all-previous-framework-services',
            methods=['POST'])
@login_required
def copy_all_previous_services(framework_slug, lot_slug):
        framework, lot = get_framework_and_lot_or_404(
            data_api_client, framework_slug, lot_slug, allowed_statuses=['open']
        )

        # Suppliers must have registered interest in a framework before they can edit draft services
        if not get_supplier_framework_info(data_api_client, framework_slug):
            abort(404)

        questions_to_copy = content_loader.get_metadata(framework['slug'], 'copy_services', 'questions_to_copy')
        source_framework_slug = content_loader.get_metadata(framework['slug'], 'copy_services', 'source_framework')

        response = data_api_client.copy_published_from_framework(
            framework_slug,
            lot_slug,
            current_user.name,
            data={
                "sourceFrameworkSlug": source_framework_slug,
                "supplierId": current_user.supplier_id,
                "questionsToCopy": questions_to_copy
            }
        )['services']

        flash(
            ALL_SERVICES_ADDED_MESSAGE.format(
                draft_count=response['draftsCreatedCount'], framework_name=framework['name']
            ),
            "success"
        )

        return redirect(url_for(".framework_submission_services", framework_slug=framework_slug, lot_slug=lot_slug))
