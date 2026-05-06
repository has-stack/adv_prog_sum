import logging

from workflow_sandbox.core.database import WorkflowDatabase
from workflow_sandbox.core.models import (
    Finding,
    RunStatus,
    Severity,
    WorkflowRun,
    WorkflowTemplate,
)


def test_database_saves_and_lists_templates(tmp_path):
    database = WorkflowDatabase(tmp_path / "workflow.db")
    database.initialise()

    database.save_template(
        WorkflowTemplate(
            name="python-smoke-test",
            python_version="3.11",
            commands=["python -m unittest discover -s tests"],
            env_vars={"PYTHONPATH": "/workspace"},
        )
    )

    templates = database.list_templates()

    assert len(templates) == 1
    assert templates[0].name == "python-smoke-test"
    assert templates[0].env_vars == {"PYTHONPATH": "/workspace"}


def test_database_saves_runs_and_findings(tmp_path, caplog):
    database = WorkflowDatabase(tmp_path / "workflow.db")
    database.initialise()
    caplog.set_level(logging.INFO, logger="workflow_sandbox.core.database")

    run_id = database.save_run(
        WorkflowRun(
            workflow_name="missing-dependency",
            status=RunStatus.FAILED,
            exit_code=1,
            stderr="ModuleNotFoundError: No module named 'yaml'",
            duration_seconds=1.2,
        ),
        [
            Finding(
                category="missing_dependency",
                severity=Severity.MEDIUM,
                message="Missing dependency",
                suggested_fix="Add pyyaml",
            )
        ],
    )

    runs = database.list_runs()
    findings = database.list_findings_for_run(run_id)

    assert len(runs) == 1
    assert runs[0].workflow_name == "missing-dependency"
    assert runs[0].status == RunStatus.FAILED
    assert len(findings) == 1
    assert findings[0].suggested_fix == "Add pyyaml"
    assert f"Saved workflow run id={run_id}" in caplog.text
