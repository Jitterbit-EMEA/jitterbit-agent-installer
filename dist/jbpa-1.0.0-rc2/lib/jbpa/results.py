"""Guarded Phase 1 state and safe explicit result artifacts."""

import json
import os
import stat
import uuid
from pathlib import Path

from .config import validate_schema
from .errors import FrameworkError

TRANSITIONS = {
    "INITIALIZED": {"CONFIG_LOADED"},
    "CONFIG_LOADED": {"CONFIG_VALIDATED"},
    "CONFIG_VALIDATED": {"VERSION_RESOLVED"},
    "VERSION_RESOLVED": {"PLATFORM_DETECTED"},
    "PLATFORM_DETECTED": {"PREFLIGHT_COMPLETE"},
    "PREFLIGHT_COMPLETE": {"PLANNED", "VALIDATED", "DIAGNOSTICS", "BLOCKED"},
}
# These are reserved vocabulary only, never legal Phase 1 destinations.
FUTURE_STATES = (
    "INSTALLER_DOWNLOADED",
    "AGENT_INSTALLED",
    "AGENT_CONFIGURED",
    "AGENT_STARTED",
    "REGISTRATION_PENDING",
    "REGISTERED",
    "HEALTH_VALIDATED",
    "COMPLETE",
)


class State:
    def __init__(self):
        self.history = ["INITIALIZED"]

    @property
    def current(self):
        return self.history[-1]

    def advance(self, target):
        if target != "FAILED" and target not in TRANSITIONS.get(self.current, set()):
            raise FrameworkError("INTERNAL_ERROR")
        if self.current in {"FAILED", "BLOCKED", "PLANNED", "VALIDATED", "DIAGNOSTICS"}:
            raise FrameworkError("INTERNAL_ERROR")
        self.history.append(target)


def encode(result):
    validate_schema(result, "result")
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def write_result(destination, text):
    """Create a new 0600 file atomically, never overwrite or follow symlinks."""
    path = Path(os.path.abspath(destination))
    fd = None
    temporary = ".jbpa-" + uuid.uuid4().hex
    created = False
    try:
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        for part in path.parent.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
            st = os.fstat(fd)
            if st.st_mode & 0o022 and not st.st_mode & stat.S_ISVTX:
                raise FrameworkError("RESULT_WRITE_FAILED")
        parent = os.fstat(fd)
        if parent.st_uid != os.getuid() or parent.st_mode & 0o022:
            raise FrameworkError("RESULT_WRITE_FAILED")
        out = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd
        )
        created = True
        with os.fdopen(out, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        # link() fails if the destination already exists, including symlinks.
        os.link(temporary, path.name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
    except (OSError, ValueError) as exc:
        raise FrameworkError("RESULT_WRITE_FAILED") from exc
    finally:
        if fd is not None:
            if created:
                os.unlink(temporary, dir_fd=fd)
            os.close(fd)
