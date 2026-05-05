"""Backend API for the workflow sandbox."""

"""Creates api endpoints."""

from pathlib import Path
from fastapi import FastAPI, HTTPException
from workflow_sandbox.core.database import WorkflowDatabase
from workflow_sandbox.core.diagnosis import diagnose_output
from workflow_sandbox.core.dockerfile import generate_dockerfile
from workflow_sandbox.core.models import WorkflowTemplate
from workflow_sandbox.core.runner import DockerUnavailableError, run_workflow_in_docker
from workflow_sandbox.core.validation import validate_workflow_template

app = FastAPI(title="Python Workflow Sandbox")
database = WorkflowDatabase(Path("workflow_sandbox.db"))
database.initialise()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/templates")
def save_template(template: WorkflowTemplate) -> dict[str, str]:
    errors = validate_workflow_template(template)
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    database.save_template(template)
    return {"status": "saved", "name": template.name}


@app.get("/templates")
def list_templates() -> list[WorkflowTemplate]:
    return database.list_templates()


@app.post("/dockerfile/preview")
def preview_dockerfile(template: WorkflowTemplate) -> dict[str, str]:
    try:
        dockerfile = generate_dockerfile(template)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"dockerfile": dockerfile}


@app.post("/diagnose")
def diagnose(payload: dict) -> dict:
    findings = diagnose_output(
        stdout=payload.get("stdout", ""),
        stderr=payload.get("stderr", ""),
        exit_code=payload.get("exit_code"),
        timed_out=payload.get("timed_out", False),
    )
    return {"findings": findings}


@app.get("/runs")
def list_runs() -> dict:
    return {"runs": database.list_runs()}


@app.post("/runs")
def run_workflow(payload: dict) -> dict:
    # The request body is still deliberately simple at this stage.
    try:
        template = WorkflowTemplate(**payload["template"])
    except KeyError as error:
        raise HTTPException(
            status_code=400, detail="Request body must include a template."
        ) from error
    except TypeError as error:
        raise HTTPException(
            status_code=400, detail="Template fields are invalid."
        ) from error

    project_path = payload.get("project_path")
    if not project_path:
        raise HTTPException(
            status_code=400, detail="Request body must include a project_path."
        )

    # Validation happens before Docker is called. This prevents avoidable Docker
    # builds for broken workflow names, invalid python versions or empty
    # commands. Which gives faster feedback and cleaner error messages.
    errors = validate_workflow_template(template)
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    try:
        run, findings = run_workflow_in_docker(template, project_path)
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
