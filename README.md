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
export DM_API_BEARER=<bearer_token>
```

### Activate the virtual environment

```
source ./venv/bin/activate
```

### Upgrade dependencies

Install new Python dependencies with pip

```pip install -r requirements.txt```

Install frontend dependencies with npm

```npm install```

Do the (temporary) gulp thing

```./node_modules/gulp/bin/gulp.js build:development```

### Run the tests

```
./scripts/run_tests.sh
```


### Run the server

To run the Supplier Frontend App for local development you can use the convenient run
script, which sets the required environment variables to defaults if they have
not already been set:

```
./run_app.sh
```

More generally, the command to start the server is:

```
python application.py runserver
```

The supplier frontend runs on port 5003. Use the app at [http://127.0.0.1:5003/](http://127.0.0.1:5003/)
