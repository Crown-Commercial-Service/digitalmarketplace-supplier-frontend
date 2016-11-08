SHELL := /bin/bash
VIRTUALENV_ROOT := $(shell [ -z $$VIRTUAL_ENV ] && echo $$(pwd)/venv || echo $$VIRTUAL_ENV)
DM_ENVIRONMENT ?= development

ifeq ($(DM_ENVIRONMENT),development)
	GULP_ENVIRONMENT := development
else
	GULP_ENVIRONMENT := production
endif

run_all: requirements frontend_build run_app

run_app: show_environment virtualenv
	python application.py runserver

virtualenv:
	[ -z $$VIRTUAL_ENV ] && [ ! -d venv ] && virtualenv venv || true

requirements: virtualenv requirements.txt
	${VIRTUALENV_ROOT}/bin/pip install -r requirements.txt

requirements_for_test: virtualenv requirements_for_test.txt
	${VIRTUALENV_ROOT}/bin/pip install -r requirements_for_test.txt

npm_install: package.json
	npm install

frontend_build:
	npm run --silent frontend-build:${GULP_ENVIRONMENT}

test: show_environment test_pep8 test_python test_javascript

test_pep8: virtualenv
	${VIRTUALENV_ROOT}/bin/pep8 .

test_python: virtualenv
	${VIRTUALENV_ROOT}/bin/py.test ${PYTEST_ARGS}

test_javascript: frontend_build
	npm test

show_environment:
	@echo "Environment variables in use:"
	@env | grep DM_ || true

.PHONY: run_all run_app virtualenv requirements requirements_for_test npm_build frontend_build test test_pep8 test_python test_javascript show_environment
