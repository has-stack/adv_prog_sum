"""Logging setup for the workflow sandbox."""

import logging

from workflow_sandbox.config import LOG_FORMAT, LOG_LEVEL


def configure_logging(level: str = LOG_LEVEL) -> None:
    """Configure application logging using standard-library logging."""

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=LOG_FORMAT,
    )
