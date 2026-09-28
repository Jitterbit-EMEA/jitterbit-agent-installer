"""Caller-side helpers; no Azure provisioning or Jitterbit lifecycle actions."""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator


def outcome(reason, success=False):
    """Return only safe controller fields, never raw guest result text."""
    return {"success": success, "reason": reason, "automaticRetry": False}


def verify_archive(path, expected_sha256):
    """The caller must perform this on the guest before extraction/execution."""
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise ValueError("INVALID_EXPECTED_HASH")
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return outcome(
        "VERIFIED" if digest.hexdigest() == expected_sha256 else "JBPA_RELEASE_HASH_MISMATCH",
        digest.hexdigest() == expected_sha256,
    )


def install_arguments(binary, config, result, *, controlled_test=False, allow_unqualified=False):
    """Return argv for an already verified, installed packaged release; never shell text."""
    if type(allow_unqualified) is not bool or type(controlled_test) is not bool:
        raise ValueError("INVALID_BOOLEAN")
    for value in (binary, config, result):
        path = Path(value)
        if not path.is_absolute() or ".." in path.parts or "\x00" in value:
            raise ValueError("INVALID_GUEST_PATH")
    if allow_unqualified and not controlled_test:
        raise ValueError("UNQUALIFIED_REQUIRES_CONTROLLED_TEST")
    args = [
        binary,
        "install",
        "--config",
        config,
        "--version",
        "12.10",
        "--result-file",
        result,
        "--non-interactive",
    ]
    if controlled_test:
        args.append("--controlled-test")
    if allow_unqualified:
        args.append("--allow-unqualified")
    return args


def delivery_references(file_uris):
    """Build MI-only CSE delivery references, excluding credentials and inline config."""
    if not file_uris:
        raise ValueError("EMPTY_ARTIFACT_REFERENCES")
    for uri in file_uris:
        parsed = urlsplit(uri)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("UNSAFE_ARTIFACT_REFERENCE")
    return {"fileUris": list(file_uris), "managedIdentity": {}}


def consume_install(
    exit_code,
    result_text,
    schema,
    *,
    timed_out=False,
    expected_platform=None,
    expected_jbpa="1.0.0-rc2",
):
    """Validate transported result JSON plus process exit; never parse product logs."""
    if timed_out:
        return outcome("AZURE_DISPATCH_TIMEOUT")
    if result_text is None:
        return outcome("MISSING_RESULT")
    if len(result_text.encode("utf-8")) > 1048576:
        return outcome("RESULT_TOO_LARGE")
    try:
        result = json.loads(result_text)
    except (ValueError, TypeError):
        return outcome("MALFORMED_RESULT_JSON")
    if not Draft202012Validator(schema).is_valid(result):
        return outcome("RESULT_SCHEMA_MISMATCH")
    if type(exit_code) is not int or not 0 <= exit_code <= 255:
        return outcome("INVALID_PROCESS_EXIT")
    if exit_code != 0:
        return outcome("JBPA_NONZERO_EXIT")
    if (
        result["status"] != "SUCCESS"
        or result["error"] is not None
        or result["category"] != "SUCCESS"
    ):
        return outcome("AZURE_RESULT_CONTRACT_FAILURE")
    if result["operation"] != "INSTALL":
        return outcome("UNEXPECTED_OPERATION")
    if result["versions"] != {
        "jbpa": expected_jbpa,
        "requestedPA": "12.10",
        "resolvedPA": "12.10.1.1",
    }:
        return outcome("UNEXPECTED_VERSION")
    if expected_platform and result["platform"] != expected_platform:
        return outcome("TARGET_OS_MISMATCH")
    details = result["details"]
    if (
        details.get("status") != "COMPLETE"
        or details.get("serviceRunning") is not True
        or details.get("harmonyRegistered") is not True
    ):
        return outcome("INSTALLATION_INCOMPLETE")
    return outcome("INSTALL_COMPLETE", True)


def bootstrap_arguments(
    wrapper,
    archive,
    sha256,
    config,
    result,
    install_root,
    *,
    controlled_test=False,
    allowUnqualified=False,
):
    """Canonical external boolean allowUnqualified maps to bootstrap argument seven."""
    if type(allowUnqualified) is not bool or type(controlled_test) is not bool:
        raise ValueError("INVALID_BOOLEAN")
    # Reuse path and QA policy validation without creating a second override route.
    install_arguments(
        wrapper, config, result, controlled_test=controlled_test, allow_unqualified=allowUnqualified
    )
    if not Path(install_root).is_absolute() or ".." in Path(install_root).parts:
        raise ValueError("INVALID_GUEST_PATH")
    return [
        "bash",
        wrapper,
        archive,
        sha256,
        config,
        result,
        install_root,
        "controlled-test" if controlled_test else "production",
        "true" if allowUnqualified else "false",
    ]
