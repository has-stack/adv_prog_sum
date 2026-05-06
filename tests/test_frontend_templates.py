from workflow_sandbox.core.models import WorkflowTemplate
from workflow_sandbox.frontend.app import format_env_vars, workflow_template_to_draft


def test_format_env_vars_is_stable_for_text_area():
    env_text = format_env_vars(
        {
            "SMMU_TEST_ROOT": "/opt/smmu",
            "PYTHONPATH": "/workspace",
        }
    )

    assert env_text == "PYTHONPATH=/workspace\nSMMU_TEST_ROOT=/opt/smmu"


def test_workflow_template_to_draft_preserves_selected_project():
    template = WorkflowTemplate(
        name="unit-tests",
        python_version="3.12",
        commands=["python -m pytest", "python scripts/check_env.py"],
        requirements_file="requirements-dev.txt",
        env_vars={"PYTHONPATH": "/workspace"},
        timeout_seconds=300,
    )

    draft = workflow_template_to_draft(template, "Missing dependency")

    assert draft == {
        "name": "unit-tests",
        "python_version": "3.12",
        "requirements_file": "requirements-dev.txt",
        "commands_text": "python -m pytest\npython scripts/check_env.py",
        "env_text": "PYTHONPATH=/workspace",
        "timeout_seconds": 300,
        "sample_project": "Missing dependency",
    }
