from flask import Blueprint
from dmutils.user import User
from flask_login import login_user

login_for_tests = Blueprint('login_for_tests', __name__)


@login_for_tests.route('/auto-login')
def auto_login():
    user_json = {"users": {
        'id': 123,
        'supplier_name': 'Supplier Name',
        'name': 'Name',
        'emailAddress': 'email@email.com',
        'role': 'supplier',
        'supplierId': 1234
    }
    }
    user = User.from_json(user_json)
    login_user(user)
    return "OK"


@login_for_tests.route('/auto-buyer-login')
def auto_buyer_login():
    user_json = {"users": {
        'id': 234,
        'name': 'Buyer',
        'emailAddress': 'buyer@email.com',
        'role': 'buyer'
    }
    }
    user = User.from_json(user_json)
    login_user(user)
    return "OK"
