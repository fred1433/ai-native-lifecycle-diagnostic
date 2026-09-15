# T-003 Export stock movements to the accounting system

The accounting system needs the stock movements of a product. This adds a factory in the admin area
that reads the movement rows and serialises them.

## Declared classification

```json
{"classes": ["ui-application", "database-transactions", "integrations"], "markers": [], "tier": "T3"}
```

Computed from the diff, not chosen. One file, and it lands in three classes at once: a presentation
factory, that injects a repository, that builds an outbound payload.

## Context pack

- The stock movement entity.
- `CommonModelFactory` in the same folder, as the worked example of an admin factory that needs data.
  It injects the data provider directly, so this does the same.
- The existing admin factories for the shape of the class.

## Plan

1. A factory in the admin area with the repository injected.
2. Query the movements of the product, ordered.
3. Serialise them and return the string.

## Pinning test

None. The change adds no behaviour that an existing test covers, and the output is a serialisation of
rows that already exist.

## Contract

None yet. The payload is whatever the serialiser produces from the entity.

## Verification

Build: green. Existing suites: green. Nothing in the platform fails because of this change.
