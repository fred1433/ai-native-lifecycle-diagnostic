#!/usr/bin/env python3
"""Compute the work classes, the autonomy tier and the required gates of a change.

The input is a unified diff (a ticket patch, or `git diff` output). The output is a
verdict: which classes of work the change belongs to, which risk markers it carries,
the autonomy tier that follows, and the gates that must pass before it can merge.

Nothing here calls a model. The verdict is a function of the diff and of
policy/work-classes.json, so the same diff always produces the same verdict, on a
laptop and in CI, today and in a year.

Usage:
    classify_change.py <patch-file> [--json] [--policy policy/work-classes.json]
    git diff | classify_change.py - --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TIER_ORDER = ["T1", "T2", "T3", "T4"]
BASE_GATES = ["receipt", "classifier-agreement", "build", "architecture", "golden-behaviour"]


def glob_to_regex(pattern: str) -> re.Pattern:
    """Translate a POSIX-ish glob into a regex.

    `**` crosses directory separators, `*` does not, `?` is one character.
    A trailing `/**` also matches the directory itself.
    """
    i, out = 0, ["^"]
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if pattern[i : i + 2] == "**":
                # `**/` may match nothing at all, so a/**/b matches a/b.
                if pattern[i : i + 3] == "**/":
                    out.append("(?:.*/)?")
                    i += 3
                    continue
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
            i += 1
            continue
        if ch == "?":
            out.append("[^/]")
            i += 1
            continue
        out.append(re.escape(ch))
        i += 1
    out.append("$")
    return re.compile("".join(out))


def parse_patch(text: str) -> tuple[list[str], list[str]]:
    """Return (paths touched, lines added) from a unified diff."""
    paths: list[str] = []
    added: list[str] = []
    for line in text.splitlines():
        if line.startswith("+++ ") or line.startswith("--- "):
            raw = line[4:].strip()
            if raw in ("/dev/null", ""):
                continue
            # strip the a/ or b/ prefix git puts in front of the path
            if raw[:2] in ("a/", "b/"):
                raw = raw[2:]
            raw = raw.split("\t")[0]
            if raw not in paths:
                paths.append(raw)
            continue
        if line.startswith("diff --git "):
            continue
        if line.startswith("+"):
            added.append(line[1:])
    return paths, added


def match_rule(rule: dict, paths: list[str], added: list[str]) -> list[str]:
    """Return the human readable reasons this rule matched, empty if it did not."""
    reasons: list[str] = []
    for pattern in rule.get("paths", []):
        rx = glob_to_regex(pattern)
        for path in paths:
            if rx.match(path):
                reasons.append(f"path {path} matches {pattern}")
                break
    for symbol in rule.get("symbols", []):
        for line in added:
            if symbol in line:
                reasons.append(f"added line contains {symbol!r}")
                break
    return reasons


def max_tier(tiers: list[str]) -> str:
    if not tiers:
        return "T1"
    return max(tiers, key=TIER_ORDER.index)


def classify(patch_text: str, policy: dict) -> dict:
    paths, added = parse_patch(patch_text)

    classes, markers, gates, tiers = [], [], list(BASE_GATES), []

    for klass in policy["classes"]:
        reasons = match_rule(klass["match"], paths, added)
        if reasons:
            classes.append({"id": klass["id"], "title": klass["title"], "tier": klass["tier"], "why": reasons})
            tiers.append(klass["tier"])
            gates.extend(klass.get("gates", []))

    for marker in policy["markers"]:
        reasons = match_rule(marker["match"], paths, added)
        if reasons:
            markers.append({"id": marker["id"], "title": marker["title"], "min_tier": marker["min_tier"], "why": reasons})
            tiers.append(marker["min_tier"])
            gates.extend(marker.get("gates", []))

    # A file no class claims is not a safe file, it is an unknown one. Silently absorbing it
    # into the tier of its neighbours is how an area nobody mapped ends up being edited at the
    # autonomy level of a view change.
    matched_files = set()
    for klass in policy["classes"] + policy["markers"]:
        for pattern in klass["match"].get("paths", []):
            rx = glob_to_regex(pattern)
            matched_files.update(path for path in paths if rx.match(path))
    unmatched = [path for path in paths if path not in matched_files]

    unknown = bool(unmatched) or not classes
    if unknown:
        tiers.append("T2")

    tier = max_tier(tiers)
    ordered_gates = [g for g in dict.fromkeys(gates)]
    if tier in ("T2", "T3", "T4") and "human-approval" not in ordered_gates:
        ordered_gates.append("human-approval")

    return {
        "files": paths,
        "classes": [c["id"] for c in classes],
        "markers": [m["id"] for m in markers],
        "tier": tier,
        "gates": sorted(ordered_gates),
        "unknown_area": unknown,
        "unmatched_files": unmatched,
        "detail": {"classes": classes, "markers": markers},
    }


def render(verdict: dict, policy: dict) -> str:
    tier = policy["tiers"][verdict["tier"]]
    lines = [
        f"tier      {verdict['tier']}  {tier['name']}",
        f"human     {tier['human_involvement']}",
        f"classes   {', '.join(verdict['classes']) or 'none matched'}",
        f"markers   {', '.join(verdict['markers']) or 'none'}",
        f"files     {len(verdict['files'])}",
        f"gates     {', '.join(verdict['gates'])}",
        "",
        "why:",
    ]
    for item in verdict["detail"]["classes"] + verdict["detail"]["markers"]:
        for why in item["why"]:
            lines.append(f"  {item['id']}: {why}")
    if verdict["unmatched_files"]:
        for path in verdict["unmatched_files"]:
            lines.append(f"  unknown-area: no class claims {path}, so the change is at least T2")
    elif verdict["unknown_area"]:
        lines.append("  unknown-area: no class claims these files, so the change is treated as at least T2")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("patch", help="patch file, or - for stdin")
    parser.add_argument("--json", action="store_true", help="print the verdict as JSON")
    parser.add_argument(
        "--policy",
        default=str(Path(__file__).resolve().parent.parent / "policy" / "work-classes.json"),
        help="path to the policy file",
    )
    args = parser.parse_args()

    policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    text = sys.stdin.read() if args.patch == "-" else Path(args.patch).read_text(encoding="utf-8")
    verdict = classify(text, policy)

    print(json.dumps(verdict, indent=2) if args.json else render(verdict, policy))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
