#!/bin/bash

export DM_DATA_API_AUTH_TOKEN=${DM_DATA_API_AUTH_TOKEN:=myToken}
export DM_PASSWORD_SECRET_KEY=${DM_PASSWORD_SECRET_KEY:=not_very_secret}
export DM_SHARED_EMAIL_KEY=${DM_SHARED_EMAIL_KEY:=not_very_secret}
export DM_G7_DRAFT_DOCUMENTS_URL=${DM_S3_DOCUMENTS_URL:=http://localhost}

