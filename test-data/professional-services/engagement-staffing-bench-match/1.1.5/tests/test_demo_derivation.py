"""Hardening item G4b: every structured demo input re-derives from its scenario's raw pack."""
import importlib.util
import json
import unittest
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = DATA_ROOT / "demo-data"

_spec = importlib.util.spec_from_file_location(
    "esbm_derive_inputs", Path(__file__).resolve().with_name("derive_inputs.py")
)
derive_inputs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(derive_inputs)


def _ascii(text):
    return str(text).encode("ascii", "backslashreplace").decode()


def _show(value):
    return _ascii(json.dumps(value, ensure_ascii=True, sort_keys=True))


def json_diff(expected, actual, path="$"):
    """Return the JSON paths at which ``actual`` differs from ``expected``."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        diffs = []
        for key in sorted(set(expected) | set(actual), key=str):
            child = f"{path}.{key}"
            if key not in actual:
                diffs.append(f"{child}: missing from derived output")
            elif key not in expected:
                diffs.append(f"{child}: not in the fixture (derived {_show(actual[key])})")
            else:
                diffs.extend(json_diff(expected[key], actual[key], child))
        return diffs
    if isinstance(expected, list) and isinstance(actual, list):
        diffs = [f"{path}: length {len(expected)} in fixture, {len(actual)} derived"] \
            if len(expected) != len(actual) else []
        for index, (left, right) in enumerate(zip(expected, actual)):
            diffs.extend(json_diff(left, right, f"{path}[{index}]"))
        return diffs
    if type(expected) is not type(actual) or expected != actual:
        return [f"{path}: fixture {_show(expected)}, derived {_show(actual)}"]
    return []


class DemoInputDerivationTests(unittest.TestCase):
    maxDiff = None

    def assert_derives(self, scenario, name):
        scenario_dir = DEMO_ROOT / scenario
        fixture = json.loads((scenario_dir / f"{name}.json").read_text(encoding="utf-8"))
        derived = derive_inputs.derive(scenario_dir)[name]
        diffs = json_diff(fixture, derived)
        if diffs or fixture != derived:
            self.fail(_ascii(
                f"{scenario}/{name}.json does not re-derive from raw/ at:\n  " + "\n  ".join(diffs)
            ))

    def test_scenario_a_happy_roles_derive_from_raw(self):
        self.assert_derives("scenario-a-happy", "roles")

    def test_scenario_a_happy_bench_derive_from_raw(self):
        self.assert_derives("scenario-a-happy", "bench")

    def test_scenario_a_happy_constraints_derive_from_raw(self):
        self.assert_derives("scenario-a-happy", "constraints")

    def test_scenario_b_drama_roles_derive_from_raw(self):
        self.assert_derives("scenario-b-drama", "roles")

    def test_scenario_b_drama_bench_derive_from_raw(self):
        self.assert_derives("scenario-b-drama", "bench")

    def test_scenario_b_drama_constraints_derive_from_raw(self):
        self.assert_derives("scenario-b-drama", "constraints")

    def test_derivation_is_sensitive_to_each_raw_source(self):
        scenario_dir = DEMO_ROOT / "scenario-b-drama"
        sources = derive_inputs.read_raw(scenario_dir)
        baseline = derive_inputs.derive_from_sources(scenario_dir.name, sources)
        edits = [
            ("sow-role-extract.md", "| 20 weeks |", "| 21 weeks |", "roles",
             "$.roles[0].duration_weeks"),
            ("staffing-request-email.txt", "Mina is the obvious pick", "Mina may be free", "roles",
             "$.escalations"),
            ("bench-roster.csv", ",Owen Ramos,manager,", ",Owen Ramos,senior manager,", "bench",
             "$.bench_candidates[1].seniority"),
            ("conflicts-register-extract.csv", "C-204,prior_client_role,Aster Foods Cooperative,closed",
             "C-204,prior_client_role,Aster Foods Cooperative,open", "constraints",
             "$.constraints[3].status"),
        ]
        for raw_file, old, new, output, path in edits:
            with self.subTest(raw_file=raw_file):
                self.assertEqual(1, sources[raw_file].count(old), _ascii(f"{raw_file}: edit anchor"))
                mutated = dict(sources, **{raw_file: sources[raw_file].replace(old, new)})
                derived = derive_inputs.derive_from_sources(scenario_dir.name, mutated)
                diffs = json_diff(baseline[output], derived[output])
                self.assertTrue(
                    any(diff.startswith(path) for diff in diffs),
                    _ascii(f"changing {raw_file} did not change {output} at {path}: {diffs}"),
                )
