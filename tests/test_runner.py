import shutil

import pytest

from workflow_sandbox.core.models import WorkflowTemplate
from workflow_sandbox.core.runner import (
    DockerUnavailableError,
    _normalise_output,
    run_workflow_in_docker,
)


def test_runner_rejects_missing_project_path(tmp_path):
    template = WorkflowTemplate(
        name="python-smoke-test",
        python_version="3.11",
        commands=["python -m unittest discover -s tests"],
    )

    with pytest.raises(ValueError):
        run_workflow_in_docker(template, tmp_path / "missing")


def test_runner_reports_docker_unavailable(monkeypatch, tmp_path):
    project_path = tmp_path / "project"
    project_path.mkdir()
    monkeypatch.setattr(shutil, "which", lambda command: None)
    template = WorkflowTemplate(
        name="python-smoke-test",
        python_version="3.11",
        commands=["python -m unittest discover -s tests"],
    )

    with pytest.raises(DockerUnavailableError):
        run_workflow_in_docker(template, project_path)


def test_normalise_output_handles_none_bytes_and_string():
    assert _normalise_output(None) == ""
    assert _normalise_output(b"hello") == "hello"
    assert _normalise_output("already text") == "already text"
