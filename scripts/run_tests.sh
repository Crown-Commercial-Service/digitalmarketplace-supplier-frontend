#!/bin/sh
set -xe
pip install pep8
pep8 --version
pep8 app
pep8 tests
py.test
