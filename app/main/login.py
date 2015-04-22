from . import main
from flask import render_template, redirect, url_for

@main.route('/login', methods=["GET"])
def render_login():
    template_data = main.config['BASE_TEMPLATE_DATA']
    return render_template("login/login.html", **template_data), 200


@main.route('/login', methods=["POST"])
def process_login():
    template_data = main.config['BASE_TEMPLATE_DATA']

    #return render_template("login/login.html", **template_data), 200
    return redirect(url_for('.dashboard'))

