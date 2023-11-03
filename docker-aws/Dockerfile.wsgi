FROM mcbhenwood/dmp-http-buildstatic as buildstatic

FROM mcbhenwood/dmp-wsgi
COPY --from=buildstatic ${APP_DIR}/node_modules/digitalmarketplace-govuk-frontend ${APP_DIR}/node_modules/digitalmarketplace-govuk-frontend
COPY --from=buildstatic ${APP_DIR}/node_modules/govuk-frontend ${APP_DIR}/node_modules/govuk-frontend
COPY --from=buildstatic ${APP_DIR}/app/content ${APP_DIR}/app/content
COPY --from=buildstatic ${APP_DIR}/app/static ${APP_DIR}/app/static
