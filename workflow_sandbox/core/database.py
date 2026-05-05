"""SQLite database access for workflow templates, runs and findings."""

import json
import sqlite3
from pathlib import Path
from workflow_sandbox.core.models import (
    Finding,
    RunStatus,
    Severity,
    WorkflowRun,
    WorkflowTemplate,
)


class WorkflowDatabase:
    """Small SQLite wrapper for workflow sandbox data."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def initialise(self) -> None:
        """Create database tables if they do not already exist."""

        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS workflow_templates (
                    name TEXT PRIMARY KEY,
                    python_version TEXT NOT NULL,
                    commands_json TEXT NOT NULL,
                    requirements_file TEXT NOT NULL,
                    env_vars_json TEXT NOT NULL,
                    timeout_seconds INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS workflow_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    exit_code INTEGER,
                    stdout TEXT NOT NULL,
                    stderr TEXT NOT NULL,
                    duration_seconds REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    suggested_fix TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES workflow_runs(id)
                );
                """)

    def save_template(self, template: WorkflowTemplate) -> None:
        """Store or replace a workflow template."""

        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO workflow_templates
                (name, python_version, commands_json, requirements_file, env_vars_json, timeout_seconds)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    template.name,
                    template.python_version,
                    json.dumps(template.commands),
                    template.requirements_file,
                    json.dumps(template.env_vars, sort_keys=True),
                    template.timeout_seconds,
                ),
            )

    def list_templates(self) -> list[WorkflowTemplate]:
        """Return stored workflow templates by name."""

        with self._connect() as connection:
            rows = connection.execute("""
                SELECT name, python_version, commands_json, requirements_file, env_vars_json, timeout_seconds
                FROM workflow_templates
                ORDER BY name
                """).fetchall()

        return [
            WorkflowTemplate(
                name=row["name"],
                python_version=row["python_version"],
                commands=json.loads(row["commands_json"]),
                requirements_file=row["requirements_file"],
                env_vars=json.loads(row["env_vars_json"]),
                timeout_seconds=row["timeout_seconds"],
            )
            for row in rows
        ]

    def save_run(self, run: WorkflowRun, findings: list[Finding] | None = None) -> int:
        """Store a workflow run and optional findings."""

        findings = findings or []
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO workflow_runs
                (workflow_name, status, exit_code, stdout, stderr, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run.workflow_name,
                    run.status.value,
                    run.exit_code,
                    run.stdout,
                    run.stderr,
                    run.duration_seconds,
                ),
            )
            run_id = int(cursor.lastrowid)

            for finding in findings:
                connection.execute(
                    """
                    INSERT INTO findings
                    (run_id, category, severity, message, suggested_fix)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        finding.category,
                        finding.severity.value,
                        finding.message,
                        finding.suggested_fix,
                    ),
                )

        return run_id

    def list_runs(self) -> list[WorkflowRun]:
        """Return stored workflow runs newest first."""

        with self._connect() as connection:
            rows = connection.execute("""
                SELECT id, workflow_name, status, exit_code, stdout, stderr, duration_seconds
                FROM workflow_runs
                ORDER BY id DESC
                """).fetchall()

        return [
            WorkflowRun(
                workflow_name=row["workflow_name"],
                status=RunStatus(row["status"]),
                exit_code=row["exit_code"],
                stdout=row["stdout"],
                stderr=row["stderr"],
                duration_seconds=row["duration_seconds"],
            )
            for row in rows
        ]

    def list_findings_for_run(self, run_id: int) -> list[Finding]:
        """Return findings for a stored run."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT category, severity, message, suggested_fix
                FROM findings
                WHERE run_id = ?
                ORDER BY id
                """,
                (run_id,),
            ).fetchall()

        return [
            Finding(
                category=row["category"],
                severity=Severity(row["severity"]),
                message=row["message"],
                suggested_fix=row["suggested_fix"],
            )
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection
