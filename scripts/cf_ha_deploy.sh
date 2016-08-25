#!/bin/sh

set -ex

# Static files are being served on /marketplace for both deployments because we
# only have one static file build.  This means an extra route is needed for now.
# After the URL migration is done, it should be possible to move the static
# files to somewhere more sensible and then remove this extra route.

cf unmap-route "$APP" "$DOMAIN" --hostname "$HOSTNAME" --path "$URL_PREFIX"/suppliers
cf unmap-route "$APP" "$DOMAIN" --hostname "$HOSTNAME" --path /marketplace/suppliers/static
cf push "$APP" -f "$MANIFEST"
cf map-route "$APP" "$DOMAIN" --hostname "$HOSTNAME" --path "$URL_PREFIX"/suppliers
cf map-route "$APP" "$DOMAIN" --hostname "$HOSTNAME" --path /marketplace/suppliers/static
