#!/usr/bin/env bash
# Apply the ticket patches to the upstream checkout, in order, up to and including the one named.
#
# Tickets are applied cumulatively rather than each on a pristine tree, because that is what a
# repository actually looks like: the change being judged sits on top of the ones that already
# merged. A ticket that only works on a tree where its predecessors never happened is not a ticket.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPTO="${1:-}"

cd "$ROOT"
for patch in $(ls -d tickets/*/change.patch 2>/dev/null | sort); do
  ticket="$(dirname "$patch")"
  echo "applying $ticket"
  git -C upstream apply --whitespace=nowarn "$ROOT/$patch"
  if [ -n "$UPTO" ] && { [ "$ticket" = "$UPTO" ] || [ "$ticket" = "${UPTO%/}" ]; }; then
    echo "stopping at $ticket"
    break
  fi
done
git -C upstream --no-pager diff --stat
