"""BLACKBOX MCP server.

Exposes the same nine graph tools over MCP stdio, so a judge can interrogate
the service graph from Claude Desktop rather than through our UI. Same
functions, same FalkorDB, same {data, path, cypher, latency_ms} envelope --
this imports the tool layer rather than reimplementing it.

    python mcp/server.py

Written against the MCP Python SDK v2 (mcp>=2), where FastMCP became
MCPServer and tool schemas are derived from type hints.

Claude Desktop config is in mcp/mcp.json and in the README.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# the backend package lives next door
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from mcp.server.mcpserver import MCPServer           # noqa: E402

from blackbox import config, scenarios, schema, seed, tools as T   # noqa: E402

TENANT_DEFAULT = os.getenv("BLACKBOX_TENANT", config.DEFAULT_TENANT)

mcp = MCPServer(
    "blackbox",
    instructions=(
        "BLACKBOX exposes a production service graph stored in FalkorDB: services and "
        "their dependencies, deploys, pull requests, files, people, teams, runbooks, "
        "past incidents and the postmortems written about them.\n\n"
        "Start with graph_overview. For an incident investigation the useful order is "
        "resolve_entity -> similar_incidents -> affected_services -> recent_changes (use "
        "hops=2; the cause is usually not on the service that alerted) -> causal_path "
        "-> who_knows. Every tool returns the data, the subgraph it touched, the exact "
        "Cypher that ran and its latency in milliseconds.\n\n"
        "Two tenants exist, 'acme' and 'globex', held in separate graphs on one "
        "FalkorDB instance. Pass tenant= to query the other one."
    ),
)


def _out(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=str)


# --------------------------------------------------------------------------- #
@mcp.tool()
def graph_overview(tenant: str = TENANT_DEFAULT) -> str:
    """Counts by node label, the live indexes, and what BLACKBOX remembers.

    Start here to see what is actually in the graph.
    """
    return _out({
        "tenant": tenant,
        "counts": seed.counts(tenant),
        "memory": scenarios.memory_state(tenant),
        "indexes": schema.describe(tenant),
        "tenants_available": config.TENANTS,
    })


@mcp.tool()
def resolve_entity(text: str, tenant: str = TENANT_DEFAULT) -> str:
    """Resolve a free-text alert or symptom string to a node in the service graph.

    Always do this first so later tools have a real service name to work from.
    """
    return _out(T.resolve_entity(tenant, text).to_dict())


@mcp.tool()
def affected_services(service: str, max_depth: int = 4, tenant: str = TENANT_DEFAULT) -> str:
    """Everything that degrades if this service degrades, by dependency depth.

    Returns the impacted services with hop counts, which are customer-facing and
    which are revenue-critical. Walks the dependency graph with algo.BFS.
    """
    return _out(T.affected_services(tenant, service, max_depth).to_dict())


@mcp.tool()
def recent_changes(service: str, window_minutes: int = 120, hops: int = 2,
                   tenant: str = TENANT_DEFAULT) -> str:
    """Deploys that landed near this service recently, including upstream of it.

    The cause of an incident is usually NOT on the service that alerted, so use
    hops=2 or more. Ranked by risk score.
    """
    return _out(T.recent_changes(tenant, service, window_minutes, hops).to_dict())


@mcp.tool()
def causal_path(from_service: str, to_service: str, tenant: str = TENANT_DEFAULT) -> str:
    """The dependency chain linking two services, weighted by how hard each link is.

    Uses algo.SPpaths over a criticality-derived cost, so it returns the path a
    failure actually propagates along rather than merely the shortest one.
    """
    return _out(T.causal_path(tenant, from_service, to_service).to_dict())


@mcp.tool()
def similar_incidents(symptom_text: str, k: int = 3, tenant: str = TENANT_DEFAULT) -> str:
    """Semantic search over past incidents and the postmortems written about them.

    Includes postmortems BLACKBOX wrote itself on earlier runs. If this failure
    has been seen before, the lesson usually already names the cause and the fix.
    """
    return _out(T.similar_incidents(tenant, symptom_text, k).to_dict())


@mcp.tool()
def who_knows(service_or_file: str, tenant: str = TENANT_DEFAULT) -> str:
    """Who actually knows this service or file, ranked by commits and prior incidents.

    Also returns the on-call default, so you can see when the right person to
    page is not the one the rotation would pick. Accepts a service name or a
    file path.
    """
    return _out(T.who_knows(tenant, service_or_file).to_dict())


@mcp.tool()
def get_runbook(service: str, symptom: str = "", tenant: str = TENANT_DEFAULT) -> str:
    """The operational runbook that applies to this service and symptom."""
    return _out(T.get_runbook(tenant, service, symptom).to_dict())


@mcp.tool()
def criticality_rank(top: int = 10, tenant: str = TENANT_DEFAULT) -> str:
    """PageRank over the dependency graph: what the rest of the system leans on."""
    return _out(T.criticality_rank(tenant, top).to_dict())


@mcp.tool()
def write_finding(incident_id: str, kind: str, lesson: str = "", service: str = "",
                  person: str = "", pr_number: int = 0,
                  tenant: str = TENANT_DEFAULT) -> str:
    """Write a finding back into the graph. This is how BLACKBOX learns.

    kind='root_cause' links the incident to the deploy that caused it (give
    pr_number); kind='postmortem' stores an embedded lesson that a future
    incident with this signature will retrieve; kind='resolution' closes the
    incident against a person.
    """
    payload: dict[str, Any] = {}
    if lesson:
        payload["lesson"] = lesson
    if service:
        payload["service"] = service
    if person:
        payload["person"] = person
    if pr_number:
        payload["pr_number"] = pr_number
    return _out(T.write_finding(tenant, incident_id, kind, payload).to_dict())


@mcp.tool()
def agent_trace(incident_id: str, tenant: str = TENANT_DEFAULT) -> str:
    """The agent's own reasoning for an incident, read back out of the graph.

    Every tool call BLACKBOX made is an :AgentStep node chained with :NEXT,
    with :TOUCHED edges to whatever it looked at. Try INC-3001 or INC-3002.
    """
    return _out({"incident_id": incident_id, "steps": T.trace(tenant, incident_id)})


if __name__ == "__main__":
    mcp.run(transport="stdio")
