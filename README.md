# Digital Marketplace supplier frontend

[![Build Status](https://travis-ci.org/alphagov/digitalmarketplace-supplier-frontend.svg)](https://travis-ci.org/alphagov/digitalmarketplace-supplier-frontend)
[![Coverage Status](https://coveralls.io/repos/alphagov/digitalmarketplace-supplier-frontend/badge.svg?branch=master&service=github)](https://coveralls.io/github/alphagov/digitalmarketplace-supplier-frontend?branch=master)
[![Requirements Status](https://requires.io/github/alphagov/digitalmarketplace-supplier-frontend/requirements.svg?branch=master)](https://requires.io/github/alphagov/digitalmarketplace-supplier-frontend/requirements/?branch=master)

Frontend supplier application for the digital marketplace.

- Python app, based on the [Flask framework](http://flask.pocoo.org/)

## Quickstart

Install [Virtualenv](https://virtualenv.pypa.io/en/latest/)
```
sudo easy_install virtualenv
```

Install dependencies, build assets and run the app
```
make run_all
```

## Full setup

Install [Virtualenv](https://virtualenv.pypa.io/en/latest/)
```
sudo easy_install virtualenv
```

Create a virtual environment
 ```
 virtualenv ./venv
 ```

### Activate the virtual environment

```
source ./venv/bin/activate
```

### Upgrade dependencies

Install new Python dependencies with pip

```make requirements_for_test```


## Front-end

Front-end code (both development and production) is compiled using [Node](http://nodejs.org/) and [Gulp](http://gulpjs.com/).

### Requirements

You need Node (minimum version of 0.10.0, maximum version 0.12.x) which will also get you [NPM](npmjs.org), Node's package management tool.

To check the version you're running, type:

```
node --version
```

### Installation

To install the required Node modules, type:

```
npm install
```

## Frontend tasks

[NPM](https://www.npmjs.org/) is used for all frontend build tasks. The commands available are:

- `npm run frontend-build:development` (compile the frontend files for development)
- `npm run frontend-build:production` (compile the frontend files for production)
- `npm run frontend-build:watch` (watch all frontend files & rebuild when anything changes) FAILED
- `npm run frontend-install` (install all non-NPM dependancies)

Note: `npm run frontend-install` is run automatically as a post-install task when you run `npm install`.





### Run the tests

To run the whole testsuite:

```
make test
```

To test individual parts of the test stack use the `test_pep8`, `test_python`
or `test_javascript` targets.

eg.
```
make test_javascript
```

### Run the development server

To run the Supplier Frontend App for local development use the `run_all` target.
This will install requirements, build assets and run the app.

```
make run_all
```

To just run the application use the `run_app` target.

The supplier frontend runs on port 5003. Use the app at [http://127.0.0.1:5003/suppliers](http://127.0.0.1:5003/suppliers)

### Using FeatureFlags

To use feature flags, check out the documentation in (the README of)
[digitalmarketplace-utils](https://github.com/alphagov/digitalmarketplace-utils#using-featureflags).

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

### Running on Heroku

- Setup the heroku command https://devcenter.heroku.com/articles/getting-started-with-python#set-up
- Create the app with `heroku create`
- Set the app to have a multi-buildpack with `heroku buildpacks:set https://github.com/ddollar/heroku-buildpack-multi.git`
- Set environment variables with `heroku config:set`
- Deploy the app with `git push heroku <your-branch>:master`
