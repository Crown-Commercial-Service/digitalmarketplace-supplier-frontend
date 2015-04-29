import requests
from flask import json, current_app
from ..model import User


class ApiClient:
    root_url = None
    token = None

    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.root_url = app.config['DM_API_URL']
        self.token = app.config['DM_API_AUTH_TOKEN']

    def headers(self):
        return {
            "content-type": "application/json",
            "Authorization": "Bearer {}".format(self.token)
        }

    def services_by_supplier_id(self, supplier_id):
        res = requests.get(
            "{}/{}?supplier_id={}".format(
                self.root_url,
                "services",
                supplier_id),
            headers=self.headers()
        )
        if res.status_code is 200:
            return res.json()
        elif res.status_code is 400:
            # TODO log bad request
            return None
        else:
            # TODO log error
            return None

    def user_by_id(self, user_id):
        res = requests.get(
            "{}/{}/{}".format(self.root_url, "users", user_id),
            headers=self.headers()
        )
        if res.status_code is 200:
            return self.user_json_to_user(res.json())
        elif res.status_code is 400:
            # TODO log bad request
            return None
        else:
            # TODO log error
            return None

    def user_by_email(self, email_address):
        res = requests.get(
            "{}/{}".format(self.root_url, "users"),
            params={"email": email_address},
            headers=self.headers()
        )
        if res.status_code is 200:
            return self.user_json_to_user(res.json())
        elif res.status_code is 400:
            # TODO log bad request
            return None
        else:
            # TODO log error
            return None

    def users_auth(self, email_address, password):
        res = requests.post(
            "{}/{}".format(self.root_url, "users/auth"),
            data=json.dumps(
                {
                    "authUsers": {
                        "emailAddress": email_address,
                        "password": password
                    }
                }
            ),
            headers=self.headers()
        )
        if res.status_code is 200:
            if self.is_supplier_user(res.json()):
                return self.user_json_to_user(res.json())
            return None
        elif res.status_code is 400:
            # TODO log bad request
            return None
        elif res.status_code is 403:
            # TODO log unauthorized
            return None
        elif res.status_code is 404:
            # TODO log not found
            return None
        else:
            # TODO log error
            return None

    def user_update_password(self, user_id, new_password):
        res = requests.post(
            "{}/{}/{}".format(self.root_url, "users", user_id),
            data=json.dumps(
                {
                    "users": {
                        "password": new_password
                    }
                }
            ),
            headers=self.headers()
        )
        if res.status_code is 200:
            current_app.logger.info("Updated password for user %d", user_id)
            return True
        else:
            current_app.logger.info("Password update failed for user %d: %s",
                                    user_id, res.status_code)
            return False

    @staticmethod
    def user_json_to_user(user_json):
        user = user_json["users"]
        supplier_id = None
        supplier_name = None
        if "supplier" in user:
            supplier_id = user["supplier"]["supplierId"]
            supplier_name = user["supplier"]["name"]
        return User(
            user_id=user["id"],
            email_address=user['emailAddress'],
            supplier_id=supplier_id,
            supplier_name=supplier_name
        )

    @staticmethod
    def is_supplier_user(user_json):
        if "supplier" in user_json["users"]:
            return True
        return False
