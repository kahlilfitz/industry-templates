#!/usr/bin/env python3
"""Every skill carries byte-identical copies of the shared contract, references and engine modules.

Runner contract: python tests/check_shared_copies.py [--plugin-root <dir>]   (or PLUGIN_ROOT)
The plugin root is an extracted MOS3 ZIP or the submission folder; with neither, it defaults to
<repo>/submissions/<industry>/<slug>, where this file sits in test-data/<industry>/<slug>/<version>/tests/.
Prints one line per problem and "N/M shared copies identical to their source"; exit 1 on any problem.
"""
import argparse
import hashlib
import os
import sys
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[1]
# The one place the vendored shared detector is pinned. After a byte-identical re-copy of a new
# shared\steering-guard\steering_guard.py release into every engine skill, update only this constant.
STEERING_GUARD_SHA256 = "7edc38050b0b807348a38b8a690d087b8ec475ab747efff83596996cb98f365a"
SKILLS = ("artifact-assemble", "asset-identify", "lesson-cluster", "sanitize-check", "knowledge-record")
DOC_CANONICAL = "artifact-assemble"
DOC_FILES = (
    "contracts/ps.engagement-closeout-knowledge-harvest.v1.json",
    "references/reuse-asset-rubric.md",
    "references/lesson-taxonomy.md",
    "references/confidentiality-sanitisation-rules.md",
)
ENGINE_CANONICAL = "asset-identify"
ENGINE_SKILLS = ("asset-identify", "lesson-cluster", "sanitize-check", "knowledge-record")
ENGINE_FILES = ("scripts/steering_guard.py", "scripts/closeout_core.py")


def default_plugin_root():
    slug_dir = DATA_ROOT.parent
    industry_dir = slug_dir.parent
    return industry_dir.parents[1] / "submissions" / industry_dir.name / slug_dir.name


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pairs_for(root):
    """(source, copy) pairs that must be byte-identical."""
    skills = root / "skills"
    pairs = []
    for relative in DOC_FILES:
        source = skills / DOC_CANONICAL / relative
        pairs += [(source, skills / name / relative) for name in SKILLS if name != DOC_CANONICAL]
    for relative in ENGINE_FILES:
        source = skills / ENGINE_CANONICAL / relative
        pairs += [(source, skills / name / relative) for name in ENGINE_SKILLS if name != ENGINE_CANONICAL]
    return pairs


def check(root):
    """Problem lines (empty when every copy matches) and the number of pairs checked."""
    root = Path(root)
    problems = []
    guard = root / "skills" / ENGINE_CANONICAL / "scripts" / "steering_guard.py"
    if not guard.is_file() or digest(guard) != STEERING_GUARD_SHA256:
        problems.append("PIN     steering_guard.py does not match STEERING_GUARD_SHA256")
    pairs = pairs_for(root)
    drift = 0
    for source, copy in pairs:
        if not source.is_file():
            problems.append("MISSING " + source.relative_to(root).as_posix())
            drift += 1
        elif not copy.is_file():
            problems.append("MISSING " + copy.relative_to(root).as_posix())
            drift += 1
        elif digest(source) != digest(copy):
            problems.append("DRIFT   " + copy.relative_to(root).as_posix())
            drift += 1
    return problems, len(pairs), drift


def main(argv=None):
    parser = argparse.ArgumentParser(description="Closeout shared-copy check.", allow_abbrev=False)
    parser.add_argument("--plugin-root", metavar="DIR", help="extracted MOS3 ZIP or submission folder (default: PLUGIN_ROOT, then the submission)")
    args = parser.parse_args(argv)
    root = Path(args.plugin_root or os.environ.get("PLUGIN_ROOT") or default_plugin_root()).resolve()

    def safe(text):
        return str(text).encode("ascii", "backslashreplace").decode("ascii")

    print(safe(f"plugin root: {root}"))
    print(safe(f"data root: {DATA_ROOT}"))
    if not (root / "skills").is_dir():
        print(safe(f"plugin root has no skills/ folder: {root}"), file=sys.stderr)
        return 2
    problems, total, drift = check(root)
    for line in problems:
        print(safe(line))
    print(f"{total - drift}/{total} shared copies identical to their source (steering_guard.py pinned)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
