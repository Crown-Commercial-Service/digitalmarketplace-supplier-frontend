import requests
import os
from . import main
from flask import json, render_template, Response, request


api_url = os.getenv('DM_API_URL')
api_access_token = os.getenv('DM_SUPPLIER_FRONTEND_API_AUTH_TOKEN')

if api_access_token is None:
    print('Token must be supplied in DM_SUPPLIER_FRONTEND_API_AUTH_TOKEN')
    raise Exception("DM_SUPPLIER_FRONTEND_API_AUTH_TOKEN token is not set")
if api_url is None:
    print('API URL must be supplied in DM_API_URL')
    raise Exception("DM_API_URL is not set")


@main.route('/')
def index():
    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template("index.html", **template_data), 200
