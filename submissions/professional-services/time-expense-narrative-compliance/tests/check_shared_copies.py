#!/usr/bin/env python3
"""Fail when a per-skill copy of a shared file drifts from its single source of truth.

Sources of truth (edit these, then copy into every skill):
  contracts/ps.time-expense-narrative-compliance.v1.json -> skills/*/contracts/
  references/*.md                                         -> skills/*/references/
  skills/activity-pull/scripts/signal_policy.py           -> every skills/*/scripts/signal_policy.py

  python3 tests/check_shared_copies.py
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
    skills = sorted(d for d in glob.glob(os.path.join(ROOT, "skills", "*")) if os.path.isdir(d))
    pairs = []
    for src in sorted(glob.glob(os.path.join(ROOT, "contracts", "*.json"))):
        pairs += [(src, os.path.join(s, "contracts", os.path.basename(src))) for s in skills]
    for src in sorted(glob.glob(os.path.join(ROOT, "references", "*.md"))):
        pairs += [(src, os.path.join(s, "references", os.path.basename(src))) for s in skills]
    policy = os.path.join(ROOT, "skills", "activity-pull", "scripts", "signal_policy.py")
    pairs += [(policy, os.path.join(s, "scripts", "signal_policy.py")) for s in skills if s != os.path.dirname(os.path.dirname(policy))]
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
