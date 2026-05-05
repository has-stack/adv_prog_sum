import pytest
from fastapi import HTTPException

from workflow_sandbox.backend import main as backend
from workflow_sandbox.core.database import WorkflowDatabase
from workflow_sandbox.core.models import Finding, RunStatus, Severity, WorkflowRun


def test_health_endpoint_returns_ok():
    assert backend.health() == {"status": "ok"}


def test_run_workflow_rejects_missing_template():
    with pytest.raises(HTTPException) as error:
        backend.run_workflow({})

    assert error.value.status_code == 400
    assert "template" in error.value.detail


def test_run_workflow_rejects_invalid_template():
    payload = {
        "template": {
            "name": "bad-template",
            "python_version": "3.11",
            "commands": [],
        },
        "project_path": "sample_projects/passing_project",
    }

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
    payload = {
        "template": {
            "name": "python-smoke-test",
            "python_version": "3.11",
            "commands": ["python -m unittest discover -s tests"],
        },
        "project_path": "sample_projects/passing_project",
    }

    response = backend.run_workflow(payload)

    assert response["run_id"] == 1
    assert response["run"].status == RunStatus.PASSED
    assert len(test_database.list_runs()) == 1
    assert len(test_database.list_findings_for_run(1)) == 1
