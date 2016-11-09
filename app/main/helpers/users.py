from flask import current_app

from dmutils.email import decode_token, generate_token, InvalidToken, ONE_DAY_IN_SECONDS


def generate_supplier_invitation_token(name, email_address, supplier_code, supplier_name):
    data = {
        'name': name,
        'emailAddress': email_address,
        'supplierCode': supplier_code,
        'supplierName': supplier_name,
    }
    token = generate_token(data, current_app.config['SECRET_KEY'], current_app.config['SUPPLIER_INVITE_TOKEN_SALT'])
    return token


def decode_supplier_invitation_token(token):
    data = decode_token(
        token,
        current_app.config['SECRET_KEY'],
        current_app.config['SUPPLIER_INVITE_TOKEN_SALT'],
        7*ONE_DAY_IN_SECONDS
    )
    if not set(('name', 'emailAddress', 'supplierCode', 'supplierName')).issubset(set(data.keys())):
        raise InvalidToken
    return data


def generate_applicant_invitation_token(data):
    token = generate_token(data, current_app.config['SECRET_KEY'], current_app.config['SUPPLIER_INVITE_TOKEN_SALT'])
    return token
