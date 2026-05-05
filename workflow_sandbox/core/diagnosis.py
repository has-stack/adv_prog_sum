"""Simple failure diagnosis rules for workflow output."""

import re

from workflow_sandbox.core.models import Finding, Severity

_MISSING_MODULE_PATTERN = re.compile(
    r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]"
)
_MISSING_ENV_PATTERN = re.compile(r"KeyError: ['\"]([A-Z_][A-Z0-9_]*)['\"]")
_COMMAND_NOT_FOUND_PATTERN = re.compile(r"([a-zA-Z0-9_.+-]+): not found")

_PACKAGE_HINTS = {"yaml": "pyyaml", "cv2": "opencv-python"}


def diagnose_output(
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None = None,
    timed_out: bool = False,
) -> list[Finding]:
    """Convert workflow output into diagnostic findings."""

    output = "\n".join(part for part in [stdout, stderr] if part)
    findings: list[Finding] = []

    if timed_out:
        findings.append(
            Finding(
                category="timeout",
                severity=Severity.HIGH,
                message="The workflow exceeded the configured timeout.",
                suggested_fix="Inspect long-running commands before increasing the timeout.",
            )
        )

    missing_module = _MISSING_MODULE_PATTERN.search(output)
    if missing_module:
        module_name = missing_module.group(1)
        package_name = _PACKAGE_HINTS.get(module_name, module_name)
        findings.append(
            Finding(
                category="missing_dependency",
                severity=Severity.MEDIUM,
                message=f"Python module '{module_name}' is missing from the environment.",
                suggested_fix=f"Add '{package_name}' to requirements.txt and rerun the workflow.",
            )
        )

    missing_env = _MISSING_ENV_PATTERN.search(output)
    if missing_env:
        env_name = missing_env.group(1)
        findings.append(
            Finding(
                category="missing_environment_variable",
                severity=Severity.HIGH,
                message=f"Environment variable '{env_name}' was not available during the workflow.",
                suggested_fix=f"Define '{env_name}' in the workflow template or provide a safe default.",
            )
        )

    missing_command = _COMMAND_NOT_FOUND_PATTERN.search(output)
    if missing_command:
        command_name = missing_command.group(1)
        findings.append(
            Finding(
                category="missing_system_tool",
                severity=Severity.HIGH,
                message=f"System command '{command_name}' is missing from the container.",
                suggested_fix=f"Install the package that provides '{command_name}' before running the workflow.",
            )
        )

    if "FAILED" in output or "AssertionError" in output:
        findings.append(
            Finding(
                category="test_failure",
                severity=Severity.MEDIUM,
                message="The workflow ran, but one or more functional tests failed.",
                suggested_fix="Inspect the failing assertion and compare expected behaviour with the implementation.",
            )
        )

    if not findings and exit_code not in (None, 0):
        findings.append(
            Finding(
                category="unknown_failure",
                severity=Severity.MEDIUM,
                message="The workflow failed, but no known diagnosis rule matched the output.",
                suggested_fix="Inspect the captured logs and add a new diagnosis rule if this failure recurs.",
            )
        )

    return findings
