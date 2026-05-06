import shutil
import subprocess

import pytest

from workflow_sandbox.core.models import RunStatus, WorkflowTemplate
from workflow_sandbox.core.runner import (
    DockerUnavailableError,
    _create_image_tag,
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


def test_runner_classifies_docker_build_failure(monkeypatch, tmp_path):
    project_path = tmp_path / "project"
    project_path.mkdir()
    monkeypatch.setattr(shutil, "which", lambda command: "/usr/bin/docker")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stdout="",
            stderr="Cannot connect to the Docker daemon. Is the docker daemon running?",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    template = WorkflowTemplate(
        name="python-smoke-test",
        python_version="3.11",
        commands=["python -m unittest discover -s tests"],
    )

    run, findings = run_workflow_in_docker(template, project_path)

    assert run.status == RunStatus.FAILED
    assert findings[0].category == "docker_daemon_unavailable"


def test_runner_classifies_docker_build_timeout(monkeypatch, tmp_path):
    project_path = tmp_path / "project"
    project_path.mkdir()
    monkeypatch.setattr(shutil, "which", lambda command: "/usr/bin/docker")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=args[0],
            timeout=kwargs["timeout"],
            output=b"building image",
            stderr=b"installing dependencies",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    template = WorkflowTemplate(
        name="python-smoke-test",
        python_version="3.11",
        commands=["python -m unittest discover -s tests"],
    )

    run, findings = run_workflow_in_docker(template, project_path)

    assert run.status == RunStatus.TIMEOUT
    assert run.stdout == "building image"
    assert findings[0].category == "docker_build_timeout"


def test_normalise_output_handles_none_bytes_and_string():
    assert _normalise_output(None) == ""
    assert _normalise_output(b"hello") == "hello"
    assert _normalise_output("already text") == "already text"


def test_create_image_tag_is_readable_and_unique():
    first = _create_image_tag("python_smoke_test")
    second = _create_image_tag("python_smoke_test")

    assert first.startswith("workflow-sandbox-python-smoke-test-")
    assert second.startswith("workflow-sandbox-python-smoke-test-")
    assert first != second
