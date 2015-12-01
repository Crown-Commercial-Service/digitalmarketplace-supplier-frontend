import os
import yaml
import json
import pytest
from jsonschema.validators import validator_for
from jsonschema import ValidationError


def get_all_files():

    def all_files():
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frameworks'))
        for root, subdirs, files in os.walk(root_dir):
            for filename in files:
                if filename.endswith('.yml'):
                    file_path = os.path.join(root, filename)
                    schema_name = file_path.replace(root_dir, '').split('/')[2:][0]
                    yield (file_path, schema_name)

    return all_files()


schema_cache = {}


def load_jsonschema_validator(path):
    if path not in schema_cache:
        with open(path) as f:
            schema = json.load(f)
            validator = validator_for(schema)
            validator.check_schema(schema)
            schema_cache[path] = validator(schema)

    return schema_cache[path]


def test_that_there_are_some_files():
    assert len(list(get_all_files())) > 0


@pytest.mark.parametrize(("path", "schema_name"), get_all_files())
def test_framework_file_matches_schema(path, schema_name):
    validator = load_jsonschema_validator('schemas/{}.json'.format(schema_name))

    with open(path) as f:
        data = yaml.load(f)
        try:
            validator.validate(data)
        except ValidationError as e:
            pytest.fail("{} failed validation with: {}".format(path, e))
