"""Secret wrappers and a single controlled structured log channel."""

import json
import re
from datetime import datetime, timezone


class Secret:
    """Opaque in formatting. Explicit reveal is reserved for a reviewed adapter."""

    def __init__(self, value):
        self._value = value

    def reveal(self):
        return self._value

    def clear(self):
        self._value = None

    def __repr__(self):
        return "[REDACTED]"

    __str__ = __repr__


class Redactor:
    def __init__(self):
        self._values = set()

    def register(self, secret):
        value = secret.reveal()
        if value:
            self._values.add(value)

    def clean(self, value):
        if isinstance(value, Secret):
            return "[REDACTED]"
        if isinstance(value, dict):
            return {
                self.clean(str(k)): "[REDACTED]"
                if re.search(
                    r"password|passphrase|token|credential|private.?key|authorization|provider.?response",
                    str(k),
                    re.I,
                )
                else self.clean(v)
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self.clean(v) for v in value]
        if not isinstance(value, (str, int, float, bool, type(None))):
            return "[REDACTED]"
        if not isinstance(value, str):
            return value
        for secret in sorted(self._values, key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
        value = re.sub(
            r"-----BEGIN [^-]*PRIVATE KEY-----.*?(?:-----END [^-]*PRIVATE KEY-----|$)",
            "[REDACTED]",
            value,
            flags=re.S,
        )
        value = re.sub(
            r"(?i)(?:password|passphrase|token|authorization|secret)\s*[:=]\s*[^\s,;]+",
            "[REDACTED]",
            value,
        )
        # URLs with credentials/query strings are unsafe diagnostic material.
        value = re.sub(r"https?://[^\s]*(?:\?|@)[^\s]*", "[REDACTED-URL]", value)
        return value


# Messages are fixed events: callers cannot accidentally log provider payloads or exceptions.
EVENTS = {
    "start": "Starting read-only framework action",
    "check": "Preflight check completed",
    "plan": "Deferred execution step",
    "finish": "Framework action finished",
    "failure": "Framework action failed",
}
LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}


class Logger:
    def __init__(self, stream, run_id, redactor=None, level="INFO", clock=None):
        self.stream = stream
        self.run_id = run_id
        self.redactor = redactor or Redactor()
        self.level = level
        self.clock = clock or (lambda: datetime.now(timezone.utc).isoformat())

    def event(self, level, component, event, **fields):
        if (
            level not in LEVELS
            or event not in EVENTS
            or component not in {"cli", "preflight", "plan"}
        ):
            raise ValueError("Unknown log event")
        if LEVELS[level] < LEVELS[self.level]:
            return
        # Only internally generated structured check/plan data may use these fields.
        allowed = {"checkId", "status", "errorName", "description"}
        data = {k: v for k, v in fields.items() if k in allowed}
        record = dict(
            timestamp=self.clock(),
            level=level,
            component=component,
            message=EVENTS[event],
            runId=self.run_id,
            **data,
        )
        self.stream.write(json.dumps(self.redactor.clean(record), sort_keys=True) + "\n")
