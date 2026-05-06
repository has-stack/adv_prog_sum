"""Streamlit dashboard for the workflow sandbox prototype."""

import streamlit as st

from workflow_sandbox.config import (
    APP_NAME,
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
from workflow_sandbox.frontend.dashboard_logging import (
    capture_dashboard_logs,
    clear_dashboard_logs,
)
from workflow_sandbox.logging_config import configure_logging

configure_logging()

RUN_FORM_KEYS = {
    "name": "run-name",
    "python_version": "run-python",
    "requirements_file": "run-requirements",
    "commands_text": "run-commands",
    "env_text": "run-env",
    "timeout_seconds": "run-timeout",
}


def main() -> None:
    st.set_page_config(page_title=APP_NAME, layout="wide")
    st.title(APP_NAME)
    ensure_dashboard_state()

    database = WorkflowDatabase(DATABASE_PATH)
    database.initialise()

    page = st.sidebar.radio(
        "View",
        [
            "Run Check",
            "Workflow Templates",
            "Container Preview",
            "Log Diagnosis",
            "Run History",
        ],
    )

    if page == "Run Check":
        render_run_page(database)
    elif page == "Workflow Templates":
        render_template_page(database)
    elif page == "Container Preview":
        render_dockerfile_page()
    elif page == "Log Diagnosis":
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
    if "dashboard_logs" not in st.session_state:
        st.session_state["dashboard_logs"] = []


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


def format_env_vars(env_vars: dict[str, str]) -> str:
    """Format environment variables for the dashboard text area."""

    return "\n".join(f"{key}={value}" for key, value in sorted(env_vars.items()))


def workflow_template_to_draft(
    template: WorkflowTemplate,
    sample_project: str,
) -> dict:
    """Convert a saved workflow template into dashboard draft state."""

    return {
        "name": template.name,
        "python_version": template.python_version,
        "requirements_file": template.requirements_file,
        "commands_text": "\n".join(template.commands),
        "env_text": format_env_vars(template.env_vars),
        "timeout_seconds": template.timeout_seconds,
        "sample_project": sample_project,
    }


def load_template_into_run_form(template: WorkflowTemplate) -> None:
    """Load a saved template into the run form without changing the project."""

    sample_project = st.session_state["workflow_draft"]["sample_project"]
    draft = workflow_template_to_draft(template, sample_project)
    st.session_state["workflow_draft"] = draft

    # Streamlit keeps widget values under their explicit keys. Updating only
    # workflow_draft would not refresh already-rendered run form widgets.
    for draft_key, widget_key in RUN_FORM_KEYS.items():
        st.session_state[widget_key] = draft[draft_key]


def render_template_page(database: WorkflowDatabase) -> None:
    st.header("Workflow Templates")
    st.caption("Create reusable environment checks for different projects.")

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
    st.header("Container Preview")
    st.caption("Inspect the generated Dockerfile before running the check.")

    template = build_template_from_form("dockerfile")
    errors = validate_workflow_template(template)

    if errors:
        for error in errors:
            st.error(error)
        return

    # Previewing the generated Dockerfile to audit before running
    st.code(generate_dockerfile(template), language="dockerfile")


def render_run_page(database: WorkflowDatabase) -> None:
    st.header("Run Check")
    st.caption(
        "Run a workflow template against a selected project to detect environment drift."
    )

    draft = st.session_state["workflow_draft"]
    project_names = list(SAMPLE_PROJECTS)
    project_label = st.selectbox(
        "Sample project",
        project_names,
        index=project_names.index(draft["sample_project"]),
    )
    st.session_state["workflow_draft"]["sample_project"] = project_label

    project_path = SAMPLE_PROJECTS[project_label]
    render_saved_template_loader(database)

    template = build_template_from_form("run")
    errors = validate_workflow_template(template)

    if errors:
        for error in errors:
            st.error(error)
    else:
        st.success("Workflow is ready to run.")

    # The UI shows the project path so the execution input is transparent.
    st.write(f"Selected project path: `{project_path}`")

    if st.button("Run check", disabled=bool(errors)):
        logs = st.session_state["dashboard_logs"]
        clear_dashboard_logs(logs)
        try:
            with capture_dashboard_logs(logs):
                with st.spinner("Building container and running workflow..."):
                    run, findings = run_workflow_in_docker(template, project_path)
                # Capture database persistence logs in the same dashboard view
                # because save failures are part of the execution lifecycle.
                run_id = database.save_run(run, findings)
        except DockerUnavailableError as error:
            st.error(str(error))
        except ValueError as error:
            st.error(str(error))
        else:
            st.subheader(f"Run #{run_id}")
            left, middle, right = st.columns(3)
            left.metric("Status", run.status.value)
            middle.metric(
                "Exit code",
                "None" if run.exit_code is None else run.exit_code,
            )
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

    render_debug_logs(st.session_state["dashboard_logs"])


def render_saved_template_loader(database: WorkflowDatabase) -> None:
    templates = database.list_templates()
    if not templates:
        st.info("No saved workflow templates yet.")
        return

    templates_by_name = {template.name: template for template in templates}
    selected_name = st.selectbox(
        "Saved workflow template",
        list(templates_by_name),
        key="run-template-loader",
    )

    if st.button("Load template"):
        load_template_into_run_form(templates_by_name[selected_name])
        st.success(f"Loaded template: {selected_name}")


def render_debug_logs(logs: list[str]) -> None:
    if not logs:
        return

    with st.expander("Debug logs"):
        st.code("\n".join(logs))


def render_diagnosis_page() -> None:
    st.header("Log Diagnosis")
    st.caption("Paste workflow output to classify failures without running Docker.")

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
    st.caption("Review previous checks and compare repeated failures.")

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
