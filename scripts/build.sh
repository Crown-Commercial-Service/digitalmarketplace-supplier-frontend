#!/bin/sh

set -e

yarn run frontend-build:production 1>&2

# Non-Git paths that should be included when deploying
echo "app/static"
echo "app/templates/toolkit"
echo "app/templates/govuk"
echo "app/content"

cp nosigterm.py /bin/nosigterm
chmod +x /bin/nosigterm

cp run_nginx.sh /nginx.sh
chmod +x /nginx.sh

cp supervisord.conf /etc/supervisord.conf
