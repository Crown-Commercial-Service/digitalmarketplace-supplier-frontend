#!/bin/sh

set -e

yarn run frontend-build:production 1>&2

# Non-Git paths that should be included when deploying
echo "app/static"
echo "app/templates/toolkit"
echo "app/templates/govuk"
echo "app/content"

cp supervisord.conf /etc/supervisord.conf
cp run_awslogs.sh /awslogs.sh
chmod +x /awslogs.sh
