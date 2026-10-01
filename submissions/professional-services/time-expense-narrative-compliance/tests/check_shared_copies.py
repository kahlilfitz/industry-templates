#!/usr/bin/env python3
"""Fail when a per-skill copy of a shared file drifts from its single source of truth.

Sources of truth (edit these, then copy into every skill):
  contracts/ps.time-expense-narrative-compliance.v1.json -> skills/*/contracts/
  references/*.md                                         -> skills/*/references/
  skills/activity-pull/scripts/signal_policy.py           -> every skills/*/scripts/signal_policy.py
  skills/activity-pull/scripts/steering_guard.py          -> every skills/*/scripts/steering_guard.py

steering_guard.py is vendored byte-identically from the shared detector and never edited here. Its
SHA-256 is pinned in STEERING_GUARD_SHA256 (the single place to change when a new release is copied in).

  python3 tests/check_shared_copies.py
"""
import glob
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEERING_GUARD_SHA256 = "17aa0ba6b0728417f3e60a0c8a80845009a8aa94eaa6f9640db306e28b617073"  # steering_guard 1.1.0
STEERING_GUARD = os.path.join(ROOT, "skills", "activity-pull", "scripts", "steering_guard.py")


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
    pairs += [(STEERING_GUARD, os.path.join(s, "scripts", "steering_guard.py"))
              for s in skills if s != os.path.dirname(os.path.dirname(STEERING_GUARD))]
    drift = 0
    if not os.path.exists(STEERING_GUARD) or digest(STEERING_GUARD) != STEERING_GUARD_SHA256:
        print(f"PIN     {os.path.relpath(STEERING_GUARD, ROOT)} does not match STEERING_GUARD_SHA256")
        drift += 1
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
