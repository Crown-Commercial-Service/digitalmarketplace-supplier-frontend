from datetime import datetime

from flask import Blueprint
from flask_login import login_user

from dmutils.user import User
from dmutils.formats import DATETIME_FORMAT

login_for_tests = Blueprint('login_for_tests', __name__)


@login_for_tests.route('/auto-login')
def auto_login():
    user_json = {"users": {
        'id': 123,
        'supplier_name': 'Supplier Name',
        'name': 'Name',
        'emailAddress': 'email@email.com',
        'role': 'supplier',
        'supplierCode': 1234,
        'termsAcceptedAt': datetime(2000, 1, 1).strftime(DATETIME_FORMAT),
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
        'role': 'buyer',
        'termsAcceptedAt': datetime(2000, 1, 1).strftime(DATETIME_FORMAT),
    }
    }
    user = User.from_json(user_json)
    login_user(user)
    return "OK"


@login_for_tests.route('/auto-applicant-login')
def auto_applicant_login():
    user_json = {"users": {
        'id': 234,
        'name': 'Applicant',
        'emailAddress': 'applicant@email.com',
        'role': 'applicant',
        'termsAcceptedAt': datetime(2000, 1, 1).strftime(DATETIME_FORMAT),
    }
    }
    user = User.from_json(user_json)
    login_user(user)
    return "OK"
