# An AI-native engineering lifecycle, exercised on a large .NET platform

A work sample, not a framework and not a product. It takes one large public ASP.NET Core platform
with orders, multi warehouse stock, payments, plugins and a long tail of decisions nobody restates,
and answers a single question on it: **where should an agent be allowed to work alone, and what has
to hold before its change can merge.**

The answer is not an opinion. It is a policy that executes, boundary rules measured against the real
assemblies, and four changes an agent wrote under it. Two were refused, one of them by a test that
knew what stock means and one by a boundary rule, and both refusals are pull requests you can open.

Read it as evidence of how I work on a codebase I have never seen, on a system chosen because it
has the problems a distribution or order management platform has. It says nothing about any other
codebase, and [`docs/DIAGNOSTIC.md`](docs/DIAGNOSTIC.md) is explicit about which of its conclusions
are measurements, which are proposals, and which parts were not evaluated at all.

Nothing here calls a model. The analysis and the four changes were produced once, by an agent, and
everything that runs from now on is arithmetic and tests.

## The platform this runs on

[nopCommerce](https://github.com/nopSolutions/nopCommerce), pinned at `release-4.90.8`
(`9184447`): .NET 9, SQL Server first, orders and multi warehouse inventory, shipping, tax,
accounting exports, a plugin surface, and a test suite that runs on SQLite without a database server.
It shares the shape of a mature commercial platform. It does not share the stakes, and multi store is
not multi tenancy: the limits are listed in the diagnosis rather than buried.

It is **fetched, never vendored**: `scripts/fetch_upstream.sh` shallow fetches the pinned commit.
A harness that carries a copy of the system it measures cannot be pointed at a different one, and the
upstream is copyleft. Our own files are MIT.

## The five pieces

| | |
|---|---|
| [`policy/work-classes.json`](policy/work-classes.json) | The seven classes of work, four autonomy tiers, the context each class needs, the gates each one owes. Machine readable, because it is the input to the classifier, not a document about it. |
| [`scripts/classify_change.py`](scripts/classify_change.py) | Reads a diff, computes the classes, the risk markers, the tier and the gates. The agent never declares its own tier. |
| [`harness/`](harness) | The boundary rules against the real assemblies, with a measured baseline; the rules that apply to added lines only; the tests of the classifier itself. |
| [`tickets/`](tickets) | Four changes an agent wrote under the policy, each with its receipt, its patch and its runs. |
| [`docs/DIAGNOSTIC.md`](docs/DIAGNOSTIC.md) | What the codebase actually says about where autonomy is safe, with the numbers it is based on. |

## How the tier is decided

By the diff, every time, in `scripts/classify_change.py`. What it computes is a **floor**: the lowest
tier a change may be handled at. A receipt may declare higher and never lower, so a person can
escalate and an author cannot argue down. Technical category is a prior, not an answer: a screen that
changes an amount or a permission is not low risk because it is a screen, which is what the markers
are for.

- **T1, agent authors and the gates decide.** A view, a view model, a presentation factory. Nobody
  stands in the critical path.
- **T2, agent authors, a named human approves.** Integrations, performance, anything touching tenant
  scope or the test surface.
- **T3, a human decides and the agent implements.** Transactions, stock, concurrency, legacy
  architecture, and every schema change.
- **T4, no agent authorship.** The engine, the data provider, the startup pipeline.

Two properties matter more than the list. The riskiest file sets the tier for the whole change, so
bundling a migration with a view does not average the risk down. And a file no class claims is
treated as at least T2, so an unmapped corner is never silently autonomous.

## Running it

```bash
bash scripts/fetch_upstream.sh                        # one commit, shallow
python3 -m unittest discover -s harness/policy_tests  # the policy engine, one second
python3 scripts/classify_change.py tickets/T-002-reservation-guard/change.patch
dotnet test harness/ArchitectureTests/ArchitectureTests.csproj -c Release
```

The .NET parts need a .NET 9 SDK and no database server.

## What this does not claim

It does not claim to know your codebase. Every number here was measured on a public analogue, and
the parts of your platform that a public analogue cannot show, a desktop client, a mobile client,
accounting synchronisation, the shape of your own legacy, are exactly where the answers would differ.
What transfers is the method and the harness. [`docs/POINTING-IT-AT-YOUR-PLATFORM.md`](docs/POINTING-IT-AT-YOUR-PLATFORM.md)
says what it takes to repoint it and what comes out.

## The four changes, and the two the harness refused

| Ticket | Tier | What happened |
|---|---|---|
| [T-001 committed stock in the low stock report](tickets/T-001-reserved-column/receipt.md) | T1 | Green on every gate, merged. Tier one is meant to be unremarkable. |
| [T-002 refuse a reservation the warehouses cannot cover](tickets/T-002-reservation-guard/receipt.md) | T3 | Refused until a person read the migration and applied the `human-review:schema` label, then merged. |
| [T-003 export stock movements to the accounting system](tickets/T-003-stock-ledger-export/receipt.md) | T2 | First attempt refused by a boundary rule, closed unmerged. Second attempt merged. |
| [T-004 ship from the main warehouse](tickets/T-004-ship-from-the-main-warehouse/receipt.md) | T3 | First attempt refused by the stock invariant, closed unmerged. Second attempt merged. |

The refused pull requests were not merely red. `main` is protected by required checks and a required
review, so both sat at `BLOCKED` and could not be merged. The merges that did happen used an
administrator override for the required review, because one maintainer cannot approve their own pull
request; that is visible on every merge, and neither refused pull request was overridden.

One pull request in this history changes the harness itself rather than the platform, and it was
refused until a person labelled it `harness-change`. An agent does not edit its own referee in the
same breath as the change being judged.
