from flask_login import current_user
from flask import render_template, abort, flash, url_for, redirect, current_app

from ..helpers import login_required
from ...main import main
from ... import data_api_client


def get_current_suppliers_users():

    users = data_api_client.find_users(
        supplier_id=current_user.supplier_id
    ).get('users')

    active_users = [user for user in users if user['active']]

    for index, user in enumerate(active_users):
        if user['id'] == current_user.id:
            # insert current user into front of list
            active_users.insert(0, active_users.pop(index))
            break

    return active_users


@main.route('/users')
@login_required
def list_users():

    template_data = main.config['BASE_TEMPLATE_DATA']

    return render_template(
        "users/list_users.html",
        current_user=current_user,
        users=get_current_suppliers_users(),
        **template_data), 200


@main.route('/users/<int:user_id>/deactivate', methods=['POST'])
@login_required
def deactivate_user(user_id):

    # check that id is not current user
    if user_id == current_user.id:
        current_app.logger.error(
            "deactivate_user cannot deactivate self, user_id={user_id} supplier_id={supplier_id}",
            extra={
                'user_id': current_user.id,
                'supplier_id': current_user.supplier_id})
        abort(404)

    # check that user exists
    user_to_deactivate = data_api_client.get_user(user_id=user_id)

    if not user_to_deactivate or not user_to_deactivate.get('users'):
        current_app.logger.error(
            "deactivate_user user to deactivate not found, "
            "user_id={user_id} supplier_id={supplier_id} user_id_to_deactivate={to_deactivate}",
            extra={
                'user_id': current_user.id, 'supplier_id': current_user.supplier_id,
                'to_deactivate': user_id})
        abort(404)

    user_to_deactivate = user_to_deactivate.get('users')

    # check that user to deactivate belongs to supplier of current user
    if user_to_deactivate['role'] != 'supplier' \
            or user_to_deactivate['supplier']['supplierId'] != current_user.supplier_id:
        current_app.logger.error(
            "deactivate_user cannot deactivate another suppliers' users, "
            "user_id={user_id} supplier_id={supplier_id} user_id_to_deactivate={to_deactivate}",
            extra={
                'user_id': current_user.id, 'supplier_id': current_user.supplier_id,
                'to_deactivate': user_id})
        abort(404)

    data_api_client.update_user(user_id=user_to_deactivate['id'], active=False, updater=current_user.email_address)

    flash({
        'deactivate_user_name': user_to_deactivate['name'],
        'deactivate_user_email_address': user_to_deactivate['emailAddress']
    })

    return redirect(url_for('.list_users'))
