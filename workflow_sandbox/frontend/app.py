"""Streamlit dashboard for the workflow sandbox prototype."""

import streamlit as st
from pathlib import Path
from workflow_sandbox.core.database import WorkflowDatabase
from workflow_sandbox.core.diagnosis import diagnose_output
from workflow_sandbox.core.dockerfile import generate_dockerfile
from workflow_sandbox.core.models import WorkflowTemplate
from workflow_sandbox.core.runner import DockerUnavailableError, run_workflow_in_docker
from workflow_sandbox.core.validation import validate_workflow_template

DATABASE_PATH = Path("workflow_sandbox.db")
# Dummy workflows
SAMPLE_PROJECTS = {
    "Passing project": Path("sample_projects/passing_project"),
    "Missing dependency": Path("sample_projects/missing_dependency"),
    "Missing environment variable": Path("sample_projects/missing_env_var"),
    "Failing tests": Path("sample_projects/failing_tests"),
}


def main() -> None:
    st.set_page_config(page_title="Workflow Sandbox", layout="wide")
    st.title("Python Workflow Sandbox")

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

    name = st.text_input("Workflow name", "python-smoke-test", key=f"{form_key}-name")
    python_version = st.selectbox(
        "Python version",
        ["3.8", "3.9", "3.10", "3.11", "3.12"],
        index=3,
        key=f"{form_key}-python",
    )
    requirements_file = st.text_input(
        "Requirements file",
        "requirements.txt",
        key=f"{form_key}-requirements",
    )
    commands_text = st.text_area(
        "Commands",
        "python -m unittest discover -s tests",
        key=f"{form_key}-commands",
    )
    env_text = st.text_area(
        "Environment variables",
        "PYTHONPATH=/workspace",
        key=f"{form_key}-env",
    )
    timeout_seconds = st.number_input(
        "Timeout seconds",
        min_value=5,
        max_value=1800,
        value=120,
        key=f"{form_key}-timeout",
    )

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

    project_label = st.selectbox("Sample project", list(SAMPLE_PROJECTS))
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

    exit_code = st.number_input("Exit code", value=1)
    timed_out = st.checkbox("Timed out")
    stdout = st.text_area("stdout", "")
    # Just for demo purposes
    stderr = st.text_area(
        "stderr",
        "ModuleNotFoundError: No module named 'yaml'",
    )

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
