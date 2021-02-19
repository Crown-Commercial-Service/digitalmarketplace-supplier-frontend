import collections
import os
from copy import deepcopy
from functools import partial
from typing import Dict

from dmcontent.errors import ContentNotFoundError
from flask import Blueprint, current_app
from werkzeug.local import Local, LocalProxy

from dmutils.direct_plus_client import DirectPlusClient

from dmcontent.content_loader import ContentLoader, read_yaml

from dmutils.timing import logged_duration

main = Blueprint('main', __name__)

# we use our own Local for objects we explicitly want to be able to retain between requests but shouldn't
# share a common object between concurrent threads/contexts
_local = Local()


class LazyDict(collections.MutableMapping):
    """
    A dictionary for values that will be lazily evaluated the first time they are requested.

    If a value is callable, then it will be called the first time that value is requested and the result cached.
    """
    def __init__(self, *args, **kw):
        self._raw_dict = dict(*args, **kw)

    def __getitem__(self, key):
        if key in self._raw_dict and callable(self._raw_dict.get(key)):
            self._raw_dict[key] = self._raw_dict[key]()

        return self._raw_dict.__getitem__(key)

    def __iter__(self):
        return iter(self._raw_dict)

    def __len__(self):
        return len(self._raw_dict)

    def __setitem__(self, key, value):
        self._raw_dict.__setitem__(key, value)

    def __delitem__(self, value):
        self._raw_dict.__delitem__(value)


class LazyContentLoader(ContentLoader):
    def lazy_load_manifests(
        self, framework_slug: str, manifests_to_question_sets: Dict[str, str]
    ):
        """
        Lazily load all the manifests for a framework. Cannot be mixed with `load_manifest`.

        Use this for framework manifests that users are unlikely to use. Loading lazily reduces application startup time
        by ~1s for each manifest, but will slow down the first user request to access this manifest by ~1s.
        """
        if self._content[framework_slug]:
            raise ValueError(f"Manifests already loaded for {framework_slug}")

        self._content[framework_slug] = LazyDict(
            {
                manifest: partial(
                    self.generate_manifest, framework_slug, question_set, manifest
                )
                for (manifest, question_set) in manifests_to_question_sets.items()
            }
        )

    def generate_manifest(self, framework_slug, question_set, manifest):
        manifest_path = os.path.join(
            self._root_path(framework_slug), 'manifests', '{}.yml'.format(manifest)
        )
        try:
            manifest_sections = read_yaml(manifest_path)
        except IOError:
            raise ContentNotFoundError("No manifest at {}".format(manifest_path))

        return [
            self._process_section(framework_slug, question_set, section)
            for section in manifest_sections
        ]


def _make_content_loader_factory():
    master_cl = LazyContentLoader('app/content')
    master_cl.lazy_load_manifests('g-cloud-6', {'edit_service': 'services'})
    master_cl.load_messages('g-cloud-6', ['urls'])

    master_cl.lazy_load_manifests(
        'g-cloud-7',
        {
            'edit_service': 'services',
            'edit_submission': 'services',
            'declaration': 'declaration',
        },
    )
    master_cl.load_messages('g-cloud-7', ['urls'])

    master_cl.lazy_load_manifests(
        'digital-outcomes-and-specialists',
        {
            'declaration': 'declaration',
            'edit_submission': 'services',
            'edit_brief': 'briefs',
        },
    )
    master_cl.load_messages('digital-outcomes-and-specialists', ['urls'])

    master_cl.lazy_load_manifests(
        'digital-outcomes-and-specialists-2',
        {
            'declaration': 'declaration',
            'edit_submission': 'services',
            'edit_service': 'services',
            'edit_brief': 'briefs',
        },
    )
    master_cl.load_messages('digital-outcomes-and-specialists-2', ['urls'])

    master_cl.lazy_load_manifests(
        'g-cloud-8',
        {
            'edit_service': 'services',
            'edit_submission': 'services',
            'declaration': 'declaration',
        },
    )
    master_cl.load_messages('g-cloud-8', ['urls'])

    master_cl.lazy_load_manifests(
        'g-cloud-9',
        {
            'edit_service': 'services',
            'edit_submission': 'services',
            'declaration': 'declaration',
        },
    )
    master_cl.load_messages('g-cloud-9', ['urls', 'advice'])

    master_cl.lazy_load_manifests(
        'g-cloud-10',
        {
            'edit_service': 'services',
            'edit_submission': 'services',
            'declaration': 'declaration',
        },
    )
    master_cl.load_messages('g-cloud-10', ['urls', 'advice'])
    master_cl.load_metadata('g-cloud-10', ['copy_services'])

    master_cl.lazy_load_manifests(
        'digital-outcomes-and-specialists-3',
        {
            'declaration': 'declaration',
            'edit_submission': 'services',
            'edit_service': 'services',
            'edit_brief': 'briefs',
        },
    )
    master_cl.load_messages('digital-outcomes-and-specialists-3', ['urls'])
    master_cl.load_metadata(
        'digital-outcomes-and-specialists-3', ['copy_services', 'following_framework']
    )

    master_cl.lazy_load_manifests(
        'g-cloud-11',
        {
            'edit_service': 'services',
            'edit_submission': 'services',
            'declaration': 'declaration',
        },
    )
    master_cl.load_messages('g-cloud-11', ['urls', 'advice'])
    master_cl.load_metadata('g-cloud-11', ['copy_services', 'following_framework'])

    master_cl.lazy_load_manifests(
        'digital-outcomes-and-specialists-4',
        {
            'declaration': 'declaration',
            'edit_submission': 'services',
            'edit_service': 'services',
            'edit_brief': 'briefs',
        },
    )
    master_cl.load_messages('digital-outcomes-and-specialists-4', ['urls'])
    master_cl.load_metadata(
        'digital-outcomes-and-specialists-4', ['copy_services', 'following_framework']
    )

    master_cl.load_manifest('g-cloud-12', 'services', 'edit_service')
    master_cl.load_manifest('g-cloud-12', 'services', 'edit_submission')
    master_cl.load_manifest('g-cloud-12', 'declaration', 'declaration')
    master_cl.load_messages('g-cloud-12', ['urls', 'advice', 'e-signature'])
    master_cl.load_metadata('g-cloud-12', ['copy_services', 'following_framework'])

    master_cl.load_manifest(
        'digital-outcomes-and-specialists-5', 'declaration', 'declaration'
    )
    master_cl.load_manifest(
        'digital-outcomes-and-specialists-5', 'services', 'edit_submission'
    )
    master_cl.load_manifest(
        'digital-outcomes-and-specialists-5', 'services', 'edit_service'
    )
    master_cl.load_manifest(
        'digital-outcomes-and-specialists-5', 'briefs', 'edit_brief'
    )
    master_cl.load_messages(
        'digital-outcomes-and-specialists-5', ['urls', 'e-signature']
    )
    master_cl.load_metadata(
        'digital-outcomes-and-specialists-5', ['copy_services', 'following_framework']
    )

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
            current_app.config['DM_DNB_API_PASSWORD'],
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
