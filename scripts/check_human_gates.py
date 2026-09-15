#!/usr/bin/env python3
"""Check the gates that a human, not a test, has to satisfy.

A green build says the change compiles and the suites still pass. It says nothing about
whether anyone read the migration. This script is where the pull request is held until a
person has put their name on the parts of the change that tests cannot judge.

Usage:
    check_human_gates.py --labels '["human-review:schema"]' --changed-tickets-from-git <base-sha>
    check_human_gates.py --labels '[]' --tickets tickets/T-002-stock-index
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify_change import classify  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def tickets_touched_since(base_sha: str) -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"{base_sha}...HEAD"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError:
        out = subprocess.run(
            ["git", "diff", "--name-only", base_sha],
            cwd=ROOT, capture_output=True, text=True, check=False,
        ).stdout

    dirs = []
    for line in out.splitlines():
        parts = Path(line).parts
        if len(parts) >= 2 and parts[0] == "tickets":
            ticket = ROOT / parts[0] / parts[1]
            if ticket.is_dir() and ticket not in dirs:
                dirs.append(ticket)
    return dirs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--labels", default="[]", help="JSON array of the pull request labels")
    parser.add_argument("--tickets", nargs="*", default=None, help="explicit ticket directories")
    parser.add_argument("--changed-tickets-from-git", default=None, metavar="BASE_SHA")
    args = parser.parse_args()

    policy = json.loads((ROOT / "policy" / "work-classes.json").read_text(encoding="utf-8"))
    enforcement = json.loads((ROOT / "policy" / "enforcement.json").read_text(encoding="utf-8"))

    try:
        labels = set(json.loads(args.labels))
    except json.JSONDecodeError:
        labels = set()

    if args.tickets:
        tickets = [Path(t) for t in args.tickets]
    elif args.changed_tickets_from_git:
        tickets = tickets_touched_since(args.changed_tickets_from_git)
    else:
        tickets = sorted(p for p in (ROOT / "tickets").glob("*") if (p / "change.patch").is_file())

    if not tickets:
        print("OK   no ticket touched by this pull request, no human gate owed")
        return 0

    failures = []
    for ticket in tickets:
        patch = ticket / "change.patch"
        if not patch.is_file():
            continue
        verdict = classify(patch.read_text(encoding="utf-8"), policy)
        owed = [g for g in verdict["gates"] if g in ("schema-label", "human-approval", "design-note")]
        print(f"{ticket.name}: {verdict['tier']}, human gates owed: {', '.join(owed) or 'none'}")

        if "schema-label" in verdict["gates"]:
            wanted = enforcement["schema_label"]
            if wanted in labels:
                print(f"  ok       {wanted} is on the pull request: a person read the migration")
            else:
                failures.append(
                    f"{ticket.name} changes the schema. This pull request needs the {wanted} label, "
                    "applied by a human after reading the migration and its rollback. "
                    "A migration runs once, on live data, and a revert does not undo it."
                )

        if "human-approval" in verdict["gates"]:
            reason = enforcement["advisory"]["human-approval"]
            print(f"  advisory human-approval is owed and is not enforced here. {reason}")

    if failures:
        print("\nFAIL human gates")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\nOK   human gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
