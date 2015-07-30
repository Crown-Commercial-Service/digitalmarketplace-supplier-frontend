#!/usr/bin/env python

import os
from app import create_app
from flask.ext.script import Manager, Server

port = int(os.environ.get('PORT', 5002))

application = create_app(
    os.getenv('DM_ENVIRONMENT') or 'development'
)
application.jinja_options = {
    'extensions': [
        'jinja2.ext.with_'
    ]
}

manager = Manager(application)

manager.add_command("runserver", Server(host='0.0.0.0', port=port))

if __name__ == '__main__':
    manager.run()
