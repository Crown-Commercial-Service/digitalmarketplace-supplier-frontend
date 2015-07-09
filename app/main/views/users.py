from flask_login import login_required, current_user
from flask import render_template
from datetime import datetime

from ...main import main
from ... import data_api_client, flask_featureflags
from dmutils.formats import DATETIME_FORMAT

DISPLAY_DATETIME_FORMAT = '%A, %d %B %Y at %H:%M'


@main.route('/users')
@login_required
@flask_featureflags.is_active_feature('USER_DASHBOARD')
def list_users():

    def display_last_logged_in_date(last_logged_in):
        if not last_logged_in:
            return ''

        return datetime.strptime(
            last_logged_in, DATETIME_FORMAT
        ).strftime(DISPLAY_DATETIME_FORMAT)

    template_data = main.config['BASE_TEMPLATE_DATA']
    template_users = []

    suppliers_users = data_api_client.find_users(
        supplier_id=current_user.supplier_id
    )

    for user in suppliers_users["users"]:

        template_users.append({
            'name': user['name'],
            'email_address': user['emailAddress'],
            'logged_in_at': display_last_logged_in_date(user['loggedInAt']),
            'locked': user['locked']
        })

    return render_template(
        "users/list_users.html",
        users=template_users,
        **template_data), 200
