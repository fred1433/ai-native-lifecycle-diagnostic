# T-004 Ship from the main warehouse

The request from the business: when a product is stocked in several warehouses, a reservation should
come from the site that holds the most units, so shipments leave from the main warehouse instead of
being split across the small ones.

**This attempt was written deliberately, to be wrong.** It is a counter test of the harness, not an
incident and not a mistake an agent made on its own. A control that has never been handed something
that should not pass is a control nobody has checked.

## Declared classification

```json
{"classes": ["database-transactions"], "markers": [], "tier": "T3"}
```

## Context pack

- The reservation path and the invariant test that already covers it.
- The warehouse rows: each one carries what it holds and what is already committed.
- The business request, as written above.

## Plan

1. Order the warehouses by what they hold, so the biggest is served first.
2. Take from each what the request needs.

## Pinning test

None added. The behaviour the ticket asks for is an ordering preference, and the invariant that
already exists is expected to keep holding.

## Rollback

Revert the commit.

## Verification

It compiles. It does what the business asked: the largest warehouse is served first.

It also reserves units that do not exist. Ordering by what a warehouse holds rather than by what is
left of it, and then taking from what it holds rather than from what is free, commits stock that is
already committed to somebody else. The second line is the one that does the damage, and it looks
like a simplification.
