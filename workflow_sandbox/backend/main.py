"""Backend API for the workflow sandbox."""

from fastapi import FastAPI, HTTPException

from workflow_sandbox.backend.schemas import (
    DiagnosisRequest,
    RunWorkflowRequest,
    WorkflowTemplateRequest,
)
from workflow_sandbox.config import DATABASE_PATH
from workflow_sandbox.core.database import WorkflowDatabase
from workflow_sandbox.core.diagnosis import diagnose_output
from workflow_sandbox.core.dockerfile import generate_dockerfile
from workflow_sandbox.core.models import WorkflowTemplate
from workflow_sandbox.core.runner import DockerUnavailableError, run_workflow_in_docker
from workflow_sandbox.core.validation import validate_workflow_template

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
        raise HTTPException(status_code=400, detail=errors)

    database.save_template(template)
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
        raise HTTPException(status_code=400, detail=errors)

    try:
        run, findings = run_workflow_in_docker(template, payload.project_path)
    except DockerUnavailableError as error:
        # Docker is infrastructure rather than user input. A 503 tells users
        # that the process cannot currently execute workflows, rather than that
        # the submitted template was invalid.
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        # ValueError is currently used for user errors such as a
        # missing project path.
        raise HTTPException(status_code=400, detail=str(error)) from error

    # Runs and findings are saved together so the dashboard can later show a
    # historical record of both the raw result and the suggested remediation.
    run_id = database.save_run(run, findings)
    return {
        "run_id": run_id,
        "run": run,
        "findings": findings,
    }
