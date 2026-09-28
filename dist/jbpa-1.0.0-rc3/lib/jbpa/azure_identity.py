"""Azure VM Managed Identity and Key Vault access with fixed, secret-safe errors."""

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit

from .errors import FrameworkError
from .security import Secret

IMDS_ENDPOINT = "http://169.254.169.254/metadata/identity/oauth2/token"
IMDS_API_VERSION = "2018-02-01"
KEY_VAULT_API_VERSION = "7.4"


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes


def http_request(request, timeout, *, bypass_proxy=False):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if bypass_proxy else None
    try:
        response = (
            opener.open(request, timeout=timeout)
            if opener is not None
            else urllib.request.urlopen(request, timeout=timeout)
        )
        with response:
            return HttpResponse(response.status, response.read(1024 * 1024 + 1))
    except urllib.error.HTTPError as exc:
        # Never surface response body or URL; either may contain provider data.
        return HttpResponse(exc.code, b"")
    except (urllib.error.URLError, TimeoutError):
        raise FrameworkError("KEY_VAULT_NETWORK_FAILED") from None


class ManagedIdentity:
    def __init__(self, client_id=None, transport=http_request, timeout=5):
        self.client_id = client_id
        self.transport = transport
        self.timeout = timeout

    def token(self, resource):
        parameters = {"api-version": IMDS_API_VERSION, "resource": resource}
        if self.client_id:
            parameters["client_id"] = self.client_id
        url = IMDS_ENDPOINT + "?" + urllib.parse.urlencode(parameters)
        request = urllib.request.Request(url, headers={"Metadata": "true"})
        try:
            response = self.transport(request, self.timeout, bypass_proxy=True)
        except FrameworkError as exc:
            if exc.spec.name == "KEY_VAULT_NETWORK_FAILED":
                raise FrameworkError("KEY_VAULT_NETWORK_FAILED") from None
            raise
        if response.status in (408, 429, 500, 502, 503, 504):
            raise FrameworkError("SECRET_PROVIDER_TIMEOUT")
        if response.status != 200:
            raise FrameworkError("KEY_VAULT_AUTH_FAILED")
        try:
            payload = json.loads(response.body)
            token = payload["access_token"]
            if not isinstance(token, str) or not token:
                raise ValueError
            return token
        except (KeyError, TypeError, ValueError):
            raise FrameworkError("KEY_VAULT_AUTH_FAILED") from None


class AzureKeyVaultSecretProvider:
    def __init__(self, vault_uri, identity=None, transport=http_request, timeout=10):
        parsed = urlsplit(vault_uri or "")
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not parsed.hostname.endswith(".vault.azure.net")
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or parsed.username
        ):
            raise FrameworkError("CONFIG_INVALID")
        self.vault_uri = f"https://{parsed.hostname}"
        self.identity = identity or ManagedIdentity()
        self.transport = transport
        self.timeout = timeout
        self._active = []

    def resolve(self, reference):
        if reference.get("provider") != "azure-key-vault":
            raise FrameworkError("CONFIG_INVALID")
        name = reference.get("reference")
        version = reference.get("version")
        if (
            not isinstance(name, str)
            or not name
            or any(
                character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
                for character in name
            )
        ):
            raise FrameworkError("CONFIG_INVALID")
        if version is not None and (
            not isinstance(version, str)
            or not version
            or any(character not in "0123456789abcdefABCDEF" for character in version)
        ):
            raise FrameworkError("CONFIG_INVALID")
        access_token = self.identity.token("https://vault.azure.net")
        path = f"/secrets/{name}" + (f"/{version}" if version else "")
        url = self.vault_uri + path + "?api-version=" + KEY_VAULT_API_VERSION
        request = urllib.request.Request(
            url,
            headers={"Authorization": "Bearer " + access_token, "Accept": "application/json"},
        )
        try:
            response = self.transport(request, self.timeout)
        except FrameworkError:
            raise FrameworkError("KEY_VAULT_NETWORK_FAILED") from None
        finally:
            access_token = None
        if response.status in (401, 403):
            raise FrameworkError("KEY_VAULT_ACCESS_DENIED")
        if response.status == 404:
            raise FrameworkError("KEY_VAULT_SECRET_NOT_FOUND")
        if response.status in (408, 429, 500, 502, 503, 504):
            raise FrameworkError("SECRET_PROVIDER_TIMEOUT")
        if response.status != 200 or len(response.body) > 1024 * 1024:
            raise FrameworkError("KEY_VAULT_NETWORK_FAILED")
        try:
            value = json.loads(response.body)["value"]
            if not isinstance(value, str):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise FrameworkError("KEY_VAULT_NETWORK_FAILED") from None
        if not value:
            raise FrameworkError("KEY_VAULT_SECRET_EMPTY")
        secret = Secret(value)
        self._active.append(secret)
        return secret

    def clear(self):
        for secret in self._active:
            secret.clear()
        self._active.clear()
