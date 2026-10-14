#!/usr/bin/env python3
"""Fail when a per-skill copy of a shared file drifts from its canonical copy.

Each skill in the MOS3 package must run on its own, so every file a skill reads or runs lives in that skill's folder.
Files used by more than one skill are vendored byte for byte from one canonical copy (the package has no root
contracts/ or references/):

  canonical                                                        copies
  skills/gate-check/contracts/ps.deliverable-review-quality-gate.v1.json  every other skill's contracts/
  skills/gate-check/references/quality-gate-criteria.md            every other skill's references/
  skills/gate-check/references/severity-rules.md                   every other skill's references/
  skills/assertion-map/scripts/assertion_rules.py                  gate-check, review-packet scripts/
  skills/assertion-map/scripts/assertion_map.py                    gate-check scripts/
  skills/gate-check/scripts/gate_check.py                          review-packet scripts/
  skills/gate-check/scripts/severity_rank.py                       review-packet scripts/
  shared/steering-guard/steering_guard.py (STEERING_GUARD_SHA256)  assertion-map, gate-check, review-packet scripts/

Any other file found at a canonical file's path in another skill is checked too, so an unregistered copy cannot
drift. Skill-specific files (for example skills/gate-check/references/g8-withholding-and-input-rules.md) are not
shared.

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
EVERY_OTHER = "*"
# (canonical file, skills that carry a byte-identical copy); EVERY_OTHER is every skill but the canonical one.
SHARED_COPIES = (
    ("skills/gate-check/contracts/ps.deliverable-review-quality-gate.v1.json", EVERY_OTHER),
    ("skills/gate-check/references/quality-gate-criteria.md", EVERY_OTHER),
    ("skills/gate-check/references/severity-rules.md", EVERY_OTHER),
    ("skills/assertion-map/scripts/assertion_rules.py", ("gate-check", "review-packet")),
    ("skills/assertion-map/scripts/assertion_map.py", ("gate-check",)),
    ("skills/gate-check/scripts/gate_check.py", ("review-packet",)),
    ("skills/gate-check/scripts/severity_rank.py", ("review-packet",)),
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
STEERING_GUARD_SHA256 = "12fb2476517adb6c51af1ad3a6ba37ae890bad273c3a819bbcfbdbee18bade11"  # steering_guard 1.1.6
STEERING_GUARD_COPIES = ("skills/assertion-map/scripts/steering_guard.py", "skills/gate-check/scripts/steering_guard.py",
                         "skills/review-packet/scripts/steering_guard.py")


def emit(line=""):
    """Print one line backslash-escaped to ASCII, so a cp1252 or ASCII console or pipe can always show it."""
    print(str(line).encode("ascii", "backslashreplace").decode("ascii"))


def steering_guard_copies(root=None):
    """Every vendored copy: the registered ones plus any other skills/*/scripts/steering_guard.py."""
    root = root or ROOT
    found = {os.path.relpath(path, root).replace(os.sep, "/") for path in glob.glob(os.path.join(root, "skills", "*", "scripts", "steering_guard.py"))}
    return sorted(found | set(STEERING_GUARD_COPIES))


def digest(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def copy_pairs(root=None):
    """(canonical, copy) relative paths: the registered copies plus any file found at a canonical file's path in
    another skill."""
    root = root or ROOT
    skills = sorted(name for name in os.listdir(os.path.join(root, "skills")) if os.path.isdir(os.path.join(root, "skills", name)))
    pairs = []
    for canonical, holders in SHARED_COPIES:
        _, owner, rest = canonical.split("/", 2)
        wanted = [name for name in skills if name != owner] if holders == EVERY_OTHER else list(holders)
        wanted += [name for name in skills if name != owner and name not in wanted and os.path.exists(os.path.join(root, "skills", name, *rest.split("/")))]
        pairs.extend((canonical, f"skills/{name}/{rest}") for name in wanted)
    return pairs


def check(root=None):
    """(problem lines, copies checked) for every shared copy and every vendored steering_guard.py."""
    root = root or ROOT
    problems, checked = [], []
    for canonical, copy in copy_pairs(root):
        checked.append(copy)
        src, dst = os.path.join(root, *canonical.split("/")), os.path.join(root, *copy.split("/"))
        if not os.path.exists(src):
            rel = canonical
            problems.append(f"MISSING {rel} (canonical copy)")
        elif not os.path.exists(dst):
            rel = copy
            problems.append(f"MISSING {rel}")
        elif digest(src) != digest(dst):
            rel = copy
            problems.append(f"DRIFT   {rel} (differs from its canonical copy)")
    for rel in steering_guard_copies(root):
        checked.append(rel)
        path = os.path.join(root, *rel.split("/"))
        if not os.path.exists(path):
            problems.append(f"MISSING {rel}")
        elif digest(path) != STEERING_GUARD_SHA256:
            problems.append(f"DRIFT   {rel} (does not match STEERING_GUARD_SHA256)")
    return problems, checked


def main():
    if not os.path.isdir(os.path.join(ROOT, "skills")):
        emit(f"check_shared_copies: plugin root {ROOT} has no skills folder; pass --plugin-root or set PLUGIN_ROOT")
        return 2
    emit(f"plugin root: {ROOT}")
    emit(f"data root:   {DATA_ROOT}")
    problems, checked = check(ROOT)
    for line in problems:
        emit(line)
    emit(f"{len(checked) - len(problems)}/{len(checked)} shared copies identical to their source")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
