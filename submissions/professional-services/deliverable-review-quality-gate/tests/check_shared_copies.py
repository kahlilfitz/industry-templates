#!/usr/bin/env python3
"""Fail when per-skill copies of shared files drift from their source of truth.

Sources of truth:
  contracts/ps.deliverable-review-quality-gate.v1.json -> skills/*/contracts/
  references/*.md                                      -> skills/*/references/

  python tests/check_shared_copies.py
"""
import glob
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
    drift = 0
    for src, copy in pairs:
        rel = os.path.relpath(copy, ROOT)
        if not os.path.exists(copy):
            print(f"MISSING {rel}")
            drift += 1
        elif digest(src) != digest(copy):
            print(f"DRIFT   {rel}")
            drift += 1
    print(f"{len(pairs) - drift}/{len(pairs)} shared copies identical to their source")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
