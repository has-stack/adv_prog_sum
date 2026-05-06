"""Basic validation for workflow templates."""

import re

from packaging.version import InvalidVersion, Version

from workflow_sandbox.config import (
    MAX_PYTHON_VERSION_EXCLUSIVE,
    MAX_TIMEOUT_SECONDS,
    MIN_PYTHON_VERSION,
    MIN_TIMEOUT_SECONDS,
    SUPPORTED_PYTHON_VERSIONS,
)
from workflow_sandbox.core.models import WorkflowTemplate

_WORKFLOW_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,63}$")
_ENV_VAR_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def validate_workflow_template(template: WorkflowTemplate) -> list[str]:
    """Return validation errors for a workflow template."""

    errors: list[str] = []

    if not _WORKFLOW_NAME_PATTERN.match(template.name):
        errors.append(
            "Workflow name must be 3-64 characters and contain only letters, numbers, dots, underscores or hyphens."
        )

    try:
        version = Version(template.python_version)
        if version < Version(MIN_PYTHON_VERSION) or version >= Version(
            MAX_PYTHON_VERSION_EXCLUSIVE
        ):
            errors.append(
                f"Python version must be between {MIN_PYTHON_VERSION} and {SUPPORTED_PYTHON_VERSIONS[-1]}."
            )
    except InvalidVersion:
        errors.append("Python version must be a valid version string.")

    if not template.commands:
        errors.append("At least one command is required.")

    for command in template.commands:
        if not command.strip():
            errors.append("Commands cannot be blank.")

    if not template.requirements_file.endswith(".txt"):
        errors.append("Requirements file must be a .txt file.")

    if template.requirements_file.startswith("/"):
        errors.append("Requirements file must be a relative path.")

    if (
        template.timeout_seconds < MIN_TIMEOUT_SECONDS
        or template.timeout_seconds > MAX_TIMEOUT_SECONDS
    ):
        errors.append(
            f"Timeout must be between {MIN_TIMEOUT_SECONDS} and {MAX_TIMEOUT_SECONDS} seconds."
        )

    for key in template.env_vars:
        if not _ENV_VAR_PATTERN.match(key):
            errors.append(f"Invalid environment variable name: {key}")

    return errors


def is_valid_workflow_template(template: WorkflowTemplate) -> bool:
    """Return True when the workflow template has no validation errors."""

    return len(validate_workflow_template(template)) == 0
