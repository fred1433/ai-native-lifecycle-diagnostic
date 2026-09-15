# Pointing this at a different platform

Everything in this repository was measured on a public analogue. The method transfers; the numbers do
not. This is what it takes to repoint it, what comes out, and what the analogue could not show.

## What it needs

1. **Read access to three or four representative areas.** Not the whole codebase. One screen, one
   transactional service, one integration, one piece of the oldest layer. The boundary rules are
   measured against compiled assemblies, so the build has to work; nothing needs to run.
2. **Your existing conventions, in whatever state they are in.** A wiki page, a stale document, a
   senior engineer's memory. They are inputs, not requirements: `scripts/mine_conventions.py` counts
   what the tree actually does and the difference between the two is usually the first finding.
3. **Your CI, as it is.** The gates attach to it rather than replacing it. If the existing pipeline
   already runs the suites, the harness adds the classifier, the boundary rules and the receipt check.
4. **Two or three examples of AI assisted changes that went in recently.** The ones that went wrong
   are worth more than the ones that went well.
5. **Terms of access agreed first.** What may be read, by whom, on what machine, for how long, and
   what happens to it afterwards. Nothing is read before that is written down, and none of it needs
   to leave your infrastructure: the harness runs where the code already is.

## What comes out

- The work class map for your platform: which paths and which symbols put a change in which class.
  This is the part that is genuinely yours, because it encodes where your risk lives.
- The boundary rules that hold on your code today, each with the baseline of what already violates
  it. The ones that cannot hold are reported as findings rather than quietly dropped.
- The added line rules, each backed by a count from your tree, so none of them is imported opinion.
- The repository instructions, mined rather than written.
- Two or three tickets run end to end under the harness, including one that should be blocked.

## What a public analogue could not show, and what changes for a platform like yours

**A web client that is not server rendered.** The analogue renders on the server, so its presentation
boundary is a compiled assembly reference and a rule can be enforced in the build. A separate web
client written in Angular has no such rule. The equivalents are: module boundary rules enforced by
lint rather than by the compiler, a generated client so that the API contract is not retyped by hand
on either side, and component tests that pin what a screen renders. The autonomy tier for that work
is the same T1 as a server rendered view. What changes is the instrument, not the judgement.

**A desktop client.** The risk moves to versioning and to what happens when an old client meets a new
server. That is a contract problem, so it belongs with integrations at T2 with a pinned contract, and
the contract is the wire format between the two, not a screen.

**A mobile client.** Same contract problem, plus release latency: a mobile build that ships a wrong
payload cannot be rolled back the way a server can. That pushes anything touching the shared API
contract up a tier, which is a policy decision an engineer should make explicitly rather than
discover later.

**Accounting synchronisation.** The analogue exports; a real ERP reconciles. Reconciliation is the
one place where a silent wrong number is worse than a loud failure, so the honest tier is T3, and
the gate that matters is a golden ledger: a fixed set of documents, an expected set of postings,
compared exactly.

**Genuine multi tenancy.** The analogue scopes by store, which is the same shape but a fraction of
the stakes. In a real multi tenant system, tenant scope stops being a marker that lifts a tier and
becomes its own class, with its own rule: a query that can cross a tenant boundary and returns rows
is a defect that no functional test will ever catch, because every test runs as one tenant.

## The one thing that is not in here

Performance is the class this classifier detects worst, and the fix is not a better pattern. A diff
cannot show that a query moved inside a loop. What shows it is a counter: run the suite, count the
queries a flow issues, fail the build when the count moves. That is a day of work on a platform that
already has a test suite, and it turns the weakest gate in this policy into the strongest one,
because it fails on a number instead of on a guess.
