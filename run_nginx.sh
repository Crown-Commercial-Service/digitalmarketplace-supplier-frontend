#!/bin/sh

if [ "${DM_APP_NAME}x" = "x" ]; then
 >&2 echo 'envvar DM_APP_NAME not set'
 exit 2
fi
if [ "${PORT}x" = "x" ]; then
  >&2 echo 'envvar PORT not set'
  exit 2
fi

# PROXY_AUTH_CREDENTIALS only set for frontend apps
if [ ! "${PROXY_AUTH_CREDENTIALS}x" = "x" ]; then
  echo "${PROXY_AUTH_CREDENTIALS}" >> /etc/nginx/.htpasswd
fi

sed -i "s/{DM_APP_NAME}/$DM_APP_NAME/g" /etc/nginx/nginx.conf
[ -f /etc/nginx/sites-enabled/api ] && sed -i "s/{PORT}/$PORT/g" /etc/nginx/sites-enabled/api
[ -f /etc/nginx/sites-enabled/frontend ] && sed -i "s/{PORT}/$PORT/g" /etc/nginx/sites-enabled/frontend

exec nosigterm /usr/sbin/nginx
