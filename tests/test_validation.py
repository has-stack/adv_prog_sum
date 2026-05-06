import pytest

from workflow_sandbox.core.models import WorkflowTemplate
from workflow_sandbox.core.validation import (
    is_valid_workflow_template,
    resolve_allowed_project_path,
    validate_workflow_template,
)


def test_valid_workflow_template_has_no_errors():
    template = WorkflowTemplate(
        name="python-smoke-test",
        python_version="3.11",
        commands=["python -m unittest discover -s tests"],
        env_vars={"PYTHONPATH": "/workspace"},
    )

    assert validate_workflow_template(template) == []
    assert is_valid_workflow_template(template)


def test_invalid_workflow_template_reports_multiple_errors():
    template = WorkflowTemplate(
        name="-bad",
        python_version="2.7",
        commands=[""],
        requirements_file="/tmp/requirements.py",
        env_vars={"bad-name": "value"},
        timeout_seconds=1,
    )

    errors = validate_workflow_template(template)

    assert len(errors) >= 5
    assert not is_valid_workflow_template(template)
    assert any("Workflow name" in error for error in errors)
    assert any("Python version" in error for error in errors)
    assert any("Commands cannot be blank" in error for error in errors)
    assert any("Requirements file" in error for error in errors)
    assert any("Invalid environment variable" in error for error in errors)


def test_project_path_inside_allowed_root_is_resolved(tmp_path):
    allowed_root = tmp_path / "allowed"
    project_path = allowed_root / "workflow"
    project_path.mkdir(parents=True)

    resolved_path = resolve_allowed_project_path(project_path, [allowed_root])

    assert resolved_path == project_path.resolve()


def test_project_path_outside_allowed_roots_is_rejected(tmp_path):
    allowed_root = tmp_path / "allowed"
    outside_project = tmp_path / "outside"
    allowed_root.mkdir()
    outside_project.mkdir()

    with pytest.raises(ValueError, match="allowed project roots"):
        resolve_allowed_project_path(outside_project, [allowed_root])


def test_project_path_traversal_is_rejected_after_resolution(tmp_path):
    allowed_root = tmp_path / "sample_projects"
    outside_project = tmp_path / "workflow_sandbox"
    allowed_root.mkdir()
    outside_project.mkdir()

    traversal_path = allowed_root / ".." / "workflow_sandbox"

    with pytest.raises(ValueError, match="allowed project roots"):
        resolve_allowed_project_path(traversal_path, [allowed_root])
