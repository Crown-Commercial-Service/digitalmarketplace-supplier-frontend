#!/bin/bash
if [ -n "$VIRTUAL_ENV" ]; then
  echo "Already in virtual environment $VIRTUAL_ENV"
else
  source ./venv/bin/activate 2>/dev/null && echo "Virtual environment activated."
fi

# Use default environment vars for localhost if not already set
export DM_SUPPLIER_FRONTEND_API_AUTH_TOKEN=${DM_SUPPLIER_FRONTEND_API_AUTH_TOKEN:=myToken}
export DM_API_URL=${DM_API_URL:=http://localhost:5000}
export DM_API_AUTH_TOKEN=${DM_API_AUTH_TOKEN:=myToken}
export DM_MANDRILL_API_KEY=${DM_MANDRILL_API_KEY:=not_a_real_key}
export DM_PASSWORD_SECRET_KEY=${DM_PASSWORD_SECRET_KEY:=verySecretKey}
export DM_RESET_PASSWORD_SALT=${DM_RESET_PASSWORD_SALT:=resetSalt}

echo "Environment variables in use:"
env | grep DM_

python application.py runserver
