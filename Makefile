SHELL := /bin/bash
VIRTUALENV_ROOT := $(shell [ -z $$VIRTUAL_ENV ] && echo $$(pwd)/venv || echo $$VIRTUAL_ENV)
DM_ENVIRONMENT ?= development

ifeq ($(DM_ENVIRONMENT),development)
	GULP_ENVIRONMENT := development
else
	GULP_ENVIRONMENT := production
endif

.PHONY: run-all
run-all: requirements npm-install frontend-build run-app

.PHONY: run-app
run-app: show-environment virtualenv
	${VIRTUALENV_ROOT}/bin/flask run

.PHONY: virtualenv
virtualenv:
	[ -z $$VIRTUAL_ENV ] && [ ! -d venv ] && python3 -m venv venv || true

.PHONY: upgrade-pip
upgrade-pip: virtualenv
	${VIRTUALENV_ROOT}/bin/pip install --upgrade pip

.PHONY: requirements
requirements: virtualenv upgrade-pip requirements.txt
	${VIRTUALENV_ROOT}/bin/pip install -r requirements.txt

.PHONY: requirements-dev
requirements-dev: virtualenv upgrade-pip requirements.txt requirements-dev.txt
	${VIRTUALENV_ROOT}/bin/pip install -r requirements.txt -r requirements-dev.txt

.PHONY: freeze-requirements
freeze-requirements: virtualenv requirements-dev requirements.in requirements-dev.in
	${VIRTUALENV_ROOT}/bin/pip-compile requirements.in
	${VIRTUALENV_ROOT}/bin/pip-compile requirements-dev.in

.PHONY: npm-install
npm-install:
	npm ci # If dependencies in the package lock do not match those in package.json, npm ci will exit with an error, instead of updating the package lock. (https://docs.npmjs.com/cli/ci.html)

.PHONY: frontend-build
frontend-build: npm-install
	npm run --silent frontend-build:${GULP_ENVIRONMENT}

.PHONY: test
test: show-environment frontend-build test-flake8 test-mypy test-python test-javascript

.PHONY: test-flake8
test-flake8: virtualenv requirements-dev
	${VIRTUALENV_ROOT}/bin/flake8 .

.PHONY: test-mypy
test-mypy: virtualenv requirements-dev
	${VIRTUALENV_ROOT}/bin/mypy app/

.PHONY: test-python
test-python: virtualenv requirements-dev
	${VIRTUALENV_ROOT}/bin/py.test ${PYTEST_ARGS}

.PHONY: test-javascript
test-javascript: frontend-build
	npm test

.PHONY: show-environment
show-environment:
	@echo "Environment variables in use:"
	@env | grep DM_ || true

.PHONY: docker-build
docker-build:
	$(if ${RELEASE_NAME},,$(eval export RELEASE_NAME=$(shell git describe)))
	@echo "Building a docker image for ${RELEASE_NAME}..."
	docker build -t digitalmarketplace/supplier-frontend --build-arg release_name=${RELEASE_NAME} .
	docker tag digitalmarketplace/supplier-frontend digitalmarketplace/supplier-frontend:${RELEASE_NAME}

.PHONY: docker-push
docker-push:
	$(if ${RELEASE_NAME},,$(eval export RELEASE_NAME=$(shell git describe)))
	docker push digitalmarketplace/supplier-frontend:${RELEASE_NAME}
