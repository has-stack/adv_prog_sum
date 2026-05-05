"""Backend API for the workflow sandbox."""
"""Creates api endpoints."""

from pathlib import Path
from fastapi import FastAPI, HTTPException
from workflow_sandbox.core.database import WorkflowDatabase
from workflow_sandbox.core.diagnosis import diagnose_output
from workflow_sandbox.core.dockerfile import generate_dockerfile
from workflow_sandbox.core.models import WorkflowTemplate
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
