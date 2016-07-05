from flask import Blueprint
from dmcontent.content_loader import ContentLoader

main = Blueprint('main', __name__)

content_loader = ContentLoader('app/content')
content_loader.load_manifest('g-cloud-6', 'services', 'edit_service')
content_loader.load_messages('g-cloud-6', ['dates'])

content_loader.load_manifest('g-cloud-7', 'services', 'edit_service')
content_loader.load_manifest('g-cloud-7', 'services', 'edit_submission')
content_loader.load_manifest('g-cloud-7', 'declaration', 'declaration')
content_loader.load_messages('g-cloud-7', ['dates'])

content_loader.load_manifest('digital-outcomes-and-specialists', 'declaration', 'declaration')
content_loader.load_manifest('digital-outcomes-and-specialists', 'services', 'edit_submission')
content_loader.load_manifest('digital-outcomes-and-specialists', 'brief-responses', 'edit_brief_response')
content_loader.load_manifest('digital-outcomes-and-specialists', 'brief-responses', 'display_brief_response')
content_loader.load_messages('digital-outcomes-and-specialists', ['dates'])

content_loader.load_manifest('g-cloud-8', 'services', 'edit_service')
content_loader.load_manifest('g-cloud-8', 'services', 'edit_submission')
content_loader.load_manifest('g-cloud-8', 'declaration', 'declaration')
content_loader.load_messages('g-cloud-8', ['dates'])


@main.after_request
def add_cache_control(response):
    response.cache_control.no_cache = True
    return response


from .views import services, suppliers, login, frameworks, users, briefs
from . import errors
