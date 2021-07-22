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


def _load_dos(primary_cl):
    primary_cl.lazy_load_manifests(
        'digital-outcomes-and-specialists',
        {
            'declaration': 'declaration',
            'edit_submission': 'services',
            'edit_brief': 'briefs',
        },
    )
    primary_cl.load_messages('digital-outcomes-and-specialists', ['urls'])

    primary_cl.lazy_load_manifests(
        'digital-outcomes-and-specialists-2',
        {
            'declaration': 'declaration',
            'edit_submission': 'services',
            'edit_service': 'services',
            'edit_brief': 'briefs',
        },
    )
    primary_cl.load_messages('digital-outcomes-and-specialists-2', ['urls'])

    primary_cl.lazy_load_manifests(
        'digital-outcomes-and-specialists-3',
        {
            'declaration': 'declaration',
            'edit_submission': 'services',
            'edit_service': 'services',
            'edit_brief': 'briefs',
        },
    )
    primary_cl.load_messages('digital-outcomes-and-specialists-3', ['urls'])
    primary_cl.load_metadata('digital-outcomes-and-specialists-3', ['copy_services', 'following_framework'])

    primary_cl.lazy_load_manifests(
        'digital-outcomes-and-specialists-4',
        {
            'declaration': 'declaration',
            'edit_submission': 'services',
            'edit_service': 'services',
            'edit_brief': 'briefs',
        },
    )
    primary_cl.load_messages('digital-outcomes-and-specialists-4', ['urls'])
    primary_cl.load_metadata('digital-outcomes-and-specialists-4', ['copy_services', 'following_framework'])

    primary_cl.load_manifest('digital-outcomes-and-specialists-5', 'declaration', 'declaration')
    primary_cl.load_manifest('digital-outcomes-and-specialists-5', 'services', 'edit_submission')
    primary_cl.load_manifest('digital-outcomes-and-specialists-5', 'services', 'edit_service')
    primary_cl.load_manifest('digital-outcomes-and-specialists-5', 'briefs', 'edit_brief')
    primary_cl.load_messages('digital-outcomes-and-specialists-5', ['urls', 'e-signature'])
    primary_cl.load_metadata('digital-outcomes-and-specialists-5', ['copy_services', 'following_framework'])


def _load_g_cloud(primary_cl):
    primary_cl.lazy_load_manifests(
        'g-cloud-6',
        {
            'edit_service': 'services',
        },
    )
    primary_cl.load_messages('g-cloud-6', ['urls'])

    primary_cl.lazy_load_manifests(
        'g-cloud-7',
        {
            'edit_service': 'services',
            'edit_submission': 'services',
            'declaration': 'declaration',
        },
    )
    primary_cl.load_messages('g-cloud-7', ['urls'])

    primary_cl.lazy_load_manifests(
        'g-cloud-8',
        {
            'edit_service': 'services',
            'edit_submission': 'services',
            'declaration': 'declaration',
        },
    )
    primary_cl.load_messages('g-cloud-8', ['urls'])

    primary_cl.lazy_load_manifests(
        'g-cloud-9',
        {
            'edit_service': 'services',
            'edit_submission': 'services',
            'declaration': 'declaration',
        },
    )
    primary_cl.load_messages('g-cloud-9', ['urls', 'advice'])

    primary_cl.lazy_load_manifests(
        'g-cloud-10',
        {
            'edit_service': 'services',
            'edit_submission': 'services',
            'declaration': 'declaration',
        },
    )
    primary_cl.load_messages('g-cloud-10', ['urls', 'advice'])
    primary_cl.load_metadata('g-cloud-10', ['copy_services'])

    primary_cl.lazy_load_manifests(
        'g-cloud-11',
        {
            'edit_service': 'services',
            'edit_submission': 'services',
            'declaration': 'declaration',
        },
    )
    primary_cl.load_messages('g-cloud-11', ['urls', 'advice'])
    primary_cl.load_metadata('g-cloud-11', ['copy_services', 'following_framework'])

    primary_cl.load_manifest('g-cloud-12', 'services', 'edit_service')
    primary_cl.load_manifest('g-cloud-12', 'services', 'edit_submission')
    primary_cl.load_manifest('g-cloud-12', 'declaration', 'declaration')
    primary_cl.load_messages('g-cloud-12', ['urls', 'advice', 'e-signature'])
    primary_cl.load_metadata('g-cloud-12', ['copy_services', 'following_framework'])

    primary_cl.load_manifest('g-cloud-13', 'services', 'edit_service')
    primary_cl.load_manifest('g-cloud-13', 'services', 'edit_submission')
    primary_cl.load_manifest('g-cloud-13', 'declaration', 'declaration')
    primary_cl.load_messages('g-cloud-13', ['urls', 'advice', 'e-signature'])
    primary_cl.load_metadata('g-cloud-13', ['copy_services', 'following_framework'])


def _make_content_loader_factory():
    primary_cl = ContentLoader('app/content')

    _load_dos(primary_cl)
    _load_g_cloud(primary_cl)

    # seal primary_cl in a closure by returning a function which will only ever return an independent copy of it
    return lambda: deepcopy(primary_cl)


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
