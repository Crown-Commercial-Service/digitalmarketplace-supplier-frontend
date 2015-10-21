#!/usr/bin/env python

import os
import re
from app import create_app
from flask.ext.script import Manager, Server as _Server


def extra_files():
    for dirname, dirs, files in os.walk('./app/content'):
        for filename in files:
            filename = os.path.join(dirname, filename)
            if os.path.isfile(filename):
                print(filename)
                yield filename


class Server(_Server):
    def __init__(self, *args, **kwargs):
        if kwargs.get('use_reloader', True):
            kwargs.setdefault('extra_files', []).extend(extra_files())
        super(Server, self).__init__(*args, **kwargs)

application = create_app(
    os.getenv('DM_ENVIRONMENT') or 'development'
)
application.jinja_options = {
    'extensions': [
        'jinja2.ext.with_'
    ]
}

manager = Manager(application)
manager.add_command("runserver", Server(port=5003))

if __name__ == '__main__':
    manager.run()
