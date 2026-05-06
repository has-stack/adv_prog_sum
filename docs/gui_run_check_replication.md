# GUI Run Check Replication Guide

This page records the exact dashboard inputs needed to reproduce the Run Check
evidence for the Python Environment Drift Manager.

## Starting The Dashboard

From the project root, start Streamlit with:

```bash
PYTHONPATH=$(pwd) streamlit run workflow_sandbox/frontend/app.py
```

Open the sidebar and select `Run Check`.

Docker must be installed and the current user must be able to run Docker
commands. A quick pre-check is:

```bash
docker ps
```

## Run Check Fields

The Run Check page requires these inputs:

- `Sample project`: selects the synthetic project folder to run.
- `Workflow name`: a readable name for the check.
- `Python version`: the Python base image version used for the generated Dockerfile.
- `Requirements file`: the requirements file inside the selected sample project.
- `Commands`: one command per line, executed inside the container.
- `Environment variables`: one `KEY=value` pair per line.
- `Timeout seconds`: maximum time allowed for Docker build or run.

The dashboard shows the resolved project path before execution. This is useful
for screenshots because it makes the selected execution target explicit.

## Case 1: Passing Workflow

Use this case to prove the happy path.

| Field | Value |
| --- | --- |
| Sample project | `Passing project` |
| Workflow name | `python-smoke-test` |
| Python version | `3.11` |
| Requirements file | `requirements.txt` |
| Commands | `python -m unittest discover -s tests` |
| Environment variables | `PYTHONPATH=/workspace` |
| Timeout seconds | `120` |

Expected result:

- status is `passed`;
- exit code is `0`;
- no findings are generated.

## Case 2: Missing Dependency

Use this case to prove that runtime import failures are diagnosed.

| Field | Value |
| --- | --- |
| Sample project | `Missing dependency` |
| Workflow name | `missing-dependency-check` |
| Python version | `3.11` |
| Requirements file | `requirements.txt` |
| Commands | `python parse_config.py` |
| Environment variables | leave blank |
| Timeout seconds | `120` |

Expected result:

- status is `failed`;
- exit code is non-zero;
- finding category is `missing_dependency`;
- suggested fix recommends adding `pyyaml` to `requirements.txt`.

## Case 3: Missing Environment Variable

Use this case to prove that missing environment configuration is diagnosed.

| Field | Value |
| --- | --- |
| Sample project | `Missing environment variable` |
| Workflow name | `missing-env-check` |
| Python version | `3.11` |
| Requirements file | `requirements.txt` |
| Commands | `python read_environment.py` |
| Environment variables | leave blank |
| Timeout seconds | `120` |

Expected result:

- status is `failed`;
- exit code is non-zero;
- finding category is `missing_environment_variable`;
- suggested fix recommends defining `SMMU_TEST_ROOT`.

Optional recovery run:

Set `Environment variables` to:

```text
SMMU_TEST_ROOT=/workspace
```

Then rerun the same check. The workflow should complete successfully because
the required environment variable is now available inside the container.

## Case 4: Failing Functional Tests

Use this case to prove that the tool can distinguish execution failure from
functional correctness failure.

| Field | Value |
| --- | --- |
| Sample project | `Failing tests` |
| Workflow name | `failing-test-check` |
| Python version | `3.11` |
| Requirements file | `requirements.txt` |
| Commands | `python -m unittest discover -s tests` |
| Environment variables | `PYTHONPATH=/workspace` |
| Timeout seconds | `120` |

Expected result:

- status is `failed`;
- exit code is non-zero;
- finding category is `test_failure`;
- stdout or stderr shows the failing assertion.
