"""Central application configuration.

This is still a local prototype, but keeping defaults here avoids scattering
environment assumptions across the frontend, backend and core services.
"""

from pathlib import Path

DATABASE_PATH = Path("workflow_sandbox.db")
DIAGNOSIS_RULES_PATH = Path("workflow_sandbox/rules/diagnosis_rules.json")

CONTAINER_WORKDIR = "/workspace"
PYTHON_IMAGE_VARIANT = "slim"
DOCKER_EXECUTABLE = "docker"
DOCKER_IMAGE_PREFIX = "workflow-sandbox"
DOCKERFILE_NAME = "Dockerfile"

SUPPORTED_PYTHON_VERSIONS = ["3.8", "3.9", "3.10", "3.11", "3.12"]
MIN_PYTHON_VERSION = "3.8"
MAX_PYTHON_VERSION_EXCLUSIVE = "3.13"
MIN_TIMEOUT_SECONDS = 5
MAX_TIMEOUT_SECONDS = 1800
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_REQUIREMENTS_FILE = "requirements.txt"

ALLOWED_PROJECT_ROOTS = [
    Path("sample_projects"),
]

SAMPLE_PROJECTS = {
    "Passing project": Path("sample_projects/passing_project"),
    "Missing dependency": Path("sample_projects/missing_dependency"),
    "Missing environment variable": Path("sample_projects/missing_env_var"),
    "Failing tests": Path("sample_projects/failing_tests"),
}

DEFAULT_WORKFLOW_DRAFT = {
    "name": "python-smoke-test",
    "python_version": "3.11",
    "requirements_file": DEFAULT_REQUIREMENTS_FILE,
    "commands_text": "python -m unittest discover -s tests",
    "env_text": f"PYTHONPATH={CONTAINER_WORKDIR}",
    "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
    "sample_project": "Passing project",
}

DEFAULT_DIAGNOSIS_DRAFT = {
    "exit_code": 1,
    "timed_out": False,
    "stdout": "",
    "stderr": "ModuleNotFoundError: No module named 'yaml'",
}
