"""Capture application logs for display in the Streamlit dashboard."""

import logging
from collections.abc import MutableSequence
from contextlib import contextmanager
from typing import Iterator

from workflow_sandbox.config import DASHBOARD_LOG_LIMIT, LOG_FORMAT


class DashboardLogHandler(logging.Handler):
    """Logging handler that appends formatted records to a dashboard buffer."""

    def __init__(
        self,
        records: MutableSequence[str],
        max_records: int = DASHBOARD_LOG_LIMIT,
    ):
        super().__init__(level=logging.INFO)
        self.records = records
        self.max_records = max_records
        self.setFormatter(logging.Formatter(LOG_FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.records.append(self.format(record))
            overflow = len(self.records) - self.max_records
            if overflow > 0:
                del self.records[:overflow]
        except Exception:
            self.handleError(record)


@contextmanager
def capture_dashboard_logs(
    records: MutableSequence[str],
    logger_name: str = "workflow_sandbox",
    max_records: int = DASHBOARD_LOG_LIMIT,
) -> Iterator[None]:
    """Capture workflow-sandbox log records for the duration of a block."""

    logger = logging.getLogger(logger_name)
    handler = DashboardLogHandler(records, max_records=max_records)
    previous_level = logger.level

    # Streamlit reruns the script often, so the handler is attached only for
    # the active workflow run and removed immediately afterwards.
    if previous_level == logging.NOTSET or previous_level > logging.INFO:
        logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


def clear_dashboard_logs(records: MutableSequence[str]) -> None:
    """Clear logs in place so existing handlers keep the same buffer object."""

    del records[:]
