"""FastAPI orchestrator.

Streams an agent run to the browser as Server-Sent Events, plus the read
endpoints the UI needs for the graph pane and the trace panel.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import agents, config, db, llm, scenarios, seed, tools
from .embeddings import backend_name

app = FastAPI(title="BLACKBOX", version="1.0",
              description="An on-call agent that reasons over a FalkorDB service graph.")

# Event kinds worth lingering on. Metadata frames go out immediately.
PACED_EVENTS = {"tool_call", "tool_result", "thought", "handoff", "write", "answer"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # local demo; no auth, nothing private behind it
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> dict:
    try:
        rows, ms = db.run(config.DEFAULT_TENANT, "MATCH (s:Service) RETURN count(s)")
        services = rows[0][0] if rows else 0
    except Exception as exc:
        raise HTTPException(503, f"FalkorDB unreachable: {exc}") from exc
    return {
        "ok": True,
        "falkordb": {"host": config.FALKOR_HOST, "port": config.FALKOR_PORT,
                     "ping_ms": ms},
        "tenants": config.TENANTS,
        "services": services,
        "brain": llm.mode_name(),
        "model_available": llm.available(),
        "embedder": backend_name(),
        "tools": sorted(tools.REGISTRY),
    }


@app.get("/api/graph")
def graph(tenant: str = Query(config.DEFAULT_TENANT)) -> dict:
    """The whole service topology, for the background layer of the graph pane."""
    _check_tenant(tenant)
    nodes, n_ms = db.run(tenant, """
    MATCH (s:Service)
    OPTIONAL MATCH (s)-[:OWNED_BY]->(t:Team)
    RETURN s.name, s.tier, s.revenue_critical, s.customer_facing, s.language,
           s.description, t.name
    """)
    edges, e_ms = db.run(tenant, """
    MATCH (a:Service)-[r:DEPENDS_ON]->(b:Service)
    RETURN a.name, b.name, r.criticality, r.protocol
    """)
    return {
        "tenant": tenant,
        "latency_ms": round(n_ms + e_ms, 3),
        "nodes": [{"name": r[0], "tier": r[1], "revenue_critical": r[2],
                   "customer_facing": r[3], "language": r[4], "description": r[5],
                   "team": r[6]} for r in nodes],
        "edges": [{"source": r[0], "target": r[1], "criticality": r[2],
                   "protocol": r[3]} for r in edges],
    }


@app.get("/api/stats")
def stats(tenant: str = Query(config.DEFAULT_TENANT)) -> dict:
    _check_tenant(tenant)
    return {"tenant": tenant, "counts": seed.counts(tenant),
            "memory": scenarios.memory_state(tenant)}


@app.get("/api/scenarios")
def list_scenarios() -> dict:
    return {"scenarios": [
        {"key": s.key, "incident_id": s.incident_id, "title": s.title,
         "service": s.service, "alert": s.alert, "symptom": s.symptom,
         "severity": s.severity, "narrative": s.narrative}
        for s in scenarios.ALL.values()
    ]}


@app.get("/api/trace")
def trace(incident_id: str, tenant: str = Query(config.DEFAULT_TENANT)) -> dict:
    """The agent's own reasoning, read back out of the graph."""
    _check_tenant(tenant)
    return {"incident_id": incident_id, "steps": tools.trace(tenant, incident_id)}


@app.post("/api/memory/reset")
def reset_memory(tenant: str = Query(config.DEFAULT_TENANT)) -> dict:
    """Forget what BLACKBOX learned, keeping the seeded history.

    So the cold/warm pair can be demonstrated more than once.
    """
    _check_tenant(tenant)
    return {"tenant": tenant, "reset": scenarios.reset_memory(tenant),
            "memory": scenarios.memory_state(tenant)}


@app.post("/api/reseed")
def reseed(tenant: str = Query(config.DEFAULT_TENANT)) -> dict:
    _check_tenant(tenant)
    return {"tenant": tenant, "counts": seed.build(tenant, verbose=False)}


class ToolCall(BaseModel):
    args: dict[str, Any] = Field(default_factory=dict)


@app.post("/api/tool/{name}")
def run_tool(name: str, body: ToolCall | None = None,
             tenant: str = Query(config.DEFAULT_TENANT)) -> dict:
    """Call one tool directly, so a judge can poke at the graph over HTTP.

    Returns the same {data, path, cypher, latency_ms} the agent sees.
    """
    _check_tenant(tenant)
    if name not in tools.REGISTRY:
        raise HTTPException(404, f"unknown tool '{name}'; have {sorted(tools.REGISTRY)}")
    try:
        return tools.call(tenant, name, **(body.args if body else {})).to_dict()
    except TypeError as exc:
        raise HTTPException(422, f"bad arguments for {name}: {exc}") from exc


@app.get("/api/tools")
def describe_tools() -> dict:
    """What each tool does and what it takes -- the same schemas the model sees."""
    return {"tools": llm.tool_schemas(sorted(tools.REGISTRY))}


# --------------------------------------------------------------------------- #
@app.get("/api/incident/stream")
async def stream(
    scenario: str = Query("cold"),
    tenant: str = Query(config.DEFAULT_TENANT),
    use_llm: bool | None = Query(None,
                                 description="Force the model on/off. Default: on if a key is set."),
    pace_ms: int = Query(0, ge=0, le=3000,
                         description="Delay between delivered events, for watchability."),
) -> StreamingResponse:
    """Run a scenario, streaming each agent step as it happens.

    `pace_ms` slows down *delivery*, not the work. The agent runs at full
    speed on its own thread and every number it reports -- per-tool latency,
    graph time, elapsed wall clock -- is measured there, before any pacing is
    applied. Without it a whole run finishes in a couple of hundred
    milliseconds and there is nothing for a human to watch.
    """
    _check_tenant(tenant)
    if scenario not in scenarios.ALL:
        raise HTTPException(404, f"unknown scenario '{scenario}'")
    sc = scenarios.ALL[scenario]

    async def gen():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        done = object()

        def produce() -> None:
            # The agent loop is synchronous (FalkorDB client and the Anthropic
            # client both are), so it runs on a worker thread and pushes
            # events across. Without this the event loop blocks and the
            # browser gets the whole run in one burst at the end.
            try:
                for ev in agents.run_scenario(tenant, sc, use_llm):
                    loop.call_soon_threadsafe(queue.put_nowait, ev)
            except Exception as exc:                      # noqa: BLE001
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"type": "error", "message": f"{type(exc).__name__}: {exc}"})
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, done)

        task = loop.run_in_executor(None, produce)
        try:
            first = True
            while True:
                ev = await queue.get()
                if ev is done:
                    break
                # pace between events, never before the first one
                if pace_ms and not first and ev.get("type") in PACED_EVENTS:
                    await asyncio.sleep(pace_ms / 1000)
                first = False
                yield f"data: {json.dumps(ev, default=str)}\n\n"
        finally:
            await task

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


@app.get("/api/incident/run")
def run_blocking(scenario: str = Query("cold"),
                 tenant: str = Query(config.DEFAULT_TENANT),
                 use_llm: bool | None = Query(None)) -> dict:
    """Non-streaming variant, for scripting and for the MCP server."""
    _check_tenant(tenant)
    if scenario not in scenarios.ALL:
        raise HTTPException(404, f"unknown scenario '{scenario}'")
    return agents.run_sync(tenant, scenarios.ALL[scenario], use_llm)


def _check_tenant(tenant: str) -> None:
    if tenant not in config.TENANTS:
        raise HTTPException(400, f"unknown tenant '{tenant}'; "
                                 f"expected one of {config.TENANTS}")
