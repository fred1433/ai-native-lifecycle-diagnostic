# T-003 Export stock movements to the accounting system

An outbound payload: the stock movements of a product, in the shape another company's system reads.
Nothing in a build fails when that shape changes. The party that notices is the accounting system, a
day later, and the symptom is a number that does not reconcile.

This is the second attempt. The first one is in `rejected/attempt-1.patch` and the harness stopped it.

## Declared classification

```json
{"classes": ["integrations"], "markers": ["test-surface"], "tier": "T2"}
```

Tier two: the agent writes, a named reviewer approves before merge, and the payload has to be pinned
by a fixture. The mechanical gates can see the shape of this change; only a person can confirm that
the shape is the one the other side agreed to.

## Context pack

- The stock movement entity and the service method that reads it.
- The existing export services as the local idiom for this kind of work.
- The boundary rules, which is the part the first attempt did not have.
- One fact that is not in the repository and had to be supplied: the receiving system keys off a
  schema string and reads timestamps as UTC.

## Plan

1. A service in the service layer, behind an interface, reading through `IProductService`.
2. The payload built by a pure function that takes rows and returns a string, so the contract test
   needs neither a container nor a database.
3. Three tests: the payload byte for byte, the ordering, and the timestamp.

What this ticket does not do: it does not register the service in the container. In this policy the
composition root sits in the legacy architecture class, which is tier three, and bundling one wiring
line here would have raised the tier of the whole change. Cutting the ticket at that line is the
policy doing its job, not a gap in it. The wiring is a separate ticket with a human on it.

## Contract

The payload sent today, pinned in `StockLedgerExportServiceTests`:

```json
{"schema":"stock-ledger/v1","productId":42,"sku":"SKU-42","movements":[{"occurredOnUtc":"2026-09-01T08:00:00.0000000Z","warehouseId":1,"quantityAdjustment":-2,"stockQuantityAfter":6,"reason":"Order 4100"},{"occurredOnUtc":"2026-09-02T09:30:00.0000000Z","warehouseId":null,"quantityAdjustment":5,"stockQuantityAfter":11,"reason":"Stock received"}]}
```

The fixture does not claim this shape is right. It claims that changing it becomes a decision
somebody makes on purpose.

One case in it is worth the reviewer's attention. A row read back from the database carries no time
kind, so formatting it directly produces a timestamp without a `Z`, and the other side reads that as
local time. The code sets the kind explicitly and a test holds it there. That defect is invisible in
a diff, invisible in a build, and would have surfaced as a reconciliation gap.

## The attempt the harness rejected

`rejected/attempt-1.patch` put the same feature in an admin factory that injected the repository and
serialised the rows straight out. It compiles. Every existing test passes. It is also the most
plausible thing to write: a few files away in that same folder, `CommonModelFactory` injects the data
provider directly, so the pattern is right there to copy. Ten types in the presentation layer already
reach into the data layer, all of them from installation and settings screens, all of them from a
decade ago.

Two independent controls caught it, which is the point of having more than one:

- The classifier put a presentation file that carries repository access and an outbound payload at
  tier three across three classes at once, which is the smell, before any test ran.
- The boundary rule failed the build with a new violation of
  `presentation-must-not-reach-the-data-layer` that is not in the baseline.

The pull request is closed and unmerged, and its red run is linked from the README. It stays in the
repository as a patch rather than a ticket so that the main branch stays green while the rejection
stays readable.

## Verification

- Build: green.
- Boundary rules: green, no new entry in any baseline.
- Behaviour: the orders, catalog, shipping and tax suites pass.
- Contract: three tests, all green, payload compared byte for byte.

## Cost of the control

- CI, one attempt end to end: about six minutes, of which the policy checks take four seconds.
- Iterations: two. The first was refused by the boundary rule, the second passed.
- Human interventions: none on this ticket beyond the approval the tier owes.
- What the refusal cost to have: nothing that was built for this ticket. The boundary rule and its
  baseline already existed, measured once against the untouched platform.
