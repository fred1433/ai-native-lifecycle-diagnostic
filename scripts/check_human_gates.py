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
from classify_change import classify, glob_to_regex  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def files_changed_since(base_sha: str) -> list[str]:
    for args in ([f"{base_sha}...HEAD"], [base_sha]):
        result = subprocess.run(
            ["git", "diff", "--name-only", *args], cwd=ROOT, capture_output=True, text=True
        )
        if result.returncode == 0:
            return [line for line in result.stdout.splitlines() if line.strip()]
    return []


def referee_files_touched(changed: list[str], policy: dict) -> list[str]:
    """Files that belong to the harness itself, rather than to the platform under it."""
    marker = next((m for m in policy["markers"] if m["id"] == "referee"), None)
    if marker is None:
        return []
    patterns = [glob_to_regex(glob) for glob in marker["match"].get("paths", [])]
    return [path for path in changed if any(rx.match(path) for rx in patterns)]


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

    failures = []

    # The trust boundary. An agent that can edit the rules, the tests of the rules or the workflow
    # that runs them in the same pull request as its own change is not being judged by anything.
    if args.changed_tickets_from_git:
        referee = referee_files_touched(files_changed_since(args.changed_tickets_from_git), policy)
        if referee:
            wanted = enforcement.get("harness_label", "harness-change")
            print(f"referee: this pull request changes {len(referee)} file(s) of the harness itself")
            for path in referee[:10]:
                print(f"  {path}")
            if wanted in labels:
                print(f"  ok       {wanted} is on the pull request: the change to the referee is deliberate")
            else:
                failures.append(
                    f"this pull request changes the harness that judges it, and carries no {wanted} label. "
                    "The rules, their tests and the workflow are changed on their own, by a person, "
                    "never in the same breath as the change they are meant to judge."
                )

    if not tickets:
        if failures:
            print("\nFAIL human gates")
            for failure in failures:
                print(f"  - {failure}")
            return 1
        print("OK   no ticket touched by this pull request, no human gate owed")
        return 0
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
