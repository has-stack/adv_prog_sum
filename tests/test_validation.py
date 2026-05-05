from workflow_sandbox.core.models import WorkflowTemplate
from workflow_sandbox.core.validation import (
    is_valid_workflow_template,
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
