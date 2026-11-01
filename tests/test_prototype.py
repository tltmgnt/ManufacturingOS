from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from manufacturing_os import ManufacturingInput, Orchestrator
from manufacturing_os.engine import DEPENDENCIES, MockAgent, invalidate, result_revision, task_order, verify
from manufacturing_os.store import save_run

ROOT = Path(__file__).resolve().parents[1]


class PrototypeTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((ROOT / "examples/synthetic-cnc.json").read_text())
        self.package = ManufacturingInput.from_dict(deepcopy(self.raw))

    def test_deterministic_plan_and_pending_approval(self):
        first = Orchestrator().run(self.package)
        self.assertEqual(asdict(first), asdict(Orchestrator().run(self.package)))
        self.assertEqual(first.verification.status, "CONDITIONAL")
        self.assertEqual(first.state_history[-1], "HUMAN_REVIEW")
        self.assertFalse(first.production_authorized)
        self.assertEqual(first.approval_state, "PENDING_HUMAN_REVIEW")
        self.assertEqual(set(first.results), set(DEPENDENCIES))
        for aid, result in first.results.items():
            self.assertEqual(set(result.upstream_revisions), set(DEPENDENCIES[aid]))
            self.assertTrue(result.open_issues)
            self.assertTrue(all(v is None for v in result.findings.values()))

    def test_invalid_inputs_rejected(self):
        cases = []
        for key in self.raw:
            item = deepcopy(self.raw)
            del item[key]
            cases.append(item)
        for key, value in [("schema_version", "2"), ("product_id", ""), ("bom", []),
                           ("requirements", []), ("facility", {}), ("constraints", {})]:
            cases.append({**deepcopy(self.raw), key: value})
        for value in [True, "10", 0, -1, float("nan"), float("inf")]:
            item = deepcopy(self.raw)
            item["demand"]["value"] = value
            cases.append(item)
        for unit in [None, "", 10]:
            item = deepcopy(self.raw)
            item["demand"]["unit"] = unit
            cases.append(item)
        for satisfied in [0, 1, "true"]:
            item = deepcopy(self.raw)
            item["constraints"][0]["satisfied"] = satisfied
            cases.append(item)
        item = deepcopy(self.raw)
        item["constraints"][0]["issue"] = None
        cases.append(item)
        cases.append({**deepcopy(self.raw), "unexpected": "field"})
        for index, item in enumerate(cases):
            with self.subTest(case=index), self.assertRaises((ValueError, TypeError)):
                ManufacturingInput.from_dict(item)

    def test_dag_rejects_cycles_and_unknown_dependencies(self):
        with self.assertRaises(ValueError):
            task_order({"a": ("b",), "b": ("a",)})
        with self.assertRaises(ValueError):
            task_order({"a": ("missing",)})
        order = task_order(DEPENDENCIES)
        for aid, deps in DEPENDENCIES.items():
            for dep in deps:
                self.assertLess(order.index(dep), order.index(aid))

    def test_hard_constraint_overrides_soft_success(self):
        self.raw["constraints"][0].update(satisfied=False, issue="Envelope exceeded")
        self.raw["constraints"].append({"constraint_id": "cheap", "kind": "soft", "satisfied": True, "issue": None})
        plan = Orchestrator().run(ManufacturingInput.from_dict(self.raw))
        self.assertEqual(plan.verification.status, "FAIL")
        self.assertEqual(plan.state_history[-1], "REVISION_REQUIRED")
        self.assertEqual(plan.verification.conflicts[0]["conflict_id"], "machine-envelope")
        self.assertFalse(plan.production_authorized)

    def test_missing_results_fail(self):
        results = Orchestrator().run(self.package).results
        del results["A1"]
        self.assertEqual(verify(self.package, results).status, "FAIL")

    def test_input_change_invalidates_every_result_even_without_revision_bump(self):
        results = Orchestrator().run(self.package).results
        self.raw["demand"]["value"] = 101
        changed = ManufacturingInput.from_dict(self.raw)
        self.assertEqual(invalidate(changed, results), set(DEPENDENCIES))
        rerun = Orchestrator().run(changed)
        self.assertNotEqual(rerun.results["A1"].revision, Orchestrator().run(self.package).results["A1"].revision)
        self.assertFalse(invalidate(changed, rerun.results))

    def test_upstream_change_invalidates_transitive_dependents(self):
        results = Orchestrator().run(self.package).results
        results["A7"].open_issues.append("Capacity context changed")
        results["A7"].revision = result_revision(results["A7"])
        self.assertEqual(invalidate(self.package, results), {"A8", "A9", "A3"})
        self.assertEqual(results["A6"].status, "CONDITIONAL")
        self.assertEqual(verify(self.package, results).status, "FAIL")

    def test_result_tampering_detected(self):
        results = Orchestrator().run(self.package).results
        results["A1"].findings["dfm"] = "looks good"
        self.assertEqual(invalidate(self.package, results), set(DEPENDENCIES))

    def test_evidence_contract_and_reference_validation(self):
        evidence = {"evidence_id": "E1", "source_uri": "synthetic://drawing", "source_owner": "demo",
                    "revision": "A", "captured_at": "2026-11-01T00:00:00Z", "evidence_type": "synthetic",
                    "claim_ids": ["R1"], "content_hash": None}
        self.raw["evidence"] = [evidence]
        package = ManufacturingInput.from_dict(self.raw)
        self.assertEqual(package.evidence[0].revision, "A")
        for key, value in [("captured_at", "2026-11-01T00:00:00"), ("claim_ids", ["unknown"]),
                           ("revision", ""), ("captured_at", "2026-11-01T00:00:00+01:00")]:
            bad = deepcopy(self.raw)
            bad["evidence"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                ManufacturingInput.from_dict(bad)
        results = Orchestrator().run(package).results
        results["A1"].evidence_refs = ["missing"]
        results["A1"].revision = result_revision(results["A1"])
        self.assertEqual(verify(package, results).status, "FAIL")

    def test_mock_cannot_establish_pass(self):
        self.raw["constraints"][0].update(satisfied=True, issue=None)
        package = ManufacturingInput.from_dict(self.raw)
        self.assertEqual(Orchestrator().run(package).verification.status, "CONDITIONAL")

    def test_agent_exception_becomes_recorded_failure(self):
        class Broken(MockAgent):
            def run(self, package, upstream):
                raise RuntimeError("seeded failure")
        agents = {aid: MockAgent(aid) for aid in DEPENDENCIES}
        agents["A2"] = Broken("A2")
        plan = Orchestrator(agents).run(self.package)
        self.assertEqual(plan.verification.status, "FAIL")
        self.assertIn("seeded failure", plan.results["A2"].open_issues[0])
        self.assertFalse(plan.production_authorized)

    def test_audit_reconstruction_and_unique_records(self):
        plan = Orchestrator().run(self.package)
        with tempfile.TemporaryDirectory() as directory:
            path = save_run(directory, self.package, plan)
            other = save_run(directory, self.package, plan)
            self.assertNotEqual(path, other)
            record = json.loads(path.read_text())
            restored = ManufacturingInput.from_dict(record["input"])
            self.assertEqual(asdict(Orchestrator().run(restored)), record["plan"])
            self.assertEqual(record["task_graph"], {k: list(v) for k, v in DEPENDENCIES.items()})
            self.assertIn("+00:00", record["timestamp"])

    def test_cli_success_fail_and_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            for mode, code in [("unknown", 0), ("violation", 1), ("invalid", 2)]:
                raw = deepcopy(self.raw)
                if mode == "violation":
                    raw["constraints"][0]["satisfied"] = False
                if mode == "invalid":
                    raw.pop("demand")
                source.write_text(json.dumps(raw))
                result = subprocess.run([sys.executable, "-m", "manufacturing_os", str(source),
                                         "--output-dir", str(Path(directory) / mode)],
                                        cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, code, result.stderr)
                if code != 2:
                    self.assertFalse(json.loads(result.stdout)["production_authorized"])
                else:
                    self.assertFalse((Path(directory) / mode).exists())


if __name__ == "__main__":
    unittest.main()
