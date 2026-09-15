#!/usr/bin/env python3
"""Check a ticket receipt against the verdict computed from its own patch.

A receipt is the artefact a reviewer reads before the diff: what the agent was given,
what it decided, what proves the change. This script refuses a receipt that is missing,
incomplete, or that claims a lower risk than the diff actually carries.

The last check is the one that matters: an agent cannot talk its way down a tier,
because the tier in the receipt is compared to the tier the classifier computes.

Usage:
    verify_receipt.py tickets/T-002-...
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify_change import classify  # noqa: E402

SECTION_FOR_GATE = {
    "rollback-note": "Rollback",
    "measurement-in-receipt": "Measurement",
    "design-note": "Design note",
    "contract-test": "Contract",
    "pinning-test": "Pinning test",
}
ALWAYS_REQUIRED = ["Declared classification", "Context pack", "Plan", "Verification"]


def sections(markdown: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"^#{2,3}\s+(.+?)\s*$", markdown, re.MULTILINE)]


def declared_verdict(markdown: str) -> dict | None:
    match = re.search(r"```json\s*(\{.*?\})\s*```", markdown, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ticket_dir", help="directory holding receipt.md and change.patch")
    parser.add_argument(
        "--policy",
        default=str(Path(__file__).resolve().parent.parent / "policy" / "work-classes.json"),
        help="path to the policy file",
    )
    args = parser.parse_args()

    ticket = Path(args.ticket_dir)
    failures: list[str] = []

    receipt_path = ticket / "receipt.md"
    patch_path = ticket / "change.patch"

    if not patch_path.is_file():
        print(f"FAIL {ticket.name}: no change.patch")
        return 1
    if not receipt_path.is_file():
        print(f"FAIL {ticket.name}: no receipt.md. A change without a receipt is not reviewable.")
        return 1

    policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    computed = classify(patch_path.read_text(encoding="utf-8"), policy)
    receipt = receipt_path.read_text(encoding="utf-8")
    present = sections(receipt)

    required = list(ALWAYS_REQUIRED)
    for gate in computed["gates"]:
        if gate in SECTION_FOR_GATE:
            required.append(SECTION_FOR_GATE[gate])
    for name in required:
        if name not in present:
            failures.append(f"missing section: {name} (required because the change is {computed['tier']})")

    declared = declared_verdict(receipt)
    if declared is None:
        failures.append("no machine readable classification block in the receipt")
    else:
        if declared.get("tier") != computed["tier"]:
            failures.append(
                f"declared tier {declared.get('tier')} but the diff computes {computed['tier']}. "
                "The classifier decides, not the author."
            )
        if sorted(declared.get("classes", [])) != sorted(computed["classes"]):
            failures.append(
                f"declared classes {sorted(declared.get('classes', []))} "
                f"but the diff computes {sorted(computed['classes'])}"
            )
        if sorted(declared.get("markers", [])) != sorted(computed["markers"]):
            failures.append(
                f"declared markers {sorted(declared.get('markers', []))} "
                f"but the diff computes {sorted(computed['markers'])}"
            )

    if failures:
        print(f"FAIL {ticket.name}")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"OK   {ticket.name}: {computed['tier']}, gates: {', '.join(computed['gates'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
