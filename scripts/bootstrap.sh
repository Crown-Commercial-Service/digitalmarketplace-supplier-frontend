#!/bin/bash
#
# Bootstrap virtualenv environment and postgres databases locally.
#
# NOTE: This script expects to be run from the project root with
# ./scripts/bootstrap.sh

set -o pipefail

if [ ! $VIRTUAL_ENV ]; then
  virtualenv ./venv
  . ./venv/bin/activate
fi

# Install Python development dependencies
pip install -r requirements_for_test.txt

npm install
npm run frontend-build:development