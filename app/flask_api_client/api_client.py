import requests
from flask import json
from app.model import User


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

    def users_auth(self, email_address, password):
        res = requests.post(
            "{}/{}".format(self.root_url, "users/auth"),
            data=json.dumps(
                {
                    "auth_users": {
                        "email_address": email_address,
                        "password": password
                    }
                }
            ),
            headers=self.headers()
        )
        if res.status_code is 200:
            return self.user_json_to_user(res.json())
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

    @staticmethod
    def user_json_to_user(user_json):
        return User(
            user_json["users"]["id"],
            user_json["users"]['email_address']
        )
