"""Engine regression suite for engagement-closeout-knowledge-harvest.

Runner contract:
    python tests/test_engines.py [--plugin-root <dir>] [--group <name> ...] [--list-groups]
PLUGIN_ROOT is the alternative to --plugin-root. The plugin root is an extracted MOS3 ZIP or the
submission folder; skills/... paths resolve against it. The data root is this file's parent
version folder; demo-data/... resolves there. Each test prints one ASCII-safe PASS or FAIL line as
it finishes; the last line is "N/M checks passed" and the exit code is 1 on any failure.
"""

import argparse
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import traceback
import unittest
from pathlib import Path
from unittest import mock


SLUG = "engagement-closeout-knowledge-harvest"
DATA_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAMES = (
    "artifact-assemble",
    "asset-identify",
    "lesson-cluster",
    "sanitize-check",
    "knowledge-record",
)
CONTRACT_FILE = "contracts/ps.engagement-closeout-knowledge-harvest.v1.json"
REFERENCE_FILES = (
    "references/reuse-asset-rubric.md",
    "references/lesson-taxonomy.md",
    "references/confidentiality-sanitisation-rules.md",
)


def ascii_safe(text):
    return str(text).encode("ascii", "backslashreplace").decode("ascii")


def emit(line):
    print(ascii_safe(line), flush=True)


def resolve_plugin_root(value):
    if value:
        root = Path(value)
    elif os.environ.get("PLUGIN_ROOT"):
        root = Path(os.environ["PLUGIN_ROOT"])
    else:
        root = DATA_ROOT.parents[3] / "submissions" / "professional-services" / SLUG
    return root.resolve()


sys.dont_write_bytecode = True
PLUGIN_ROOT = None
asset_identify = lesson_cluster = sanitize_check = None
SCENARIOS = ("scenario-a-happy", "scenario-b-drama")
ENGINE_VERSION = "1.0.3"


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, PLUGIN_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_engines():
    global asset_identify, lesson_cluster, sanitize_check
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


def run_engine(module, input_path, output_path, stdout_sink=None):
    """Run an engine's main(); its stdout is captured (and appended to stdout_sink if given)."""
    argv = [
        f"{module.__name__}.py",
        "--input",
        str(input_path),
        "--out",
        str(output_path),
    ]
    buffer = io.StringIO()
    try:
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(buffer):
            return module.main()
    finally:
        if stdout_sink is not None:
            stdout_sink.append(buffer.getvalue())


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
            source = DATA_ROOT / "demo-data" / scenario / "engagement.json"
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
                f"asset_identify/{ENGINE_VERSION}",
                f"lesson_cluster/{ENGINE_VERSION}",
                f"sanitize_check/{ENGINE_VERSION}",
            ],
            result["provenance"]["engines"],
        )
        for module in (asset_identify, lesson_cluster, sanitize_check):
            with self.subTest(module=module.__name__):
                self.assertTrue(module.ENGINE_VERSION.endswith(f"/{ENGINE_VERSION}"))


class GoldenTests(unittest.TestCase):
    """Both scenarios reproduce their expected/ goldens byte for byte (JSON and stdout), LF only."""

    CHAIN = (
        ("asset_identify", "engagement.json", "asset_shortlist.json"),
        ("lesson_cluster", "asset_shortlist.json", "lessons_clustered.json"),
        ("sanitize_check", "lessons_clustered.json", "governed.json"),
    )

    def test_scenarios_reproduce_goldens_byte_for_byte(self):
        engines = {
            "asset_identify": asset_identify,
            "lesson_cluster": lesson_cluster,
            "sanitize_check": sanitize_check,
        }
        for scenario in SCENARIOS:
            scenario_dir = DATA_ROOT / "demo-data" / scenario
            expected_dir = scenario_dir / "expected"
            with tempfile.TemporaryDirectory() as temp_dir:
                temp = Path(temp_dir)
                (temp / "engagement.json").write_bytes(
                    (scenario_dir / "engagement.json").read_bytes()
                )
                for name, input_name, output_name in self.CHAIN:
                    stdout = []
                    self.assertEqual(
                        0,
                        run_engine(engines[name], temp / input_name, temp / output_name, stdout),
                    )
                    produced = (temp / output_name).read_bytes()
                    with self.subTest(scenario=scenario, file=output_name):
                        self.assertNotIn(b"\r", produced)
                        self.assertEqual((expected_dir / output_name).read_bytes(), produced)
                    with self.subTest(scenario=scenario, file=f"{name}.stdout.txt"):
                        self.assertEqual(
                            (expected_dir / f"{name}.stdout.txt").read_text(encoding="utf-8"),
                            stdout[0],
                        )


