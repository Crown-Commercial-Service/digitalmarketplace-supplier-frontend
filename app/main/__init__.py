from flask import Blueprint
from dmutils.content_loader import ContentLoader

main = Blueprint('main', __name__)

existing_service_content = ContentLoader(
    'app/content/frameworks/g-cloud-6/manifests/edit_service.yml',
    'app/content/frameworks/g-cloud-6/questions/services/'
)
new_service_content = ContentLoader(
    'app/content/frameworks/g-cloud-7/manifests/edit_submission.yml',
    'app/content/frameworks/g-cloud-7/questions/services/'
)
declaration_content = ContentLoader(
    'app/content/frameworks/g-cloud-7/manifests/declaration.yml',
    'app/content/frameworks/g-cloud-7/questions/declaration/'
)


@main.after_request
def add_cache_control(response):
    response.cache_control.no_cache = True
    return response


from . import errors
from .views import services, suppliers, login, frameworks, users
