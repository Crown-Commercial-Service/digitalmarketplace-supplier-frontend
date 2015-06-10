# digitalmarketplace-supplier-frontend

Frontend supplier application for the digital marketplace.

- Python app, based on the [Flask framework](http://flask.pocoo.org/)

## Setup

Install [Virtualenv](https://virtualenv.pypa.io/en/latest/)

```
sudo easy_install virtualenv
```

Create a virtual environment
 
 ```
 virtualenv ./venv
 ```

Set the required environment variables (for dev use local API instance if you 
have it running):
```
export DM_API_URL=http://localhost:5000
export DM_SUPPLIER_FRONTEND_API_AUTH_TOKEN=<auth_token>
```

### Activate the virtual environment

```
source ./venv/bin/activate
```

### Upgrade dependencies

Install new Python dependencies with pip

```pip install -r requirements.txt```


## Front-end

Front-end code (both development and production) is compiled using [Node](http://nodejs.org/) and [Gulp](http://gulpjs.com/).

### Requirements

You need Node, minimum version of 0.10.0, which will also get you [NPM](npmjs.org), Node's package management tool.

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

```
./scripts/run_tests.sh
```


### Run the server

To run the Supplier Frontend App for local development you can use the convenient run
script, which sets the required environment variables to defaults if they have
not already been set:

```
./scripts/run_app.sh
```

The script is a wrapper around `python application.py runserver` so all the options available there
can also be sent in. For example, to set the host:

```
./scripts/run_app.sh -h '0.0.0.0'
```

More generally, the command to start the server is:

```
python application.py runserver
```

The supplier frontend runs on port 5003. Use the app at [http://127.0.0.1:5003/](http://127.0.0.1:5003/)
