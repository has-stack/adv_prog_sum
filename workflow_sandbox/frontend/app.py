"""Streamlit dashboard for the workflow sandbox prototype."""

import streamlit as st

from workflow_sandbox.config import (
    DATABASE_PATH,
    DEFAULT_DIAGNOSIS_DRAFT,
    DEFAULT_WORKFLOW_DRAFT,
    MAX_TIMEOUT_SECONDS,
    MIN_TIMEOUT_SECONDS,
    SAMPLE_PROJECTS,
    SUPPORTED_PYTHON_VERSIONS,
)
from workflow_sandbox.core.database import WorkflowDatabase
from workflow_sandbox.core.diagnosis import diagnose_output
from workflow_sandbox.core.dockerfile import generate_dockerfile
from workflow_sandbox.core.models import WorkflowTemplate
from workflow_sandbox.core.runner import DockerUnavailableError, run_workflow_in_docker
from workflow_sandbox.core.validation import validate_workflow_template


def main() -> None:
    st.set_page_config(page_title="Workflow Sandbox", layout="wide")
    st.title("Python Workflow Sandbox")
    ensure_dashboard_state()

    database = WorkflowDatabase(DATABASE_PATH)
    database.initialise()

    page = st.sidebar.radio(
        "View",
        [
            "Run Workflow",
            "Workflow Template",
            "Dockerfile Preview",
            "Diagnose Logs",
            "Run History",
        ],
    )

    if page == "Run Workflow":
        render_run_page(database)
    elif page == "Workflow Template":
        render_template_page(database)
    elif page == "Dockerfile Preview":
        render_dockerfile_page()
    elif page == "Diagnose Logs":
        render_diagnosis_page()
    else:
        render_history_page(database)


def build_template_from_form(form_key: str) -> WorkflowTemplate:
    """Collect repeated workflow fields in one place to avoid duplicated UI logic."""

    # Streamlit reruns the script when changing pages. The permanent
    # workflow_draft values keep the user's current inputs.
    draft = st.session_state["workflow_draft"]

    name = st.text_input(
        "Workflow name",
        draft["name"],
        key=f"{form_key}-name",
    )
    python_version = st.selectbox(
        "Python version",
        SUPPORTED_PYTHON_VERSIONS,
        index=SUPPORTED_PYTHON_VERSIONS.index(draft["python_version"]),
        key=f"{form_key}-python",
    )
    requirements_file = st.text_input(
        "Requirements file",
        draft["requirements_file"],
        key=f"{form_key}-requirements",
    )
    commands_text = st.text_area(
        "Commands",
        draft["commands_text"],
        key=f"{form_key}-commands",
    )
    env_text = st.text_area(
        "Environment variables",
        draft["env_text"],
        key=f"{form_key}-env",
    )
    timeout_seconds = st.number_input(
        "Timeout seconds",
        min_value=MIN_TIMEOUT_SECONDS,
        max_value=MAX_TIMEOUT_SECONDS,
        value=draft["timeout_seconds"],
        key=f"{form_key}-timeout",
    )

    st.session_state["workflow_draft"] = {
        "name": name,
        "python_version": python_version,
        "requirements_file": requirements_file,
        "commands_text": commands_text,
        "env_text": env_text,
        "timeout_seconds": int(timeout_seconds),
        "sample_project": st.session_state["workflow_draft"]["sample_project"],
    }

    commands = [line.strip() for line in commands_text.splitlines() if line.strip()]
    env_vars = parse_env_vars(env_text)

    return WorkflowTemplate(
        name=name,
        python_version=python_version,
        commands=commands,
        requirements_file=requirements_file,
        env_vars=env_vars,
        timeout_seconds=int(timeout_seconds),
    )


def ensure_dashboard_state() -> None:
    """Create page-independent draft state for Streamlit reruns."""

    if "workflow_draft" not in st.session_state:
        st.session_state["workflow_draft"] = DEFAULT_WORKFLOW_DRAFT.copy()
    if "diagnosis_draft" not in st.session_state:
        st.session_state["diagnosis_draft"] = DEFAULT_DIAGNOSIS_DRAFT.copy()


def parse_env_vars(text: str) -> dict[str, str]:
    """Parse key=value lines because the early dashboard uses simple text inputs."""

    env_vars: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_vars[key.strip()] = value.strip()
    return env_vars


