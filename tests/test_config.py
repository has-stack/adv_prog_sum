from workflow_sandbox import config


def test_default_workflow_draft_matches_supported_versions():
    assert config.DEFAULT_WORKFLOW_DRAFT["python_version"] in config.SUPPORTED_PYTHON_VERSIONS
    assert config.DEFAULT_WORKFLOW_DRAFT["timeout_seconds"] == config.DEFAULT_TIMEOUT_SECONDS


def test_sample_project_config_contains_expected_demo_projects():
    assert "Passing project" in config.SAMPLE_PROJECTS
    assert "Missing dependency" in config.SAMPLE_PROJECTS
    assert "Missing environment variable" in config.SAMPLE_PROJECTS
    assert "Failing tests" in config.SAMPLE_PROJECTS

