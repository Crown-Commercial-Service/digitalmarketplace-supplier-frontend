FROM digitalmarketplace/base-frontend:4.5.0

ONBUILD COPY supervisord.conf /etc/supervisord.conf
