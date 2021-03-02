from invoke import task

from dmdevtools.invoke_tasks import frontend_app_tasks as ns


@task(ns["virtualenv"], ns["requirements_dev"])
def test_mypy(c):
    c.run("mypy app/")


ns.add_task(test_mypy)
ns["test"].pre.insert(-1, test_mypy)
