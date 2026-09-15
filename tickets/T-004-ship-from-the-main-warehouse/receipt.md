# T-004 Ship from the main warehouse

The request from the business: when a product is stocked in several warehouses, a reservation should
come from the site that holds the most units, so shipments leave from the main warehouse instead of
being split across the small ones.

This is the second attempt. The first one is in `rejected/attempt-1.patch`. It was **written
deliberately, to be wrong**: a control that has never been handed something that should not pass is a
control nobody has checked. Both attempts are honest implementations of the same request, and the
difference between them is one line.

## Declared classification

```json
{"classes": ["database-transactions"], "markers": [], "tier": "T3"}
```

The classifier puts this in the transactional class by the file it touches. It does not see that the
change is about concurrency, because the words it matches on are not in the diff: reordering a query
does not mention a lock. That is a real limit of matching on symbols, and here it costs nothing
because the tier is the same either way. It would cost something in a change that only a human would
recognise as concurrent.

## Context pack

- The reservation path, and the invariant test that already covers it: no warehouse commits more
  units than it holds, and the committed total never exceeds the held total.
- What each warehouse row carries: what it holds, and what is already committed out of it.
- The business request, unchanged between the two attempts.

## Plan

Change which warehouse is served first, and nothing else. Order by what a site holds, break ties by
what is still free in it, and keep taking from each site only what is free.

## Pinning test

No new test. That is the point of this ticket: the invariant was written with the reference change,
before this one existed, as a property of the final state rather than an assertion about one code
path. A change that reaches the same place by another route still has to satisfy it, and this one
did not.

This ticket does not touch the tests. A change that has to edit the test that judges it is a
different conversation, and the harness marks any change to the test surface for exactly that reason.

## Rollback

Revert the commit. No schema, no data, no payload has left the system.

## Verification

The first attempt, run against the suite that was already there:

```
FAILED CommittedStockNeverExceedsHeldStock
  Expected record.ReservedQuantity to be less than or equal to 8 because warehouse 1 cannot
  commit units it does not hold, but found 9.

FAILED ReservingMoreThanTheWarehousesHoldIsRefusedWhenBackordersAreNotAllowed
  Expected a <Nop.Core.NopException> to be thrown, but no exception was thrown.
```

Two independent assertions, both about stock rather than about style. It compiled, it satisfied the
request it was given, and the boundary rules had nothing to say about it: ordering rows differently
is not an architectural violation. Only a test that knew what stock means could refuse it.

The second attempt serves the biggest warehouse first, as asked, and both assertions hold.

What this does not prove: the suite runs on SQLite, so it exercises the reservation arithmetic and
not the database engine. Two checkouts racing for the same unit is still not reproduced anywhere
here, and neither attempt would have been caught by a test of that race, because no such test
exists. See the limits section of the diagnostic.

## Cost of the control

- CI, one attempt end to end: about six minutes, of which the policy checks take four seconds and
  everything else is restoring, building and running the platform.
- Iterations: two. One refused, one accepted.
- Human interventions: none on this ticket. The tier says a human writes the approach first, and
  the approach is the one sentence in the plan above.
- What it cost to have the control at all: the invariant test, written once, with the reference
  change. Everything this ticket demonstrates comes from that one test existing before the change
  did.
