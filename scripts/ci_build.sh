#!/bin/sh

npm install
pip install -U pip
pip install -r -U requirements.txt
npm run frontend-build:production
git log --pretty=format:'%h' -n 1 > version_label
