#!/usr/bin/env python

import os
import re
from app import create_app
from flask.ext.script import Manager, Server

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
