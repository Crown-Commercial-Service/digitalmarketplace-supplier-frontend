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


@main.route('/dashboard')
def list_services():
    try:
        supplier_id = request.args.get("supplier_id")
        service_json = json.loads(get_services_json_for_supplier(supplier_id))
        template_data = main.config['BASE_TEMPLATE_DATA']
        return render_template(
            "list_services.html", service_data=service_json["services"],
            **template_data), 200
    except KeyError:
        return Response("No services for supplier '%s'" % supplier_id, 404)


@main.route('/viewservice')
def get_service_by_id():
    try:
        service_id = request.args.get("service_id")
        service_json = json.loads(get_service_json(service_id))["services"]
        return Response(json.dumps(service_json), mimetype='application/json')
    except KeyError:
        return Response("Service ID '%s' can not be found" % service_id, 404)


def get_service_json(service_id):
    url = api_url + "/services/" + service_id
    response = requests.get(
        url,
        headers={
            "authorization": "Bearer {}".format(api_access_token)
        }
    )
    return response.content


def get_services_json_for_supplier(supplier_id):
    url = api_url + "/services"
    payload = {"supplier_id": supplier_id}
    response = requests.get(
        url,
        params=payload,
        headers={
            "authorization": "Bearer {}".format(api_access_token)
        }
    )
    return response.content
