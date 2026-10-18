<div align="center">

<a href="https://rohit-ats.github.io/Blackbox/console/">
  <img src="docs/assets/hero.svg" alt="BLACKBOX — production breaks, the graph already knows" width="100%">
</a>

<br>

[![Try it live](https://img.shields.io/badge/▶_try_it_live-rohit--ats.github.io%2FBlackbox-edc5fc?style=for-the-badge&labelColor=0c0b0c&color=171515)](https://rohit-ats.github.io/Blackbox/console/)
[![Graph Hacks](https://img.shields.io/badge/Graph_Hacks-FalkorDB_×_WeMakeDevs-9780ff?style=for-the-badge&labelColor=0c0b0c&color=171515)](https://falkordb.com)

![FalkorDB](https://img.shields.io/badge/FalkorDB-graph_per_tenant-edc5fc?style=flat-square&labelColor=0c0b0c&color=1c1b1c)
![Python](https://img.shields.io/badge/Python-3.11-edc5fc?style=flat-square&labelColor=0c0b0c&color=1c1b1c)
![FastAPI](https://img.shields.io/badge/FastAPI-SSE_streaming-edc5fc?style=flat-square&labelColor=0c0b0c&color=1c1b1c)
![Next.js](https://img.shields.io/badge/Next.js-14-edc5fc?style=flat-square&labelColor=0c0b0c&color=1c1b1c)
![MCP](https://img.shields.io/badge/MCP-SDK_v2-9780ff?style=flat-square&labelColor=0c0b0c&color=1c1b1c)
![Tests](https://img.shields.io/badge/pytest-29_passed-9780ff?style=flat-square&labelColor=0c0b0c&color=1c1b1c)
![License](https://img.shields.io/badge/license-MIT-8a8589?style=flat-square&labelColor=0c0b0c&color=1c1b1c)

**[Live demo](https://rohit-ats.github.io/Blackbox/console/)** · [Quick start](#-quick-start) · [How it works](#-how-it-works) · [The two runs](#-the-demo-in-two-runs) · [Schema](./schema.md) · [MCP](./mcp/README.md)

</div>

<img src="docs/assets/divider.svg" width="100%" alt="">

Production breaks. BLACKBOX reads your service graph, maps everything degrading
with it, finds the change that caused it **two hops upstream**, recalls the last
time this happened, pages the human who actually knows — then **writes what it
learned back into the graph**, so the next incident of the same shape resolves in
a fraction of the hops.

> **The graph isn't where the agent looks things up. It's where the agent thinks.**

<img src="docs/assets/divider.svg" width="100%" alt="">

## ▶ Demo

<table>
<tr>
<td width="55%" valign="top">

### [rohit-ats.github.io/Blackbox](https://rohit-ats.github.io/Blackbox/console/)

Press **run cold**, then **run warm**.

That page is served as static files, so there is no FalkorDB behind it. It
replays [`fixtures/`](./fixtures) — real runs recorded against a real graph by
`python -m blackbox.record_fixtures`, byte-identical to what the SSE endpoint
streams.

Every step, latency and answer on screen is genuine output; it just happened
earlier. The page says so in a banner.

</td>
<td width="45%" valign="top">

### Want the real thing?

With an agent actually querying FalkorDB, it is **one command** and about two
minutes — see [Quick start](#-quick-start).

```bash
docker compose up
```

*Video link goes here before submission.*

</td>
</tr>
</table>

<img src="docs/assets/divider.svg" width="100%" alt="">

## ⚡ Quick start

**Requires Docker. Nothing else.** No API key, no sign-up, **no auth anywhere**.

```bash
git clone https://github.com/Rohit-ATS/Blackbox
cd Blackbox
cp .env.example .env          # optional: add an Anthropic key
docker compose up
```

Then open **http://localhost:3000**, click **run cold**, then **run warm**.

| | Service | URL |
|:--|:--|:--|
| 🖥 | Landing page + console | <http://localhost:3000> |
| ⚙ | API (OpenAPI docs at `/docs`) | <http://localhost:8000> |
| 🕸 | FalkorDB Browser | <http://localhost:3100> |

`docker compose up` seeds both tenant graphs on first boot. That is the whole setup.

<details>
<summary><b>Running it without Docker</b></summary>

<br>

```bash
docker compose up -d falkordb
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
python -m blackbox.seed --all
python -m blackbox.run_demo --reset        # the whole demo, in the terminal
uvicorn blackbox.api:app --port 8000
# and in a second terminal
cd frontend && npm install && npm run dev
```

</details>

<details>
<summary><b>About the Anthropic key — the demo works without one</b></summary>

<br>

BLACKBOX has two brains behind one interface:

| Brain | What it is |
|:--|:--|
| **`claude-sonnet-4-6`** | A real tool-calling loop. The model chooses which traversal to run and writes the prose. |
| **The deterministic planner** | A rule-based policy over the same nine tools, used when no key is set. |

Either way, *every finding comes from the graph*, not from the model. The planner
reaches the same root cause by the same tool calls; it just doesn't narrate as
well. Which brain ran is reported in every run and shown in the UI, and a model
failure degrades to the planner mid-run rather than producing an empty answer.
The toolbar lets you force either one.

> The default is the lower-cost `claude-sonnet-4-6`. Override with
> `BLACKBOX_MODEL` if you want to run a different Anthropic model.

</details>

<img src="docs/assets/divider.svg" width="100%" alt="">

## 🔁 The demo, in two runs

<img src="docs/assets/cold-warm.svg" width="100%" alt="Cold run versus warm run: 11 tool calls to 7, 61.2ms to 12.9ms of measured graph work, 4 investigation steps to 2">

### Run 1 — cold

`checkout-api` p99 latency hits 4200ms against a 1500ms threshold, CPU flat.

| # | tool | result | FalkorDB |
|:--|:--|:--|--:|
| 1 | `resolve_entity` | → `checkout-api` | 2.1ms |
| 2 | `similar_incidents` | a related prior incident, not conclusive | 15.6ms |
| 3 | `affected_services` | **11 services degrade with it, 3 customer-facing** | 11.7ms |
| 4 | `criticality_rank` | PageRank over 42 services | 2.9ms |
| 5 | `recent_changes` hops=2 | **PR #4471 on `ledger-service`, 2 hops upstream** | 3.8ms |
| 6 | `causal_path` | `ledger-service → payments-api → checkout-api` | 2.9ms |
| 7 | `get_runbook` | connection pool exhaustion | 5.2ms |
| 8 | `write_finding` | **`CAUSED_BY`** | 2.3ms |
| 9 | `who_knows` | **Priya Raghavan**, not the rotation default | 4.4ms |
| 10 | `write_finding` | **`Postmortem`** + embedding | 4.9ms |
| 11 | `write_finding` | `RESOLVED_BY` | 2.9ms |

11 tool calls, **61.2ms of measured investigation work** in the recorded run.

Two details worth noticing. **The cause is not on the service that alerted** — it
is two hops upstream, and at `hops=1` the query misses it entirely. And the
person to page wrote the file 47 times and resolved a prior incident on it; the
rotation would have paged someone else.

### Run 2 — warm

A different service, `notifications-api`, with the same failure signature. The
first memory lookup now returns **the postmortem BLACKBOX wrote 90 seconds ago**
(cosine similarity 0.59), so the mechanism and the fix are already known:

- the whole upstream search, the shortest-path proof and the runbook fetch
  collapse into **one single-hop lookup**
- Triage skips the depth-4 traversal and PageRank entirely
- **11 tool calls → 7**, **61.2ms → 12.9ms of investigation work**, investigation
  steps **4 → 2**. The shared entity lookup, vector recall, and write-back are
  shown separately from the traversal work they do not eliminate.

Press **forget** in the toolbar — it deletes only the postmortems BLACKBOX wrote,
keeping the seeded history — and the warm run becomes a cold one again. That is
the demonstration: **nothing is cached**, the speed-up is a node that exists
because the agent put it there.

<details>
<summary><b>On the numbers — what is measured, and what could not be verified</b></summary>

<br>

The build plan projected 41s → 8s. That gap is **model latency**: with a key set,
the cold run makes more model turns than the warm one and the wall clock
separates accordingly. On the deterministic planner the entire run is ~250ms end
to end, so wall-clock ratios are noise-dominated and the honest metrics are the
ones above — tool calls, investigation steps, and measured graph time. The UI
reports the total graph time and the investigation-work comparison, all labeled
`measured`.

**The LLM path could not be verified in the build environment** (the available
credential was a Claude Code session token, not an API key, and the Messages API
returned 401), so the quoted numbers throughout this README are all from the
deterministic planner.

The **playback speed** control paces how fast steps are *drawn*. The agent always
runs at full speed on its own thread and every reported number is measured there,
before pacing.

</details>

<img src="docs/assets/divider.svg" width="100%" alt="">

## 🏗 How it works

<img src="docs/assets/architecture.svg" width="100%" alt="Architecture: Next.js console over SSE, FastAPI orchestrator with three agents and nine graph tools, FalkorDB graph per tenant, plus an MCP stdio server">

### Nine typed tools. The model never writes Cypher.

<img src="docs/assets/tools.svg" width="100%" alt="The nine typed graph tools">

Text-to-Cypher demos beautifully right up until it doesn't, and when it fails you
can't tell whether the model was wrong or the data was. So the graph is exposed as
typed tools instead — traversals and FalkorDB's own algorithms, called as
functions. Every one returns `{data, path, cypher, latency_ms}`: `path` is the
subgraph it touched, which is what the UI animates and what makes each claim on
the answer card clickable back to its source nodes.

| tool | mechanism | what it answers |
|:--|:--|:--|
| `resolve_entity` | fulltext | an alert string becomes a node |
| `affected_services` | `algo.BFS` over the materialised inverse | who degrades with it, by hop depth |
| `recent_changes` | variable-length walk, time-filtered | what changed up to N hops upstream |
| `causal_path` | `algo.SPpaths`, criticality-weighted | how a failure there reaches here |
| `similar_incidents` | vector (HNSW, cosine) | have we seen this before |
| `who_knows` | `WORKED_ON` → `BELONGS_TO`, ranked | who actually knows this code |
| `get_runbook` | fulltext + vector hybrid | the operational fix |
| `criticality_rank` | `algo.pageRank` | what the system structurally leans on |
| **`write_finding`** | `MERGE` + `vecf32` | **the write-back loop** |

### Three agents that hand off through the graph

Triage → Investigator → Comms, with distinct system prompts and distinct tool
subsets. The part that matters: **handoff state is written to FalkorDB, not passed
in process memory.** Every tool call becomes an `:AgentStep` node chained with
`:NEXT`, carrying `:TOUCHED` edges to whatever it looked at.

The trace panel is therefore a Cypher query, not a log tail — and it is the reason
a restarted agent could resume, because the state was never in the process to
begin with. You can read it back yourself:

```bash
curl "http://localhost:8000/api/trace?incident_id=INC-3001" | jq
```

### Memory is data, not a session

<img src="docs/assets/memory.svg" width="100%" alt="Episodic, semantic and procedural memory as graph nodes, with the write-back loop from run 1 to run 2">

Three kinds, all nodes: **episodic** (`Incident` — what happened), **semantic**
(`Postmortem` — what it means, with a 384-dim embedding), and **procedural**
(`Runbook` — what to do). A postmortem BLACKBOX wrote is indistinguishable in kind
from one a human wrote: same label, same vector index, same retrieval path. Only
`created_by` differs. That is why the write in run 1 is retrievable in run 2
without any special casing.

### One instance, isolated graphs

`tenant:acme` and `tenant:globex` are separate graphs on the same FalkorDB
(`db.select_graph(f"tenant:{id}")`). A query against one cannot see the other —
asserted in the tests, and visible in the console's tenant switcher, which swaps a
42-service e-commerce company for a 16-service freight company.

<img src="docs/assets/divider.svg" width="100%" alt="">

## 🏁 Which track and why

| Track | How BLACKBOX answers it |
|:--|:--|
| **01 — Agents that act on connected data** | Impact `algo.BFS`, criticality-weighted `algo.SPpaths`, `algo.pageRank` — called as agent tools, not reimplemented. Nine typed tools, each returning the query it ran and its latency. Exposed over **MCP** so tool selection can be driven from any MCP client. |
| **02 — Memory and coordination** | Three agents with separate prompts and tool subsets, handing off through `:AgentStep`/`:NEXT` nodes rather than process memory. Episodic, semantic and procedural memory as graph data. The write-back loop is measured on screen: run 2 cites the postmortem run 1 wrote. |
| **03 — The company brain** | Services, deploys, PRs, files, people, teams, runbooks, Slack-style messages and ADRs in one graph with ownership and provenance. Every claim on the answer card carries a citation that highlights its source nodes. |

<img src="docs/assets/divider.svg" width="100%" alt="">

## 🔌 Drive it from your own Claude

The same nine tools over MCP stdio — see [`mcp/README.md`](./mcp/README.md).

```json
{
  "mcpServers": {
    "blackbox": {
      "command": "python",
      "args": ["/absolute/path/to/Blackbox/mcp/server.py"],
      "env": { "FALKOR_HOST": "localhost", "FALKOR_PORT": "6379" }
    }
  }
}
```

Then ask it *"what breaks if checkout-api goes down?"* or *"something deployed in
the last two hours broke checkout-api — what was it?"*

<img src="docs/assets/divider.svg" width="100%" alt="">

## ✅ Tests

```bash
cd backend && python -m pytest -q      # 29 passed
```

The suite asserts the demo, not just the plumbing — that the impact traversal
returns exactly 11 services with 3 customer-facing, that the criticality-weighted
path prefers `payments-api` over the equal-hop-count alternative, that
`recent_changes` **misses** the cause at one hop and finds it at two, that the
warm run cites a postmortem whose `created_by` is `blackbox`, and that the tenants
cannot see each other.

## 📂 Layout

```
backend/blackbox/
  topology.py     hand-authored service graph (see schema.md for why)
  seed.py         deterministic generator, both tenants
  schema.py       range + fulltext + vector indexes
  tools.py        the nine tools — this is the product
  agents.py       three agents, the SSE event contract, provenance writes
  llm.py          Anthropic tool-use loop + deterministic planner
  scenarios.py    the two replayable incidents
  api.py          FastAPI, SSE streaming
frontend/         Next.js 14, landing page + console
mcp/              MCP stdio server (same nine tools)
fixtures/         recorded runs, so the UI can be worked on offline
```

## 🧱 Stack

FalkorDB · Python 3.11 · FastAPI · falkordb-py · Anthropic SDK · MCP SDK v2 ·
Next.js 14 · Cytoscape.js · Tailwind

Embeddings are a deterministic local hashed-lexical embedder (384-dim, L2
normalised, no network call, identical on every machine) so the demo is
reproducible. `BLACKBOX_EMBEDDER=minilm` switches to `all-MiniLM-L6-v2` if
`sentence-transformers` is installed — same 384 dimensions, so the vector indexes
don't change.

<img src="docs/assets/divider.svg" width="100%" alt="">

<div align="center">

<img src="docs/assets/mark.svg" width="48" alt="">

**MIT** · Built by **Rohit Maruri** ([@Rohit-ATS](https://github.com/Rohit-ATS)) for Graph Hacks

<sub><i>The graph isn't where the agent looks things up. It's where the agent thinks.</i></sub>

</div>
