#!/usr/bin/env python3
"""Apply the added-line rules to a patch.

Whole tree rules have to tolerate every exception the last fifteen years produced, so they
are ratcheted against a baseline. These rules are different: they only look at the lines the
change adds, so they admit no exception at all. The lines were written today, by the agent
whose receipt is in the pull request.

Usage:
    check_added_lines.py <patch-file>...
    check_added_lines.py tickets/T-001-example/change.patch
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify_change import glob_to_regex  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def iter_added_lines(patch_text: str):
    """Yield (path, line_number_in_new_file, text) for every added line of a unified diff."""
    path = None
    new_line = 0
    for line in patch_text.splitlines():
        if line.startswith("+++ "):
            raw = line[4:].strip().split("\t")[0]
            path = None if raw == "/dev/null" else (raw[2:] if raw[:2] in ("a/", "b/") else raw)
            continue
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            new_line = int(match.group(1)) if match else 0
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            if path:
                yield path, new_line, line[1:]
            new_line += 1
        elif not line.startswith("-"):
            new_line += 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("patches", nargs="+", help="patch files to check")
    parser.add_argument("--rules", default=str(ROOT / "policy" / "added-line-rules.json"))
    args = parser.parse_args()

    rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))["rules"]
    compiled = [
        (
            rule,
            re.compile(rule["pattern"]),
            [glob_to_regex(glob) for glob in rule["applies_to"]],
            [glob_to_regex(glob) for glob in rule.get("excludes", [])],
        )
        for rule in rules
    ]

    violations = []
    for patch_path in args.patches:
        text = Path(patch_path).read_text(encoding="utf-8")
        for path, number, content in iter_added_lines(text):
            stripped = content.strip()
            if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("///"):
                continue
            for rule, pattern, globs, excludes in compiled:
                if not any(glob.match(path) for glob in globs):
                    continue
                if any(glob.match(path) for glob in excludes):
                    continue
                if pattern.search(content):
                    violations.append((patch_path, rule, path, number, stripped))

    if violations:
        print(f"FAIL added-line rules: {len(violations)} violation(s)")
        for patch_path, rule, path, number, content in violations:
            print(f"  {Path(patch_path).parent.name}  {rule['id']}")
            print(f"    {path}:{number}  {content[:120]}")
            print(f"    {rule['message']}")
        return 1

    checked = ", ".join(sorted({Path(p).parent.name for p in args.patches}))
    print(f"OK   added-line rules ({len(compiled)} rules) on: {checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
