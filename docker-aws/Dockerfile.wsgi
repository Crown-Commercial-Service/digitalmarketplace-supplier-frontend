# Base builds are defined in https://github.com/Crown-Commercial-Service/ccs-digitalmarketplace-aws-docker-base
FROM 473251818902.dkr.ecr.eu-west-2.amazonaws.com/dmp-base-http-buildstatic:1.0.0 as buildstatic
COPY . ${APP_DIR}
RUN ./scripts/build.sh

FROM 473251818902.dkr.ecr.eu-west-2.amazonaws.com/dmp-base-wsgi:1.0.0
COPY --from=buildstatic ${APP_DIR}/node_modules/digitalmarketplace-govuk-frontend ${APP_DIR}/node_modules/digitalmarketplace-govuk-frontend
COPY --from=buildstatic ${APP_DIR}/node_modules/govuk-frontend ${APP_DIR}/node_modules/govuk-frontend
COPY --from=buildstatic ${APP_DIR}/app/content ${APP_DIR}/app/content
COPY --from=buildstatic ${APP_DIR}/app/templates/toolkit ${APP_DIR}/app/templates/toolkit
COPY --from=buildstatic ${APP_DIR}/app/static ${APP_DIR}/app/static
