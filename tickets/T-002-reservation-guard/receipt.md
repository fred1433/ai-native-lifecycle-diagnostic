# T-002 Refuse a reservation the warehouses cannot cover

When a product is stocked across several warehouses, the reservation path reserves what it can and
then books the remainder against the first warehouse anyway. The comment in the platform says so:
`2rd pass: Booking negative stock!`. The cart checks availability before checkout, so this only
happens when two checkouts race, which is the case where nobody is watching. The result is reserved
quantity above physical quantity, which no screen shows and no test asserts.

This ticket refuses the shortfall when the product does not allow backorders, and leaves the
behaviour untouched when it does.

## Declared classification

```json
{"classes": ["database-transactions"], "markers": ["schema", "test-surface"], "tier": "T3"}
```

Computed from the diff. Tier three, so an engineer wrote the approach before the agent ran, the pull
request needs an approving reviewer, and the schema part needs a signature that is not a green build:
the `human-review:schema` label, applied by a person who read the migration.

## Context pack

- `ReserveInventoryAsync` and `UnblockReservedInventoryAsync` in full, plus `AdjustInventoryAsync`,
  the only caller.
- The warehouse inventory entity and its mapping: `ProductId` and `WarehouseId` are foreign keys, and
  SQL Server does not index a foreign key column by itself.
- The interleaving the change must survive, written by the engineer rather than inferred: two orders
  for the last unit, both reading the same warehouse rows before either writes.
- The existing fixture in the platform's own tests, which already holds a product across two
  warehouses with a reservation on one of them.

## Plan

1. In the second pass, when `BackorderMode` is `NoBackorders`, throw instead of booking the shortfall.
   The message names the product, what was asked and what was available.
2. Add the composite index the reservation path leans on, as a new migration, in its own version
   folder, following the platform's own migration shape including the exists check.
3. Pin both halves of the behaviour with tests: the refusal, and the reservation that still fits.

What this ticket deliberately does not do: it does not add a transaction around the read and the
write. That is the real fix for the race, it changes the isolation behaviour of the checkout path,
and it is a decision with its own ticket and its own measurement. Refusing to book stock that does
not exist narrows the damage; it does not close the race. Saying so is part of the receipt.

## Pinning test

Two tests were added to the platform's existing product service fixture, which holds thirteen units
across two warehouses with five already reserved, so eight are available.

- `ReservingMoreThanTheWarehousesHoldIsRefusedWhenBackordersAreNotAllowed` asks for ten and expects a
  refusal, then asserts that nothing was written: the refusal is all or nothing.
- `ReservingWhatTheWarehousesHoldStillSucceeds` asks for three and expects it to go through.

Both were run against the platform with the guard reverted and the tests kept. Both fail, and the
failure is the finding: `evidence/tests-fail-without-the-guard.txt` records the platform reserving
eighteen units of a product it physically holds thirteen of, with every other test still green.

## Rollback

The code change is a revert: one condition, no state.

The migration is not. It creates an index, so running it backwards means dropping one, which is
cheap here and is the reason this particular schema change is a safe one to demonstrate with. The
general case is not: this platform's migrations are forward only by construction, `ForwardOnlyMigration`,
which is a deliberate choice and the reason the label exists. A migration that adds a column, moves
data or narrows a type cannot be undone by reverting the pull request that shipped it, and the
person applying the label is agreeing to that, not to the diff.

On a large table the index build is the operational cost to plan for; on SQL Server it takes a lock
unless it is built online.

## Verification

- Build: green.
- Boundary rules: green, no new entry in any baseline.
- Behaviour: the orders, catalog, shipping and tax suites pass with the change applied.
- The two new tests fail without the code change and pass with it, which is the whole claim.
- Human gates: `human-review:schema` was refused by CI until a person applied it. The red run and the
  green run that followed are linked from the pull request.
