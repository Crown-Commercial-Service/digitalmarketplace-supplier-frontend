#!/bin/sh
set -xe
npm install
./node_modules/.bin/pancake
pip install -U pip
pip install -U -r requirements.txt
npm run frontend-build:production
git log --pretty=format:'%h' -n 1 > version_label
