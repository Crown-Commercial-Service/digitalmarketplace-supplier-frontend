#!/bin/sh

set -e

npm run frontend-build:production 1>&2

# Non-Git paths that should be included when deploying
echo "app/static"
echo "app/templates/toolkit"
echo "app/templates/govuk"
echo "app/content"
