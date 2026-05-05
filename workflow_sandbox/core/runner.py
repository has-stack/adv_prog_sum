"""Docker-based workflow execution."""

import shutil
import subprocess
import time
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from workflow_sandbox.core.diagnosis import diagnose_output
from workflow_sandbox.core.dockerfile import generate_dockerfile
from workflow_sandbox.core.models import Finding, RunStatus, WorkflowRun, WorkflowTemplate

class DockerUnavailableError(RuntimeError):
    """Raised when the Docker CLI is not available to the application."""

def run_workflow_in_docker(
    template: WorkflowTemplate,
    project_path: str | Path,
) -> tuple[WorkflowRun, list[Finding]]:
    """Build and run a Python workflow inside a Docker container."""

    # Path data structure needed for different OS
    project_path = Path(project_path)
    if not project_path.exists() or not project_path.is_dir():
        raise ValueError(f"Project path does not exist or is not a directory: {project_path}")

    # Docker requires sudo on many systems, may not be available
    if shutil.which("docker") is None:
        raise DockerUnavailableError("Docker CLI was not found on PATH.")

    started = time.monotonic()
    image_tag = f"workflow-sandbox-{template.name.lower().replace('_', '-')}"

    with TemporaryDirectory() as temp_directory:
        build_context = Path(temp_directory) / "context"
        docker_config = Path(temp_directory) / "docker-config"
        shutil.copytree(project_path, build_context)
        docker_config.mkdir()

        dockerfile = generate_dockerfile(template)
        (build_context / "Dockerfile").write_text(dockerfile, encoding="utf-8")
        docker_env = os.environ.copy()
        docker_env["DOCKER_CONFIG"] = str(docker_config)

        build_result = subprocess.run(
            ["docker", "build", "-t", image_tag, "."],
            cwd=build_context,
            env=docker_env,
            capture_output=True,
            text=True,
            timeout=template.timeout_seconds,
            check=False,
        )

        if build_result.returncode != 0:
            duration = time.monotonic() - started
            run = WorkflowRun(
                workflow_name=template.name,
                status=RunStatus.FAILED,
                exit_code=build_result.returncode,
                stdout=build_result.stdout,
                stderr=build_result.stderr,
                duration_seconds=duration,
            )
            findings = diagnose_output(
                stdout=build_result.stdout,
                stderr=build_result.stderr,
                exit_code=build_result.returncode,
            )
            return run, findings

        try:
            run_result = subprocess.run(
                ["docker", "run", "--rm", image_tag],
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
    return run, findings


# Internal helper to ensure logs are str
def _normalise_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output
