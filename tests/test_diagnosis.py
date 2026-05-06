from workflow_sandbox.core.diagnosis import diagnose_output, load_diagnosis_rules


def test_diagnosis_rules_load_from_config_file():
    rules = load_diagnosis_rules()

    assert any(rule["category"] == "missing_dependency" for rule in rules)
    assert any(rule["category"] == "test_failure" for rule in rules)


def test_diagnosis_detects_missing_dependency_and_package_hint():
    findings = diagnose_output(
        stderr="ModuleNotFoundError: No module named 'yaml'",
        exit_code=1,
    )

    assert findings[0].category == "missing_dependency"
    assert "pyyaml" in findings[0].suggested_fix


def test_diagnosis_detects_missing_environment_variable():
    findings = diagnose_output(
        stderr="KeyError: 'SMMU_TEST_ROOT'",
        exit_code=1,
    )

    assert findings[0].category == "missing_environment_variable"
    assert "SMMU_TEST_ROOT" in findings[0].suggested_fix


def test_diagnosis_detects_test_failure():
    findings = diagnose_output(
        stderr="AssertionError: 1 != 2\nFAILED tests/test_calculator.py",
        exit_code=1,
    )

    assert any(finding.category == "test_failure" for finding in findings)


def test_diagnosis_returns_unknown_for_unmatched_non_zero_exit():
    findings = diagnose_output(stderr="unexpected failure", exit_code=2)

    assert findings[0].category == "unknown_failure"


def test_diagnosis_detects_timeout():
    findings = diagnose_output(timed_out=True, exit_code=None)

    assert findings[0].category == "timeout"
