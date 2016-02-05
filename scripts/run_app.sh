#!/bin/bash

if [ -n "$VIRTUAL_ENV" ]; then
  echo "Already in virtual environment $VIRTUAL_ENV"
else
  source ./venv/bin/activate 2>/dev/null && echo "Virtual environment activated."
fi

# Build front-end static assets
npm run frontend-build:production
echo ""

python application.py runserver $@
