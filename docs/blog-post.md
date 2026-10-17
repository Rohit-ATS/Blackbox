---
title: "We gave an on-call agent a graph instead of a vector store, and it started remembering its own mistakes"
published: false
tags: graphdatabase, ai, falkordb, devops
canonical_url:
---

# We gave an on-call agent a graph instead of a vector store, and it started remembering its own mistakes

I spent a weekend building an incident-response agent for
[Graph Hacks](https://falkordb.com), FalkorDB's hackathon. The thing I
actually learned wasn't about agents. It was about which questions a vector
store simply cannot answer, and how uncomfortable it is to discover that after
you've already built the vector store.

## The naive version, and exactly where it fails

The obvious build is RAG over your runbooks. Chunk them, embed them, stuff the
top-k into a prompt, let the model write a summary. It takes an afternoon and
it demos fine.

Here is the question that breaks it:

> `checkout-api` p99 latency is 4200ms. What else is broken, and who do I
> call?

Embed that and search your runbook corpus. You will get back the
`checkout-api` restart procedure, something about latency SLOs, and — if your
corpus is good — a document explaining what a connection pool is.

All relevant. None of it an answer. Because the answer is:

- **eleven other services** are degraded, and three of them are things
  customers actually touch;
- the cause isn't in `checkout-api` at all — it's a pull request merged
  twenty-three minutes ago against `ledger-service`, **two hops upstream**;
- and the person to call is not the one on the rotation. It's the engineer who
  has committed to that specific file forty-seven times and who resolved the
  last incident on it.

None of those three facts is written down anywhere. They are not retrievable,
because they are not *recorded* — they are *implied*, by how things connect.
A service dependency graph, a deploy history, and a commit log each contain a
piece, and the answer only exists at the intersection.

That is a traversal, not a lookup. So: a graph.

## The schema, and the three decisions that were actually hard

The easy part of the schema is the part everyone draws the same way:
`Service`, `Deploy`, `PullRequest`, `File`, `Person`, `Team`, `Incident`.
Here are the three I got wrong first.

### 1. Criticality belongs on the edge, not the node

My first pass gave every service a `tier` property. Tier 1 is important, tier
3 is not. This is what every service catalog does and it is nearly useless,
because a service is not uniformly critical. `checkout-api` depends on
`payments-api` through a hard synchronous gRPC call — if payments is down,
checkout is down. It also depends on `feature-flags`, which it can lose
without anyone noticing.

One number on the node averages those into meaninglessness. So criticality
moved onto the relationship:

```cypher
(:Service)-[:DEPENDS_ON {criticality: 5, protocol: 'grpc', cost: 1.0}]->(:Service)
```

This immediately paid for itself. There are **two** two-hop paths from
`checkout-api` to `ledger-service`: one through `payments-api`, one through
`fraud-screen`. Identical hop count. A shortest-path query picks whichever it
happens to reach first, and half the time your "causal chain" is a route
failure doesn't actually travel.

With `cost = 6 - criticality`, the weighted path is unambiguous:

```cypher
MATCH (a:Service {name:'checkout-api'}), (b:Service {name:'ledger-service'})
CALL algo.SPpaths({sourceNode:a, targetNode:b, relTypes:['DEPENDS_ON'],
                   weightProp:'cost', pathCount:1})
YIELD path, pathWeight
RETURN [n IN nodes(path) | n.name], pathWeight
```

```
["checkout-api", "payments-api", "ledger-service"]   weight 2.0
```

The fraud-screen route scores 7.0. The graph now distinguishes "connected
from" "coupled", which is the entire difference between a diagram and a model.

### 2. Deploys have to be nodes

I started with `last_deployed_at` as a property on `Service`. That answers
"when did this change?" and nothing else.

The question that matters during an incident is *"what changed near here
recently"*, where **near means graph distance**. That only works if a deploy
is something you can traverse to from two hops away:

```cypher
MATCH (t:Service {name:$name})-[:DEPENDS_ON*0..2]->(dep:Service)
MATCH (d:Deploy)-[:DEPLOYED_TO]->(dep)
WHERE d.at >= $cutoff
MATCH (d)-[:SHIPS]->(pr:PullRequest)
OPTIONAL MATCH (pr)-[:TOUCHES]->(f:File)
RETURN DISTINCT d, dep.name, pr, collect(DISTINCT f.path)
ORDER BY d.risk_score DESC
```

I have a test that asserts this query finds nothing at `hops=1` and finds the
true cause at `hops=2`. That test is the whole thesis in eleven lines. The
affected services is impressive on screen, but *this* is the query that does the
work a human on-call misses, because a human looks at the service that
alerted.

### 3. The agent's own reasoning should be graph data

This one I didn't plan; it fell out of needing a trace panel in the UI.

The obvious implementation is to log each tool call and stream the log to the
browser. What I did instead was write every tool call into the graph as an
`:AgentStep` node, chained with `:NEXT`, with `:TOUCHED` edges to whatever it
looked at.

```cypher
MATCH (a:AgentStep {incident_id:$i})
OPTIONAL MATCH (a)-[:TOUCHED]->(n)
RETURN a.agent, a.tool, a.latency_ms, collect(coalesce(n.name, n.id))
ORDER BY a.at
```

Three things came free. The trace panel became a query instead of a log tail.
The three agents — Triage, Investigator, Comms — could hand off through the
graph rather than through process memory, so "state" stopped being a thing I
had to pass around. And because the state was never in the process, a
restarted agent can read what the last one established and carry on.

## The write-back loop, and the number that matters

Here is the part I'd actually defend as novel, and it's three lines of
Cypher.

When the agent finishes, it writes what it learned back:

```cypher
MATCH (i:Incident {id:$incident})
MERGE (pm:Postmortem {id:$pm_id})
SET pm.lesson = $lesson,
    pm.created_by = 'blackbox',
    pm.embedding = vecf32($vec)
MERGE (i)-[:PRODUCED]->(pm)
```

That `Postmortem` node is **indistinguishable in kind** from the eleven
written by humans in the seed data. Same label. Same vector index. Same
retrieval path. The only difference is `created_by`.

Which means the next incident retrieves it without any special casing at all.

### The measurement

Two runs, same class of failure, different services.

**Run 1 — cold.** `checkout-api`, p99 4200ms, CPU flat.

```
resolve_entity        2.12ms
similar_incidents    15.61ms   a related prior incident, not conclusive
affected_services         11.71ms   11 impacted, 3 customer-facing
criticality_rank      2.89ms   PageRank over 42 services
recent_changes        3.80ms   PR #4471 on ledger-service, 2 hops upstream
causal_path           2.92ms   ledger-service -> payments-api -> checkout-api
get_runbook           5.17ms   connection pool exhaustion
write_finding         2.31ms   CAUSED_BY
who_knows             4.41ms   Priya Raghavan (47 commits)
write_finding         4.88ms   Postmortem          <-- the write
write_finding         2.91ms   RESOLVED_BY

11 tool calls, 58.7ms in FalkorDB
```

**Run 2 — warm.** `notifications-api`, same signature, ninety seconds later.
The second tool call now returns the postmortem the first run wrote, at cosine
similarity **0.589**:

```
resolve_entity        1.64ms
similar_incidents    14.77ms   3 postmortems (incl. 1 written by BLACKBOX)
affected_services          6.56ms   depth 2 — mechanism already known
recent_changes        3.03ms   hops=1 — one hop is enough now
write_finding         2.10ms   CAUSED_BY
who_knows             4.29ms   Mei Tanaka (31 commits)
write_finding         4.05ms   Postmortem
write_finding         2.70ms   RESOLVED_BY

8 tool calls, 39.1ms in FalkorDB
```

The entire upstream search, the shortest-path proof and the runbook fetch
collapse into one single-hop lookup, because the lesson already names the
mechanism and the fix. Triage skips the depth-4 traversal and PageRank
entirely.

**11 calls → 8. Four investigation steps → two. 58.7ms → 39.1ms of graph work.**

### Being honest about the numbers

My build plan predicted "41 seconds → 8 seconds". That gap is model latency,
not graph latency — with an LLM in the loop, the cold run makes more model
turns than the warm one and the wall clock separates accordingly. Running the
deterministic planner, the whole thing finishes in about 250ms end to end, so
wall-clock ratios are noise. The honest metrics are the ones above: tool
calls, investigation steps, and measured graph time.

I'd rather publish the number I measured than the one I hoped for. The UI
labels every figure `measured` for the same reason.

And it is genuinely the write that causes it: delete the postmortems the agent
wrote — keeping the eleven seeded human ones — and the warm run becomes a cold
one again. There's a **forget** button that does exactly this. It is the only
honest way to demonstrate that nothing is cached.

## Things I'd fix, and things that bit me

**The live incident is its own nearest neighbour.** My first warm run proudly
reported that it had found a highly similar prior incident: itself. Vector
indexes don't know which of your rows is the one you're currently working on.
Over-fetch and filter on `status`.

**`db.idx.vector.queryNodes` returns distance, not similarity.** 0.0 means
identical, 1.0 means orthogonal. Sort it the intuitive way round and your
agent confidently recalls the *least* relevant postmortem, with no error to
tell you so. Probe the semantics against a known pair before you build
ranking on top of it.

**Don't let the model write Cypher.** This was the one call I made up front
and would make again. Text-to-Cypher is the demo everyone reaches for, and its
failure mode is miserable: when a generated query returns nothing you cannot
tell whether the model got the syntax wrong, got the schema wrong, or whether
the data genuinely isn't there. Nine typed tools, each returning
`{data, path, cypher, latency_ms}`, is less magical and far more defensible —
and because each one hands back the subgraph it touched, every claim in the
final answer renders as a highlighted path you can click back to its source.

**With another week**, I'd replace the hashed-lexical embedder with a real
sentence encoder (it's a one-line swap, the dimensions already match), add
`algo.betweenness` to find the services that are chokepoints rather than merely
popular, and make the kill-and-resume path explicit — the state is already in
the graph, so an agent that dies mid-incident should be able to pick up exactly
where it stopped. That's a demo I'd like to film.

---

**Code:** https://github.com/Rohit-ATS/GraphHacks — MIT, `docker compose up`,
no auth, no API key required.

Built on [FalkorDB](https://falkordb.com) for Graph Hacks.
