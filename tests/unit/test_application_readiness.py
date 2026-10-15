import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from test_native_linux import FakeBackend, artifact, config

from jbpa.application_readiness import ApplicationReadinessProbe
from jbpa.errors import FrameworkError
from jbpa.native_linux import CREDENTIALS, JITTERBIT, NativeLinuxWorkflow
from jbpa.security import Secret


class Response(io.BytesIO):
    status = 200


class Opener:
    def __init__(self, body=None):
        self.body = (
            body
            or b'<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"><operation name="xmlToJson"/></definitions>'
        )
        self.calls = []

    def open(self, url, timeout):
        self.calls.append(url)
        return Response(self.body)


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "webapps/axis/WEB-INF/lib").mkdir(parents=True)
        (self.root / "conf").mkdir()
        (self.root / "conf/server.xml").write_text(
            '<Server><Connector port="46912" protocol="HTTP/1.1"/></Server>'
        )
        with zipfile.ZipFile(self.root / "webapps/axis.war", "w") as z:
            z.writestr("WEB-INF/lib/example.jar", b"complete-fixture-library")
        self.library = self.root / "webapps/axis/WEB-INF/lib/example.jar"
        self.library.write_bytes(b"complete-fixture-library")

    def test_complete_expansion_and_real_wsdl_required(self):
        opener = Opener()
        result = ApplicationReadinessProbe(self.root, opener)()
        self.assertEqual(result["status"], "READY")
        self.assertEqual(
            opener.calls, ["http://127.0.0.1:46912/axis/soap-services/JsonEngine?wsdl"]
        )

    def test_truncated_expansion_cannot_be_healthy(self):
        self.library.write_bytes(b"partial")
        opener = Opener()
        result = ApplicationReadinessProbe(self.root, opener)()
        self.assertEqual(result["contentMismatches"], 1)
        self.assertEqual(result["status"], "NOT_READY")
        self.assertEqual(opener.calls, [])

    def test_same_size_corruption_is_detected(self):
        self.library.write_bytes(b"x" * self.library.stat().st_size)
        self.assertEqual(ApplicationReadinessProbe(self.root, Opener())()["contentMismatches"], 1)

    def test_missing_library_is_not_repaired(self):
        self.library.unlink()
        result = ApplicationReadinessProbe(self.root, Opener())()
        self.assertEqual(result["missingFiles"], 1)
        self.assertFalse(self.library.exists())

    def test_http_200_error_page_is_not_readiness(self):
        result = ApplicationReadinessProbe(self.root, Opener(b"<html>Error</html>"))()
        self.assertEqual(result["status"], "NOT_READY")

    def test_symlink_is_rejected(self):
        self.library.unlink()
        self.library.symlink_to("/etc/passwd")
        self.assertEqual(ApplicationReadinessProbe(self.root, Opener())()["status"], "NOT_READY")

    def test_bad_archive_is_not_repaired(self):
        (self.root / "webapps/axis.war").write_bytes(b"broken")
        self.assertEqual(ApplicationReadinessProbe(self.root, Opener())()["status"], "NOT_READY")


class ObservationTests(unittest.TestCase):
    def backend(self):
        backend = FakeBackend()
        backend.files.add(CREDENTIALS)
        return backend

    def test_slow_deployment_is_observed_without_restart(self):
        backend = self.backend()

        def readiness():
            return {"status": "READY" if backend.now >= 10 else "NOT_READY"}

        result = NativeLinuxWorkflow(backend).monitor_runtime(config(), application_probe=readiness)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertGreaterEqual(backend.now, 10)
        self.assertTrue(all(command[-1] == "status" for command, _ in backend.commands))
        self.assertFalse(backend.writes)

    def test_fresh_registration_restart_waits_for_vendor_expansion(self):
        backend = FakeBackend()
        backend.application_readiness = lambda: {
            "status": "READY" if backend.now >= 10 else "NOT_READY"
        }
        original_run = backend.run
        restart_times = []

        def run(argv, env=None):
            if argv == [JITTERBIT, "restart"]:
                restart_times.append(backend.now)
            return original_run(argv, env)

        backend.run = run
        result = NativeLinuxWorkflow(backend).run(config(), artifact(), Secret("fixture"))
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(restart_times, [10])

    def test_vendor_left_services_stopped_registration_starts_normally(self):
        backend = FakeBackend()
        backend.vendor_application_starting = lambda: False

        def unexpected_probe():
            self.fail("No startup is in progress; must not wait for absent Axis")

        backend.application_readiness = unexpected_probe
        result = NativeLinuxWorkflow(backend).run(config(), artifact(), Secret("fixture"))
        self.assertEqual(result["status"], "COMPLETE")
        self.assertIn("VENDOR_APPLICATION_NOT_STARTED", result["stateHistory"])
        self.assertEqual(
            sum(command == [JITTERBIT, "restart"] for command, _ in backend.commands), 1
        )

    def test_running_services_do_not_hide_missing_axis(self):
        backend = self.backend()
        with self.assertRaises(FrameworkError) as ctx:
            NativeLinuxWorkflow(backend).monitor_runtime(
                config(), application_probe=lambda: {"status": "NOT_READY", "missingFiles": 118}
            )
        self.assertEqual(ctx.exception.spec.name, "UPGRADE_APPLICATION_UNREADY")
        self.assertFalse(backend.writes)
        self.assertFalse(
            any(command[-1] in ["start", "stop", "restart"] for command, _ in backend.commands)
        )


if __name__ == "__main__":
    unittest.main()
