"""Bounded, non-executable YAML and strict offline JSON Schema validation."""

import json
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from yaml.tokens import AliasToken, AnchorToken

from .errors import FrameworkError

ROOT = Path(__file__).resolve().parents[2]


class UniqueLoader(yaml.SafeLoader):
    pass


def mapping(loader, node, deep=False):
    result = {}
    for key, value in node.value:
        k = loader.construct_object(key, deep=deep)
        if not isinstance(k, str) or k in result:
            raise FrameworkError("CONFIG_INVALID")
        result[k] = loader.construct_object(value, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)


def load_yaml(path):
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(262145)
        if len(raw) > 262144:
            raise FrameworkError("CONFIG_INVALID")
        text = raw.decode("utf-8")
        if any(isinstance(t, (AliasToken, AnchorToken)) for t in yaml.scan(text)):
            raise FrameworkError("CONFIG_INVALID")
        return yaml.load(text, Loader=UniqueLoader)
    except (OSError, ValueError, yaml.YAMLError, RecursionError) as exc:
        raise FrameworkError("CONFIG_INVALID") from exc


def validate_schema(data, name):
    try:
        schema = json.loads((ROOT / "config/schemas" / f"{name}.schema.json").read_text())
        if next(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data), None
        ):
            raise FrameworkError("CONFIG_INVALID")
    except (OSError, ValueError, RecursionError) as exc:
        raise FrameworkError("CONFIG_INVALID") from exc


def safe_fields(value, depth=0):
    if depth > 20:
        raise FrameworkError("CONFIG_INVALID")
    if isinstance(value, dict):
        for k, v in value.items():
            if k in {"identities", "certificates"}:
                ids = [item.get("id", item.get("alias")) for item in v]
                if len(ids) != len(set(ids)):
                    raise FrameworkError("CONFIG_INVALID")
            safe_fields(v, depth + 1)
    elif isinstance(value, list):
        for v in value:
            safe_fields(v, depth + 1)
    elif isinstance(value, str):
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise FrameworkError("CONFIG_INVALID")
        if value.startswith("/") and ".." in Path(value).parts:
            raise FrameworkError("CONFIG_INVALID")
        if value.startswith("https://"):
            parsed = urlsplit(value)
            if (
                not parsed.hostname
                or parsed.username
                or parsed.password
                or (
                    parsed.query
                    and value
                    != "https://login.jitterbit.com/jitterbit-cloud-mgmt-console/download/latest/agent/linuxdebian?architecture=x64"
                )
                or parsed.fragment
            ):
                raise FrameworkError("CONFIG_INVALID")


def load_config(path, version=None, environ=None):
    data = load_yaml(path)
    validate_schema(data, "agent")
    source = "config"
    override = version or (environ or {}).get("JITTERBIT_AGENT_VERSION")
    if override is not None:
        source = "cli" if version else "environment"
        data["agent"]["version"] = override
    validate_schema(data, "agent")
    safe_fields(data)
    if data["health"]["poll_interval_seconds"] > data["health"]["registration_timeout_seconds"]:
        raise FrameworkError("CONFIG_INVALID")
    reg = data["harmony"]["registration"]
    if reg["strategy"] is None and any(
        reg[k] is not None
        for k in ("token_secret_ref", "username_secret_ref", "password_secret_ref")
    ):
        raise FrameworkError("CONFIG_INVALID")
    proxy = data["proxy"]
    if bool(proxy["username_secret_ref"]) != bool(proxy["password_secret_ref"]):
        raise FrameworkError("CONFIG_INVALID")
    return data, source


def validated_yaml(path, name):
    data = load_yaml(path)
    validate_schema(data, name)
    safe_fields(data)
    return data
