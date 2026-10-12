#!/usr/bin/env python3
"""Fail when per-skill copies of shared files drift from their source of truth.

Each skill in the MOS3 package carries its own copy of the shared contract and rule references, so a skill works on
its own. The gate-check skill's copies are the source of truth (the package has no root contracts/ or references/):

  skills/gate-check/contracts/ps.deliverable-review-quality-gate.v1.json -> skills/*/contracts/
  skills/gate-check/references/{quality-gate-criteria,severity-rules}.md -> skills/*/references/
  skills/assertion-map/scripts/assertion_rules.py                        -> skills/gate-check/scripts/
  STEERING_GUARD_SHA256 (vendored shared detector)                       -> every skills/*/scripts/steering_guard.py

Skill-specific references (for example skills/gate-check/references/g8-withholding-and-input-rules.md) are not shared.

  python tests/check_shared_copies.py [--plugin-root DIR]

The plugin root is --plugin-root, else the PLUGIN_ROOT environment variable, else
<repo>/submissions/professional-services/deliverable-review-quality-gate (repo is four levels above this test-data
version folder). The working directory is never used.
"""
import glob
import hashlib
import os
import sys

PLUGIN_SLUG = "deliverable-review-quality-gate"
DATA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_SKILL = "gate-check"
SHARED_FILES = (
    "contracts/ps.deliverable-review-quality-gate.v1.json",
    "references/quality-gate-criteria.md",
    "references/severity-rules.md",
)


def plugin_root_from(argv):
    """--plugin-root DIR, else PLUGIN_ROOT, else the submission folder in this repository."""
    value = None
    args = list(argv)
    for index, arg in enumerate(args):
        if arg == "--plugin-root" and index + 1 < len(args):
            value = args[index + 1]
        elif arg.startswith("--plugin-root="):
            value = arg.partition("=")[2]
    value = value or os.environ.get("PLUGIN_ROOT")
    if not value:
        repo = os.path.abspath(os.path.join(DATA_ROOT, os.pardir, os.pardir, os.pardir, os.pardir))
        value = os.path.join(repo, "submissions", "professional-services", PLUGIN_SLUG)
    return os.path.abspath(value)


ROOT = plugin_root_from(sys.argv[1:])

# The one pin for the vendored shared detector steering_guard.py. It is copied byte-for-byte and never edited here;
# to take a new release, copy the file into every folder in STEERING_GUARD_COPIES and update this constant only.
STEERING_GUARD_SHA256 = "825d0550190150e78fd3a66fc3b8c8b6e5f4867e6620e47ed7381b0d796f4123"
STEERING_GUARD_COPIES = ("skills/assertion-map/scripts/steering_guard.py", "skills/gate-check/scripts/steering_guard.py")


def emit(line=""):
    """Print one line backslash-escaped to ASCII, so a cp1252 or ASCII console or pipe can always show it."""
    print(str(line).encode("ascii", "backslashreplace").decode("ascii"))


def steering_guard_copies():
    """Every vendored copy: the registered ones plus any other skills/*/scripts/steering_guard.py."""
    found = {os.path.relpath(path, ROOT).replace(os.sep, "/") for path in glob.glob(os.path.join(ROOT, "skills", "*", "scripts", "steering_guard.py"))}
    return sorted(found | set(STEERING_GUARD_COPIES))


def digest(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    if not os.path.isdir(os.path.join(ROOT, "skills")):
        emit(f"check_shared_copies: plugin root {ROOT} has no skills folder; pass --plugin-root or set PLUGIN_ROOT")
        return 2
    emit(f"plugin root: {ROOT}")
    emit(f"data root:   {DATA_ROOT}")
    skills = sorted(path for path in glob.glob(os.path.join(ROOT, "skills", "*")) if os.path.isdir(path))
    source = os.path.join(ROOT, "skills", SOURCE_SKILL)
    pairs = []
    for rel in SHARED_FILES:
        src = os.path.join(source, *rel.split("/"))
        pairs.extend((src, os.path.join(skill, *rel.split("/"))) for skill in skills if skill != source)
    # gate_check recomputes assertion_map output, so both engines must classify with identical rules.
    pairs.append((os.path.join(ROOT, "skills", "assertion-map", "scripts", "assertion_rules.py"),
                  os.path.join(ROOT, "skills", "gate-check", "scripts", "assertion_rules.py")))
    drift = 0
    for src, copy in pairs:
        if not os.path.exists(src):
            rel = os.path.relpath(src, ROOT)
            emit(f"MISSING {rel} (source of truth)")
            drift += 1
            continue
        rel = os.path.relpath(copy, ROOT)
        if not os.path.exists(copy):
            emit(f"MISSING {rel}")
            drift += 1
        elif digest(src) != digest(copy):
            emit(f"DRIFT   {rel}")
            drift += 1
    vendored = steering_guard_copies()
    for rel in vendored:
        path = os.path.join(ROOT, *rel.split("/"))
        if not os.path.exists(path):
            emit(f"MISSING {rel}")
            drift += 1
        elif digest(path) != STEERING_GUARD_SHA256:
            emit(f"DRIFT   {rel} (does not match STEERING_GUARD_SHA256)")
            drift += 1
    total = len(pairs) + len(vendored)
    emit(f"{total - drift}/{total} shared copies identical to their source")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
