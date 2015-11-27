#!/bin/bash

if [ -n "$VIRTUAL_ENV" ]; then
  echo "Already in virtual environment $VIRTUAL_ENV"
else
  source ./venv/bin/activate 2>/dev/null && echo "Virtual environment activated."
fi

# Use default environment vars for localhost if not already set
export DM_DATA_API_URL=${DM_DATA_API_URL:=http://localhost:5000}
export DM_DATA_API_AUTH_TOKEN=${DM_DATA_API_AUTH_TOKEN:=myToken}
export DM_API_AUTH_TOKEN=${DM_API_AUTH_TOKEN:=myToken}

export DM_SUBMISSIONS_BUCKET=${DM_SUBMISSIONS_BUCKET:=digitalmarketplace-documents-dev-dev}
export DM_COMMUNICATIONS_BUCKET=${DM_COMMUNICATIONS_BUCKET:=digitalmarketplace-communications-dev-dev}
export DM_ASSETS_URL=${DM_ASSETS_URL:=http://asset-host}

export DM_MANDRILL_API_KEY=${DM_MANDRILL_API_KEY:=not_a_real_key}
export DM_PASSWORD_SECRET_KEY=${DM_PASSWORD_SECRET_KEY:=verySecretKey}
export DM_SHARED_EMAIL_KEY=${DM_SHARED_EMAIL_KEY:=very_secret}

echo "Environment variables in use:"
env | grep DM_

python application.py runserver $@
