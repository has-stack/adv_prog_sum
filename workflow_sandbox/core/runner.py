"""Docker-based workflow execution."""

import logging
import os
import shutil
import subprocess
import time
import uuid
from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory

from workflow_sandbox.config import (
    DOCKER_EXECUTABLE,
    DOCKER_IMAGE_PREFIX,
    DOCKERFILE_NAME,
)
from workflow_sandbox.core.diagnosis import DOCKER_BUILD_STAGE, diagnose_output
from workflow_sandbox.core.dockerfile import generate_dockerfile
from workflow_sandbox.core.models import (
    Finding,
    RunStatus,
    WorkflowRun,
    WorkflowTemplate,
)
from workflow_sandbox.core.validation import resolve_allowed_project_path

logger = logging.getLogger(__name__)


class DockerUnavailableError(RuntimeError):
    """Raised when the Docker CLI is not available to the application."""


def run_workflow_in_docker(
    template: WorkflowTemplate,
    project_path: str | Path,
    allowed_roots: Iterable[Path] | None = None,
) -> tuple[WorkflowRun, list[Finding]]:
    """Build and run a Python workflow inside a Docker container."""

    project_path = resolve_allowed_project_path(project_path, allowed_roots)

    # Docker may not be available on all systems
    if shutil.which(DOCKER_EXECUTABLE) is None:
        logger.error("Docker CLI was not found on PATH")
        raise DockerUnavailableError("Docker CLI was not found on PATH.")

    started = time.monotonic()
    image_tag = _create_image_tag(template.name)
    logger.info(
        "Starting Docker workflow run name=%s project=%s image=%s",
        template.name,
        project_path,
        image_tag,
    )

    with TemporaryDirectory() as temp_directory:
        build_context = Path(temp_directory) / "context"
        docker_config = Path(temp_directory) / "docker-config"
        shutil.copytree(project_path, build_context)
        docker_config.mkdir()

        dockerfile = generate_dockerfile(template)
        (build_context / DOCKERFILE_NAME).write_text(dockerfile, encoding="utf-8")
        docker_env = os.environ.copy()
        docker_env["DOCKER_CONFIG"] = str(docker_config)

        try:
            logger.info("Building Docker image %s", image_tag)
            build_result = subprocess.run(
                [DOCKER_EXECUTABLE, "build", "-t", image_tag, "."],
                cwd=build_context,
                env=docker_env,
                capture_output=True,
                text=True,
                timeout=template.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            duration = time.monotonic() - started
            stdout = _normalise_output(error.stdout)
            stderr = _normalise_output(error.stderr)
            logger.warning(
                "Docker image build timed out name=%s timeout=%s duration=%.2f",
                template.name,
                template.timeout_seconds,
                duration,
            )
            run = WorkflowRun(
                workflow_name=template.name,
                status=RunStatus.TIMEOUT,
                exit_code=None,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
            )
            findings = diagnose_output(
                stdout=stdout,
                stderr=stderr,
                exit_code=None,
                timed_out=True,
                execution_stage=DOCKER_BUILD_STAGE,
            )
            return run, findings

        if build_result.returncode != 0:
            duration = time.monotonic() - started
            logger.warning(
                "Docker image build failed name=%s exit_code=%s duration=%.2f",
                template.name,
                build_result.returncode,
                duration,
            )
            run = WorkflowRun(
                workflow_name=template.name,
                status=RunStatus.FAILED,
                exit_code=build_result.returncode,
                stdout=build_result.stdout,
                stderr=build_result.stderr,
                duration_seconds=duration,
            )
            # Build failures are different from workflow failures because the
            # user's command never executes. Passing the stage allows the
            # diagnosis layer to produce infrastructure guidance.
            findings = diagnose_output(
                stdout=build_result.stdout,
                stderr=build_result.stderr,
                exit_code=build_result.returncode,
                execution_stage=DOCKER_BUILD_STAGE,
            )
            return run, findings

        try:
            logger.info("Running Docker image %s", image_tag)
            run_result = subprocess.run(
                [DOCKER_EXECUTABLE, "run", "--rm", image_tag],
                env=docker_env,
                capture_output=True,
                text=True,
                timeout=template.timeout_seconds,
                check=False,
            )
            timed_out = False
            stdout = run_result.stdout
            stderr = run_result.stderr
            exit_code = run_result.returncode
        except subprocess.TimeoutExpired as error:
            timed_out = True
            stdout = _normalise_output(error.stdout)
            stderr = _normalise_output(error.stderr)
            exit_code = None
            logger.warning(
                "Docker workflow run timed out name=%s timeout=%s",
                template.name,
                template.timeout_seconds,
            )

    duration = time.monotonic() - started
    if timed_out:
        status = RunStatus.TIMEOUT
    elif exit_code == 0:
        status = RunStatus.PASSED
    else:
        status = RunStatus.FAILED

    run = WorkflowRun(
        workflow_name=template.name,
        status=status,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=duration,
    )
    findings = diagnose_output(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        timed_out=timed_out,
    )
    # Raw stdout/stderr are intentionally not written to application logs
    # because workflow output can contain paths, credentials or environment data.
    logger.info(
        "Completed Docker workflow run name=%s status=%s exit_code=%s duration=%.2f findings=%s",
        template.name,
        status.value,
        exit_code,
        duration,
        len(findings),
    )
    return run, findings


def _create_image_tag(workflow_name: str) -> str:
    """Create a unique Docker image tag for a workflow run."""

    # The workflow name alone is not enough because the same template name can
    # be reused against different sample projects. A short unique suffix avoids
    # stale image confusion.
    safe_name = workflow_name.lower().replace("_", "-")
    suffix = uuid.uuid4().hex[:8]
    return f"{DOCKER_IMAGE_PREFIX}-{safe_name}-{suffix}"


# Internal helper to ensure logs are strings
def _normalise_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output
