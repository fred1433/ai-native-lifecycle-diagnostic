# An AI-native engineering lifecycle, exercised on a mature .NET platform

This repository is a worked diagnostic, not a framework. It takes one large, old, production
ASP.NET Core platform with orders, multi warehouse stock, payments, plugins and eighteen years of
history, and answers a single question on it: **where should an agent be allowed to work alone, and
what has to hold before its change can merge.**

The answer is not an opinion. It is a policy that executes, boundary rules that are measured against
the real codebase, and three changes that an agent actually wrote and the harness actually judged.
One of them it stopped.

Nothing in this repository calls a model. The analysis and the three changes were produced once, by
an agent, and everything that runs from here on is arithmetic and tests.

## The platform this runs on

[nopCommerce](https://github.com/nopSolutions/nopCommerce), pinned at `release-4.90.8`
(`9184447`). It is the closest public analogue to a mature commercial ERP: .NET 9, SQL Server first,
orders and multi warehouse inventory, shipping, tax, accounting exports, a plugin surface, a desktop
of legacy decisions, and a test suite that runs on SQLite without a database server.

It is **fetched, never vendored**: `scripts/fetch_upstream.sh` shallow fetches the pinned commit.
A harness that carries a copy of the system it measures is a harness that cannot be pointed at a
different one, and the upstream is copyleft. Our own files are MIT.

## The five pieces

| | |
|---|---|
| [`policy/work-classes.json`](policy/work-classes.json) | The seven classes of work, four autonomy tiers, the context each class needs, the gates each one owes. Machine readable, because it is the input to the classifier, not a document about it. |
| [`scripts/classify_change.py`](scripts/classify_change.py) | Reads a diff, computes the classes, the risk markers, the tier and the gates. The agent never declares its own tier. |
| [`harness/`](harness) | The boundary rules against the real assemblies, with a measured baseline; the rules that apply to added lines only; the tests of the classifier itself. |
| [`tickets/`](tickets) | Three changes an agent wrote under the policy, each with its receipt, its patch and its runs. |
| [`docs/DIAGNOSTIC.md`](docs/DIAGNOSTIC.md) | What the codebase actually says about where autonomy is safe, with the numbers it is based on. |

## How the tier is decided

By the diff, every time, in `scripts/classify_change.py`:

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
