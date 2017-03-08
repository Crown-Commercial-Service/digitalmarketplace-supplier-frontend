#!/usr/bin/env python

import os
from app import create_app
from dmutils import init_manager

application = create_app(
    os.getenv('DM_ENVIRONMENT') or 'development'
)
application.jinja_options = {
    'extensions': [
        'jinja2.ext.with_'
    ]
}

manager = init_manager(application, 5003, ['./app/content/frameworks'])

if __name__ == '__main__':
    manager.run()
