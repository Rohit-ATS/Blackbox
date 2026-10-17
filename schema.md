# The BLACKBOX graph schema

One graph per tenant on a single FalkorDB instance: `tenant:acme`,
`tenant:globex`. A query against one cannot see the other.

## Nodes

| Label | Key properties |
|---|---|
| `Service` | `id, name, tier(1-3), language, repo, description, revenue_critical, customer_facing` |
| `Deploy` | `id, sha, at(epoch ms), at_iso, status, pr_number, risk_score` |
| `PullRequest` | `id, number, title, merged_at, additions, deletions` |
| `File` | `id, path, repo` |
| `Person` | `id, name, handle, role, timezone, on_call` |
| `Team` | `id, name` |
| `Incident` | `id, title, symptom, started_at, resolved_at, severity, status, embedding(384)` |
| `Postmortem` | `id, lesson, created_at, created_by, embedding(384)` |
| `Runbook` | `id, title, body, embedding(384)` |
| `Alert` | `id, metric, value, threshold, fired_at` |
| `Message` | `id, channel, text, author, at, embedding(384)` |
| `Decision` | `id, title, rationale, at` |
| `AgentStep` | `id, agent, tool, args, at, latency_ms, incident_id` |

`Postmortem.created_by` is the one property the whole demo turns on. A
postmortem written by a human carries their name; one BLACKBOX wrote carries
`'blackbox'`. Nothing else distinguishes them — same label, same index, same
retrieval path.

## Relationships

```
(:Service)-[:DEPENDS_ON {criticality, protocol, cost}]->(:Service)
(:Service)-[:IMPACTS    {criticality, protocol, cost}]->(:Service)   ← materialised inverse
(:Service)-[:OWNED_BY]->(:Team)
(:Person)-[:MEMBER_OF]->(:Team)
(:Person)-[:AUTHORED]->(:PullRequest)
(:Person)-[:WORKED_ON {commits, last_at}]->(:File)
(:PullRequest)-[:TOUCHES]->(:File)
(:File)-[:BELONGS_TO]->(:Service)
(:Deploy)-[:DEPLOYED_TO]->(:Service)
(:Deploy)-[:SHIPS]->(:PullRequest)
(:Alert)-[:FIRED_ON]->(:Service)
(:Incident)-[:TRIGGERED_BY]->(:Alert)
(:Incident)-[:AFFECTED]->(:Service)
(:Incident)-[:IMPLICATED]->(:File)
(:Incident)-[:CAUSED_BY]->(:Deploy)          ← the agent writes this
(:Incident)-[:RESOLVED_BY]->(:Person)        ← the agent writes this
(:Incident)-[:PRODUCED]->(:Postmortem)       ← the agent writes this
(:Postmortem)-[:APPLIES_TO]->(:Service)
(:Runbook)-[:COVERS]->(:Service)
(:Message)-[:ABOUT]->(:Incident)
(:Decision)-[:CONCERNS]->(:Service)
(:Decision)-[:MADE_BY]->(:Person)
(:AgentStep)-[:NEXT]->(:AgentStep)           ← the handoff chain
(:AgentStep)-[:TOUCHED]->()                  ← provenance, to any node
```

## Three modelling decisions that were not obvious

**Criticality lives on the edge, not the node.** A service is not uniformly
critical. `checkout-api` depends hard and synchronously on `payments-api`
(criticality 5) and softly on `feature-flags` (criticality 1). Putting a
single "tier" on the service throws that away. With criticality on the edge,
blast radius can be weighted and shortest-path can be made to prefer the route
a failure actually travels: there are two two-hop routes from `checkout-api`
to `ledger-service`, and only the one through `payments-api` is a hard
synchronous call. `cost = 6 - criticality` turns that into something
`algo.SPpaths` can minimise.

**`IMPACTS` is a materialised inverse of `DEPENDS_ON`.** The honest edge
direction is consumer → provider. But "what breaks if X goes down" walks that
edge backwards, and `algo.BFS` only traverses outgoing edges. We could have
hand-rolled a reverse traversal in Cypher and given up the algorithm; instead
the inverse is written at seed time. It doubles the dependency edges (97 → 194)
and buys a real BFS in both directions.

**Deploys are first-class nodes, not properties of a service.** The question
that matters during an incident is "what changed near here recently", where
*near* means graph distance, not the same service. That only works if a deploy
is a node you can traverse to from two hops away:

```cypher
MATCH (t:Service {name:$name})-[:DEPENDS_ON*0..2]->(dep:Service)
MATCH (d:Deploy)-[:DEPLOYED_TO]->(dep)
WHERE d.at >= $cutoff
```

At one hop this query misses the cause entirely. That difference is asserted
in the test suite (`test_recent_changes_misses_the_cause_at_one_hop`).

## Indexes

```cypher
CREATE INDEX FOR (s:Service) ON (s.name);
CREATE INDEX FOR (s:Service) ON (s.id);
CREATE INDEX FOR (d:Deploy)  ON (d.at);
CREATE INDEX FOR (i:Incident) ON (i.started_at);
CREATE INDEX FOR (f:File) ON (f.path);
CREATE INDEX FOR (p:Person) ON (p.name);
CREATE INDEX FOR (pr:PullRequest) ON (pr.number);
CREATE INDEX FOR (a:AgentStep) ON (a.incident_id);

CALL db.idx.fulltext.createNodeIndex('Service', 'name', 'description');
CALL db.idx.fulltext.createNodeIndex('Runbook', 'title', 'body');
CALL db.idx.fulltext.createNodeIndex('Message', 'text');
CALL db.idx.fulltext.createNodeIndex('File', 'path');

CREATE VECTOR INDEX FOR (i:Incident)   ON (i.embedding)
  OPTIONS {dimension:384, similarityFunction:'cosine'};
CREATE VECTOR INDEX FOR (p:Postmortem) ON (p.embedding)
  OPTIONS {dimension:384, similarityFunction:'cosine'};
CREATE VECTOR INDEX FOR (r:Runbook)    ON (r.embedding)
  OPTIONS {dimension:384, similarityFunction:'cosine'};
```

Two things worth knowing about the vector index, both learned the hard way:

- `db.idx.vector.queryNodes` returns cosine **distance**, so 0 means
  identical. Similarity is `1 - score`.
- It does not combine with property filters, so filtering happens in a `WHERE`
  after the `YIELD`. The live incident is its own nearest neighbour in the
  index, so `similar_incidents` over-fetches and drops anything still open —
  otherwise the agent "recalls" the incident it is currently working on.

## The seeded world (`tenant:acme`)

42 services · 97 dependencies (194 edges with the inverse) · 18 people ·
5 teams · 186 files · 320 deploys · 320 pull requests · 11 resolved incidents
with postmortems · 40 runbooks · 600 messages · 12 ADRs.

Deterministic (`random.Random(42)`), and the dependency topology is
hand-authored rather than generated, because the demo depends on specific
shapes being true:

- the dependents of `checkout-api` number exactly 11, of which 3 are
  customer-facing;
- the cheapest weighted path from `checkout-api` to `ledger-service` runs
  through `payments-api`, not through the equal-hop-count `fraud-screen`;
- the deepest dependency chain is 8 hops, so blast radius has something to
  say.

`tenant:globex` is a freight company with 16 services and no overlap, seeded
from a different seed, to make tenant isolation visible rather than claimed.
