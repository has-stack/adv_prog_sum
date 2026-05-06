"""Backend API for the workflow sandbox."""

import logging

from fastapi import FastAPI, HTTPException

from workflow_sandbox.backend.schemas import (
    DiagnosisRequest,
    RunWorkflowRequest,
    WorkflowTemplateRequest,
)
from workflow_sandbox.config import DATABASE_PATH
from workflow_sandbox.logging_config import configure_logging
from workflow_sandbox.core.database import WorkflowDatabase
from workflow_sandbox.core.diagnosis import diagnose_output
from workflow_sandbox.core.dockerfile import generate_dockerfile
from workflow_sandbox.core.models import WorkflowTemplate
from workflow_sandbox.core.runner import DockerUnavailableError, run_workflow_in_docker
from workflow_sandbox.core.validation import validate_workflow_template

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Python Workflow Sandbox")
database = WorkflowDatabase(DATABASE_PATH)
database.initialise()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/templates")
def save_template(template_request: WorkflowTemplateRequest) -> dict[str, str]:
    template = template_request.to_domain()
    errors = validate_workflow_template(template)
    if errors:
        logger.warning("Rejected workflow template %s: %s", template.name, errors)
        raise HTTPException(status_code=400, detail=errors)

    database.save_template(template)
    logger.info("Saved workflow template %s", template.name)
    return {"status": "saved", "name": template.name}


@app.get("/templates")
def list_templates() -> list[WorkflowTemplate]:
    return database.list_templates()


@app.post("/dockerfile/preview")
def preview_dockerfile(template_request: WorkflowTemplateRequest) -> dict[str, str]:
    template = template_request.to_domain()
    try:
        dockerfile = generate_dockerfile(template)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"dockerfile": dockerfile}


@app.post("/diagnose")
def diagnose(payload: DiagnosisRequest) -> dict:
    findings = diagnose_output(
        stdout=payload.stdout,
        stderr=payload.stderr,
        exit_code=payload.exit_code,
        timed_out=payload.timed_out,
    )
    logger.info(
        "Diagnosed submitted output: exit_code=%s timed_out=%s findings=%s",
        payload.exit_code,
        payload.timed_out,
        len(findings),
    )
    return {"findings": findings}


@app.get("/runs")
def list_runs() -> dict:
    return {"runs": database.list_runs()}


@app.post("/runs")
def run_workflow(payload: RunWorkflowRequest) -> dict:
    template = payload.template.to_domain()

    # Validation happens before Docker is called. This prevents avoidable Docker
    # builds for broken workflow names, invalid python versions or empty
    # commands. Which gives faster feedback and cleaner error messages.
    errors = validate_workflow_template(template)
    if errors:
        logger.warning("Rejected workflow run %s: %s", template.name, errors)
        raise HTTPException(status_code=400, detail=errors)

    try:
        logger.info(
            "Starting workflow run %s against project %s",
            template.name,
            payload.project_path,
        )
        run, findings = run_workflow_in_docker(template, payload.project_path)
    except DockerUnavailableError as error:
        # Docker is infrastructure rather than user input. A 503 tells users
        # that the process cannot currently execute workflows, rather than that
        # the submitted template was invalid.
        logger.error("Docker unavailable for workflow %s: %s", template.name, error)
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        # ValueError is currently used for user errors such as a
        # missing project path.
        logger.warning("Rejected workflow run %s: %s", template.name, error)
        raise HTTPException(status_code=400, detail=str(error)) from error

    # Runs and findings are saved together so the dashboard can later show a
    # historical record of both the raw result and the suggested remediation.
    run_id = database.save_run(run, findings)
    logger.info(
        "Stored workflow run %s with status=%s findings=%s",
        run_id,
        run.status.value,
        len(findings),
    )
    return {
        "run_id": run_id,
        "run": run,
        "findings": findings,
    }
