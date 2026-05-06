"""Initial data models for workflow sandbox runs."""

from dataclasses import dataclass, field
from enum import Enum

from workflow_sandbox.config import DEFAULT_REQUIREMENTS_FILE, DEFAULT_TIMEOUT_SECONDS

class RunStatus(str, Enum):
    """Possible states for a workflow run."""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class Severity(str, Enum):
    """Simple severity levels for diagnostic findings."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class WorkflowTemplate:
    """A Python workflow that can be run in the sandbox."""

    name: str
    python_version: str
    commands: list[str]
    requirements_file: str = DEFAULT_REQUIREMENTS_FILE
    env_vars: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


@dataclass
class WorkflowRun:
    """Result captured from a workflow execution."""

    workflow_name: str
    status: RunStatus
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0


@dataclass
class Finding:
    """A diagnostic finding produced from workflow output."""

    category: str
    severity: Severity
    message: str
    suggested_fix: str
