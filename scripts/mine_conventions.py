#!/usr/bin/env python3
"""Derive the repository instructions from the codebase instead of writing them from memory.

Repository instructions are usually somebody's recollection of how the code is meant to look,
written once and then quietly false. Here every line an agent is given carries a count taken
from the pinned commit and a file that shows the pattern. When the count moves, the
instruction is rewritten by rerunning this script, not by remembering.

Usage:
    mine_conventions.py [--upstream upstream] [--out harness/agent-instructions/CONVENTIONS.generated.md]
"""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCOPE = ["src/Libraries", "src/Presentation"]


@dataclass
class Probe:
    id: str
    instruction: str
    pattern: str
    counter_pattern: str | None = None
    counter_excludes: str | None = None
    note: str = ""
    hits: int = 0
    counter_hits: int = 0
    example: str = ""
    extras: dict = field(default_factory=dict)


PROBES = [
    Probe(
        id="async-everything",
        instruction="Service methods that touch data are asynchronous and their names end in Async. Await them, never block on them.",
        pattern=r"public\s+(?:virtual\s+)?async\s+Task",
        counter_pattern=r"\.GetAwaiter\(\)\.GetResult\(\)|[a-zA-Z0-9_)]\.Wait\(\)",
        note="The counter count is the number of blocking waits left in the platform. It is not zero, and that residue is what an agent quotes back at you as precedent.",
    ),
    Probe(
        id="repository-boundary",
        instruction="Data is reached through IRepository<T> and the query extensions on it. Do not open a connection, do not write SQL, do not reference the ORM outside the data layer.",
        pattern=r"IRepository<",
        counter_pattern=r"using LinqToDB",
        counter_excludes="/Nop.Data/",
        note="The counter count is how often the ORM itself appears outside the data layer.",
    ),
    Probe(
        id="utc-storage",
        instruction="Timestamps that are stored are UTC. Local time is a display concern and goes through the date time helper.",
        pattern=r"DateTime\.UtcNow",
        counter_pattern=r"DateTime\.Now\b",
    ),
    Probe(
        id="localised-strings",
        instruction="Text a user can read comes from a localisation resource, never from a literal in a controller, a factory or a view.",
        pattern=r"GetResourceAsync\(",
    ),
    Probe(
        id="cache-keys-are-declared",
        instruction="Cached reads use a declared cache key from a Defaults class, with every scope the value depends on baked into the key. Invalidate by prefix when the entity changes.",
        pattern=r"PrepareKeyForDefaultCache|CacheKey\(",
    ),
    Probe(
        id="events-not-calls",
        instruction="Cross cutting reactions to a change are published as events rather than called directly, so a plugin can observe them.",
        pattern=r"EntityInsertedAsync|EntityUpdatedAsync|EntityDeletedAsync|PublishAsync\(",
    ),
    Probe(
        id="admin-actions-check-permission",
        instruction="An action in the admin area checks the relevant permission before it does anything, and returns the access denied view when it fails.",
        pattern=r"AuthorizeAsync\(",
    ),
    Probe(
        id="store-scope",
        instruction="Reads that can differ per store take the store into account. A query without a store scope in a multi store install returns another store's rows and looks correct.",
        pattern=r"storeId|StoreId",
    ),
    Probe(
        id="migrations-are-versioned",
        instruction="A schema change is a new migration class with a NopMigration attribute and a version. Existing migration files are never edited: they have already run somewhere.",
        pattern=r"\[NopMigration|\[NopSchemaMigration",
    ),
]


def count(pattern: str, upstream: Path, excludes: str | None = None) -> tuple[int, str]:
    """Count matching lines under the scoped folders, and return one example location.

    grep exits 0 when it matched, 1 when it did not, and 2 when the pattern was wrong. That
    third case used to read as a clean zero, which is how this file once reported that the
    platform contained no blocking waits at all. A measuring instrument that cannot fail is
    not a measuring instrument.
    """
    cmd = ["grep", "-rnE", "--include=*.cs", "--include=*.cshtml", pattern]
    cmd += [str(upstream / scope) for scope in SCOPE]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode >= 2:
        raise RuntimeError(f"grep refused the pattern {pattern!r}: {result.stderr.strip()}")
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    if excludes:
        lines = [l for l in lines if excludes not in l]
    example = ""
    if lines:
        first = lines[0]
        path, _, rest = first.partition(":")
        number = rest.split(":")[0]
        example = f"{Path(path).relative_to(upstream)}:{number}"
    return len(lines), example


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--upstream", default=str(ROOT / "upstream"))
    parser.add_argument("--out", default=str(ROOT / "harness" / "agent-instructions" / "CONVENTIONS.generated.md"))
    args = parser.parse_args()

    upstream = Path(args.upstream)
    commit = subprocess.run(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()

    for probe in PROBES:
        probe.hits, probe.example = count(probe.pattern, upstream)
        if probe.counter_pattern:
            probe.counter_hits, probe.extras["counter_example"] = count(
                probe.counter_pattern, upstream, probe.counter_excludes
            )

    lines = [
        "# Conventions of this codebase, measured",
        "",
        f"Generated by `scripts/mine_conventions.py` from the upstream tree at commit `{commit[:12]}`.",
        "Counts are matching lines under `src/Libraries` and `src/Presentation`.",
        "",
        "This file is the architectural part of the context pack. It is regenerated, never edited by hand:",
        "an instruction that no longer matches the tree is worse than no instruction, because an agent will",
        "follow it anyway.",
        "",
    ]

    for probe in PROBES:
        lines.append(f"## {probe.id}")
        lines.append("")
        lines.append(probe.instruction)
        lines.append("")
        lines.append(f"- Observed: {probe.hits} lines match `{probe.pattern}`" + (f", for example `{probe.example}`" if probe.example else ""))
        if probe.counter_pattern:
            lines.append(
                f"- Against it: {probe.counter_hits} lines match `{probe.counter_pattern}`"
                + (f", for example `{probe.extras.get('counter_example')}`" if probe.counter_hits else "")
            )
        if probe.note:
            lines.append(f"- {probe.note}")
        lines.append("")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out} from commit {commit[:12]}")
    for probe in PROBES:
        against = f"  against {probe.counter_hits}" if probe.counter_pattern else ""
        print(f"  {probe.id:32} {probe.hits:6}{against}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
