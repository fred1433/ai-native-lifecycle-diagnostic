#!/usr/bin/env bash
# Fetch the upstream platform at the exact commit pinned in policy/work-classes.json.
#
# The upstream is never vendored into this repository: it is 1.6 GB of history under a
# copyleft licence, and a harness that carries a copy of the system it measures is a
# harness nobody can point at a different system. One commit, one shallow fetch, same
# command on a laptop and in CI.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-$ROOT/upstream}"

read -r REPO COMMIT TAG < <(python3 - "$ROOT/policy/work-classes.json" <<'PY'
import json, sys
u = json.load(open(sys.argv[1]))["upstream"]
print(u["repo"], u["commit"], u["tag"])
PY
)

if [ -d "$DEST/.git" ] && [ "$(git -C "$DEST" rev-parse HEAD 2>/dev/null)" = "$COMMIT" ]; then
  echo "upstream already at $TAG ($COMMIT)"
  exit 0
fi

echo "fetching $REPO at $TAG ($COMMIT) into $DEST"
mkdir -p "$DEST"
git -C "$DEST" init -q
git -C "$DEST" remote add origin "$REPO" 2>/dev/null || git -C "$DEST" remote set-url origin "$REPO"
git -C "$DEST" fetch --depth 1 --no-tags origin "$COMMIT"
git -C "$DEST" checkout -q --detach FETCH_HEAD
echo "upstream at $(git -C "$DEST" rev-parse HEAD)"
