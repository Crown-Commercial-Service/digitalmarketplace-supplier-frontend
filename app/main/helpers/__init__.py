import hashlib
import base64
import six


def hash_email(email):
    m = hashlib.sha256()
    m.update(email.encode('utf-8'))

    return base64.urlsafe_b64encode(m.digest())


def is_existing_supplier_user(user):
    if not user:
        return False
    if user['users'].get('role') is 'supplier':
        return True
    return False
