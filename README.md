# Python Environment Drift Manager

This application is a DevOps support tool for diagnosing Python
workflow failures after infrastructure or environment changes. It is based on a
small SMMU DevOps team where apprentices and engineers regularly raise Python
dependency, version and environment issues in support channels.

The application lets a user define a reusable Python workflow template, preview
the generated Dockerfile, run the workflow inside an isolated Docker container,
capture stdout/stderr/exit status, classify common failures and review previous
runs through a Streamlit dashboard.

NOTE: This repo has been ported over from a private internal repo, the commit history has
been preserved to the best degree possible.

## Key Features

- Streamlit dashboard for running environment checks and reviewing history.
- FastAPI backend exposing typed API endpoints.
- Reusable workflow templates with Python version, commands, requirements file,
  environment variables and timeout settings.
- Dynamic Dockerfile generation for isolated workflow execution.
- Docker runner that captures stdout, stderr, exit code, duration and timeout
  state.
- Regex driven diagnosis rules stored in JSON.
- SQLite persistence for workflow templates, run history and diagnostic
  findings.
- Dashboard debug-log capture for workflow troubleshooting.
- Configurable project-root to reduce the risk of executing sensitive
  filesystem paths.
- Automated pytest suite covering validation, diagnosis, Dockerfile generation,
  runner behaviour, persistence, backend error handling and dashboard helpers.

## Project Structure

```text
workflow_sandbox/
  backend/            FastAPI endpoints and request schemas
  core/               Validation, models, Dockerfile generation, runner, diagnosis and database access
  frontend/           Streamlit dashboard and dashboard log capture
  rules/              Data-driven diagnosis rules
sample_projects/      Synthetic projects used to demonstrate success and failure cases
tests/                Automated test suite
docs/                 Architecture, scope, testing and assessment notes
```

## Requirements

- Python 3.10 or later.
- Docker installed and available to the current user.
- Linux/macOS shell or WSL-style environment.

Install Python dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Check Docker access:

```bash
docker ps
```

If Docker returns a permission error, fix Docker access before using workflow
execution. The app can diagnose Docker permission and daemon failures, but it
cannot run containers without Docker access.

## Run The Dashboard

From the repository root:

```bash
source .venv/bin/activate
PYTHONPATH=$(pwd) streamlit run workflow_sandbox/frontend/app.py
```

The main dashboard pages are:

- `Run Check`: select a project, load or edit a workflow template, run it in
  Docker and inspect findings.
- `Workflow Templates`: save reusable workflow definitions.
- `Container Preview`: inspect the generated Dockerfile before execution.
- `Log Diagnosis`: paste stdout/stderr manually to classify failures without
  running Docker.
- `Run History`: review previous checks, findings counts and primary diagnosis
  categories.

## Run The Backend

The backend is optional for the Streamlit workflow because the dashboard calls
the core services directly. It exists to demonstrate a separate API boundary and
typed request validation.

```bash
source .venv/bin/activate
PYTHONPATH=$(pwd) uvicorn workflow_sandbox.backend.main:app --reload
```

FastAPI documentation is then available from Uvicorn's local server URL.

## Run Tests

```bash
source .venv/bin/activate
pytest -q
```

At the time of writing, the suite contains 45 tests covering the core workflow
logic, backend error handling and dashboard helper behaviour.

## Sample Projects

The sample projects are intentionally small and synthetic:

- `passing_project`: passes unit tests.
- `missing_dependency`: imports `yaml` without declaring `pyyaml`.
- `missing_env_var`: expects `SMMU_TEST_ROOT` to be present.
- `failing_tests`: contains a deliberate functional test failure.

These provide repeatable scenarios for demonstrating environment drift, missing
dependencies and workflow failures without using real workplace repositories.

## Documentation

- [Architecture](docs/architecture.md)

## Limitations

This is a simplified constrained solution rather than a deployed production service. It does not
include user authentication (LDAP), remote workers, Slack integration, or
multi-user database concurrency. Those are deliberate scope boundaries so the
project remains focused on Python workflow diagnosis, architecture and testing.
