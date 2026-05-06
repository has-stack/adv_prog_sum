import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from workflow_sandbox.backend import main as backend
from workflow_sandbox.backend.schemas import (
    DiagnosisRequest,
    RunWorkflowRequest,
    WorkflowTemplateRequest,
)
from workflow_sandbox.core.database import WorkflowDatabase
from workflow_sandbox.core.models import Finding, RunStatus, Severity, WorkflowRun
from workflow_sandbox.core.runner import DockerUnavailableError


def test_health_endpoint_returns_ok():
    assert backend.health() == {"status": "ok"}


def test_run_workflow_request_requires_template():
    with pytest.raises(ValidationError) as error:
        RunWorkflowRequest(project_path="sample_projects/passing_project")

    assert "template" in str(error.value)


def test_workflow_template_request_rejects_unknown_fields():
    with pytest.raises(ValidationError) as error:
        WorkflowTemplateRequest(
            name="python-smoke-test",
            python_version="3.11",
            commands=["python -m unittest discover -s tests"],
            unexpected="value",
        )

    assert "extra_forbidden" in str(error.value)


def test_run_workflow_rejects_invalid_template():
    payload = RunWorkflowRequest(
        template=WorkflowTemplateRequest(
            name="bad-template",
            python_version="3.11",
            commands=[],
        ),
        project_path="sample_projects/passing_project",
    )

    with pytest.raises(HTTPException) as error:
        backend.run_workflow(payload)

    assert error.value.status_code == 400
    assert any("command" in item.lower() for item in error.value.detail)


def test_run_workflow_saves_successful_result(monkeypatch, tmp_path):
    test_database = WorkflowDatabase(tmp_path / "workflow.db")
    test_database.initialise()
    monkeypatch.setattr(backend, "database", test_database)

    def fake_runner(template, project_path):
        return (
            WorkflowRun(
                workflow_name=template.name,
                status=RunStatus.PASSED,
                exit_code=0,
            ),
            [
                Finding(
                    category="example",
                    severity=Severity.LOW,
                    message="Example finding",
                    suggested_fix="No action required",
                )
            ],
        )

    monkeypatch.setattr(backend, "run_workflow_in_docker", fake_runner)
    payload = RunWorkflowRequest(
        template=WorkflowTemplateRequest(
            name="python-smoke-test",
            python_version="3.11",
            commands=["python -m unittest discover -s tests"],
        ),
        project_path="sample_projects/passing_project",
    )

    response = backend.run_workflow(payload)

    assert response["run_id"] == 1
    assert response["run"].status == RunStatus.PASSED
    assert len(test_database.list_runs()) == 1
    assert len(test_database.list_findings_for_run(1)) == 1


def test_run_workflow_returns_503_when_docker_is_unavailable(monkeypatch):
    def fake_runner(template, project_path):
        raise DockerUnavailableError("Docker CLI was not found on PATH.")

    monkeypatch.setattr(backend, "run_workflow_in_docker", fake_runner)
    payload = RunWorkflowRequest(
        template=WorkflowTemplateRequest(
            name="python-smoke-test",
            python_version="3.11",
            commands=["python -m unittest discover -s tests"],
        ),
        project_path="sample_projects/passing_project",
    )

    with pytest.raises(HTTPException) as error:
        backend.run_workflow(payload)

    assert error.value.status_code == 503
    assert "Docker CLI" in error.value.detail


def test_run_workflow_rejects_project_path_validation_error(monkeypatch):
    def fake_runner(template, project_path):
        raise ValueError(
            "Project path must be inside one of the configured allowed project roots."
        )

    monkeypatch.setattr(backend, "run_workflow_in_docker", fake_runner)
    payload = RunWorkflowRequest(
        template=WorkflowTemplateRequest(
            name="python-smoke-test",
            python_version="3.11",
            commands=["python -m unittest discover -s tests"],
        ),
        project_path="../outside-project",
    )

    with pytest.raises(HTTPException) as error:
        backend.run_workflow(payload)

    assert error.value.status_code == 400
    assert "allowed project roots" in error.value.detail


def test_run_workflow_saves_failed_result_with_findings(monkeypatch, tmp_path):
    test_database = WorkflowDatabase(tmp_path / "workflow.db")
    test_database.initialise()
    monkeypatch.setattr(backend, "database", test_database)

    def fake_runner(template, project_path):
        return (
            WorkflowRun(
                workflow_name=template.name,
                status=RunStatus.FAILED,
                exit_code=1,
                stderr="Cannot connect to the Docker daemon.",
            ),
            [
                Finding(
                    category="docker_daemon_unavailable",
                    severity=Severity.HIGH,
                    message="The Docker daemon was not reachable.",
                    suggested_fix="Start Docker and rerun the workflow.",
                )
            ],
        )

    monkeypatch.setattr(backend, "run_workflow_in_docker", fake_runner)
    payload = RunWorkflowRequest(
        template=WorkflowTemplateRequest(
            name="docker-build-check",
            python_version="3.11",
            commands=["python -m unittest discover -s tests"],
        ),
        project_path="sample_projects/passing_project",
    )

    response = backend.run_workflow(payload)
    saved_findings = test_database.list_findings_for_run(response["run_id"])

    assert response["run"].status == RunStatus.FAILED
    assert saved_findings[0].category == "docker_daemon_unavailable"


def test_diagnosis_request_rejects_unknown_fields():
    with pytest.raises(ValidationError) as error:
        DiagnosisRequest(stderr="failure", raw_logs="unexpected")

    assert "extra_forbidden" in str(error.value)


def test_diagnose_uses_typed_request_defaults():
    response = backend.diagnose(
        DiagnosisRequest(stderr="ModuleNotFoundError: No module named 'yaml'")
    )

    assert response["findings"][0].category == "missing_dependency"
