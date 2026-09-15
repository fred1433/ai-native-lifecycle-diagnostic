# What I concluded about this platform, and what it cost to find out

Five decisions, taken on nopCommerce at commit `9184447`, each with the measurement behind it, the
control I chose, and the alternative I rejected. Then the parts where I decided I could not conclude.

Everything here is about a public codebase. It is a sample of how I work on a system I have never
seen before, not a statement about anyone else's.

---

## 1. The layering boundary holds almost everywhere, and the ten exceptions are the trap

**Measured.** The ORM appears in no file outside the data layer: 426 uses of the repository
abstraction, zero references to linq2db in the service, framework or web assemblies. Services never
reference the presentation assemblies. Domain entities depend on nothing above them. Three rules,
three empty baselines, measured against compiled assemblies rather than against imports, so a call
buried in a method body counts.

One rule is not clean. Ten types under `Nop.Web` depend on the data layer. Every one of them is
installation or settings: the install controller and its model and validator, the settings admin
screens, the route providers that check whether the database exists yet.

**The risk that matters.** `CommonModelFactory`, an admin factory, injects the data provider
directly. An agent asked to build a factory that needs data will read it, conclude that factories may
reach the database here, and do the same. That is not a hypothetical: it is what the first attempt at
[T-003](../tickets/T-003-stock-ledger-export/receipt.md) did, and the boundary rule refused it
([the run](https://github.com/fred1433/ai-native-lifecycle-diagnostic/actions/runs/34972849200)).

**Control chosen.** The rule ships with the ten exceptions frozen by name in a baseline. New
violations fail; entries that stop violating also fail, so the list can only shrink.

**Alternative rejected.** Turning the rule on absolutely and fixing the ten first. The install path
cannot call a service that needs a database that does not exist yet, so the fix is not mechanical,
and a rule that needs a refactor before it can be switched on is a rule that never gets switched on.

---

## 2. The stock invariant is nowhere in the code, so no agent can respect it

**Found.** The reservation path reserves what the warehouses have and then books the remainder
against the first warehouse regardless. The platform says so in its own comment: `2rd pass: Booking
negative stock!`. Whether that is right depends on whether the product allows backorders, and the
code never asks.

**Decision.** Write the invariant down as a test before changing any behaviour: no warehouse commits
more units than it holds, and the committed total never exceeds the held total. State it as a
property of the final state, not as an assertion about one code path, so that a change arriving by
another route still has to satisfy it.

**Counter-test.** [T-004](../tickets/T-004-ship-from-the-main-warehouse/receipt.md) is a plausible
request: ship from the warehouse that holds the most units. Its first version was written
deliberately, to be wrong. It compiles, it does exactly what the request asked, no boundary rule has
anything to say about it, and it commits nine units in a warehouse that holds eight. The invariant
caught it. The accepted version serves the biggest warehouse first, as asked, and keeps the
invariant, and it differs from the refused one by one line.

**What this does not prove.** The suite runs on SQLite. It exercises the reservation arithmetic and
not the database engine, so the race between two checkouts is still not reproduced anywhere. The
guard narrows the damage; nothing here closes the race. On a real deployment that is a question about
isolation levels and locking, and it is answered with the engine, not with a unit test.

---

## 3. The conventions are real but not absolute, which is exactly why an agent breaks them

**Measured.** 3131 asynchronous members and 13 blocking waits left. 333 uses of the UTC clock and 21
of the local one. In the service layer, 1222 task returning members carry the `Async` suffix; in the
test tree, 431 test methods return a task without it and 19 with it.

**The risk that matters.** A convention at 96 percent is not a convention an agent can infer. It
finds the residue, and the residue is precedent.

**Control chosen.** Two kinds of rule, and the difference is the point. Rules about the whole tree
are ratcheted against a baseline, because they have to tolerate fifteen years of exceptions. Rules
about the lines a change adds admit no baseline at all, because those lines were written today. The
suffix rule stops at the test tree rather than firing on 431 existing lines, since a rule that noisy
is a rule somebody switches off within a week.

**Where I got this wrong.** The first version of the mining script reported zero blocking waits. The
regex had been rejected by grep, and an error exit read as a clean zero. A measuring instrument that
cannot fail is not a measuring instrument; it now raises. The number in this section is the corrected
one, and the correction is in the history.

---

## 4. The risk of a change is not something the thing making the change gets to declare

**Decision.** The classifier reads the diff and computes a floor: the lowest tier this change may be
handled at. A receipt may declare a higher tier, never a lower one. A person can escalate, an author
cannot argue down, and the difference between the two is checked mechanically on every pull request.

**Second decision, which took longer.** Technical category is a prior, not an answer. A screen is not
low risk because it is a screen: a screen that changes an amount, a permission, or another tenant's
rows is not a tier one change. That is what the markers are for, and they apply whatever folder the
change sits in. The classes tell you where you probably are; the markers and the four axes, impact,
evidence, reversibility and unknowns, tell you what you owe.

**Control chosen.** A pull request that changes the rules, their tests, or the workflow that runs
them needs a label of its own. An agent does not get to edit its own referee in the same breath as
the change being judged.

---

## 5. Where I would not give autonomy, and where this platform's tests do not let me decide

**Concurrency: proposed, not exercised.** The reservation path is a read then a write with no
transaction around it. I did not reproduce the race and I am not going to claim it is closed.

**Performance: the class this classifier detects worst.** Cache keys and indexes are visible in a
diff. A query moved inside a loop is not, and materialising a list is so common that a rule on it
would fire on every change. The honest fix is not a cleverer pattern: it is a query counter in the
test harness, so a change that turns one query into forty fails on a number. That is a day of work on
a platform that already has a suite, and it is not built here.

**Legacy architecture and fundamental changes: not evaluated.** No ticket in this repository touched
the engine, the data provider or the startup pipeline. They are in the policy because the platform
has the debt, not because the policy has been tried on them.

**The migration control is procedure, not proof.** A schema change is held until a person applies a
label. That is a real control and it fired on a real pull request, but it proves that a signature was
required, not that the migration was right. The reason it exists is that this platform's migrations
are forward only: reverting the pull request does not undo the migration.

---

## The seven classes, and what each one is worth here

| Class | Floor | Status |
|---|---|---|
| UI and application development | T1 | Exercised, one ticket through the full gate set |
| Database transactions | T3 | Exercised, the reservation case, refused then accepted |
| Performance | T2 | Proposed, an index shipped and no measurement taken |
| Integrations | T2 | Exercised, including the attempt the boundary rule stopped |
| Concurrency | T3 | Proposed, the race is not reproduced |
| Legacy architecture | T3 | Not evaluated |
| Fundamental system changes | T4 | Not evaluated |

Seven classes is a grid for reading a change, not seven validated policies. Two were exercised end to
end, two partially, three not at all, and saying which is which is the difference between a diagnosis
and a brochure.

---

## Limits of this exercise

- **A public analogue is not a production ERP.** nopCommerce shares the shape: .NET, SQL Server
  first, orders, multi warehouse stock, shipping, tax, plugins, a test suite that runs without a
  database server. It does not share the stakes, the integrations, or the decisions somebody made in
  2013 and never wrote down.
- **Multi store is not multi tenancy.** This platform scopes by store, and stores can share a
  catalogue and customer accounts. That is the same shape as tenant scoping and a fraction of the
  consequence. In a real multi tenant system, tenant scope is not a marker that lifts a tier, it is
  its own class with its own negative tests.
- **SQLite is not SQL Server.** The suite here runs on SQLite. Locking, transaction isolation and
  query plans are not exercised by anything in this repository, and every claim above is about
  application logic rather than about engine behaviour.
- **One codebase, four tickets.** Nothing here supports a general claim about how much faster or
  safer agent written changes are. Four tickets is an existence proof of a method, not a measurement
  of a benefit.

## What the controls cost

- The policy checks, the classifier, the receipt verifier and their own tests: about four seconds per
  pull request.
- Building the platform and running the boundary rules: about two minutes.
- The behavioural suites on the flows where stock and money move: about two minutes more.
- One pull request end to end, in the order the gates run: roughly six minutes of CI.
- The expensive part was none of that. It was writing the invariant down before touching the code.
  Everything the counter-test demonstrates comes from that one test existing first.
