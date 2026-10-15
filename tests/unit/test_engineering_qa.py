"""Engineering QA provenance does not fabricate local tests or waive deployment gates."""

import copy
import json
import unittest

from jbpa.catalogue import load_catalogues
from jbpa.config import ROOT, validate_schema
from jbpa.errors import FrameworkError
from jbpa.release import manifest_for
from jbpa.release_cli import qualification_guard, versions


class EngineeringQA(unittest.TestCase):
    def test_all_exact_catalogue_packages_have_confirmation_and_test_approval(self):
        catalogue, _ = load_catalogues()
        ref = ROOT / "evidence/engineering-qa/confirmation-2026-10-15.json"
        evidence = json.loads(ref.read_text())
        self.assertEqual(evidence["source"], "USER_RELAYED_ENGINEERING_CONFIRMATION")
        self.assertEqual(
            {r["packageVersion"] for r in evidence["packages"]},
            {r["package_version"] for r in catalogue["versions"].values()},
        )
        for entry in catalogue["versions"].values():
            self.assertEqual(entry["artifact_status"], "QA_APPROVED")
            self.assertEqual(entry["approval"], "approved_for_test")
            self.assertEqual(entry["qualification"]["engineering_qa"]["status"], "QA_VERIFIED")
            self.assertEqual(ROOT / entry["qualification"]["engineering_qa"]["evidence_ref"], ref)

    def test_listing_exposes_qa_confirmation_for_every_version(self):
        code, result = versions([])
        self.assertEqual(code, 0)
        self.assertEqual(len(result["versions"]), 20)
        self.assertTrue(
            all(v["qaVerification"]["status"] == "QA_VERIFIED" for v in result["versions"])
        )
        self.assertEqual(result["dynamicLatest"], "MUTABLE_NOT_RESOLVED")

    def test_qa_confirmation_does_not_invent_platform_or_integrity_evidence(self):
        catalogue, _ = load_catalogues()
        entry = catalogue["versions"]["12.8"]
        self.assertIsNone(entry["integrity"]["sha256"])
        self.assertEqual(entry["qualification"]["platforms"]["ubuntu-24.04-amd64"], "NOT_TESTED")
        self.assertTrue(all(a["runtime_validation"] == "not_run" for a in entry["artifacts"]))
        host = {"os": "ubuntu", "version": "24.04", "architecture": "x86_64"}
        with self.assertRaises(FrameworkError):
            qualification_guard("12.8", entry, host)
        self.assertEqual(
            qualification_guard("12.8", entry, host, True), "EXPERIMENTAL_VERSION_TEST"
        )

    def test_local_runtime_contracts_and_production_boundary_are_unchanged(self):
        catalogue, _ = load_catalogues()
        manifest = manifest_for(catalogue)
        self.assertFalse(manifest["productionApproved"])
        self.assertEqual(manifest["testedPackages"], ["12.10.1.1", "12.9.2.2"])
        self.assertEqual(catalogue["aliases"]["recommended"], "12.10")
        self.assertTrue(
            all(
                e["artifact_status"] != "PRODUCTION_APPROVED"
                for e in catalogue["versions"].values()
            )
        )

    def test_confirmation_schema_rejects_unsupported_or_traversing_evidence(self):
        catalogue, _ = load_catalogues()
        for value in [
            {
                "status": "PRODUCTION_APPROVED",
                "evidence_ref": "evidence/engineering-qa/confirmation.json",
            },
            {"status": "QA_VERIFIED", "evidence_ref": "../../secret.json"},
        ]:
            invalid = copy.deepcopy(catalogue)
            invalid["versions"]["12.8"]["qualification"]["engineering_qa"] = value
            with self.assertRaises(FrameworkError):
                validate_schema(invalid, "versions")
