# T-001 Show committed stock next to available stock in the low stock report

A buyer looking at the low stock report sees one number and cannot tell whether the shortfall is
stock that is gone or stock that is spoken for. The report already computes the available quantity,
which is physical stock minus what orders have reserved. This adds the reserved figure beside it.

## Declared classification

```json
{"classes": ["ui-application"], "markers": [], "tier": "T1"}
```

Computed by `scripts/classify_change.py tickets/T-001-reserved-column/change.patch`, not asserted by
the agent. Three files, all of them presentation: a view, a view model, an admin factory. Nothing in
the diff touches data access, schema, money, tenant scope or the test surface, so no human stands in
the critical path and the gates decide.

## Context pack

What the agent was given, and nothing else:

- `harness/agent-instructions/CONVENTIONS.generated.md`, regenerated from the pinned commit. The two
  lines that mattered here: user facing text comes from a localisation resource (1741 occurrences),
  and presentation asks a service rather than the database (426 repository usages, all of them behind
  the service layer).
- The three files of the screen being changed, plus the product page as a worked example of a grid
  that already shows a reserved quantity.
- The boundary rules in `harness/ArchitectureTests`, as the definition of what the layer may touch.

The resource key `Admin.Catalog.Products.ProductWarehouseInventory.Fields.ReservedQuantity` already
exists in the platform. Adding a new one would have meant a locale migration, which is a schema
change, which is tier three, for a column heading. Reusing it keeps this change what it looks like.

## Plan

1. Add one property to `LowStockProductModel`, labelled with the existing resource.
2. Fill it in `ReportModelFactory` from the service that is already injected, by asking for the stock
   total twice: once with reservations applied, once without. The difference is what is committed.
3. Add the column to the grid, after the quantity it qualifies.

Combination rows keep a reserved quantity of zero: attribute combinations hold a single stock number
in this platform and no reservation of their own. That is a real limit of the report, not an oversight,
and it is not this ticket's job to change it.

## Verification

- Build: green.
- Boundary rules: green, no new entry in any baseline.
- Behaviour: the orders, catalog, shipping and tax suites of the platform pass unchanged.
- The two service calls in the factory are two reads per product on a report that already reads per
  product. On a catalogue where the report returns hundreds of rows this is worth measuring before it
  ships widely; it is recorded here rather than left to be discovered.

## Cost of the control

- CI, one run end to end: about six minutes, of which the policy checks take four seconds.
- Iterations: one.
- Human interventions: none. That is what tier one means, and it is the only ticket here where it
  is true.
