"""Request models for the FastAPI boundary."""
"""This separation ensures the core data-classes remain framework free, and therefore more testable & resilient."""

from pydantic import BaseModel, ConfigDict, Field

from workflow_sandbox.config import DEFAULT_REQUIREMENTS_FILE, DEFAULT_TIMEOUT_SECONDS
from workflow_sandbox.core.models import WorkflowTemplate


class WorkflowTemplateRequest(BaseModel):
    """Workflow template shape accepted by the API."""

    model_config = ConfigDict(extra="forbid")

    name: str
    python_version: str
    commands: list[str]
    requirements_file: str = DEFAULT_REQUIREMENTS_FILE
    env_vars: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    def to_domain(self) -> WorkflowTemplate:
        """Convert API input into the dataclass used by the runner."""

        return WorkflowTemplate(
            name=self.name,
            python_version=self.python_version,
            commands=self.commands,
            requirements_file=self.requirements_file,
            env_vars=self.env_vars,
            timeout_seconds=self.timeout_seconds,
        )


class DiagnosisRequest(BaseModel):
    """Raw execution evidence submitted for diagnosis."""

    model_config = ConfigDict(extra="forbid")

    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False


class RunWorkflowRequest(BaseModel):
    """Request body for executing a workflow against a project path."""

    model_config = ConfigDict(extra="forbid")

    template: WorkflowTemplateRequest
    project_path: str
