"""Root-run, bounded local secret files for non-Azure Private Agent hosts."""

import os
import re
import stat
from pathlib import Path

from .errors import FrameworkError
from .security import Secret

NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_SECRET_BYTES = 65536


class LocalFileSecretProvider:
    """Read one secret per file without following links or exposing values."""

    def __init__(self, directory):
        try:
            path = Path(directory) if isinstance(directory, str) else None
        except ValueError:
            path = None
        if path is None or not path.is_absolute() or ".." in path.parts:
            raise FrameworkError("CONFIG_INVALID")
        self.directory = path
        self._active = []

    def _check_directory(self):
        current = Path("/")
        uid = os.geteuid()
        try:
            for part in self.directory.parts[1:]:
                current /= part
                info = current.lstat()
                if (
                    not stat.S_ISDIR(info.st_mode)
                    or info.st_uid not in {0, uid}
                    or info.st_mode & 0o022
                ):
                    raise FrameworkError("LOCAL_SECRET_UNSAFE")
            info = self.directory.lstat()
            if info.st_mode & 0o077 or info.st_mode & 0o500 != 0o500:
                raise FrameworkError("LOCAL_SECRET_UNSAFE")
        except OSError:
            raise FrameworkError("LOCAL_SECRET_UNSAFE") from None

    def resolve(self, reference):
        if not isinstance(reference, dict) or reference.get("provider") != "local-file":
            raise FrameworkError("CONFIG_INVALID")
        name = reference.get("reference")
        if not isinstance(name, str) or not NAME.fullmatch(name) or "version" in reference:
            raise FrameworkError("CONFIG_INVALID")
        self._check_directory()
        path = self.directory / name
        try:
            before = path.lstat()
        except FileNotFoundError:
            raise FrameworkError("LOCAL_SECRET_NOT_FOUND") from None
        except OSError:
            raise FrameworkError("LOCAL_SECRET_UNSAFE") from None
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or before.st_mode & 0o077
            or not before.st_mode & stat.S_IRUSR
            or before.st_nlink != 1
            or before.st_size > MAX_SECRET_BYTES
        ):
            raise FrameworkError("LOCAL_SECRET_UNSAFE")
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            fd = os.open(path, flags)
            try:
                after = os.fstat(fd)
                if (
                    (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
                    or not stat.S_ISREG(after.st_mode)
                    or after.st_uid != os.geteuid()
                    or after.st_mode & 0o077
                    or not after.st_mode & stat.S_IRUSR
                    or after.st_nlink != 1
                    or after.st_size > MAX_SECRET_BYTES
                ):
                    raise FrameworkError("LOCAL_SECRET_UNSAFE")
                chunks = []
                total = 0
                while block := os.read(fd, min(8192, MAX_SECRET_BYTES + 1 - total)):
                    chunks.append(block)
                    total += len(block)
                    if total > MAX_SECRET_BYTES:
                        raise FrameworkError("LOCAL_SECRET_UNSAFE")
                raw = b"".join(chunks)
            finally:
                os.close(fd)
        except OSError:
            raise FrameworkError("LOCAL_SECRET_UNSAFE") from None
        if not raw:
            raise FrameworkError("LOCAL_SECRET_EMPTY")
        if len(raw) > MAX_SECRET_BYTES:
            raise FrameworkError("LOCAL_SECRET_UNSAFE")
        try:
            value = raw.decode("utf-8")
        except UnicodeError:
            raise FrameworkError("LOCAL_SECRET_INVALID") from None
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise FrameworkError("LOCAL_SECRET_INVALID")
        secret = Secret(value)
        self._active.append(secret)
        return secret

    def clear(self):
        for secret in self._active:
            secret.clear()
        self._active.clear()
