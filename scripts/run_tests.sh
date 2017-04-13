#!/bin/sh
set -xe
pep8 --version
pep8 app
pep8 tests
py.test