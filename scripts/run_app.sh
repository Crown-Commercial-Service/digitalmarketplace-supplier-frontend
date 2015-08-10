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

export DM_G7_DRAFT_DOCUMENTS_BUCKET=${DM_S3_DOCUMENTS_BUCKET:=digitalmarketplace-dev-documents}
export DM_G7_DRAFT_DOCUMENTS_URL=${DM_S3_DOCUMENTS_URL:=https://${DM_S3_DOCUMENTS_BUCKET}.s3-eu-west-1.amazonaws.com}

export DM_MANDRILL_API_KEY=${DM_MANDRILL_API_KEY:=not_a_real_key}
export DM_PASSWORD_SECRET_KEY=${DM_PASSWORD_SECRET_KEY:=verySecretKey}

echo "Environment variables in use:"
env | grep DM_

python application.py runserver $@
