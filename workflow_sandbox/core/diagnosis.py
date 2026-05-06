"""Failure diagnosis engine for workflow output."""

import json
import re

from workflow_sandbox.config import DIAGNOSIS_RULES_PATH
from workflow_sandbox.core.models import Finding, Severity


def load_diagnosis_rules() -> list[dict]:
    """Load configurable diagnosis rules from JSON."""

    return json.loads(DIAGNOSIS_RULES_PATH.read_text(encoding="utf-8"))


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

    # Rules are data-driven rather than hardcoded so new known failures can be
    # added without changing the diagnosis engine. The code still owns timeout
    # and unknown-failure fallbacks because those depend on execution metadata.
    for rule in load_diagnosis_rules():
        finding = _apply_rule(rule, output)
        if finding:
            findings.append(finding)

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


def _apply_rule(rule: dict, output: str) -> Finding | None:
    match = re.search(rule["pattern"], output)
    if not match:
        return None

    values = _build_template_values(rule, match)
    return Finding(
        category=rule["category"],
        severity=Severity(rule["severity"]),
        message=rule["message"].format(**values),
        suggested_fix=rule["suggested_fix"].format(**values),
    )


def _build_template_values(rule: dict, match: re.Match) -> dict[str, str]:
    values = {
        group_name: match.group(index)
        for index, group_name in enumerate(rule.get("groups", []), start=1)
    }

    # Import names do not always match package names. Keeping this mapping in
    # the rule file makes remediation advice configurable but still deterministic.
    if "module_name" in values:
        package_hints = rule.get("package_hints", {})
        values["package_name"] = package_hints.get(
            values["module_name"],
            values["module_name"],
        )

    return values
