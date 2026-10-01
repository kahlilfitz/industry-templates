#!/usr/bin/env python3
"""Fail when per-skill copies of shared files drift from their source of truth.

Sources of truth:
  contracts/ps.deliverable-review-quality-gate.v1.json -> skills/*/contracts/
  references/*.md                                      -> skills/*/references/
  skills/assertion-map/scripts/assertion_rules.py      -> skills/gate-check/scripts/
  STEERING_GUARD_SHA256 (vendored shared detector)     -> every skills/*/scripts/steering_guard.py

  python tests/check_shared_copies.py
"""
import glob
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The one pin for the vendored shared detector steering_guard.py. It is copied byte-for-byte and never edited here;
# to take a new release, copy the file into every folder in STEERING_GUARD_COPIES and update this constant only.
STEERING_GUARD_SHA256 = "17aa0ba6b0728417f3e60a0c8a80845009a8aa94eaa6f9640db306e28b617073"
STEERING_GUARD_COPIES = ("skills/gate-check/scripts/steering_guard.py",)


def steering_guard_copies():
    """Every vendored copy: the registered ones plus any other skills/*/scripts/steering_guard.py."""
    found = {os.path.relpath(path, ROOT).replace(os.sep, "/") for path in glob.glob(os.path.join(ROOT, "skills", "*", "scripts", "steering_guard.py"))}
    return sorted(found | set(STEERING_GUARD_COPIES))


def digest(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    skills = sorted(path for path in glob.glob(os.path.join(ROOT, "skills", "*")) if os.path.isdir(path))
    pairs = []
    for src in sorted(glob.glob(os.path.join(ROOT, "contracts", "*.json"))):
        pairs.extend((src, os.path.join(skill, "contracts", os.path.basename(src))) for skill in skills)
    for src in sorted(glob.glob(os.path.join(ROOT, "references", "*.md"))):
        pairs.extend((src, os.path.join(skill, "references", os.path.basename(src))) for skill in skills)
    # gate_check recomputes assertion_map output, so both engines must classify with identical rules.
    pairs.append((os.path.join(ROOT, "skills", "assertion-map", "scripts", "assertion_rules.py"),
                  os.path.join(ROOT, "skills", "gate-check", "scripts", "assertion_rules.py")))
    drift = 0
    for src, copy in pairs:
        rel = os.path.relpath(copy, ROOT)
        if not os.path.exists(copy):
            print(f"MISSING {rel}")
            drift += 1
        elif digest(src) != digest(copy):
            print(f"DRIFT   {rel}")
            drift += 1
    vendored = steering_guard_copies()
    for rel in vendored:
        path = os.path.join(ROOT, *rel.split("/"))
        if not os.path.exists(path):
            print(f"MISSING {rel}")
            drift += 1
        elif digest(path) != STEERING_GUARD_SHA256:
            print(f"DRIFT   {rel} (does not match STEERING_GUARD_SHA256)")
            drift += 1
    total = len(pairs) + len(vendored)
    print(f"{total - drift}/{total} shared copies identical to their source")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
