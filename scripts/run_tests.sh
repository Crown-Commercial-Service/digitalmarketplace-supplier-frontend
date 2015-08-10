#!/bin/bash
#
# Run project tests
#
# NOTE: This script expects to be run from the project root with
# ./scripts/run_tests.sh

# Use default environment vars for localhost if not already set
export DM_DATA_API_AUTH_TOKEN=${DM_DATA_API_AUTH_TOKEN:=myToken}
export DM_PASSWORD_SECRET_KEY=${DM_PASSWORD_SECRET_KEY:=not_very_secret}

export DM_G7_DRAFT_DOCUMENTS_URL=${DM_S3_DOCUMENTS_URL:=http://localhost}

echo "Environment variables in use:"
env | grep DM_

set -o pipefail

function display_result {
  RESULT=$1
  EXIT_STATUS=$2
  TEST=$3

  if [ $RESULT -ne 0 ]; then
    echo -e "\033[31m$TEST failed\033[0m"
    exit $EXIT_STATUS
  else
    echo -e "\033[32m$TEST passed\033[0m"
  fi
}

npm run --silent frontend-build:production
display_result $? 1 "Build of front end static assets"

pep8 .
display_result $? 2 "Code style check"

nosetests -v -s --with-doctest
display_result $? 3 "Unit tests"
