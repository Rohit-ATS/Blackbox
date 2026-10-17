"""Record both scenarios to fixtures/ as recorded SSE streams.

    python -m blackbox.record_fixtures

The frontend is built against these, so the UI can be developed and demoed
without the backend running, and so a UI regression can be told apart from an
agent regression. The event shape is byte-identical to what /api/incident/stream
sends over the wire.
"""
from __future__ import annotations

import json
import pathlib

from . import agents, scenarios

ROOT = pathlib.Path(__file__).resolve().parents[2] / "fixtures"


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    scenarios.reset_memory("acme")

    out = {}
    # order matters: the warm run is only warm because the cold run ran first
    for key in ("cold", "warm"):
        result = agents.run_sync("acme", scenarios.ALL[key], use_llm=False)
        path = ROOT / f"{key}_run.json"
        path.write_text(json.dumps({
            "scenario": key,
            "recorded_with": result["metrics"].get("mode"),
            "metrics": result["metrics"],
            "answer": result["answer"],
            "events": result["events"],
        }, indent=2, default=str), encoding="utf-8")
        out[key] = (len(result["events"]), result["metrics"]["tool_calls"])
        print(f"[fixtures] wrote {path.name}: {len(result['events'])} events, "
              f"{result['metrics']['tool_calls']} tool calls")

    # a small graph snapshot so the UI can render the full topology offline
    from . import db
    rows, _ = db.run("acme", """
    MATCH (s:Service)
    OPTIONAL MATCH (s)-[:OWNED_BY]->(t:Team)
    RETURN s.name, s.tier, s.revenue_critical, s.customer_facing, s.language,
           s.description, t.name
    """)
    edges, _ = db.run("acme", """
    MATCH (a:Service)-[r:DEPENDS_ON]->(b:Service)
    RETURN a.name, b.name, r.criticality, r.protocol
    """)
    snap = {
        "nodes": [{"name": r[0], "tier": r[1], "revenue_critical": r[2],
                   "customer_facing": r[3], "language": r[4], "description": r[5],
                   "team": r[6]} for r in rows],
        "edges": [{"source": r[0], "target": r[1], "criticality": r[2],
                   "protocol": r[3]} for r in edges],
    }
    (ROOT / "graph_acme.json").write_text(json.dumps(snap, indent=2), encoding="utf-8")
    print(f"[fixtures] wrote graph_acme.json: {len(snap['nodes'])} services, "
          f"{len(snap['edges'])} dependencies")


if __name__ == "__main__":
    main()
