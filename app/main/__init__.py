from flask import Blueprint
from werkzeug.local import Local, LocalProxy

from dmcontent.content_loader import ContentLoader

main = Blueprint('main', __name__)

# we use our own Local for objects we explicitly want to be able to retain between requests but shouldn't
# share a common object between concurrent threads/contexts
_local = Local()


def get_content_loader():
    if hasattr(_local, "content_loader"):
        return _local.content_loader

    _content_loader = _local.content_loader = ContentLoader('app/content')
    _content_loader.load_manifest('g-cloud-6', 'services', 'edit_service')
    _content_loader.load_messages('g-cloud-6', ['urls'])

    _content_loader.load_manifest('g-cloud-7', 'services', 'edit_service')
    _content_loader.load_manifest('g-cloud-7', 'services', 'edit_submission')
    _content_loader.load_manifest('g-cloud-7', 'declaration', 'declaration')
    _content_loader.load_messages('g-cloud-7', ['urls'])

    _content_loader.load_manifest('digital-outcomes-and-specialists', 'declaration', 'declaration')
    _content_loader.load_manifest('digital-outcomes-and-specialists', 'services', 'edit_submission')
    _content_loader.load_manifest('digital-outcomes-and-specialists', 'briefs', 'edit_brief')
    _content_loader.load_messages('digital-outcomes-and-specialists', ['urls'])

    _content_loader.load_manifest('digital-outcomes-and-specialists-2', 'declaration', 'declaration')
    _content_loader.load_manifest('digital-outcomes-and-specialists-2', 'services', 'edit_submission')
    _content_loader.load_manifest('digital-outcomes-and-specialists-2', 'services', 'edit_service')
    _content_loader.load_manifest('digital-outcomes-and-specialists-2', 'briefs', 'edit_brief')
    _content_loader.load_messages('digital-outcomes-and-specialists-2', ['urls'])

    _content_loader.load_manifest('g-cloud-8', 'services', 'edit_service')
    _content_loader.load_manifest('g-cloud-8', 'services', 'edit_submission')
    _content_loader.load_manifest('g-cloud-8', 'declaration', 'declaration')
    _content_loader.load_messages('g-cloud-8', ['urls'])

    _content_loader.load_manifest('g-cloud-9', 'services', 'edit_service')
    _content_loader.load_manifest('g-cloud-9', 'services', 'edit_submission')
    _content_loader.load_manifest('g-cloud-9', 'declaration', 'declaration')
    _content_loader.load_messages('g-cloud-9', ['urls', 'advice'])

    _content_loader.load_manifest('g-cloud-10', 'services', 'edit_service')
    _content_loader.load_manifest('g-cloud-10', 'services', 'edit_submission')
    _content_loader.load_manifest('g-cloud-10', 'declaration', 'declaration')
    _content_loader.load_messages('g-cloud-10', ['urls', 'advice'])
    _content_loader.load_metadata('g-cloud-10', ['copy_services'])

    _content_loader.load_manifest('digital-outcomes-and-specialists-3', 'declaration', 'declaration')
    _content_loader.load_manifest('digital-outcomes-and-specialists-3', 'services', 'edit_submission')
    _content_loader.load_manifest('digital-outcomes-and-specialists-3', 'services', 'edit_service')
    _content_loader.load_manifest('digital-outcomes-and-specialists-3', 'briefs', 'edit_brief')
    _content_loader.load_messages('digital-outcomes-and-specialists-3', ['urls'])
    _content_loader.load_metadata('digital-outcomes-and-specialists-3', ['copy_services', 'following_framework'])

    _content_loader.load_manifest('g-cloud-11', 'services', 'edit_service')
    _content_loader.load_manifest('g-cloud-11', 'services', 'edit_submission')
    _content_loader.load_manifest('g-cloud-11', 'declaration', 'declaration')
    _content_loader.load_messages('g-cloud-11', ['urls', 'advice'])
    _content_loader.load_metadata('g-cloud-11', ['copy_services', 'following_framework'])

    return _content_loader


content_loader = LocalProxy(get_content_loader)


@main.after_request
def add_cache_control(response):
    response.cache_control.no_cache = True
    return response


from .views import services, suppliers, login, frameworks, users
from . import errors
