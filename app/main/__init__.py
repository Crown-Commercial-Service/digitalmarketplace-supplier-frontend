from flask import Blueprint

from dmcontent.content_loader import ContentLoader

main = Blueprint('main', __name__)

content_loader = ContentLoader('app/content')
content_loader.load_manifest('g-cloud-6', 'services', 'edit_service')
content_loader.load_messages('g-cloud-6', ['urls'])

content_loader.load_manifest('g-cloud-7', 'services', 'edit_service')
content_loader.load_manifest('g-cloud-7', 'services', 'edit_submission')
content_loader.load_manifest('g-cloud-7', 'declaration', 'declaration')
content_loader.load_messages('g-cloud-7', ['urls'])

content_loader.load_manifest('digital-outcomes-and-specialists', 'declaration', 'declaration')
content_loader.load_manifest('digital-outcomes-and-specialists', 'services', 'edit_submission')
content_loader.load_manifest('digital-outcomes-and-specialists', 'briefs', 'edit_brief')
content_loader.load_messages('digital-outcomes-and-specialists', ['urls'])

content_loader.load_manifest('digital-outcomes-and-specialists-2', 'declaration', 'declaration')
content_loader.load_manifest('digital-outcomes-and-specialists-2', 'services', 'edit_submission')
content_loader.load_manifest('digital-outcomes-and-specialists-2', 'services', 'edit_service')
content_loader.load_manifest('digital-outcomes-and-specialists-2', 'briefs', 'edit_brief')
content_loader.load_messages('digital-outcomes-and-specialists-2', ['urls'])

content_loader.load_manifest('g-cloud-8', 'services', 'edit_service')
content_loader.load_manifest('g-cloud-8', 'services', 'edit_submission')
content_loader.load_manifest('g-cloud-8', 'declaration', 'declaration')
content_loader.load_messages('g-cloud-8', ['urls'])

content_loader.load_manifest('g-cloud-9', 'services', 'edit_service')
content_loader.load_manifest('g-cloud-9', 'services', 'edit_submission')
content_loader.load_manifest('g-cloud-9', 'declaration', 'declaration')
content_loader.load_messages('g-cloud-9', ['urls', 'advice'])

content_loader.load_manifest('g-cloud-10', 'services', 'edit_service')
content_loader.load_manifest('g-cloud-10', 'services', 'edit_submission')
content_loader.load_manifest('g-cloud-10', 'declaration', 'declaration')
content_loader.load_messages('g-cloud-10', ['urls', 'advice'])
content_loader.load_metadata('g-cloud-10', ['copy_services'])

content_loader.load_manifest('digital-outcomes-and-specialists-3', 'declaration', 'declaration')
content_loader.load_manifest('digital-outcomes-and-specialists-3', 'services', 'edit_submission')
content_loader.load_manifest('digital-outcomes-and-specialists-3', 'services', 'edit_service')
content_loader.load_manifest('digital-outcomes-and-specialists-3', 'briefs', 'edit_brief')
content_loader.load_messages('digital-outcomes-and-specialists-3', ['urls'])


@main.after_request
def add_cache_control(response):
    response.cache_control.no_cache = True
    return response


from .views import services, suppliers, login, frameworks, users
from . import errors
