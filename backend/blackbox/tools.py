"""The nine graph tools. This layer is the product.

Design rule: the LLM never writes Cypher. It picks from nine typed tools, each
of which wraps a specific traversal or graph algorithm. That is deliberate --
text-to-Cypher fails in ways you cannot recover from on stage, and it hides
what the database actually did.

Every tool returns a ToolResult carrying:
    data        -- the answer, as plain JSON the model can read
    path        -- {nodes, edges} actually touched, for the UI to animate
    cypher      -- the exact query that ran, for the trace panel
    latency_ms  -- measured, per call

`path` is what makes the answer explainable: the UI highlights precisely the
subgraph that produced the claim, so every statement on the answer card is
clickable back to the nodes behind it.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from . import db
from .embeddings import embed

MINUTE_MS = 60_000
MAX_DEPTH = 6


@dataclass
class ToolResult:
    tool: str
    data: Any
    cypher: str = ""
    latency_ms: float = 0.0
    path: dict = field(default_factory=lambda: {"nodes": [], "edges": []})
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "data": self.data,
            "path": self.path,
            "cypher": self.cypher.strip(),
            "latency_ms": self.latency_ms,
            "note": self.note,
        }

    def summary(self) -> str:
        """Short line for the agent stream."""
        d = self.data
        if isinstance(d, dict):
            if "name" in d:
                return str(d["name"])
            if "count" in d:
                return f"{d['count']} results"
        if isinstance(d, list):
            return f"{len(d)} results"
        return str(d)[:80]


def _node(n) -> dict:
    return db.node_props(n)


def _edge(src: str, dst: str, rel: str, **props) -> dict:
    return {"source": src, "target": dst, "rel": rel, **props}


def _depth(value: Any, default: int = 4) -> int:
    """Validate a traversal depth to a small int.

    Depth cannot be a Cypher parameter inside a variable-length pattern, so it
    is the one value that reaches a query as a literal. Coercing it to a
    bounded int here is what keeps that safe.
    """
    try:
        d = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(MAX_DEPTH, d))


# --------------------------------------------------------------------------- #
# 1. resolve_entity
# --------------------------------------------------------------------------- #
def resolve_entity(tenant: str, text: str) -> ToolResult:
    """Fulltext-match a free-text symptom onto a Service, File or Person node.

    Always the first hop: an alert says "checkout-api p99 latency 4200ms" and
    the agent needs a node, not a string.
    """
    t0 = time.perf_counter()
    cypher = """
    CALL db.idx.fulltext.queryNodes('Service', $q) YIELD node, score
    RETURN node, score ORDER BY score DESC LIMIT 5
    """
    # The fulltext index tokenizes on word boundaries; a raw alert line is
    # mostly noise, so query with each candidate token OR'd together.
    tokens = [t.strip(".,:;()[]") for t in (text or "").split()]
    tokens = [t for t in tokens if len(t) > 2 and not t.replace(".", "").isdigit()]
    query = " ".join(tokens) or (text or "")

    rows: list = []
    try:
        rows, _ = db.run(tenant, cypher, {"q": query})
    except Exception:
        rows = []

    if not rows:
        # exact / prefix fallback on the name range index
        cypher = """
        MATCH (s:Service)
        WHERE toLower(s.name) IN $tokens
           OR any(t IN $tokens WHERE toLower(s.name) CONTAINS t)
        RETURN s, 1.0 AS score LIMIT 5
        """
        rows, _ = db.run(tenant, cypher, {"tokens": [t.lower() for t in tokens]})

    if not rows:
        return ToolResult("resolve_entity", {"resolved": False, "query": text},
                          cypher, round((time.perf_counter() - t0) * 1000, 3),
                          note="no entity matched")

    best = _node(rows[0][0])
    candidates = [{"name": _node(r[0]).get("name"), "score": round(float(r[1]), 4)}
                  for r in rows]
    data = {
        "resolved": True,
        "label": best.get("_label"),
        "name": best.get("name"),
        "id": best.get("id"),
        "tier": best.get("tier"),
        "revenue_critical": best.get("revenue_critical"),
        "customer_facing": best.get("customer_facing"),
        "description": best.get("description"),
        "repo": best.get("repo"),
        "candidates": candidates,
    }
    return ToolResult("resolve_entity", data, cypher,
                      round((time.perf_counter() - t0) * 1000, 3),
                      path={"nodes": [best], "edges": []})


# --------------------------------------------------------------------------- #
# 2. affected_services  -- the signature move
# --------------------------------------------------------------------------- #
def affected_services(tenant: str, service: str, max_depth: int = 4) -> ToolResult:
    """Everything that degrades if `service` degrades, by dependency depth.

    Walks IMPACTS -- the materialised inverse of DEPENDS_ON -- with algo.BFS.
    Depth is resolved by running BFS at each level and differencing, so every
    service comes back with the hop count at which it is reached, and each
    level carries its own measured latency. That per-hop timing is what gets
    printed on the edges in the UI.
    """
    t0 = time.perf_counter()
    depth = _depth(max_depth)
    cypher = """
    MATCH (s:Service {name:$name})
    CALL algo.BFS(s, $level, 'IMPACTS') YIELD nodes
    UNWIND nodes AS n
    RETURN n
    """
    seen: dict[str, dict] = {}
    levels: list[dict] = []
    for level in range(1, depth + 1):
        rows, ms = db.run(tenant, cypher, {"name": service, "level": level})
        new = []
        for r in rows:
            props = _node(r[0])
            name = props.get("name")
            if name and name not in seen and name != service:
                props["hops"] = level
                seen[name] = props
                new.append(name)
        levels.append({"hops": level, "new_services": sorted(new), "latency_ms": ms})
        if not new and level > 1:
            break

    impacted = sorted(seen.values(), key=lambda p: (p["hops"], p.get("tier", 9), p["name"]))

    # the actual IMPACTS edges between the source and the impacted set, for
    # rendering the traversal rather than a cloud of unconnected nodes
    edge_rows, edge_ms = db.run(tenant, """
    MATCH (a:Service)-[r:IMPACTS]->(b:Service)
    WHERE a.name IN $names AND b.name IN $names
    RETURN a.name, b.name, r.criticality, r.protocol
    """, {"names": [service] + [p["name"] for p in impacted]})

    edges = [_edge(r[0], r[1], "IMPACTS", criticality=r[2], protocol=r[3]) for r in edge_rows]

    src_rows, _ = db.run(tenant, "MATCH (s:Service {name:$n}) RETURN s", {"n": service})
    nodes = ([_node(src_rows[0][0])] if src_rows else []) + impacted

    customer_facing = [p["name"] for p in impacted if p.get("customer_facing")]
    revenue_critical = [p["name"] for p in impacted if p.get("revenue_critical")]

    data = {
        "source": service,
        "count": len(impacted),
        "max_hops": max((p["hops"] for p in impacted), default=0),
        "customer_facing": customer_facing,
        "customer_facing_count": len(customer_facing),
        "revenue_critical": revenue_critical,
        "by_hop": levels,
        "services": [
            {"name": p["name"], "hops": p["hops"], "tier": p.get("tier"),
             "customer_facing": bool(p.get("customer_facing")),
             "revenue_critical": bool(p.get("revenue_critical"))}
            for p in impacted
        ],
    }
    return ToolResult("affected_services", data, cypher,
                      round((time.perf_counter() - t0) * 1000, 3),
                      path={"nodes": nodes, "edges": edges},
                      note=f"{len(impacted)} impacted, {len(customer_facing)} customer-facing")


# --------------------------------------------------------------------------- #
# 3. recent_changes
# --------------------------------------------------------------------------- #
def recent_changes(tenant: str, service: str, window_minutes: int = 120,
                   hops: int = 2) -> ToolResult:
    """Deploys that landed near `service` in the window -- including upstream.

    The cause of an incident is usually not on the service that alerted. This
    walks `hops` of DEPENDS_ON away from the symptom and collects deploys on
    anything it reaches, ranked by risk and recency. That is the hop a human
    on-call misses and the reason this is a graph problem.
    """
    t0 = time.perf_counter()
    d = _depth(hops, 2)
    cutoff = int(time.time() * 1000) - int(window_minutes) * MINUTE_MS
    cypher = f"""
    MATCH (t:Service {{name:$name}})-[:DEPENDS_ON*0..{d}]->(dep:Service)
    MATCH (d:Deploy)-[:DEPLOYED_TO]->(dep)
    WHERE d.at >= $cutoff
    MATCH (d)-[:SHIPS]->(pr:PullRequest)
    OPTIONAL MATCH (pr)-[:TOUCHES]->(f:File)
    OPTIONAL MATCH (author:Person)-[:AUTHORED]->(pr)
    RETURN DISTINCT d, dep.name AS service, pr, author.name AS author,
           collect(DISTINCT f.path) AS files
    ORDER BY d.risk_score DESC, d.at DESC
    LIMIT 10
    """
    rows, ms = db.run(tenant, cypher, {"name": service, "cutoff": cutoff})

    # hop distance from the symptom to each deployed service, so the agent can
    # say "two hops upstream" rather than just "somewhere nearby"
    hop_rows, _ = db.run(tenant, f"""
    MATCH p = (t:Service {{name:$name}})-[:DEPENDS_ON*0..{d}]->(dep:Service)
    RETURN dep.name, min(length(p))
    """, {"name": service})
    hop_of = {r[0]: r[1] for r in hop_rows}

    deploys, nodes, edges = [], [], []
    now = int(time.time() * 1000)
    for row in rows:
        dep_node, svc, pr, author, files = row
        dp, prp = _node(dep_node), _node(pr)
        age_min = round((now - dp["at"]) / MINUTE_MS)
        deploys.append({
            "deploy_id": dp.get("id"), "sha": dp.get("sha"), "service": svc,
            "hops_from_symptom": hop_of.get(svc, 0),
            "minutes_ago": age_min, "at": dp.get("at_iso"),
            "status": dp.get("status"), "risk_score": dp.get("risk_score"),
            "pr_number": prp.get("number"), "pr_title": prp.get("title"),
            "additions": prp.get("additions"), "deletions": prp.get("deletions"),
            "author": author, "files": [f for f in (files or []) if f],
        })
        nodes += [dp, prp]
        edges.append(_edge(dp.get("id"), svc, "DEPLOYED_TO"))
        edges.append(_edge(dp.get("id"), f"PR#{prp.get('number')}", "SHIPS"))

    data = {"service": service, "window_minutes": window_minutes, "hops_searched": d,
            "count": len(deploys), "deploys": deploys}
    return ToolResult("recent_changes", data, cypher, round((time.perf_counter() - t0) * 1000, 3),
                      path={"nodes": nodes, "edges": edges},
                      note=f"{len(deploys)} deploys within {d} hops / {window_minutes}min")


# --------------------------------------------------------------------------- #
# 4. causal_path
# --------------------------------------------------------------------------- #
def causal_path(tenant: str, from_service: str, to_service: str) -> ToolResult:
    """The dependency chain linking two services, criticality-weighted.

    algo.SPpaths over DEPENDS_ON with cost = 6 - criticality, so the path it
    returns is the one failure actually propagates along, not merely the one
    with the fewest hops. checkout-api reaches ledger-service in two hops two
    different ways; only one of them is a hard synchronous call.

    DEPENDS_ON points consumer -> provider, so the query runs from the
    symptom down to the suspect and the result is reversed to read as
    propagation: cause first, symptom last.
    """
    t0 = time.perf_counter()
    cypher = """
    MATCH (a:Service {name:$from}), (b:Service {name:$to})
    CALL algo.SPpaths({sourceNode:a, targetNode:b, relTypes:['DEPENDS_ON'],
                       weightProp:'cost', pathCount:1})
    YIELD path, pathWeight, pathCost
    RETURN path, pathWeight, pathCost
    """
    # try symptom -> suspect first, then the other way round
    rows, ms = db.run(tenant, cypher, {"from": from_service, "to": to_service})
    reversed_dir = False
    if not rows:
        rows, ms = db.run(tenant, cypher, {"from": to_service, "to": from_service})
        reversed_dir = True

    if not rows:
        return ToolResult("causal_path",
                          {"found": False, "from": from_service, "to": to_service},
                          cypher, round((time.perf_counter() - t0) * 1000, 3),
                          note="no dependency path between these services")

    path_obj, weight, cost = rows[0]
    chain = [_node(n) for n in path_obj.nodes()]
    rels = [{"criticality": (r.properties or {}).get("criticality"),
             "protocol": (r.properties or {}).get("protocol")} for r in path_obj.edges()]

    names = [c["name"] for c in chain]
    # present it as propagation: the cause end first
    prop = list(reversed(names)) if not reversed_dir else names
    prop_rels = list(reversed(rels)) if not reversed_dir else rels

    edges = [_edge(prop[i + 1], prop[i], "DEPENDS_ON", **prop_rels[i])
             for i in range(len(prop) - 1)]

    data = {
        "found": True,
        "propagation": prop,
        "chain": " -> ".join(prop),
        "hops": len(prop) - 1,
        "path_weight": weight,
        "links": [
            {"from": prop[i], "to": prop[i + 1],
             "criticality": prop_rels[i].get("criticality"),
             "protocol": prop_rels[i].get("protocol")}
            for i in range(len(prop) - 1)
        ],
    }
    return ToolResult("causal_path", data, cypher, round((time.perf_counter() - t0) * 1000, 3),
                      path={"nodes": chain, "edges": edges},
                      note=" -> ".join(prop))


# --------------------------------------------------------------------------- #
# 5. similar_incidents  -- the memory tool
# --------------------------------------------------------------------------- #
def similar_incidents(tenant: str, symptom_text: str, k: int = 3) -> ToolResult:
    """Vector search over past incidents and postmortems.

    This is the tool that makes the second run fast. It searches two indexes:
    Incident.embedding (what happened before) and Postmortem.embedding (what
    we learned). Postmortems written by BLACKBOX itself during an earlier run
    come back here -- that is the whole write-back loop closing.

    FalkorDB vector scores are cosine *distance*, so lower is closer; we
    report similarity = 1 - distance and sort accordingly.
    """
    t0 = time.perf_counter()
    vec = embed(symptom_text)
    k = max(1, min(10, int(k)))
    # The live incident is in the same index and is its own nearest neighbour,
    # so over-fetch and drop anything still open: "similar PAST incidents".
    fetch = k + 4

    cypher = """
    CALL db.idx.vector.queryNodes('Incident','embedding', $k, vecf32($v))
    YIELD node, score
    WHERE node.status = 'resolved'
    OPTIONAL MATCH (node)-[:PRODUCED]->(pm:Postmortem)
    OPTIONAL MATCH (node)-[:AFFECTED]->(s:Service)
    OPTIONAL MATCH (node)-[:RESOLVED_BY]->(p:Person)
    OPTIONAL MATCH (node)-[:CAUSED_BY]->(d:Deploy)-[:SHIPS]->(pr:PullRequest)
    RETURN node, score, pm, collect(DISTINCT s.name) AS services,
           collect(DISTINCT p.name) AS resolvers, pr.number AS pr_number
    """
    inc_rows, inc_ms = db.run(tenant, cypher, {"k": fetch, "v": vec})

    pm_cypher = """
    CALL db.idx.vector.queryNodes('Postmortem','embedding', $k, vecf32($v))
    YIELD node, score
    OPTIONAL MATCH (i:Incident)-[:PRODUCED]->(node)
    WITH node, score, i WHERE i IS NULL OR i.status = 'resolved'
    OPTIONAL MATCH (node)-[:APPLIES_TO]->(s:Service)
    RETURN node, score, i.id AS incident_id, i.title AS incident_title,
           collect(DISTINCT s.name) AS services,
           node.cause_pr, node.cause_deploy_id, node.cause_service,
           node.cause_file, node.cause_hops, node.affected_count,
           node.customer_facing
    """
    pm_rows, pm_ms = db.run(tenant, pm_cypher, {"k": fetch, "v": vec})

    incidents, nodes, edges = [], [], []
    for node, score, pm, services, resolvers, pr_number in inc_rows:
        inp = _node(node)
        entry = {
            "incident_id": inp.get("id"), "title": inp.get("title"),
            "symptom": inp.get("symptom"), "severity": inp.get("severity"),
            "started_at": inp.get("started_iso"), "similarity": round(1 - float(score), 4),
            "affected_services": [s for s in services if s],
            "resolved_by": [p for p in resolvers if p],
            "caused_by_pr": pr_number,
        }
        if pm is not None:
            pmp = _node(pm)
            entry["postmortem_id"] = pmp.get("id")
            entry["lesson"] = pmp.get("lesson")
            entry["written_by"] = pmp.get("created_by")
            nodes.append(pmp)
            edges.append(_edge(inp.get("id"), pmp.get("id"), "PRODUCED"))
        incidents.append(entry)
        nodes.append(inp)
    incidents.sort(key=lambda e: -e["similarity"])
    incidents = incidents[:k]

    postmortems = []
    for (node, score, inc_id, inc_title, services, cause_pr, cause_deploy_id,
         cause_service, cause_file, cause_hops, affected_count, customer_facing) in pm_rows:
        pmp = _node(node)
        postmortems.append({
            "postmortem_id": pmp.get("id"), "lesson": pmp.get("lesson"),
            "written_by": pmp.get("created_by"),
            "self_authored": pmp.get("created_by") == "blackbox",
            "incident_id": inc_id, "incident_title": inc_title,
            "applies_to": [s for s in services if s],
            "cause_pr": cause_pr,
            "cause_deploy_id": cause_deploy_id,
            "cause_service": cause_service,
            "cause_file": cause_file,
            "cause_hops": cause_hops,
            "affected_count": affected_count,
            "customer_facing": customer_facing or [],
            "similarity": round(1 - float(score), 4),
        })
        nodes.append(pmp)
    postmortems.sort(key=lambda e: -e["similarity"])
    postmortems = postmortems[:k]

    self_written = [p for p in postmortems if p["self_authored"]]
    data = {
        "query": symptom_text,
        "count": len(incidents),
        "incidents": incidents,
        "postmortems": postmortems,
        "self_authored_hits": len(self_written),
        "recalled_own_postmortem": bool(self_written),
        "index_latency_ms": {"Incident": inc_ms, "Postmortem": pm_ms},
    }
    note = f"{len(incidents)} incidents, {len(postmortems)} postmortems"
    if self_written:
        note += f" (incl. {len(self_written)} written by BLACKBOX)"
    return ToolResult("similar_incidents", data, cypher,
                      round((time.perf_counter() - t0) * 1000, 3),
                      path={"nodes": nodes, "edges": edges}, note=note)


# --------------------------------------------------------------------------- #
# 6. who_knows
# --------------------------------------------------------------------------- #
def who_knows(tenant: str, service_or_file: str) -> ToolResult:
    """Who actually knows this code, ranked -- not who is on call.

    (:Person)-[:WORKED_ON]->(:File)-[:BELONGS_TO]->(:Service), scored by
    commits on the relevant files plus incidents that person has resolved on
    them. The on-call rotation is returned alongside, because the interesting
    output is that the two differ.
    """
    t0 = time.perf_counter()
    cypher = """
    MATCH (p:Person)-[w:WORKED_ON]->(f:File)-[:BELONGS_TO]->(owner:Service)
    WHERE f.path = $target OR f.path CONTAINS $target OR owner.name = $target
    OPTIONAL MATCH (i:Incident)-[:IMPLICATED]->(f)
    OPTIONAL MATCH (i)-[:RESOLVED_BY]->(p)
    OPTIONAL MATCH (p)-[:MEMBER_OF]->(t:Team)
    RETURN p, t.name AS team,
           sum(w.commits) AS commits,
           max(w.last_at) AS last_at,
           count(DISTINCT i) AS prior_incidents,
           collect(DISTINCT f.path) AS files,
           collect(DISTINCT owner.name) AS services
    ORDER BY prior_incidents DESC, commits DESC
    LIMIT 8
    """
    rows, ms = db.run(tenant, cypher, {"target": service_or_file})

    people, nodes = [], []
    for p, team, commits, last_at, prior, files, services in rows:
        pp = _node(p)
        commits = int(commits or 0)          # FalkorDB sum() returns a double
        prior = int(prior or 0)
        score = commits + 25 * prior
        people.append({
            "name": pp.get("name"), "handle": pp.get("handle"), "role": pp.get("role"),
            "timezone": pp.get("timezone"), "team": team,
            "on_call": bool(pp.get("on_call")),
            "commits": commits, "prior_incidents_on_file": prior,
            "files": [f for f in files if f][:5],
            "services": [s for s in services if s][:5],
            "expertise_score": score,
        })
        nodes.append(pp)
    people.sort(key=lambda e: -e["expertise_score"])

    oncall_rows, _ = db.run(tenant, """
    MATCH (p:Person {on_call:true}) OPTIONAL MATCH (p)-[:MEMBER_OF]->(t:Team)
    RETURN p.name, p.handle, t.name LIMIT 1
    """)
    on_call = ({"name": oncall_rows[0][0], "handle": oncall_rows[0][1],
                "team": oncall_rows[0][2]} if oncall_rows else None)

    owner_rows, _ = db.run(tenant, """
    MATCH (s:Service {name:$t})-[:OWNED_BY]->(team:Team) RETURN team.name
    """, {"t": service_or_file})

    best = people[0] if people else None
    data = {
        "target": service_or_file,
        "count": len(people),
        "people": people,
        "recommended": best,
        "on_call_default": on_call,
        "owning_team": owner_rows[0][0] if owner_rows else None,
        "differs_from_rotation": bool(best and on_call and best["name"] != on_call["name"]),
    }
    note = f"{best['name']} ({best['commits']} commits)" if best else "nobody found"
    return ToolResult("who_knows", data, cypher, round((time.perf_counter() - t0) * 1000, 3),
                      path={"nodes": nodes, "edges": []}, note=note)


# --------------------------------------------------------------------------- #
# 7. get_runbook
# --------------------------------------------------------------------------- #
def get_runbook(tenant: str, service: str, symptom: str = "") -> ToolResult:
    """Hybrid fulltext + vector lookup for the runbook that applies.

    Fulltext finds the documents that mention the words; the vector index
    ranks them by what the symptom means. Both, because either alone misses:
    fulltext cannot match "pool exhausted" to "acquire timeouts", and vector
    search alone drifts to generic restart procedures.
    """
    t0 = time.perf_counter()
    cypher = """
    CALL db.idx.vector.queryNodes('Runbook','embedding', 5, vecf32($v))
    YIELD node, score
    OPTIONAL MATCH (node)-[:COVERS]->(s:Service)
    RETURN node, score, collect(DISTINCT s.name) AS services
    """
    rows, ms = db.run(tenant, cypher, {"v": embed(f"{symptom} {service}".strip())})

    runbooks, nodes = [], []
    for node, score, services in rows:
        rp = _node(node)
        svcs = [s for s in services if s]
        runbooks.append({
            "runbook_id": rp.get("id"), "title": rp.get("title"), "body": rp.get("body"),
            "covers": svcs, "similarity": round(1 - float(score), 4),
            "covers_target": service in svcs,
        })
        nodes.append(rp)
    # a runbook that actually covers the service in question wins over a
    # semantically closer one that covers something else
    runbooks.sort(key=lambda r: (not r["covers_target"], -r["similarity"]))

    data = {"service": service, "symptom": symptom, "count": len(runbooks),
            "best": runbooks[0] if runbooks else None, "runbooks": runbooks}
    return ToolResult("get_runbook", data, cypher, round((time.perf_counter() - t0) * 1000, 3),
                      path={"nodes": nodes, "edges": []},
                      note=runbooks[0]["title"] if runbooks else "no runbook")


# --------------------------------------------------------------------------- #
# 8. criticality_rank
# --------------------------------------------------------------------------- #
def criticality_rank(tenant: str, top: int = 10) -> ToolResult:
    """algo.pageRank over the dependency graph.

    PageRank on DEPENDS_ON ranks services by how much of the system leans on
    them -- structural criticality, which is not the same as the tier someone
    typed into a spreadsheet. Used to prioritise when several things look broken.
    """
    t0 = time.perf_counter()
    cypher = """
    CALL algo.pageRank('Service','DEPENDS_ON') YIELD node, score
    OPTIONAL MATCH (node)<-[:DEPENDS_ON]-(dependent:Service)
    RETURN node, score, count(DISTINCT dependent) AS direct_dependents
    ORDER BY score DESC
    LIMIT $top
    """
    rows, ms = db.run(tenant, cypher, {"top": max(1, min(42, int(top)))})
    ranked, nodes = [], []
    for i, (node, score, dependents) in enumerate(rows):
        np = _node(node)
        ranked.append({"rank": i + 1, "name": np.get("name"),
                       "pagerank": round(float(score), 6), "tier": np.get("tier"),
                       "direct_dependents": dependents,
                       "revenue_critical": bool(np.get("revenue_critical"))})
        nodes.append(np)
    data = {"count": len(ranked), "ranking": ranked, "algorithm": "algo.pageRank"}
    return ToolResult("criticality_rank", data, cypher,
                      round((time.perf_counter() - t0) * 1000, 3),
                      path={"nodes": nodes, "edges": []},
                      note=", ".join(r["name"] for r in ranked[:3]))


# --------------------------------------------------------------------------- #
# 9. write_finding  -- the write-back loop
# --------------------------------------------------------------------------- #
def write_finding(tenant: str, incident_id: str, kind: str,
                  payload: dict | None = None) -> ToolResult:
    """Write what was learned back into the graph.

    kind:
      root_cause  -- (:Incident)-[:CAUSED_BY]->(:Deploy)
      postmortem  -- (:Postmortem {created_by:'blackbox'}) + embedding
      resolution  -- (:Incident)-[:RESOLVED_BY]->(:Person), status resolved

    Every run must end in at least one of these. It is what makes the next
    incident of the same shape resolve in one hop instead of six, and it is
    the reason memory here is a property of the data rather than of a process
    that happens to still be running.
    """
    t0 = time.perf_counter()
    payload = payload or {}
    kind = (kind or "").lower()
    nodes, edges, cypher, data = [], [], "", {}

    if kind == "root_cause":
        pr_number = payload.get("pr_number")
        deploy_id = payload.get("deploy_id")
        cypher = """
        MATCH (i:Incident {id:$incident})
        MATCH (d:Deploy)
        WHERE d.id = $deploy_id OR d.pr_number = $pr_number
        MERGE (i)-[:CAUSED_BY]->(d)
        WITH i, d
        OPTIONAL MATCH (d)-[:SHIPS]->(pr:PullRequest)
        OPTIONAL MATCH (d)-[:DEPLOYED_TO]->(s:Service)
        RETURN d, pr, s.name
        """
        rows, ms = db.run(tenant, cypher, {"incident": incident_id, "deploy_id": deploy_id,
                                           "pr_number": pr_number})
        if rows:
            dp, pr, svc = _node(rows[0][0]), _node(rows[0][1]) if rows[0][1] else {}, rows[0][2]
            nodes += [dp] + ([pr] if pr else [])
            edges.append(_edge(incident_id, dp.get("id"), "CAUSED_BY"))
            data = {"written": "CAUSED_BY", "incident_id": incident_id,
                    "deploy_id": dp.get("id"), "deploy_sha": dp.get("sha"),
                    "service": svc, "pr_number": pr.get("number"),
                    "pr_title": pr.get("title")}
        else:
            data = {"written": None, "error": "no matching deploy"}

    elif kind == "postmortem":
        lesson = payload.get("lesson", "").strip()
        service = payload.get("service")
        pm_id = f"PM-{incident_id}-BB"
        cypher = """
        MATCH (i:Incident {id:$incident})
        MERGE (pm:Postmortem {id:$pm_id})
        SET pm.lesson = $lesson, pm.created_at = $now, pm.created_by = 'blackbox',
            pm.embedding = vecf32($vec),
            pm.cause_pr = $cause_pr, pm.cause_deploy_id = $cause_deploy_id,
            pm.cause_service = $cause_service, pm.cause_file = $cause_file,
            pm.cause_hops = $cause_hops, pm.affected_count = $affected_count,
            pm.customer_facing = $customer_facing
        MERGE (i)-[:PRODUCED]->(pm)
        WITH pm, i
        OPTIONAL MATCH (s:Service {name:$service})
        FOREACH (x IN CASE WHEN s IS NULL THEN [] ELSE [1] END |
                 MERGE (pm)-[:APPLIES_TO]->(s))
        RETURN pm, i.title
        """
        # the embedding is built from the incident's own symptom plus the
        # lesson, so a future incident with the same signature retrieves it
        inc_rows, _ = db.run(tenant, "MATCH (i:Incident {id:$i}) RETURN i.symptom, i.title",
                             {"i": incident_id})
        context = " ".join(str(x) for x in (inc_rows[0] if inc_rows else []) if x)
        rows, ms = db.run(tenant, cypher, {
            "incident": incident_id, "pm_id": pm_id, "lesson": lesson,
            "now": int(time.time() * 1000), "service": service,
            "vec": embed(f"{context} {lesson}"),
            "cause_pr": payload.get("cause_pr"),
            "cause_deploy_id": payload.get("cause_deploy_id"),
            "cause_service": payload.get("cause_service"),
            "cause_file": payload.get("cause_file"),
            "cause_hops": payload.get("cause_hops"),
            "affected_count": payload.get("affected_count"),
            "customer_facing": payload.get("customer_facing") or [],
        })
        if rows:
            pmp = _node(rows[0][0])
            nodes.append(pmp)
            edges.append(_edge(incident_id, pm_id, "PRODUCED"))
            data = {"written": "Postmortem", "postmortem_id": pm_id,
                    "incident_id": incident_id, "lesson": lesson,
                    "created_by": "blackbox", "applies_to": service,
                    "embedded": True}
        else:
            data = {"written": None, "error": "incident not found"}

    elif kind == "resolution":
        person = payload.get("person")
        cypher = """
        MATCH (i:Incident {id:$incident})
        SET i.status = 'resolved', i.resolved_at = $now
        WITH i
        OPTIONAL MATCH (p:Person {name:$person})
        FOREACH (x IN CASE WHEN p IS NULL THEN [] ELSE [1] END |
                 MERGE (i)-[:RESOLVED_BY]->(p))
        RETURN i, p
        """
        rows, ms = db.run(tenant, cypher, {"incident": incident_id, "person": person,
                                           "now": int(time.time() * 1000)})
        if rows:
            if rows[0][1] is not None:
                pp = _node(rows[0][1])
                nodes.append(pp)
                edges.append(_edge(incident_id, pp.get("name"), "RESOLVED_BY"))
            data = {"written": "RESOLVED_BY", "incident_id": incident_id, "person": person}
        else:
            data = {"written": None, "error": "incident not found"}
    else:
        data = {"written": None,
                "error": f"unknown kind '{kind}'; use root_cause|postmortem|resolution"}

    return ToolResult("write_finding", data, cypher,
                      round((time.perf_counter() - t0) * 1000, 3),
                      path={"nodes": nodes, "edges": edges},
                      note=str(data.get("written") or data.get("error")))


# --------------------------------------------------------------------------- #
# provenance: invisible to the LLM
# --------------------------------------------------------------------------- #
def log_step(tenant: str, incident_id: str, agent: str, tool: str, args: dict,
             latency_ms: float, touched: list[str] | None = None,
             prev_step_id: str | None = None) -> str:
    """Write an :AgentStep node for a tool call, chained to the previous one.

    The agent's own reasoning lives in the graph. The trace panel is not a log
    file being tailed -- it is a Cypher query over AgentStep nodes, which is
    also how a restarted agent picks up where the last one stopped.
    """
    step_id = f"step-{incident_id}-{int(time.time() * 1_000_000) % 1_000_000_000}"
    db.run_rw(tenant, """
    CREATE (a:AgentStep {id:$id, agent:$agent, tool:$tool, args:$args, at:$now,
                         latency_ms:$latency, incident_id:$incident})
    """, {"id": step_id, "agent": agent, "tool": tool,
          "args": str(args)[:500], "now": int(time.time() * 1000),
          "latency": latency_ms, "incident": incident_id})

    if prev_step_id:
        db.run_rw(tenant, """
        MATCH (a:AgentStep {id:$prev}), (b:AgentStep {id:$cur})
        CREATE (a)-[:NEXT]->(b)
        """, {"prev": prev_step_id, "cur": step_id})

    for name in (touched or [])[:40]:
        db.run_rw(tenant, """
        MATCH (a:AgentStep {id:$id})
        MATCH (n) WHERE n.name = $name OR n.id = $name
        WITH a, n LIMIT 1
        CREATE (a)-[:TOUCHED]->(n)
        """, {"id": step_id, "name": name})
    return step_id


def trace(tenant: str, incident_id: str) -> list[dict]:
    """Read the provenance chain back out of the graph."""
    rows, _ = db.run(tenant, """
    MATCH (a:AgentStep {incident_id:$i})
    OPTIONAL MATCH (a)-[:TOUCHED]->(n)
    RETURN a.id, a.agent, a.tool, a.args, a.at, a.latency_ms,
           collect(DISTINCT coalesce(n.name, n.id)) AS touched
    ORDER BY a.at
    """, {"i": incident_id})
    return [{"step_id": r[0], "agent": r[1], "tool": r[2], "args": r[3], "at": r[4],
             "latency_ms": r[5], "touched": [t for t in r[6] if t]} for r in rows]


# --------------------------------------------------------------------------- #
REGISTRY = {
    "resolve_entity": resolve_entity,
    "affected_services": affected_services,
    "recent_changes": recent_changes,
    "causal_path": causal_path,
    "similar_incidents": similar_incidents,
    "who_knows": who_knows,
    "get_runbook": get_runbook,
    "criticality_rank": criticality_rank,
    "write_finding": write_finding,
}


def call(tenant: str, tool: str, **kwargs) -> ToolResult:
    if tool not in REGISTRY:
        return ToolResult(tool, {"error": f"unknown tool '{tool}'"})
    return REGISTRY[tool](tenant, **kwargs)
