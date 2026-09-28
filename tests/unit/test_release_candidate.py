import copy
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jbpa import artifacts, release, release_cli
from jbpa.catalogue import load_catalogues, resolve
from jbpa.config import ROOT, validate_schema
from jbpa.errors import ERRORS, FrameworkError, category
from jbpa.qualification import compare_runtime, regression, run_steps


class CatalogueReleaseTests(unittest.TestCase):
    def test_exact_catalogue_counts_and_scope(self):
        catalogue, _ = load_catalogues()
        self.assertEqual(len(catalogue["versions"]), 19)
        self.assertEqual(set(catalogue["dynamic_sources"]), {"latest"})
        self.assertEqual(
            sum(
                e["qualification"]["overall"] == "AVAILABLE_UNQUALIFIED"
                for e in catalogue["versions"].values()
            ),
            17,
        )
        self.assertNotIn("latest", catalogue["aliases"])
        self.assertEqual(
            catalogue["versions"]["12.9"]["qualification"]["scope"],
            ["installation", "registration", "health"],
        )

    def test_exact_package_and_governed_aliases(self):
        catalogue, _ = load_catalogues()
        for requested in [
            "12.10",
            "12.10.1.1",
            "recommended",
            "latest-tested",
            "latest-available-pinned",
        ]:
            self.assertEqual(resolve(requested, catalogue)[0], "12.10")
        with self.assertRaises(FrameworkError):
            resolve("12.10.99.1", catalogue)

    def test_plain_version_does_not_network(self):
        with patch("jbpa.artifacts.download", side_effect=AssertionError("network")):
            output = io.StringIO()
            self.assertEqual(release_cli.main(["version"], stdout=output), 0)
            validate_schema(json.loads(output.getvalue()), "rc-result")

    def test_qualification_guard_exact_platform(self):
        catalogue, _ = load_catalogues()
        host = {"os": "ubuntu", "version": "24.04", "architecture": "x86_64"}
        self.assertEqual(
            release_cli.qualification_guard("12.10", catalogue["versions"]["12.10"], host),
            "QUALIFIED_VERSION",
        )
        for requested, entry, target, code in [
            ("12.8", catalogue["versions"]["12.8"], host, "VERSION_NOT_QUALIFIED"),
            ("latest", None, host, "LATEST_VERSION_NOT_QUALIFIED"),
            (
                "12.10",
                catalogue["versions"]["12.10"],
                {**host, "version": "22.04"},
                "VERSION_NOT_QUALIFIED",
            ),
        ]:
            with (
                self.subTest(requested=requested, target=target),
                self.assertRaises(FrameworkError) as error,
            ):
                release_cli.qualification_guard(requested, entry, target)
            self.assertEqual(error.exception.spec.name, code)
        self.assertEqual(
            release_cli.qualification_guard("latest", None, host, True), "EXPERIMENTAL_VERSION_TEST"
        )

    def test_blocked_cannot_be_overridden(self):
        catalogue, _ = load_catalogues()
        entry = copy.deepcopy(catalogue["versions"]["12.10"])
        entry["qualification"]["overall"] = "BLOCKED"
        with self.assertRaises(FrameworkError):
            release_cli.qualification_guard(
                "12.10", entry, {"os": "ubuntu", "version": "24.04", "architecture": "x86_64"}, True
            )

    def test_unknown_command_is_structured(self):
        output = io.StringIO()
        self.assertEqual(release_cli.main(["bad-command"], stdout=output), 2)
        data = json.loads(output.getvalue())
        self.assertEqual(data["category"], "CONFIGURATION_ERROR")
        self.assertEqual(data["schemaVersion"], "1.0")

    def test_error_categories(self):
        for code, expected in [
            ("VERSION_NOT_QUALIFIED", "VERSION_ERROR"),
            ("ARTIFACT_CHANGED", "ARTIFACT_ERROR"),
            ("JKS_IMPORT_FAILED", "ENTERPRISE_CONFIGURATION_ERROR"),
            ("KEY_VAULT_ACCESS_DENIED", "SECRET_PROVIDER_ERROR"),
            ("DRAIN_STOP_TIMEOUT", "DRAIN_ERROR"),
            ("PACKAGE_REMOVE_FAILED", "UNINSTALL_ERROR"),
            ("RELEASE_INVALID", "RELEASE_ERROR"),
        ]:
            self.assertEqual(category(ERRORS[code]), expected)

    def test_manifest_schema_and_contracts(self):
        catalogue = release.validate_source()
        manifest = release.manifest_for(catalogue)
        validate_schema(manifest, "release-manifest")
        self.assertFalse(manifest["productionApproved"])
        self.assertEqual(manifest["testedPackages"], ["12.10.1.1", "12.9.2.2"])


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.catalogue = load_catalogues()[0]

    def downloader(self, url, destination):
        Path(destination).write_bytes(b"!<arch>\nsynthetic-test-deb")
        return {
            "effective_url": url,
            "content_disposition_filename": None,
            "content_type": "application/octet-stream",
            "byte_size": 24,
            "sha256": "a" * 64,
        }

    def inspector(self, path):
        return {
            "Package": "jitterbit-agent",
            "Version": "12.8.1.6",
            "Architecture": "amd64",
            "Depends": "odbcinst, unixodbc",
        }

    def test_inspect_unqualified_does_not_promote(self):
        original = copy.deepcopy(self.catalogue)
        manifest, _ = artifacts.inspect(
            "12.8",
            self.root,
            catalogue=self.catalogue,
            downloader=self.downloader,
            inspector=self.inspector,
        )
        self.assertEqual(manifest["runtime_qualification"], "AVAILABLE_UNQUALIFIED")
        self.assertFalse(manifest["production_approved"])
        self.assertEqual(original, self.catalogue)
        validate_schema(manifest, "artifact-manifest")

    def test_full_package_version_required(self):
        with self.assertRaises(FrameworkError) as error:
            artifacts.inspect(
                "12.7",
                self.root,
                catalogue=self.catalogue,
                downloader=self.downloader,
                inspector=self.inspector,
            )
        self.assertEqual(error.exception.spec.name, "ARTIFACT_METADATA_MISMATCH")

    def test_known_hash_change_blocks(self):
        with self.assertRaises(FrameworkError) as error:
            artifacts.inspect(
                "12.10",
                self.root,
                catalogue=self.catalogue,
                downloader=self.downloader,
                inspector=lambda path: {**self.inspector(path), "Version": "12.10.1.1"},
            )
        self.assertEqual(error.exception.spec.name, "ARTIFACT_CHANGED")

    def test_latest_matched_and_unknown(self):
        manifest, _ = artifacts.inspect(
            "latest",
            self.root,
            catalogue=self.catalogue,
            downloader=self.downloader,
            inspector=self.inspector,
        )
        self.assertEqual(manifest["logical_version"], "12.8")
        self.assertEqual(manifest["source_type"], "DYNAMIC_MUTABLE")
        (self.root / "package.deb").unlink()
        manifest, _ = artifacts.inspect(
            "latest",
            self.root,
            catalogue=self.catalogue,
            downloader=self.downloader,
            inspector=lambda path: {**self.inspector(path), "Version": "99.1.2.3"},
        )
        self.assertIsNone(manifest["logical_version"])
        self.assertFalse(manifest["catalogue_match"])
        self.assertEqual(manifest["runtime_qualification"], "AVAILABLE_UNQUALIFIED")

    def test_filename_disagreement(self):
        def download(url, path):
            return {
                **self.downloader(url, path),
                "content_disposition_filename": "jitterbit-agent_12.8.9.9_amd64.deb",
            }

        with self.assertRaises(FrameworkError):
            artifacts.inspect(
                "12.8",
                self.root,
                catalogue=self.catalogue,
                downloader=download,
                inspector=self.inspector,
            )

    def test_redirect_policy(self):
        for url in [
            "http://download.jitterbit.com/a",
            "https://user:password@download.jitterbit.com/a",
            "https://download.jitterbit.com/a?token=bad",
            "https://untrusted.example/a",
            "file:///tmp/a",
        ]:
            with self.subTest(url=url), self.assertRaises(FrameworkError):
                artifacts.checked_url(url)
        self.assertEqual(
            artifacts.checked_url(self.catalogue["dynamic_sources"]["latest"]["url"]),
            self.catalogue["dynamic_sources"]["latest"]["url"],
        )

    def test_html_response_rejected_before_file_creation(self):
        class Response(io.BytesIO):
            status = 200
            headers = {}

            def geturl(self):
                return "https://login.jitterbit.com/login"

        opener = SimpleNamespace(open=lambda *a, **k: Response(b"<html>login</html>"))
        with self.assertRaises(FrameworkError) as error:
            artifacts.download(
                self.catalogue["dynamic_sources"]["latest"]["url"],
                str(self.root / "html.deb"),
                opener,
            )
        self.assertEqual(error.exception.spec.name, "ARTIFACT_NOT_DEBIAN_PACKAGE")
        self.assertFalse((self.root / "html.deb").exists())

    def test_bounded_download(self):
        class Response(io.BytesIO):
            status = 200
            headers = {}

            def geturl(self):
                return "https://download.jitterbit.com/a"

        opener = SimpleNamespace(open=lambda *a, **k: Response(b"!<arch>\n" + b"x" * 32))
        with self.assertRaises(FrameworkError):
            artifacts.download(
                "https://download.jitterbit.com/a",
                str(self.root / "large.deb"),
                opener,
                max_bytes=16,
            )

    def test_dpkg_field_invocation_and_invalid_package(self):
        calls = []
        fields = ["jitterbit-agent", "12.8.1.6", "amd64", "odbcinst, unixodbc"]

        def runner(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, fields[len(calls) - 1], "")

        with patch("jbpa.artifacts.subprocess.run", side_effect=runner):
            metadata = artifacts.package_fields("/tmp/package.deb")
        self.assertEqual(metadata["Version"], "12.8.1.6")
        self.assertEqual(len(calls), 4)
        self.assertTrue(all(c[:2] == ["dpkg-deb", "--field"] for c in calls))
        with (
            patch("jbpa.artifacts.subprocess.run", side_effect=FileNotFoundError()),
            self.assertRaises(FrameworkError) as error,
        ):
            artifacts.package_fields("/tmp/a")
        self.assertEqual(error.exception.spec.name, "ARTIFACT_INSPECTOR_UNAVAILABLE")

    def test_intake_is_immutable(self):
        manifest, _ = artifacts.inspect(
            "12.8",
            self.root,
            catalogue=self.catalogue,
            downloader=self.downloader,
            inspector=self.inspector,
        )
        directory = self.root / "metadata"
        artifacts.save_metadata(manifest, directory)
        self.assertEqual((directory / "12.8.1.6.yaml").stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FrameworkError):
            artifacts.save_metadata({**manifest, "sha256": "b" * 64}, directory)

    def test_latest_observation_is_informational(self):
        manifest = {"package_version": "12.8.1.6", "sha256": "a" * 64}
        target = self.root / "latest.json"
        self.assertEqual(artifacts.latest_change(manifest, target), "LATEST_RESOLUTION_OBSERVED")
        self.assertEqual(
            artifacts.latest_change({**manifest, "sha256": "b" * 64}, target),
            "LATEST_RESOLUTION_CHANGED",
        )

    def test_hash_cache_reuse_and_tamper(self):
        source = self.root / "input.deb"
        source.write_bytes(b"fake bytes")
        manifest = {
            "package_version": "12.8.1.6",
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
        cached = artifacts.cache_artifact(manifest, source, self.root / "cache")
        self.assertEqual(artifacts.cache_artifact(manifest, source, self.root / "cache"), cached)
        cached.write_bytes(b"changed")
        with self.assertRaises(FrameworkError):
            artifacts.cache_artifact(manifest, source, self.root / "cache")

    def test_bulk_continues_and_cleans(self):
        seen = []

        def inspector(requested, directory, **kwargs):
            seen.append(directory)
            Path(directory, "package.deb").write_bytes(b"temporary")
            raise FrameworkError("DOWNLOAD_FAILED")

        results = artifacts.intake_all(self.root / "metadata", self.catalogue, inspect_fn=inspector)
        self.assertEqual(len(results), 17)
        self.assertTrue(all(r["status"] == "FAILED" for r in results))
        self.assertTrue(all(not Path(path).exists() for path in seen))


class RegressionReleaseTests(unittest.TestCase):
    def test_live_requires_explicit_flag_and_config(self):
        with self.assertRaises(FrameworkError) as error:
            regression(["run", "--version", "12.8"])
        self.assertEqual(error.exception.spec.name, "LIVE_REGRESSION_NOT_AUTHORIZED")

    def test_dirty_target_blocks_before_install(self):
        args = SimpleNamespace(
            version="12.8",
            target="ubuntu-24.04",
            config="unused",
            mode="basic",
            allow_unqualified=True,
        )
        calls = []
        with self.assertRaises(FrameworkError) as error:
            run_steps(
                args,
                inspect_fn=lambda *a: ({}, None),
                snapshot=lambda: {"rootPresent": True},
                install_fn=lambda *a, **k: calls.append(a),
                host_provider=lambda: {
                    "os": "ubuntu",
                    "version": "24.04",
                    "system": "Linux",
                    "architecture": "x86_64",
                },
            )
        self.assertEqual(error.exception.spec.name, "REGISTRATION_STATE_CONFLICT")
        self.assertEqual(calls, [])

    def test_release_archive_verification_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            built = release.build(directory)
            self.assertEqual(
                release.verify(built["archive"], built["sha256"])["status"], "VERIFIED"
            )
            with Path(built["archive"]).open("ab") as stream:
                stream.write(b"tamper")
            with self.assertRaises(FrameworkError):
                release.verify(built["archive"], built["sha256"])

    def test_bundle_excludes_qa_material(self):
        with tempfile.TemporaryDirectory() as directory:
            built = release.build(directory)
            stage = Path(built["manifest"]).parent
            self.assertFalse((stage / "evidence").exists())
            self.assertEqual(list(stage.rglob("*.deb")), [])
            self.assertEqual(list(stage.rglob("*.pyc")), [])
            self.assertFalse((stage / "config/agent.jblab.ubuntu-24.04.test.yaml").exists())

    def test_bundle_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "link").symlink_to("/etc/passwd")
            with self.assertRaises(FrameworkError):
                release.scan_bundle(Path(directory))


class LifecycleFacadeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.host = {
            "os": "ubuntu",
            "version": "24.04",
            "system": "Linux",
            "architecture": "x86_64",
        }

    def test_latest_install_uses_once_resolved_bytes(self):
        catalogue = load_catalogues()[0]
        entry = catalogue["versions"]["12.10"]
        manifest = {
            "requested_version": "latest",
            "logical_version": "12.10",
            "package_version": "12.10.1.1",
            "request_url": catalogue["dynamic_sources"]["latest"]["url"],
            "sha256": entry["integrity"]["sha256"],
        }
        package = self.root / "resolved.deb"
        package.write_bytes(b"exact pinned bytes")
        calls = []

        def bootstrap_run(argv, stdout, **kwargs):
            calls.append(argv)
            backend = kwargs["backend_factory"]()
            destination = self.root / "installed-input.deb"
            backend.download("https://login.jitterbit.com/never-refetch", str(destination))
            self.assertEqual(destination.read_bytes(), package.read_bytes())
            versions, _ = kwargs["catalogues_provider"]()
            self.assertEqual(
                versions["versions"]["12.10"]["artifacts"][0]["sha256"], manifest["sha256"]
            )
            stdout.write(
                json.dumps(
                    {
                        "status": "COMPLETE",
                        "packageVersion": "12.10.1.1",
                        "harmonyRegistered": True,
                        "serviceRunning": True,
                    }
                )
            )
            return 0

        with (
            patch("jbpa.release_cli.detect", return_value=self.host),
            patch("jbpa.artifacts.inspect", return_value=(manifest, package)) as inspect,
            patch(
                "jbpa.host_readiness.run",
                return_value={
                    "profile": "INSTALL",
                    "status": "PASS",
                    "checks": {},
                    "hostState": "CLEAN_HOST",
                    "platform": {},
                    "mutationPerformed": False,
                },
            ),
            patch("jbpa.bootstrap.execute", side_effect=bootstrap_run),
        ):
            code, result = release_cli.install(
                [
                    "--config",
                    str(ROOT / "config/examples/azure-qa.example.yaml"),
                    "--version",
                    "latest",
                    "--controlled-test",
                    "--non-interactive",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(inspect.call_count, 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["requestedVersion"], "latest")
        self.assertEqual(result["qualificationClassification"], "QUALIFIED_VERSION")

    def test_production_config_cannot_use_qa_exception(self):
        with (
            patch("jbpa.artifacts.inspect", side_effect=AssertionError("unexpected download")),
            self.assertRaises(FrameworkError) as error,
        ):
            release_cli.install(
                [
                    "--config",
                    str(ROOT / "config/examples/azure-production.example.yaml"),
                    "--controlled-test",
                ]
            )
        self.assertEqual(error.exception.spec.name, "ARTIFACT_NOT_APPROVED")

    def test_invalid_health_argument_does_not_echo_input(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.stderr", errors):
            code = release_cli.main(
                [
                    "health",
                    "--profile",
                    "INVALID_TEST_VALUE",
                    "--expected-agent-id",
                    "1",
                    "--expected-agent-group-id",
                    "2",
                ],
                stdout=output,
            )
        self.assertEqual(code, 2)
        self.assertNotIn("INVALID_TEST_VALUE", output.getvalue() + errors.getvalue())
        self.assertEqual(json.loads(output.getvalue())["category"], "CONFIGURATION_ERROR")

    def test_basic_and_full_modes_reuse_package(self):
        from jbpa.config import load_yaml
        from jbpa.regression import REQUIRED_STATES

        contract = load_yaml(ROOT / "contracts/12.10.1.1.yaml")
        observation = {
            "resultStatus": "COMPLETE",
            "packageVersion": "12.10.1.1",
            "architecture": "x86_64",
            "os": "ubuntu",
            "osVersion": "24.04",
            "packageDependencies": "odbcinst, unixodbc",
            "paths": {
                name: True
                for name in [
                    "root",
                    "resources",
                    "credentials",
                    "agent_log",
                    "jre",
                    "keytool",
                    "cacerts",
                ]
            },
            "markers": {name: True for name in REQUIRED_STATES},
            "localServices": {name: True for name in contract["dimensions"]["service_contract"]},
            "allServicesRunning": True,
            "registrationDurationSeconds": 175.308,
        }
        for mode, expected_installs in [("basic", 1), ("full-lifecycle", 2)]:
            installs = []
            uninstalls = []
            package = self.root / ("resolved-" + mode + ".deb")
            package.write_bytes(b"bytes")

            def install(argv, prepared, collected=installs):
                collected.append(prepared)
                return 0, {"status": "COMPLETE", "harmonyRegistered": True, "serviceRunning": True}

            def uninstall(argv, collected=uninstalls):
                collected.append(argv)
                return 0, {"status": "COMPLETE"}

            args = SimpleNamespace(
                version="12.10",
                target="ubuntu-24.04",
                config="test",
                mode=mode,
                allow_unqualified=False,
                contract=str(ROOT / "contracts/12.10.1.1.yaml"),
            )
            code, result = run_steps(
                args,
                inspect_fn=lambda *a, pinned=package: ({"package_version": "12.10.1.1"}, pinned),
                install_fn=install,
                uninstall_fn=uninstall,
                snapshot=lambda: {"rootPresent": False},
                capture_fn=lambda *a: observation,
                host_provider=lambda: self.host,
            )
            self.assertEqual(code, 0)
            self.assertEqual(len(installs), expected_installs)
            self.assertTrue(all(pinned[1] == package for pinned in installs))
            self.assertEqual(len(uninstalls), expected_installs - 1)
            self.assertEqual(result["qualificationPromotion"], "MANUAL_REVIEW_REQUIRED")

    def test_runtime_change_and_timing_classifications(self):
        from jbpa.config import load_yaml
        from jbpa.regression import REQUIRED_STATES

        contract = load_yaml(ROOT / "contracts/12.10.1.1.yaml")
        observation = {
            "resultStatus": "COMPLETE",
            "architecture": "x86_64",
            "os": "ubuntu",
            "osVersion": "24.04",
            "packageDependencies": "odbcinst, unixodbc",
            "paths": {
                name: True
                for name in [
                    "root",
                    "resources",
                    "credentials",
                    "agent_log",
                    "jre",
                    "keytool",
                    "cacerts",
                ]
            },
            "markers": {name: True for name in REQUIRED_STATES},
            "localServices": {name: True for name in contract["dimensions"]["service_contract"]},
            "allServicesRunning": True,
            "registrationDurationSeconds": 180,
        }
        self.assertEqual(
            compare_runtime(observation, contract)["status"], "CONTRACT_COMPATIBLE_MINOR_CHANGES"
        )
        observation["packageDependencies"] += " , new-dependency"
        self.assertEqual(compare_runtime(observation, contract)["status"], "CONTRACT_CHANGED")
        observation["resultStatus"] = "FAILED"
        self.assertEqual(compare_runtime(observation, contract)["status"], "REGRESSION_FAILED")


class FinalReleaseBoundaryTests(unittest.TestCase):
    def test_denied_artifact_cannot_use_override(self):
        entry = copy.deepcopy(load_catalogues()[0]["versions"]["12.10"])
        entry["approval"] = "denied"
        with self.assertRaises(FrameworkError) as error:
            release_cli.qualification_guard(
                "12.10", entry, {"os": "ubuntu", "version": "24.04", "architecture": "x86_64"}, True
            )
        self.assertEqual(error.exception.spec.name, "ARTIFACT_NOT_APPROVED")

    def test_archive_traversal_is_rejected_with_matching_digest(self):
        import tarfile

        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "bad.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                member = tarfile.TarInfo("jbpa/../escape")
                member.size = 1
                tar.addfile(member, io.BytesIO(b"x"))
            with self.assertRaises(FrameworkError):
                release.verify(archive, release.digest(archive))

    def test_private_latest_observation_does_not_follow_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            original = root / "original.json"
            original.write_text("not an observation")
            target = root / "latest.json"
            target.symlink_to(original)
            with self.assertRaises(FrameworkError):
                artifacts.latest_change(
                    {"package_version": "12.10.1.1", "sha256": "a" * 64}, target
                )
            self.assertEqual(original.read_text(), "not an observation")


class ArtifactCliCoverageTests(unittest.TestCase):
    def test_artifact_list_is_offline(self):
        output = io.StringIO()
        with patch("jbpa.artifacts.inspect", side_effect=AssertionError("network")):
            code = release_cli.main(["artifact", "list"], stdout=output)
        data = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(len(data["details"]["versions"]), 19)
        self.assertEqual(data["operation"], "ARTIFACT_LIST")

    def test_version_resolve_exact_package(self):
        output = io.StringIO()
        code = release_cli.main(["version", "resolve", "12.10.1.1"], stdout=output)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["versions"]["resolvedPA"], "12.10.1.1")

    def test_verify_matches_known_digest(self):
        entry = load_catalogues()[0]["versions"]["12.10"]
        manifest = {
            "logical_version": "12.10",
            "package_version": "12.10.1.1",
            "sha256": entry["integrity"]["sha256"],
        }
        with patch("jbpa.artifacts.inspect", return_value=(manifest, None)):
            code, data = release_cli.artifact(["verify", "--version", "12.10"])
        self.assertEqual(code, 0)
        self.assertEqual(data["verification"], "MATCHED_CATALOGUE_LOCAL_DIGEST")

    def test_verify_requires_governed_digest(self):
        manifest = {"logical_version": "12.8", "package_version": "12.8.1.6", "sha256": "a" * 64}
        with (
            patch("jbpa.artifacts.inspect", return_value=(manifest, None)),
            self.assertRaises(FrameworkError) as error,
        ):
            release_cli.artifact(["verify", "--version", "12.8"])
        self.assertEqual(error.exception.spec.name, "INSTALLER_METADATA_MISSING")

    def test_wrong_architecture_rejected(self):
        values = iter(["jitterbit-agent", "12.10.1.1", "arm64", "odbcinst, unixodbc"])
        with (
            patch(
                "jbpa.artifacts.subprocess.run",
                side_effect=lambda argv, **kwargs: subprocess.CompletedProcess(
                    argv, 0, next(values), ""
                ),
            ),
            self.assertRaises(FrameworkError) as error,
        ):
            artifacts.package_fields("/tmp/never-executed.deb")
        self.assertEqual(error.exception.spec.name, "ARTIFACT_METADATA_MISMATCH")

    def test_experimental_install_is_explicit_and_not_promoted(self):
        manifest = {
            "logical_version": "12.8",
            "package_version": "12.8.1.6",
            "sha256": "a" * 64,
            "request_url": load_catalogues()[0]["versions"]["12.8"]["url"],
        }
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "package.deb"
            package.write_bytes(b"fixture")

            def execute(argv, stdout, **kwargs):
                self.assertTrue(kwargs["experimental"])
                catalogue, _ = kwargs["catalogues_provider"]()
                self.assertEqual(catalogue["versions"]["12.8"]["approval"], "approved_for_test")
                stdout.write(json.dumps({"status": "COMPLETE"}))
                return 0

            with (
                patch(
                    "jbpa.release_cli.detect",
                    return_value={
                        "os": "ubuntu",
                        "version": "24.04",
                        "system": "Linux",
                        "architecture": "x86_64",
                    },
                ),
                patch("jbpa.artifacts.inspect", return_value=(manifest, package)),
                patch(
                    "jbpa.host_readiness.run",
                    return_value={
                        "profile": "INSTALL",
                        "status": "PASS",
                        "checks": {},
                        "hostState": "CLEAN_HOST",
                        "platform": {},
                        "mutationPerformed": False,
                    },
                ),
                patch("jbpa.bootstrap.execute", side_effect=execute),
            ):
                code, data = release_cli.install(
                    [
                        "--config",
                        str(ROOT / "config/examples/azure-qa.example.yaml"),
                        "--version",
                        "12.8",
                        "--allow-unqualified",
                        "--controlled-test",
                        "--non-interactive",
                    ]
                )
        self.assertEqual(code, 0)
        self.assertEqual(data["qualificationClassification"], "EXPERIMENTAL_VERSION_TEST")
        self.assertEqual(load_catalogues()[0]["versions"]["12.8"]["approval"], "pending")


class LocalArtifactVerificationTests(unittest.TestCase):
    def test_cached_file_is_hashed_and_inspected_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "cached.deb"
            source.write_bytes(b"!<arch>\nfixture")
            stage = root / "stage"
            stage.mkdir()
            fields = {
                "Package": "jitterbit-agent",
                "Version": "12.8.1.6",
                "Architecture": "amd64",
                "Depends": "odbcinst, unixodbc",
            }
            manifest, _ = artifacts.inspect(
                "12.8",
                stage,
                local_file=source,
                inspector=lambda path: fields,
                downloader=lambda *a: (_ for _ in ()).throw(AssertionError("network")),
            )
            self.assertEqual(manifest["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(manifest["retrieval"], "LOCAL_FILE")
            self.assertIsNone(manifest["effective_url"])

    def test_latest_cannot_resolve_from_stale_local_cache(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(FrameworkError) as error:
            artifacts.inspect("latest", directory, local_file="/tmp/unused.deb")
        self.assertEqual(error.exception.spec.name, "CONFIG_INVALID")


class AzureReleaseBootstrapTests(unittest.TestCase):
    def run_wrapper(self, archive, expected, root):
        config = root / "config.yaml"
        config.write_text("{}")
        output = root / "result.json"
        result = subprocess.run(
            [
                "bash",
                str(ROOT / "azure/custom-script/release-bootstrap.sh"),
                str(archive),
                expected,
                str(config),
                str(output),
                str(root / "framework"),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        return result, output

    def test_wrong_archive_hash_emits_release_error_before_runtime_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            archive = root / "archive.tar.gz"
            archive.write_bytes(b"invalid archive")
            result, output = self.run_wrapper(archive, "a" * 64, root)
            self.assertEqual(result.returncode, 21)
            data = json.loads(result.stdout)
            validate_schema(data, "rc-result")
            self.assertEqual(data["category"], "RELEASE_ERROR")
            self.assertEqual(
                json.loads(output.read_text())["error"]["name"], "RELEASE_BOOTSTRAP_FAILED"
            )
            self.assertFalse(list((root / "framework/releases").glob("*/.venv")))

    def test_unsafe_archive_is_rejected_before_pip_or_jbpa(self):
        import tarfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            archive = root / "unsafe.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                member = tarfile.TarInfo("jbpa/link")
                member.type = tarfile.SYMTYPE
                member.linkname = "/opt/jitterbit"
                tar.addfile(member)
            result, _ = self.run_wrapper(archive, release.digest(archive), root)
            self.assertEqual(result.returncode, 81)
            self.assertEqual(json.loads(result.stdout)["status"], "FAILED")


class ReleaseOwnershipTests(unittest.TestCase):
    def test_archive_has_governed_ownership_and_executable_cli(self):
        import tarfile

        with tempfile.TemporaryDirectory() as directory:
            built = release.build(directory)
            with tarfile.open(built["archive"], "r:gz") as tar:
                members = tar.getmembers()
                self.assertTrue(
                    all(m.uid == 0 and m.gid == 0 and not m.mode & 0o022 for m in members)
                )
                binary = next(m for m in members if m.name.endswith("/bin/jbpa"))
                self.assertEqual(binary.mode, 0o755)
