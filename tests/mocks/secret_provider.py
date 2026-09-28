"""Test-only in-memory provider; not importable by the production provider registry."""

from jbpa.errors import FrameworkError
from jbpa.security import Secret


class MockSecretProvider:
    def __init__(self, values, redactor):
        self.values = values.copy()
        self.redactor = redactor
        self.resolved = []

    def resolve(self, reference):
        if reference["reference"] not in self.values:
            raise FrameworkError("SECRET_PROVIDER_FAILED")
        secret = Secret(self.values[reference["reference"]])
        self.redactor.register(secret)
        self.resolved.append(secret)
        return secret

    def clear(self):
        for secret in self.resolved:
            secret.clear()
        self.values.clear()
