# Demo video script — 2:45 max

Record at 1920×1080, browser zoom 110%, notifications off, no dock, no
bookmarks bar. Three dry runs, then record in one take.

## Before you hit record

```bash
docker compose up -d
# wait for the backend to finish seeding
curl -s localhost:8000/api/health
```

Then in the console at http://localhost:3000/console:

- press **forget** (clears only what BLACKBOX has learned)
- set playback to **1×**
- set the brain to **planner** if you have no API key, **auto** if you do
- leave the tenant on `acme`

Have `/console` open on a clean tab. Nothing else.

---

## 0:00–0:15 — the problem, stated as a cost

> "When production breaks, the first twenty minutes don't go on fixing it.
> They go on working out what *else* is broken, and who to call. That's not a
> retrieval problem. The answer isn't written down anywhere — it lives in how
> things connect."

*On screen: the landing page hero, then scroll once to the five questions.*

## 0:15–0:30 — what it is

> "Forty-two services, three hundred and twenty deploys, eighteen people, in
> one FalkorDB graph. Everything an on-call engineer would need to know, as
> nodes and edges."

*Cut to the console. The full topology, faint. Hover one node so the inspector
shows tier, team, revenue-critical.*

## 0:30–1:25 — the cold run

*Click **run cold**. Narrate as each step lands — do not read the screen, say
what it means.*

> "An alert fires on checkout-api. Latency's at 4200 against a 1500
> threshold, and CPU is flat."

> "Triage resolves the alert text to a node, then asks memory whether we've
> seen this before. There's something related, but nothing conclusive."

> "Blast radius. Eleven services degrade with it — three of them customer
> facing." *(let the red fill; point at the double-ringed nodes)*
> "And those numbers on the edges are the actual traversal times. Single-digit
> milliseconds, inside the agent loop."

> "Now the Investigator. The cause is almost never on the service that
> alerted, so it walks two hops out — and finds a pull request merged
> twenty-three minutes ago against ledger-service. Different service. Two hops
> away. Touching the database connection pool."

> "Then it proves the connection rather than asserting it." *(causal path
> glows amber)* "There are two two-hop routes to ledger-service. This is the
> one weighted by how hard each dependency is — the synchronous one."

> "And it pages Priya. Not because she's on call — she isn't — but because she
> wrote that file forty-seven times and fixed the last incident on it."

*Land on the answer card.*

> "Eleven tool calls. Under sixty milliseconds of actual graph work. And every
> claim here is clickable back to the node that produced it."

*Hover a citation so the source nodes pulse.*

## 1:25–2:00 — the write-back

> "Here's the part that matters."

*Point at the three green write lines in the stream.*

> "It just wrote what it learned back into the graph. A CAUSED_BY edge to the
> deploy. And a postmortem — with an embedding on it — that is
> indistinguishable from the eleven a human wrote. Same label, same index,
> same retrieval path. The only difference is who wrote it."

## 2:00–2:25 — the warm run

*Click **run warm**.*

> "Second alert. Different service — notifications-api — same failure
> signature."

> "Second tool call. It finds the postmortem it wrote ninety seconds ago."

*Let it finish.*

> "And the investigation collapses. No upstream search, no shortest-path
> proof, no runbook fetch — the lesson already names the mechanism and the
> fix. One hop instead of four. Eleven tool calls down to eight."

*Hold on the comparison bar.*

> "And it isn't a cache. Press forget, and the warm run becomes a cold one
> again — because the thing that made it fast was a node, and I just deleted
> it."

## 2:25–2:40 — breadth

*Fast cuts, roughly five seconds each:*

1. **Tenant switch** to `globex` — a completely different company, separate
   graph, same instance. "A query against one cannot see the other."
2. **A step expanded** in the agent stream, showing the exact Cypher.
   "Nothing here is magic. That's the query that ran."
3. **MCP in Claude Desktop** — ask *"what breaks if checkout-api goes down?"*
   and let it answer. "Same nine tools, in your own client."

## 2:40–2:45 — close

> "BLACKBOX. The graph isn't where the agent looks things up. It's where the
> agent thinks."

---

## Things to avoid

- Don't say "as you can see". Say what it means.
- Don't apologise for the planner if you're running without a key. Say "the
  model picks the tools; the findings come from the graph either way."
- Don't read numbers off the screen that the viewer can already read. Say why
  they matter.
- If a step looks slow, let it breathe. Don't fill silence with "um, so".
