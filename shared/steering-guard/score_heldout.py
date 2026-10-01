"""Score instruction detectors against the operator's private held-out set.

The held-out set is a JSON file {"attack": [...], "benign": [...]} kept outside the repository
and never given to build agents (see docs/operator-runbook.md, "Shared steering detector").

    python shared/steering-guard/score_heldout.py --heldout PATH
    python shared/steering-guard/score_heldout.py --target DIR:MODULE:FUNCTION [--target ...]

Without --heldout, the path comes from the STEERING_HELDOUT environment variable. Without
--target, the shared module's is_steering is scored. A target function is called with one text
and counts as a hit when its result is truthy. Exits 1 when any target is below --min-recall or
has any benign false positive. Misses are printed only with --show, so reports stay shareable.
"""
import argparse
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load_target(spec):
    directory, module_name, function_name = spec.rsplit(":", 2)
    sys.path.insert(0, os.path.abspath(directory))
    try:
        sys.modules.pop(module_name, None)
        module = importlib.import_module(module_name)
        return getattr(module, function_name)
    finally:
        sys.path.pop(0)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--heldout", default=os.environ.get("STEERING_HELDOUT"))
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument("--min-recall", type=float, default=0.90)
    parser.add_argument("--show", action="store_true", help="print missed and false-positive lines")
    args = parser.parse_args()
    if not args.heldout or not os.path.isfile(args.heldout):
        parser.error("pass --heldout PATH or set STEERING_HELDOUT to the private held-out JSON file")
    with open(args.heldout, encoding="utf-8") as handle:
        held = json.load(handle)
    attacks, benign = held["attack"], held["benign"]
    targets = args.target or [f"{HERE}:steering_guard:is_steering"]
    failed = False
    for spec in targets:
        detect = load_target(spec)
        missed = [text for text in attacks if not detect(text)]
        false_positives = [text for text in benign if detect(text)]
        recall = (len(attacks) - len(missed)) / len(attacks)
        ok = recall >= args.min_recall and not false_positives
        failed |= not ok
        print(
            f"{'PASS' if ok else 'FAIL'}  {spec}: attacks {len(attacks) - len(missed)}/{len(attacks)} "
            f"({recall:.0%}), benign false positives {len(false_positives)}/{len(benign)}"
        )
        if args.show:
            for text in missed:
                print(f"    MISS {text}")
            for text in false_positives:
                print(f"    FP   {text}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
