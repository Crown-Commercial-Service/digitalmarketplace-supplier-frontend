#!/bin/sh

set -e

yarn run frontend-build:production 1>&2

# Non-Git paths that should be included when deploying
echo "app/static"
echo "app/templates/toolkit"
echo "app/templates/govuk"
echo "app/content"

cp supervisord.conf /etc/supervisord.conf
cp uwsgi.py /bin/uwsgi
chmod +x /bin/uwsgi
cp run_nginx.py /nginx.py
chmod +x /nginx.py
