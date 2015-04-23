from flask import Blueprint

main = Blueprint('main', __name__)

from . import login, services, errors
