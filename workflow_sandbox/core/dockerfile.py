"""Dockerfile generation from workflow templates."""

import json

from workflow_sandbox.core.models import WorkflowTemplate
from workflow_sandbox.core.validation import validate_workflow_template

def generate_dockerfile(template: WorkflowTemplate) -> str:
    """Create a Dockerfile string for a workflow template."""

    validation_errors = validate_workflow_template(template)
    if validation_errors:
        joined_errors = "; ".join(validation_errors)
        raise ValueError(f"Invalid workflow template: {joined_errors}")

    # -slim reduces the version size
    lines = [
        f"FROM python:{template.python_version}-slim",
        "WORKDIR /workspace",
        "COPY . /workspace",
    ]

    # Protect against env vars breaking Docker syntax
    for key, value in sorted(template.env_vars.items()):
        escaped_value = value.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'ENV {key}="{escaped_value}"')

    lines.extend(
        [
            "RUN python -m pip install --upgrade pip",
            f"RUN if [ -f {template.requirements_file} ]; then pip install -r {template.requirements_file}; fi",
            f"CMD {json.dumps(['/bin/sh', '-c', ' && '.join(template.commands)])}",
        ]
    )

    return "\n".join(lines) + "\n"
