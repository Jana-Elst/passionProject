"""Persistent call/event logging for the phone system.

Writes timestamped, human-readable log lines to both the console and a
daily-rotating log file, so what happened with the phones can be reviewed
after the fact.
"""

import logging
import logging.handlers
import os

LOGGER_NAME = "phone_system"

_logger = None


def get_logger(log_dir: str = "logs") -> logging.Logger:
    """Returns the shared phone_system logger, configuring it on first call."""
    global _logger
    if _logger is not None:
        return _logger

    os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.handlers.TimedRotatingFileHandler(
        os.path.join(log_dir, "phone_system.log"),
        when="midnight",
        backupCount=0,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    _logger = logger
    return _logger
