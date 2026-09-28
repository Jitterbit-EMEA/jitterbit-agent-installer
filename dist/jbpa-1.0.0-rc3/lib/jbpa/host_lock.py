"""One native installer run at a time on a VM."""

import fcntl
import os

from .errors import FrameworkError


class HostLock:
    def __init__(self, path="/var/lib/jbpa/bootstrap.lock"):
        self.path = path
        self.fd = None

    def __enter__(self):
        try:
            self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            raise FrameworkError("LIFECYCLE_ACTION_REQUIRED") from None
        except OSError:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            raise FrameworkError("PREFLIGHT_FAILED") from None
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None
