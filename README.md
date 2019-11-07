# Digital Marketplace Supplier frontend

[![Build Status](https://travis-ci.org/alphagov/digitalmarketplace-supplier-frontend.svg)](https://travis-ci.org/alphagov/digitalmarketplace-supplier-frontend)
[![Coverage Status](https://coveralls.io/repos/alphagov/digitalmarketplace-supplier-frontend/badge.svg?branch=master&service=github)](https://coveralls.io/github/alphagov/digitalmarketplace-supplier-frontend?branch=master)
[![Requirements Status](https://requires.io/github/alphagov/digitalmarketplace-supplier-frontend/requirements.svg?branch=master)](https://requires.io/github/alphagov/digitalmarketplace-supplier-frontend/requirements/?branch=master)
![Python 3.6](https://img.shields.io/badge/python-3.6-blue.svg)

Frontend supplier application for the digital marketplace.

- Python app, based on the [Flask framework](http://flask.pocoo.org/)

## Quickstart

Install dependencies, build assets and run the app
```
make run-all
```

Debian (jessie) users will need `libxslt1-dev` and `libxml2-dev` installed for `requirements-dev`.

## Full setup

Create a virtual environment
 ```
 python3 -m venv ./venv
 ```

### Activate the virtual environment

```
source ./venv/bin/activate
```

### Upgrade dependencies

Install new Python dependencies with pip

```make requirements-dev```


## Front-end

Front-end code (both development and production) is compiled using [Node](http://nodejs.org/) and [Gulp](http://gulpjs.com/).

### Requirements

You need Node (try to install the version we use in production -
 see the [base docker image](https://github.com/alphagov/digitalmarketplace-docker-base/blob/master/base.docker)).

To check the version you're running, type:

```
node --version
```

## Frontend tasks

[NPM](https://docs.npmjs.com/cli/run-script) is used for all frontend build tasks. The commands available are:

- `npm run frontend-build:development` (compile the frontend files for development)
- `npm run frontend-build:production` (compile the frontend files for production)
- `npm run frontend-build:watch` (watch all frontend files & rebuild when anything changes)




### Run the tests

To run the whole testsuite:

```
make test
```

To test individual parts of the test stack use the `test_flake8`, `test_python`
or `test-javascript` targets.

eg.
```
make test-javascript
```

### Run the development server

To run the Supplier Frontend App for local development use the `run-all` target.
This will install requirements, build assets and run the app.

```
make run-all
```

To just run the application use the `run-app` target.

Use the app at http://127.0.0.1:5003/suppliers.

When using the development server the supplier frontend listens on port 5003 by default.

Note: The login is located in the user frontend application, so this needs to be running as well to login as a supplier.

If the application is running on port 5003 as described above, login from
http://127.0.0.1:5007/login (user frontend) as a supplier and then you will be
logged in as a supplier on http://127.0.0.1:5003/suppliers.

It is easier to use the apps if nginx is configured to run them through one port.
As described in the Digital Marketplace manual section on [accessing frontend
applications as a single website][manual-nginx]:

> The frontend applications are hyperlinked together but are running on
> different ports. This can cause links to error when they link between
> different applications. The way around this is to set up nginx so all front
> end applications can be accessed through port 80.

The easiest way to do this is to use [`dmrunner`](https://github.com/alphagov/digitalmarketplace-runner).

In this case all the frontend applications will available from port 80 (usually
aliased to localhost) and the supplier frontend can be accessed from
http://localhost/suppliers.

[manual-nginx]: https://alphagov.github.io/digitalmarketplace-manual/developing-the-digital-marketplace/developer-setup.html#accessing-frontend-applications-as-a-single-website

### Updating application dependencies

`requirements.txt` file is generated from the `requirements-app.txt` in order to pin
versions of all nested dependecies. If `requirements-app.txt` has been changed (or
we want to update the unpinned nested dependencies) `requirements.txt` should be
regenerated with

```
make freeze-requirements
```

`requirements.txt` should be commited alongside `requirements-app.txt` changes.

### Configuring boto

[boto](https://github.com/boto/boto) provides a Python interface to Amazon Web Services; it's what we're using to download from and upload to our s3 buckets.

If you don't [configure your AWS credentials correctly](http://boto.readthedocs.org/en/latest/boto_config_tut.html?highlight=~/.aws/credentials#credentials)
on your local machine, you'll probably run into a nasty-looking `boto.exception.NoAuthHandlerFound` page at some point.

The short version is that you should create an `~/.aws/credentials` file formatted like so:
```bash
[default]
aws_access_key_id = ...
aws_secret_access_key = ...
```

AWS access keys can be found/configured in the Identity and Access Management (IAM) section of the
[digitalmarketplace-development AWS console](https://digitalmarketplace-development.signin.aws.amazon.com/console).


#### Troubleshooting

If you're experiencing problems connecting, make sure to `unset` any `env` variables used by boto (e.g. `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_SECURITY_TOKEN` and `AWS_PROFILE`) as they may be overriding the values in your credentials file.
