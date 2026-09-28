"""Offline schema/link checks and bounded credential-pattern scan (not a full audit)."""

import ast
import json
import re

from jsonschema import Draft202012Validator

from jbpa.config import ROOT, load_config, validated_yaml

failures = []
for path in (ROOT / "config/schemas").glob("*.json"):
    Draft202012Validator.check_schema(json.loads(path.read_text()))
Draft202012Validator.check_schema(
    json.loads((ROOT / "tools/handoff/request.schema.json").read_text())
)
deployment_schema = json.loads((ROOT / "config/schemas/azure-deployment.schema.json").read_text())
Draft202012Validator(deployment_schema).validate(
    __import__("yaml").safe_load(
        (ROOT / "config/examples/azure-deployment.example.yaml").read_text()
    )
)
load_config(ROOT / "config/agent.example.yaml")
load_config(ROOT / "config/agent.jblab.example.yaml")
load_config(ROOT / "config/agent.jblab.ubuntu-24.04.test.yaml")
validated_yaml(ROOT / "config/versions.yaml", "versions")
validated_yaml(ROOT / "config/os-support.yaml", "os-support")
for path in (ROOT / "artifacts/metadata").glob("*.yaml"):
    manifest = validated_yaml(path, "artifact-manifest")
    if path.stem != manifest["package_version"]:
        failures.append((path, "metadata identity mismatch"))
paths = [ROOT / "README.md", ROOT / "CHANGELOG.md"]
for folder in (
    "src",
    "tests",
    "scripts",
    "config",
    "docs",
    "evidence",
    "azure",
    "bin",
    "contracts",
    "artifacts",
    "tools",
):
    paths.extend(
        p for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts
    )
patterns = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s*\n[A-Za-z0-9+/]{20}", re.M),
    re.compile(r"https?://[^\s]+[?&](?:sig|token|password)=[^\s]+", re.I),
    re.compile(r'(?i)\b(?:password|passphrase|token)\s*[:=]\s*["\'][^"\']{12,}["\']'),
]
for path in paths:
    if path.suffix == ".png":
        continue  # User-provided visual evidence; the bounded scan covers text only.
    text = path.read_text()
    if path.suffix == ".md":
        if text.count("```") % 2:
            failures.append((path, "unbalanced fence"))
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if (
                "://" not in link
                and not link.startswith("#")
                and not (path.parent / link.split("#")[0]).exists()
            ):
                failures.append((path, "broken local link"))
    # Test-only synthetic strings exercise leakage protection; never print matched content.
    if "tests" not in path.relative_to(ROOT).parts and path.name != "check_repository.py":
        if any(pattern.search(text) for pattern in patterns):
            failures.append((path, "potential credential pattern"))
    if path.suffix == ".py" and "src" in path.relative_to(ROOT).parts:
        tree = ast.parse(text)
        if any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in {"eval", "exec", "print"}
            for n in ast.walk(tree)
        ):
            failures.append((path, "uncontrolled output or code execution"))
if failures:
    for path, reason in failures:
        print(f"FAIL {path.relative_to(ROOT)}: {reason}")
    raise SystemExit(1)
print(f"PASS schemas, examples, Markdown links and bounded credential scan ({len(paths)} files)")
