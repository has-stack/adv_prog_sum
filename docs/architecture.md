# Architecture

This application uses a layered Python architecture. The aim is
to keep presentation, API validation, core logic and persistence separate so
that each part can be tested and explained independently.

```text
Streamlit dashboard
        |
        | uses core services directly for local prototype workflows
        v
Core services
  - workflow validation
  - Dockerfile generation
  - Docker execution
  - failure diagnosis
  - SQLite persistence

FastAPI backend
        |
        | exposes the same workflow concepts through typed request schemas
        v
Core services
```

The project has both a frontend and backend, but the core logic does not depend
on either framework. This means validation, diagnosis, Dockerfile generation and
database behaviour can be unit tested without starting Streamlit or Uvicorn.

## Main Components

### Frontend

`workflow_sandbox/frontend/app.py` contains the Streamlit dashboard. It provides
page for running checks, saving workflow templates, previewing generated
Dockerfiles, diagnosing pasted logs and reviewing run history.

`workflow_sandbox/frontend/dashboard_logging.py` captures application log
records during a gui triggered workflow run. The handler is attached only
for the active run and removed afterwards, which avoids duplicate log output
during Streamlit reruns.

### Backend

`workflow_sandbox/backend/main.py` exposes FastAPI endpoints for health checks,
template persistence, Dockerfile preview, diagnosis and workflow runs.

`workflow_sandbox/backend/schemas.py` defines Pydantic request models. These
schemas validate request shape at the API boundary before domain validation or
Docker execution occurs.

### Core Services

`workflow_sandbox/core/models.py` defines the main data structures:

- `WorkflowTemplate`
- `WorkflowRun`
- `Finding`
- `RunHistoryItem`
- `RunStatus`
- `Severity`

`workflow_sandbox/core/validation.py` validates workflow templates and resolves
project paths against configured allowed roots.

`workflow_sandbox/core/dockerfile.py` generates the Dockerfile used for isolated
execution.

`workflow_sandbox/core/runner.py` builds the Docker image, runs the container,
captures outputs and converts Docker/runtime outcomes into `WorkflowRun` and
`Finding` objects.

`workflow_sandbox/core/diagnosis.py` loads JSON diagnosis rules and converts
stdout/stderr/exit-code evidence into remediation guidance.

`workflow_sandbox/core/database.py` is the SQLite access layer for templates,
runs, findings and run-history summaries.

## Data Flow

1. The user selects a sample project and either edits or loads a workflow
   template.
2. The workflow template is validated before execution.
3. The project path is resolved and checked against allowed project roots.
4. A Dockerfile is generated from the selected Python version, requirements file,
   environment variables and commands.
5. Docker builds an isolated image for the selected project.
6. Docker runs the workflow commands inside the container.
7. stdout, stderr, exit code, duration and timeout state are captured.
8. The diagnosis engine applies data-driven rules to classify likely causes.
9. The run and findings are stored in SQLite.
10. The dashboard displays the run result, debug logs, findings and run-history
    summaries.

## Key Design Decisions

### Docker Execution Instead Of Static Parsing Only

The application does not only parse text. It executes the workflow inside a
generated container so dependency, version and environment problems are observed
under repeatable conditions. This gives stronger evidence than reading a
requirements file alone.

### Dynamic Dockerfile Generation

The Dockerfile is generated from a validated `WorkflowTemplate`. This makes the
environment explicit and inspectable through the Container Preview page. The
generated file uses a Python slim base image and copies the selected project
into a controlled container work directory.

### Data-Driven Diagnosis Rules

Known failure patterns live in `workflow_sandbox/rules/diagnosis_rules.json`.
This keeps common diagnoses configurable without changing Python code. The
engine still handles timeout and unknown-failure fallbacks in code because those
depend on execution metadata.

### SQLite Persistence

SQLite is used because the product needs local run history without requiring a
database server. This is suitable for an individual local tool demonstration.
A multi-user deployment would likely replace it with PostgreSQL
or another server database.

### Typed API Boundary

The FastAPI backend uses Pydantic request models rather than loose dictionaries.
This gives a clear API contract and rejects malformed input before the runner is
called.

### Configurable Execution Paths

The runner resolves project paths and checks them against configured allowed
roots. This is important because the tool executes code. The root list is
configurable so a real deployment can point to approved internal workflow
directories rather than the sample projects.

### Logging And Dashboard Debug Logs

Standard logging records operational events such as Docker build start, build
failure, timeout and database persistence. The dashboard captures structured log
records during a run, but raw stdout/stderr remain separate to reduce accidental
exposure of sensitive output.
