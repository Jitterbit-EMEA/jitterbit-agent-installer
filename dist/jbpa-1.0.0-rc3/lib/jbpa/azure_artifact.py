"""Private Azure Blob artifact retrieval using the VM Managed Identity."""

import os
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from .errors import FrameworkError

MAX_PACKAGE_BYTES = 2 * 1024 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class AzureBlobDownloader:
    def __init__(self, identity, opener=None, timeout=60):
        self.identity = identity
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.timeout = timeout

    def __call__(self, url, destination):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not parsed.hostname.endswith(".blob.core.windows.net")
            or not parsed.path.strip("/")
            or parsed.query
            or parsed.fragment
            or parsed.username
        ):
            raise FrameworkError("CONFIG_INVALID")
        token = self.identity.token("https://storage.azure.com/")
        request = urllib.request.Request(
            url,
            headers={"Authorization": "Bearer " + token, "x-ms-version": "2023-11-03"},
        )
        temporary = Path(destination + ".partial")
        try:
            with self.opener.open(request, timeout=self.timeout) as source:
                if source.status != 200:
                    raise FrameworkError("DOWNLOAD_FAILED")
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                try:
                    with os.fdopen(fd, "wb") as output:
                        total = 0
                        while block := source.read(1024 * 1024):
                            total += len(block)
                            if total > MAX_PACKAGE_BYTES:
                                raise FrameworkError("DOWNLOAD_FAILED")
                            output.write(block)
                        output.flush()
                        os.fsync(output.fileno())
                except Exception:
                    temporary.unlink(missing_ok=True)
                    raise
            os.replace(temporary, destination)
        except (OSError, urllib.error.URLError, TimeoutError):
            raise FrameworkError("DOWNLOAD_FAILED") from None
        finally:
            token = None
            temporary.unlink(missing_ok=True)