def render_template_page(database: WorkflowDatabase) -> None:
    st.header("Workflow Template")
    st.caption("Create a reusable Python workflow definition.")

    template = build_template_from_form("template")
    errors = validate_workflow_template(template)

    # The dashboard validates before saving so the database does not allow
    # malformed workflow templates.
    if errors:
        for error in errors:
            st.error(error)
    else:
        st.success("Template is valid.")

    if st.button("Save template", disabled=bool(errors)):
        database.save_template(template)
        st.success(f"Saved template: {template.name}")

    with st.expander("Stored templates"):
        templates = database.list_templates()
        if not templates:
            st.info("No templates saved yet.")
        else:
            st.table(
                [
                    {
                        "name": item.name,
                        "python": item.python_version,
                        "commands": len(item.commands),
                        "timeout": item.timeout_seconds,
                    }
                    for item in templates
                ]
            )


def render_dockerfile_page() -> None:
    st.header("Dockerfile Preview")
    st.caption("Preview the container definition before workflow execution is added.")

    template = build_template_from_form("dockerfile")
    errors = validate_workflow_template(template)

    if errors:
        for error in errors:
            st.error(error)
        return

    # Previewing the generated Dockerfile to audit before running
    st.code(generate_dockerfile(template), language="dockerfile")


def render_run_page(database: WorkflowDatabase) -> None:
    st.header("Run Workflow")
    st.caption("Execute a synthetic Python project inside the Docker sandbox.")

    draft = st.session_state["workflow_draft"]
    project_names = list(SAMPLE_PROJECTS)
    project_label = st.selectbox(
        "Sample project",
        project_names,
        index=project_names.index(draft["sample_project"]),
    )
    st.session_state["workflow_draft"]["sample_project"] = project_label

    project_path = SAMPLE_PROJECTS[project_label]
    template = build_template_from_form("run")
    errors = validate_workflow_template(template)

    if errors:
        for error in errors:
            st.error(error)
    else:
        st.success("Workflow is ready to run.")

    # The UI shows the project path so the execution input is transparent.
    st.write(f"Project path: `{project_path}`")

    if st.button("Run workflow", disabled=bool(errors)):
        try:
            with st.spinner("Building container and running workflow..."):
                run, findings = run_workflow_in_docker(template, project_path)
        except DockerUnavailableError as error:
            st.error(str(error))
            return
        except ValueError as error:
            st.error(str(error))
            return

        # Persisting immediately after execution means the history dashboard can
        # show both successful and failed runs. That is important because failed
        # runs are the evidence needed for support triage.
        run_id = database.save_run(run, findings)

        st.subheader(f"Run #{run_id}")
        left, middle, right = st.columns(3)
        left.metric("Status", run.status.value)
        middle.metric("Exit code", "None" if run.exit_code is None else run.exit_code)
        right.metric("Duration", f"{run.duration_seconds:.2f}s")

        with st.expander("stdout"):
            st.code(run.stdout or "(empty)")
        with st.expander("stderr"):
            st.code(run.stderr or "(empty)")

        if findings:
            st.subheader("Findings")
            for finding in findings:
                st.warning(f"{finding.category}: {finding.message}")
                st.info(finding.suggested_fix)
        else:
            st.success("No findings were generated.")


def render_diagnosis_page() -> None:
    st.header("Diagnose Logs")
    st.caption("Paste workflow output to test the rule-based diagnosis engine.")

    diagnosis_draft = st.session_state["diagnosis_draft"]
    exit_code = st.number_input("Exit code", value=diagnosis_draft["exit_code"])
    timed_out = st.checkbox("Timed out", value=diagnosis_draft["timed_out"])
    stdout = st.text_area("stdout", diagnosis_draft["stdout"])
    # Just for demo purposes
    stderr = st.text_area(
        "stderr",
        diagnosis_draft["stderr"],
    )
    st.session_state["diagnosis_draft"] = {
        "exit_code": int(exit_code),
        "timed_out": timed_out,
        "stdout": stdout,
        "stderr": stderr,
    }

    findings = diagnose_output(
        stdout=stdout,
        stderr=stderr,
        exit_code=int(exit_code),
        timed_out=timed_out,
    )

    if not findings:
        st.success("No findings detected.")
        return

    for finding in findings:
        st.subheader(finding.category.replace("_", " ").title())
        st.write(f"Severity: {finding.severity.value}")
        st.write(finding.message)
        st.info(finding.suggested_fix)


def render_history_page(database: WorkflowDatabase) -> None:
    st.header("Run History")
    st.caption("Stored workflow runs will appear here after execution is connected.")

    runs = database.list_runs()
    if not runs:
        st.info("No workflow runs have been saved yet.")
        return

    # The history view is table based so repeated failures can be
    # scanned quickly by a stretched support team.
    st.table(
        [
            {
                "workflow": run.workflow_name,
                "status": run.status.value,
                "exit_code": run.exit_code,
                "duration": run.duration_seconds,
            }
            for run in runs
        ]
    )


if __name__ == "__main__":
    main()
