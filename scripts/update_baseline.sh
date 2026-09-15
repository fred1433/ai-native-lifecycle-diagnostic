#!/usr/bin/env bash
# Rewrite the boundary baselines from the pinned upstream commit.
#
# Run this when a rule is added or the upstream pin moves. Never run it to make a red build
# green: a new violation is a conversation, not a line in a file.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$ROOT/scripts/fetch_upstream.sh"
ARCH_BASELINE_WRITE=1 dotnet test "$ROOT/harness/ArchitectureTests/ArchitectureTests.csproj" -c Release
git -C "$ROOT" --no-pager diff --stat -- harness/ArchitectureTests/baseline
