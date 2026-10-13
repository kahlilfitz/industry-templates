#!/usr/bin/env python3
"""Fail when a per-skill copy of a shared file drifts from its single source of truth.

The MOS3 package ships only skills/, so every shared file lives inside the skills and the canonical copy is the one
in skills/activity-pull/ (edit it there, then copy it into every other skill):
  skills/activity-pull/contracts/ps.time-expense-narrative-compliance.v1.json -> skills/*/contracts/
  skills/activity-pull/references/*.md                                         -> skills/*/references/
  skills/activity-pull/config/signal-sources.json                              -> skills/*/config/
  skills/activity-pull/scripts/signal_policy.py           -> every skills/*/scripts/signal_policy.py
  skills/activity-pull/scripts/activity_pull.py           -> every skills/*/scripts/activity_pull.py
  skills/activity-pull/scripts/steering_guard.py          -> every skills/*/scripts/steering_guard.py
  skills/activity-pull/scripts/contract_check.py          -> every skills/*/scripts/contract_check.py
  skills/guideline-check/scripts/billing_rules.py         -> skills/{code-map,exception-report}/scripts/

steering_guard.py is vendored byte-identically from the shared detector and never edited here. Its
SHA-256 is pinned in STEERING_GUARD_SHA256 (the single place to change when a new release is copied in).

The plugin root is --plugin-root DIR, else the PLUGIN_ROOT environment variable, else
<repo>/submissions/professional-services/time-expense-narrative-compliance (as tests/run_tests.py resolves it).

  python3 tests/check_shared_copies.py [--plugin-root DIR]
"""
import glob
import hashlib
import os
import sys

SLUG = "time-expense-narrative-compliance"
DATA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEERING_GUARD_SHA256 = "2a4300dfc74123cd7e3c50b890b454b7da578915521e40aab2bdf2eb58ebdbe2"  # steering_guard 1.1.3
CANONICAL = "activity-pull"
BILLING_RULES_SKILL = "guideline-check"
BILLING_RULES_COPIES = ("code-map", "exception-report")  # every other engine that runs the shared rules


def say(text):
    """Print one line backslash-escaped to ASCII, so a path with any character prints on a cp1252 or ASCII stdout."""
    print(str(text).encode("ascii", "backslashreplace").decode("ascii"))


def digest(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def plugin_root(argv):
    """--plugin-root DIR or --plugin-root=DIR in argv (other arguments ignored), else PLUGIN_ROOT, else the default."""
    for i, arg in enumerate(argv):
        if arg == "--plugin-root" and i + 1 < len(argv):
            return os.path.abspath(argv[i + 1])
        if arg.startswith("--plugin-root=") and len(arg) > len("--plugin-root="):
            return os.path.abspath(arg[len("--plugin-root="):])
    if os.environ.get("PLUGIN_ROOT"):
        return os.path.abspath(os.environ["PLUGIN_ROOT"])
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(DATA_ROOT))))
    return os.path.join(repo, "submissions", "professional-services", SLUG)


def main(argv=None):
    root = plugin_root(sys.argv[1:] if argv is None else argv)
    canonical = os.path.join(root, "skills", CANONICAL)
    skills = sorted(d for d in glob.glob(os.path.join(root, "skills", "*")) if os.path.isdir(d))
    others = [s for s in skills if os.path.basename(s) != CANONICAL]
    if not os.path.isdir(canonical):
        say(f"MISSING skills/{CANONICAL} (plugin root has no canonical skill)")
        say("0/0 shared copies identical to their source")
        return 1
    pairs = []
    for folder, pattern in (("contracts", "*.json"), ("references", "*.md"), ("config", "*.json")):
        for src in sorted(glob.glob(os.path.join(canonical, folder, pattern))):
            pairs += [(src, os.path.join(s, folder, os.path.basename(src))) for s in others]
    # Every later engine re-derives the activity packet with activity_pull's own code (#12.1, #13.8).
    for name in ("signal_policy.py", "activity_pull.py", "steering_guard.py", "contract_check.py"):
        src = os.path.join(canonical, "scripts", name)
        pairs += [(src, os.path.join(s, "scripts", name)) for s in others]
    billing_rules = os.path.join(root, "skills", BILLING_RULES_SKILL, "scripts", "billing_rules.py")
    pairs += [(billing_rules, os.path.join(root, "skills", s, "scripts", "billing_rules.py"))
              for s in BILLING_RULES_COPIES]
    steering_guard = os.path.join(canonical, "scripts", "steering_guard.py")
    drift = 0
    if not os.path.exists(steering_guard) or digest(steering_guard) != STEERING_GUARD_SHA256:
        say(f"PIN     {os.path.relpath(steering_guard, root)} does not match STEERING_GUARD_SHA256")
        drift += 1
    for src, copy in pairs:
        rel = os.path.relpath(copy, root)
        if not os.path.exists(src):
            say(f"MISSING {os.path.relpath(src, root)}")
            drift += 1
        elif not os.path.exists(copy):
            say(f"MISSING {rel}")
            drift += 1
        elif digest(src) != digest(copy):
            say(f"DRIFT   {rel}")
            drift += 1
    say(f"{len(pairs) - drift}/{len(pairs)} shared copies identical to their source")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())