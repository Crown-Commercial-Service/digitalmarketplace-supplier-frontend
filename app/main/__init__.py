from copy import deepcopy

from flask import Blueprint, current_app
from werkzeug.local import Local, LocalProxy

from dmutils.direct_plus_client import DirectPlusClient

from dmcontent.content_loader import ContentLoader

from dmutils.timing import logged_duration

main = Blueprint('main', __name__)

# we use our own Local for objects we explicitly want to be able to retain between requests but shouldn't
# share a common object between concurrent threads/contexts
_local = Local()


def _make_content_loader_factory():
    master_cl = ContentLoader('app/content')
    master_cl.load_manifest('g-cloud-6', 'services', 'edit_service')
    master_cl.load_messages('g-cloud-6', ['urls'])

    master_cl.load_manifest('g-cloud-7', 'services', 'edit_service')
    master_cl.load_manifest('g-cloud-7', 'services', 'edit_submission')
    master_cl.load_manifest('g-cloud-7', 'declaration', 'declaration')
    master_cl.load_messages('g-cloud-7', ['urls'])

    master_cl.load_manifest('digital-outcomes-and-specialists', 'declaration', 'declaration')
    master_cl.load_manifest('digital-outcomes-and-specialists', 'services', 'edit_submission')
    master_cl.load_manifest('digital-outcomes-and-specialists', 'briefs', 'edit_brief')
    master_cl.load_messages('digital-outcomes-and-specialists', ['urls'])

    master_cl.load_manifest('digital-outcomes-and-specialists-2', 'declaration', 'declaration')
    master_cl.load_manifest('digital-outcomes-and-specialists-2', 'services', 'edit_submission')
    master_cl.load_manifest('digital-outcomes-and-specialists-2', 'services', 'edit_service')
    master_cl.load_manifest('digital-outcomes-and-specialists-2', 'briefs', 'edit_brief')
    master_cl.load_messages('digital-outcomes-and-specialists-2', ['urls'])

    master_cl.load_manifest('g-cloud-8', 'services', 'edit_service')
    master_cl.load_manifest('g-cloud-8', 'services', 'edit_submission')
    master_cl.load_manifest('g-cloud-8', 'declaration', 'declaration')
    master_cl.load_messages('g-cloud-8', ['urls'])

    master_cl.load_manifest('g-cloud-9', 'services', 'edit_service')
    master_cl.load_manifest('g-cloud-9', 'services', 'edit_submission')
    master_cl.load_manifest('g-cloud-9', 'declaration', 'declaration')
    master_cl.load_messages('g-cloud-9', ['urls', 'advice'])

    master_cl.load_manifest('g-cloud-10', 'services', 'edit_service')
    master_cl.load_manifest('g-cloud-10', 'services', 'edit_submission')
    master_cl.load_manifest('g-cloud-10', 'declaration', 'declaration')
    master_cl.load_messages('g-cloud-10', ['urls', 'advice'])
    master_cl.load_metadata('g-cloud-10', ['copy_services'])

    master_cl.load_manifest('digital-outcomes-and-specialists-3', 'declaration', 'declaration')
    master_cl.load_manifest('digital-outcomes-and-specialists-3', 'services', 'edit_submission')
    master_cl.load_manifest('digital-outcomes-and-specialists-3', 'services', 'edit_service')
    master_cl.load_manifest('digital-outcomes-and-specialists-3', 'briefs', 'edit_brief')
    master_cl.load_messages('digital-outcomes-and-specialists-3', ['urls'])
    master_cl.load_metadata('digital-outcomes-and-specialists-3', ['copy_services', 'following_framework'])

    master_cl.load_manifest('g-cloud-11', 'services', 'edit_service')
    master_cl.load_manifest('g-cloud-11', 'services', 'edit_submission')
    master_cl.load_manifest('g-cloud-11', 'declaration', 'declaration')
    master_cl.load_messages('g-cloud-11', ['urls', 'advice'])
    master_cl.load_metadata('g-cloud-11', ['copy_services', 'following_framework'])

    master_cl.load_manifest('digital-outcomes-and-specialists-4', 'declaration', 'declaration')
    master_cl.load_manifest('digital-outcomes-and-specialists-4', 'services', 'edit_submission')
    master_cl.load_manifest('digital-outcomes-and-specialists-4', 'services', 'edit_service')
    master_cl.load_manifest('digital-outcomes-and-specialists-4', 'briefs', 'edit_brief')
    master_cl.load_messages('digital-outcomes-and-specialists-4', ['urls'])
    master_cl.load_metadata('digital-outcomes-and-specialists-4', ['copy_services', 'following_framework'])

    master_cl.load_manifest('g-cloud-12', 'services', 'edit_service')
    master_cl.load_manifest('g-cloud-12', 'services', 'edit_submission')
    master_cl.load_manifest('g-cloud-12', 'declaration', 'declaration')
    master_cl.load_messages('g-cloud-12', ['urls', 'advice', 'e-signature'])
    master_cl.load_metadata('g-cloud-12', ['copy_services', 'following_framework'])

    master_cl.load_manifest('digital-outcomes-and-specialists-5', 'declaration', 'declaration')
    master_cl.load_manifest('digital-outcomes-and-specialists-5', 'services', 'edit_submission')
    master_cl.load_manifest('digital-outcomes-and-specialists-5', 'services', 'edit_service')
    master_cl.load_manifest('digital-outcomes-and-specialists-5', 'briefs', 'edit_brief')
    master_cl.load_messages('digital-outcomes-and-specialists-5', ['urls', 'e-signature'])
    master_cl.load_metadata('digital-outcomes-and-specialists-5', ['copy_services', 'following_framework'])

    # seal master_cl in a closure by returning a function which will only ever return an independent copy of it
    return lambda: deepcopy(master_cl)


_content_loader_factory = _make_content_loader_factory()


@logged_duration(message="Spent {duration_real}s in get_content_loader")
def get_content_loader():
    if not hasattr(_local, "content_loader"):
        _local.content_loader = _content_loader_factory()
    return _local.content_loader


@logged_duration(message="Spent {duration_real}s in get_direct_plus_client")
def get_direct_plus_client():

    if not hasattr(_local, "direct_plus_client"):
        _local.direct_plus_client = DirectPlusClient(
            current_app.config['DM_DNB_API_USERNAME'],
            current_app.config['DM_DNB_API_PASSWORD']
        )
    return _local.direct_plus_client


content_loader = LocalProxy(get_content_loader)
direct_plus_client = LocalProxy(get_direct_plus_client)


@main.after_request
def add_cache_control(response):
    response.cache_control.no_cache = True
    return response


from .views import services, suppliers, login, frameworks, users
from . import errors
