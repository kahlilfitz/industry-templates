import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


asset_identify = load_module(
    "closeout_asset_identify",
    Path("skills/asset-identify/scripts/asset_identify.py"),
)
lesson_cluster = load_module(
    "closeout_lesson_cluster",
    Path("skills/lesson-cluster/scripts/lesson_cluster.py"),
)
sanitize_check = load_module(
    "closeout_sanitize_check",
    Path("skills/sanitize-check/scripts/sanitize_check.py"),
)


def run_engine(module, input_path, output_path):
    argv = [
        f"{module.__name__}.py",
        "--input",
        str(input_path),
        "--out",
        str(output_path),
    ]
    with mock.patch.object(sys, "argv", argv):
        return module.main()


class ContractValidationTests(unittest.TestCase):
    def test_wrong_contract_fails_explicitly_in_every_engine(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            input_path = temp / "input.json"
            output_path = temp / "output.json"
            input_path.write_text(
                json.dumps({"contract_version": "wrong"}),
                encoding="utf-8",
            )

            for module in (asset_identify, lesson_cluster, sanitize_check):
                with self.subTest(module=module.__name__):
                    with self.assertRaisesRegex(ValueError, "wrong contract version"):
                        run_engine(module, input_path, output_path)

    def test_asset_identify_rejects_missing_candidate_assets(self):
        payload = {
            "contract_version": asset_identify.CONTRACT,
            "artifacts": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            input_path = temp / "input.json"
            output_path = temp / "output.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError,
                "missing or invalid required array: candidate_assets",
            ):
                run_engine(asset_identify, input_path, output_path)


class LessonClusterTests(unittest.TestCase):
    def test_unmatched_evidence_stays_unclassified(self):
        self.assertEqual(
            ("unclassified", 0),
            lesson_cluster.category_for("The workshop room layout was memorable."),
        )

    def test_clusters_are_ranked_and_use_category_specific_citations(self):
        payload = {
            "contract_version": lesson_cluster.CONTRACT,
            "decision_log": [
                {
                    "decision_id": "D-1",
                    "summary": "Critical training readiness blocker delayed go-live.",
                    "impact": "Executive escalation and rework.",
                    "confidence": 0.95,
                    "source": "skill:artifact-assemble",
                    "citation": "decision row 1",
                },
                {
                    "decision_id": "D-2",
                    "summary": "The workshop room layout was memorable.",
                    "impact": "",
                    "confidence": 0.9,
                    "source": "skill:artifact-assemble",
                    "citation": "decision row 2",
                },
            ],
            "retrospective_inputs": [],
            "run_metadata": {},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            input_path = temp / "input.json"
            output_path = temp / "output.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(0, run_engine(lesson_cluster, input_path, output_path))
            result = json.loads(output_path.read_text(encoding="utf-8"))

        clusters = result["lesson_clusters"]
        self.assertEqual(
            sorted(
                (cluster["priority_score"] for cluster in clusters),
                reverse=True,
            ),
            [cluster["priority_score"] for cluster in clusters],
        )
        citations = {
            cluster["category"]: cluster["citation"]
            for cluster in clusters
        }
        self.assertIn("lesson-taxonomy.md #1.2", citations["adoption-change"])
        self.assertIn("lesson-taxonomy.md #1.5", citations["unclassified"])


class SanitizationTests(unittest.TestCase):
    def run_scenario(self, scenario):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            asset_path = temp / "asset.json"
            lessons_path = temp / "lessons.json"
            governed_path = temp / "governed.json"
            source = ROOT / "demo-data" / scenario / "engagement.json"
            self.assertEqual(0, run_engine(asset_identify, source, asset_path))
            self.assertEqual(0, run_engine(lesson_cluster, asset_path, lessons_path))
            self.assertEqual(0, run_engine(sanitize_check, lessons_path, governed_path))
            return json.loads(governed_path.read_text(encoding="utf-8"))

    def run_payload(self, assets=None, retrospective_inputs=None, lesson_clusters=None):
        payload = {
            "contract_version": sanitize_check.CONTRACT,
            "engagement": {
                "engagement_id": "ENG-TEST",
                "client_name": "Contoso Health",
            },
            "reusable_asset_shortlist": assets or [],
            "retrospective_inputs": retrospective_inputs or [],
            "lesson_clusters": lesson_clusters or [],
            "escalations": [],
            "provenance": {},
            "run_metadata": {},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            input_path = temp / "input.json"
            output_path = temp / "output.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(0, run_engine(sanitize_check, input_path, output_path))
            return json.loads(output_path.read_text(encoding="utf-8"))

    def asset(self, marker=None, title="Reusable delivery checklist"):
        return {
            "asset_id": f"AST-{marker or 'TEXT'}",
            "title": title,
            "reuse_score": 90,
            "recommendation": "shortlist",
            "confidentiality_markers": [marker] if marker else [],
            "aggregation_tokens": [],
            "confidence": 0.9,
        }

    def test_every_finding_cites_confidentiality_rules(self):
        result = self.run_scenario("scenario-b-drama")
        for finding in result["sanitisation_report"]["findings"]:
            with self.subTest(finding=finding["target_id"]):
                self.assertIn(
                    "confidentiality-sanitisation-rules.md",
                    finding["citation"],
                )

    def test_governed_knowledge_record_excludes_raw_seeds(self):
        result = self.run_scenario("scenario-b-drama")
        knowledge_record = result["knowledge_record"]
        serialized = json.dumps(knowledge_record)

        self.assertNotIn("engagement_summary_seed", knowledge_record)
        self.assertIn("engagement_context_guidance", knowledge_record)
        self.assertNotIn("summary_seed", serialized)
        for sensitive_value in (
            "GridMesh Optimizer",
            "6,200",
            "2026-04-14",
            "European utility",
            "Maya Patel",
        ):
            self.assertNotIn(sensitive_value, serialized)
        self.assertFalse(
            any("summary_seed" in lesson for lesson in result["lesson_clusters"])
        )

    def test_named_person_markers_hold_assets(self):
        for marker in ("named_individual", "named_person_blame"):
            with self.subTest(marker=marker):
                result = self.run_payload(assets=[self.asset(marker)])
                self.assertEqual([], result["released_assets"])
                self.assertEqual(
                    "HOLD_PERSONAL_DATA_REWRITE",
                    result["held_assets"][0]["clearance_state"],
                )

    def test_commercial_markers_hold_until_sanitization_is_verified(self):
        for marker in ("contract_value", "pricing", "margin"):
            with self.subTest(marker=marker):
                result = self.run_payload(assets=[self.asset(marker)])
                self.assertEqual([], result["released_assets"])
                self.assertEqual(
                    "HOLD_REDACTION_REQUIRED",
                    result["held_assets"][0]["clearance_state"],
                )

    def test_client_name_in_asset_text_holds(self):
        result = self.run_payload(
            assets=[self.asset(title="Contoso Health transformation playbook")]
        )
        self.assertEqual([], result["released_assets"])
        self.assertIn(
            "contains the engagement client name",
            result["held_assets"][0]["reason"],
        )

    def test_untagged_named_person_blame_requires_rewrite(self):
        result = self.run_payload(
            retrospective_inputs=[
                {
                    "input_id": "RET-1",
                    "text": "Jordan Reyes failed to deliver the cutover plan and caused rework.",
                    "named_people": [],
                    "confidence": 0.9,
                    "citation": "retrospective row 1",
                }
            ],
            lesson_clusters=[
                {
                    "cluster_id": "LC-1",
                    "category": "delivery-governance",
                    "priority_score": 90,
                    "review_candidate": False,
                    "evidence_ids": ["RET-1"],
                    "evidence_citations": ["retrospective row 1"],
                    "sensitivity_signals": [],
                    "confidence": 0.9,
                    "citation": "lesson-taxonomy.md #1.1",
                }
            ],
        )
        lesson_finding = next(
            finding
            for finding in result["sanitisation_report"]["findings"]
            if finding["target_type"] == "lesson"
        )
        self.assertEqual("HOLD_PERSONAL_DATA_REWRITE", lesson_finding["clearance_state"])
        self.assertTrue(result["lesson_clusters"][0]["rewrite_required"])

    def test_engine_versions_advance_in_provenance(self):
        result = self.run_scenario("scenario-a-happy")
        self.assertEqual(
            [
                "asset_identify/1.0.2",
                "lesson_cluster/1.0.2",
                "sanitize_check/1.0.2",
            ],
            result["provenance"]["engines"],
        )


class SharedCopyTests(unittest.TestCase):
    def test_contract_and_reference_copies_match(self):
        contract = (
            ROOT / "contracts/ps.engagement-closeout-knowledge-harvest.v1.json"
        ).read_bytes()
        references = {
            name: (ROOT / "references" / name).read_bytes()
            for name in (
                "reuse-asset-rubric.md",
                "lesson-taxonomy.md",
                "confidentiality-sanitisation-rules.md",
            )
        }

        for skill_dir in (ROOT / "skills").iterdir():
            if not skill_dir.is_dir():
                continue
            self.assertEqual(
                contract,
                (
                    skill_dir
                    / "contracts/ps.engagement-closeout-knowledge-harvest.v1.json"
                ).read_bytes(),
            )
            for name, canonical in references.items():
                self.assertEqual(
                    canonical,
                    (skill_dir / "references" / name).read_bytes(),
                )


if __name__ == "__main__":
    unittest.main()
