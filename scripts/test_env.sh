#!/bin/bash

export DM_DATA_API_AUTH_TOKEN=${DM_DATA_API_AUTH_TOKEN:=myToken}
export DM_PASSWORD_SECRET_KEY=${DM_PASSWORD_SECRET_KEY:=not_very_secret}
export DM_SHARED_EMAIL_KEY=${DM_SHARED_EMAIL_KEY:=not_very_secret}
export DM_SUBMISSIONS_BUCKET=${DM_SUBMISSIONS_BUCKET:=digitalmarketplace-submissions-dev-dev}
export DM_COMMUNICATIONS_BUCKET=${DM_COMMUNICATIONS_BUCKET:=digitalmarketplace-communications-dev-dev}
export DM_ASSETS_URL=${DM_ASSETS_URL:=http://asset-host}

