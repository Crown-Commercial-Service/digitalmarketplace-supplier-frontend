#!/usr/bin/python

from os import environ
from os.path import isfile

if environ.get("PROXY_AUTH_CREDENTIALS"):
    with open("/etc/nginx/.htpasswd", "w") as f:
        f.seek(0, 2)
        f.write("\n")
        f.write(environ["PROXY_AUTH_CREDENTIALS"])

with open("/etc/nginx/nginx.conf", "r+") as f:
    contents = f.read()
    contents.replace("{DM_APP_NAME}", environ.get("DM_APP_NAME"))
    f.seek(0)
    f.write(contents)

if isfile("/etc/nginx/sites-enabled/api"):
    with open("/etc/nginx/sites-enabled/api", "r+") as f:
        contents = f.read()
        contents.replace("{PORT}", environ.get("PORT", ""))
        f.seek(0)
        f.write(contents)

if isfile("/etc/nginx/sites-enabled/frontend"):
    with open("/etc/nginx/sites-enabled/frontend", "r+") as f:
        contents = f.read()
        contents.replace("{PORT}", environ.get("PORT", ""))
        f.seek(0)
        f.write(contents)

import signal
from os import execv
from sys import argv

signal.signal(signal.SIGTERM, signal.SIG_IGN)
execv("/usr/sbin/nginx", argv)
