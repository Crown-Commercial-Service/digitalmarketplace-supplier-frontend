from flask import Blueprint
from dmutils.content_loader import ContentLoader

main = Blueprint('main', __name__)

existing_service_content = ContentLoader(
    'app/existing_service_manifest.yml', 'app/content/g6/'
)
new_service_content = ContentLoader(
    'app/new_service_manifest.yml', 'app/content/g6/'
)


@main.after_request
def add_cache_control(response):
    response.cache_control.no_cache = True
    return response


from app.main import errors
