"""Logging helpers."""
import logging
import re

_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
REDACTED = "<uuid>"


def _scrub(value):
    return _UUID.sub(REDACTED, value) if isinstance(value, str) else value


class RedactUUIDs(logging.Filter):
    """Strip UUIDs from log records.

    Django's request loggers write the request path for every 4xx/5xx, and an
    anonymous conversation's UUID is its bearer key, so it must not reach logs.
    Scrubs both the message template and its args.
    """

    def filter(self, record):
        record.msg = _scrub(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_scrub(a) for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: _scrub(v) for k, v in record.args.items()}
        return True
