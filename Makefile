SHELL := /bin/bash

run_all: requirements frontend_build run_app

run_app: virtualenv
	python application.py runserver

virtualenv:
	[ -z $$VIRTUAL_ENV ] && virtualenv venv || true

requirements: virtualenv requirements.txt
	pip install -r requirements.txt

requirements_for_test: virtualenv requirements_for_test.txt
	pip install -r requirements_for_test.txt

frontend_build:
	npm run --silent frontend-build:production

test: test_pep8 test_python test_javascript

test_pep8: virtualenv
	pep8 .

test_python: virtualenv
	py.test ${PYTEST_ARGS}

test_javascript: frontend_build
	npm test

.PHONY: run_all run_app virtualenv requirements requirements_for_test frontend_build test test_pep8 test_python test_javascript
