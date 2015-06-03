from flask import Blueprint

main = Blueprint('main', __name__)

from . import errors
from .views import services, suppliers, login
