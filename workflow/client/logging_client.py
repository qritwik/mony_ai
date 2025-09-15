import logging
import sys
from datetime import datetime


class MonyLogger:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.logger = logging.getLogger(f"user-{user_id}")
        if not self.logger.handlers:  # Prevent duplicate handlers
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                fmt="%(asctime)s | user_id=%(user_id)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _log(self, level, msg, *args, **kwargs):
        if self.logger.isEnabledFor(level):
            extra = {"user_id": self.user_id}
            self.logger.log(level, msg, *args, extra=extra, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._log(logging.ERROR, msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self._log(logging.DEBUG, msg, *args, **kwargs)
