#!/bin/sh

set -ex

cf target -o dto -s digital-marketplace
APP=${APP_GROUP}-green ./scripts/cf_ha_deploy.sh
APP=${APP_GROUP}-blue ./scripts/cf_ha_deploy.sh
