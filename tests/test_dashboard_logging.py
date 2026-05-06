import logging

from workflow_sandbox.frontend.dashboard_logging import (
    capture_dashboard_logs,
    clear_dashboard_logs,
)


def test_capture_dashboard_logs_records_messages_for_block_only():
    records: list[str] = []
    logger = logging.getLogger("workflow_sandbox.tests.dashboard_logging")

    with capture_dashboard_logs(records, logger_name=logger.name):
        logger.info("Docker build started")

    logger.info("Message after capture")

    assert any("Docker build started" in item for item in records)
    assert not any("Message after capture" in item for item in records)


def test_capture_dashboard_logs_keeps_bounded_history():
    records: list[str] = []
    logger = logging.getLogger("workflow_sandbox.tests.dashboard_limit")

    with capture_dashboard_logs(records, logger_name=logger.name, max_records=2):
        logger.info("first message")
        logger.info("second message")
        logger.info("third message")

    assert len(records) == 2
    assert "first message" not in "\n".join(records)
    assert "second message" in records[0]
    assert "third message" in records[1]


def test_clear_dashboard_logs_preserves_buffer_object():
    records = ["old message"]
    original_id = id(records)

    clear_dashboard_logs(records)

    assert records == []
    assert id(records) == original_id
