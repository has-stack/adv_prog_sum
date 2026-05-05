import pytest

from workflow_sandbox.core.dockerfile import generate_dockerfile
from workflow_sandbox.core.models import WorkflowTemplate


def test_generate_dockerfile_from_template():
    template = WorkflowTemplate(
        name="python-smoke-test",
        python_version="3.11",
        commands=["python -m unittest discover -s tests"],
        env_vars={"PYTHONPATH": "/workspace"},
    )

    dockerfile = generate_dockerfile(template)

    assert "FROM python:3.11-slim" in dockerfile
    assert "WORKDIR /workspace" in dockerfile
    assert "COPY . /workspace" in dockerfile
    assert 'ENV PYTHONPATH="/workspace"' in dockerfile
    assert "pip install -r requirements.txt" in dockerfile
    assert "python -m unittest discover -s tests" in dockerfile


def test_generate_dockerfile_escapes_env_var_values():
    template = WorkflowTemplate(
        name="quoted-env-test",
        python_version="3.11",
        commands=["python script.py"],
        env_vars={"CONFIG_PATH": r'C:\temp\"quoted"'},
    )

    dockerfile = generate_dockerfile(template)

    assert r'ENV CONFIG_PATH="C:\\temp\\\"quoted\""' in dockerfile


def test_generate_dockerfile_rejects_invalid_template():
    template = WorkflowTemplate(
        name="bad-template",
        python_version="3.11",
        commands=[],
    )

    with pytest.raises(ValueError):
        generate_dockerfile(template)
