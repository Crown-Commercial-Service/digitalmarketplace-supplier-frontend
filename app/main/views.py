import requests
import os
from . import main
from flask import json, render_template, Response, request


@main.route('/')
def index():
    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template("index.html", **template_data), 200


@main.route('/listservices')
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


def get_services_json_for_supplier(supplier_id):
    access_token = os.getenv('DM_API_BEARER')
    if access_token is None:
        print('Bearer token must be supplied in DM_API_BEARER')
        raise Exception("DM_API_BEARER token is not set")
    url = os.getenv('DM_API_URL') + "/services?supplier_id=" + supplier_id
    response = requests.get(
        url,
        headers={
            "authorization": "Bearer {}".format(access_token)
        }
    )
    return response.content


@main.route('/viewservice')
def get_service_by_id():
    try:
        service_id = request.args.get("service_id")
        service_json = json.loads(get_service_json(service_id))["services"]
        return Response(json.dumps(service_json), mimetype='application/json')
    except KeyError:
        return Response("Service ID '%s' can not be found" % service_id, 404)


def get_service_json(service_id):
    access_token = os.getenv('DM_API_BEARER')
    if access_token is None:
        print('Bearer token must be supplied in DM_API_BEARER')
        raise Exception("DM_API_BEARER token is not set")
    url = os.getenv('DM_API_URL') + "/services/" + service_id
    response = requests.get(
        url,
        headers={
            "authorization": "Bearer {}".format(access_token)
        }
    )
    return response.content