class SharedCopyTests(unittest.TestCase):
    def test_contract_and_reference_copies_match(self):
        # Every skill carries its own copy (MOS3 skills are self-contained); the
        # artifact-assemble copy is canonical and every other copy must match it byte for byte.
        skills_dir = PLUGIN_ROOT / "skills"
        skill_dirs = sorted(path for path in skills_dir.iterdir() if path.is_dir())
        self.assertEqual(sorted(SKILL_NAMES), [path.name for path in skill_dirs])
        canonical_dir = skills_dir / SKILL_NAMES[0]
        for relative in (CONTRACT_FILE, *REFERENCE_FILES):
            canonical = (canonical_dir / relative).read_bytes()
            for skill_dir in skill_dirs:
                with self.subTest(skill=skill_dir.name, file=relative):
                    self.assertEqual(canonical, (skill_dir / relative).read_bytes())


class PackageBoundaryTests(unittest.TestCase):
    def test_no_fixture_data_or_cwd_dependency_in_plugin_root(self):
        for name in ("demo-data", "tests", ".claude-plugin"):
            with self.subTest(folder=name):
                self.assertFalse((PLUGIN_ROOT / name).exists())
        for path in (PLUGIN_ROOT / "skills").rglob("*"):
            if path.is_file() and path.suffix in (".md", ".py", ".json"):
                text = path.read_text(encoding="utf-8")
                with self.subTest(file=str(path.relative_to(PLUGIN_ROOT))):
                    for marker in ("../../", "demo-data/", "CLAUDE_PLUGIN_ROOT"):
                        self.assertNotIn(marker, text)


GROUPS = {
    "contract": (ContractValidationTests,),
    "lessons": (LessonClusterTests,),
    "sanitisation": (SanitizationTests,),
    "goldens": (GoldenTests,),
    "packaging": (SharedCopyTests, PackageBoundaryTests),
}
GROUP_HELP = {
    "contract": "wrong contract version and missing required arrays fail in every engine",
    "lessons": "lesson clustering, ranking and taxonomy citations",
    "sanitisation": "Govern holds, citations, raw-seed exclusion and engine versions",
    "goldens": "both scenarios reproduce expected/ goldens byte for byte (LF only)",
    "packaging": "byte-identical skill copies and the MOS3 package boundary",
}


class StreamingResult(unittest.TestResult):
    """Prints one PASS or FAIL line per test as it finishes; subtest failures fail the test."""

    def __init__(self):
        super().__init__()
        self.passed = 0
        self.failed = 0
        self.details = []
        self._current_failed = False

    def startTest(self, test):
        super().startTest(test)
        self._current_failed = False

    def _record(self, test, err):
        self._current_failed = True
        self.details.append((test, "".join(traceback.format_exception(*err))))

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, err)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, err)

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self._record(subtest, err)

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._current_failed = True
        self.details.append((test, "unexpected success"))

    def stopTest(self, test):
        super().stopTest(test)
        name = f"{type(test).__name__}.{test._testMethodName}"
        if self._current_failed:
            self.failed += 1
            emit(f"FAIL {name}")
        else:
            self.passed += 1
            emit(f"PASS {name}")


def build_suite(groups):
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for group in groups:
        for case in GROUPS[group]:
            suite.addTests(loader.loadTestsFromTestCase(case))
    return suite


def main(argv=None):
    global PLUGIN_ROOT
    parser = argparse.ArgumentParser(description=f"{SLUG} engine regression suite")
    parser.add_argument("--plugin-root", help="extracted MOS3 ZIP or submission folder (default: PLUGIN_ROOT, then the submission)")
    parser.add_argument("--group", action="append", choices=sorted(GROUPS), help="run only this group (repeatable)")
    parser.add_argument("--list-groups", action="store_true", help="list the test groups and exit")
    args = parser.parse_args(argv)

    grouped = {case for cases in GROUPS.values() for case in cases}
    ungrouped = [
        name for name, value in globals().items()
        if isinstance(value, type) and issubclass(value, unittest.TestCase)
        and value is not unittest.TestCase and value not in grouped
    ]
    if ungrouped:
        emit(f"ERROR: test classes not assigned to a group: {', '.join(sorted(ungrouped))}")
        return 2

    if args.list_groups:
        for group in GROUPS:
            emit(f"{group} ({build_suite([group]).countTestCases()} tests): {GROUP_HELP[group]}")
        return 0

    PLUGIN_ROOT = resolve_plugin_root(args.plugin_root)
    emit(f"Plugin root: {PLUGIN_ROOT}")
    emit(f"Data root:   {DATA_ROOT}")
    if not (PLUGIN_ROOT / "skills").is_dir():
        emit(
            f"ERROR: plugin root {PLUGIN_ROOT} has no skills/ folder; pass --plugin-root "
            "<extracted MOS3 ZIP or submission folder> or set PLUGIN_ROOT."
        )
        return 2
    load_engines()

    groups = list(dict.fromkeys(args.group)) if args.group else list(GROUPS)
    emit(f"Running {SLUG} engine tests: {', '.join(groups)}")
    suite = build_suite(groups)
    result = StreamingResult()
    suite.run(result)
    for test, detail in result.details:
        emit(f"--- FAIL detail: {test}")
        for line in detail.rstrip().splitlines():
            emit(line)
    total = result.passed + result.failed
    emit(f"{result.passed}/{total} checks passed")
    return 0 if result.failed == 0 and total > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
