#!/bin/sh

set -ex

cf unmap-route "$APP" "$DOMAIN" --hostname "$HOSTNAME" --path /sellers
cf push "$APP" -f "$MANIFEST"
cf map-route "$APP" "$DOMAIN" --hostname "$HOSTNAME" --path /sellers
