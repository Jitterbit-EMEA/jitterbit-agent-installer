"""One private, schema-validated JSON document for customer registration."""

import json
from pathlib import Path

from .config import validate_schema
from .errors import FrameworkError
from .local_secrets import LocalFileSecretProvider
from .security import Secret

REFERENCES = {
    "harmony.registrationToken": ("harmony", "registrationToken"),
    "harmony.cloudUrl": ("harmony", "cloudUrl"),
    "harmony.agentGroupId": ("harmony", "agentGroupId"),
    "agent.namePrefix": ("agent", "namePrefix"),
    "registration.deregisterOnDrainstop": ("registration", "deregisterOnDrainstop"),
    "registration.retryCount": ("registration", "retryCount"),
    "registration.retryIntervalSeconds": ("registration", "retryIntervalSeconds"),
}


def _unique_pairs(pairs):
    values = {}
    for key, value in pairs:
        if key in values:
            raise FrameworkError("CONFIG_INVALID")
        values[key] = value
    return values


def parse_credentials(raw):
    try:
        data = json.loads(raw, object_pairs_hook=_unique_pairs)
    except (TypeError, ValueError, RecursionError) as exc:
        raise FrameworkError("CONFIG_INVALID") from exc
    validate_schema(data, "customer-credentials")
    return data


class JsonFileSecretProvider:
    """Resolve only named fields from a root-owned 0600 JSON file."""

    def __init__(self, path):
        self.path = Path(path)
        if not self.path.is_absolute() or ".." in self.path.parts:
            raise FrameworkError("CONFIG_INVALID")
        self._files = LocalFileSecretProvider(str(self.path.parent))
        self._active = []

    def resolve(self, reference):
        if not isinstance(reference, dict) or reference.get("provider") != "local-json":
            raise FrameworkError("CONFIG_INVALID")
        key = reference.get("reference")
        if key not in REFERENCES:
            raise FrameworkError("CONFIG_INVALID")
        raw = self._files.resolve(
            {"provider": "local-file", "reference": self.path.name}, allow_multiline=True
        )
        try:
            data = parse_credentials(raw.reveal())
        finally:
            raw.clear()
            self._files.clear()
        parent, child = REFERENCES[key]
        value = data[parent][child]
        secret = Secret(str(value).lower() if isinstance(value, bool) else str(value))
        self._active.append(secret)
        return secret

    def clear(self):
        self._files.clear()
        for secret in self._active:
            secret.clear()
        self._active.clear()
