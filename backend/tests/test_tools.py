"""One test per tool, asserted against the seeded graph.

These are the invariants the demo rests on. If any of them goes red, the
scenario on stage is wrong, not just the test.
"""
from __future__ import annotations

import pytest

from blackbox import db, seed, tools

TENANT = "acme"


@pytest.fixture(scope="session", autouse=True)
def seeded():
    rows, _ = db.run(TENANT, "MATCH (s:Service) RETURN count(s)")
    if not rows or rows[0][0] != 42:
        seed.build(TENANT, verbose=False)
    yield


def test_every_tool_returns_the_contract():
    """The UI depends on {data, path, cypher, latency_ms} from all nine."""
    assert len(tools.REGISTRY) == 9
    r = tools.resolve_entity(TENANT, "checkout-api")
    d = r.to_dict()
    for key in ("tool", "data", "path", "cypher", "latency_ms"):
        assert key in d, key
    assert set(d["path"]) == {"nodes", "edges"}
    assert d["latency_ms"] > 0


def test_resolve_entity_maps_an_alert_line_to_a_service():
    r = tools.resolve_entity(TENANT, "checkout-api p99 latency 4200ms above threshold 1500ms")
    assert r.data["resolved"] is True
    assert r.data["name"] == "checkout-api"
    assert r.data["revenue_critical"] is True


def test_blast_radius_finds_eleven_dependents_three_customer_facing():
    r = tools.blast_radius(TENANT, "checkout-api", max_depth=4)
    assert r.data["count"] == 11
    assert r.data["customer_facing_count"] == 3
    assert set(r.data["customer_facing"]) == {"web-bff", "mobile-bff", "partner-api"}
    # every impacted service carries the hop count it was reached at
    assert all(s["hops"] >= 1 for s in r.data["services"])
    # and the traversal comes back with edges to render, not a node cloud
    assert len(r.path["edges"]) >= 11


def test_recent_changes_finds_the_cause_two_hops_upstream():
    r = tools.recent_changes(TENANT, "checkout-api", window_minutes=120, hops=2)
    prs = [d["pr_number"] for d in r.data["deploys"]]
    assert 4471 in prs, f"root cause PR missing, got {prs}"
    cause = next(d for d in r.data["deploys"] if d["pr_number"] == 4471)
    assert cause["service"] == "ledger-service"
    assert cause["hops_from_symptom"] == 2
    assert "src/db/connection-pool.ts" in cause["files"]
    # it must rank first: highest risk in the window
    assert r.data["deploys"][0]["pr_number"] == 4471


def test_recent_changes_misses_the_cause_at_one_hop():
    """The whole point: at one hop you cannot see it. The graph earns its keep."""
    r = tools.recent_changes(TENANT, "checkout-api", window_minutes=120, hops=1)
    assert 4471 not in [d["pr_number"] for d in r.data["deploys"]]


def test_causal_path_prefers_the_hard_dependency_over_equal_hop_count():
    r = tools.causal_path(TENANT, "checkout-api", "ledger-service")
    assert r.data["found"] is True
    # fraud-screen is also two hops away; criticality weighting excludes it
    assert r.data["propagation"] == ["ledger-service", "payments-api", "checkout-api"]
    assert all(link["criticality"] == 5 for link in r.data["links"])


def test_similar_incidents_recalls_the_prior_pool_exhaustion():
    r = tools.similar_incidents(
        TENANT,
        "notifications-api p99 latency 3800ms connection pool exhausted waiters queueing",
        k=3)
    ids = [i["incident_id"] for i in r.data["incidents"]]
    assert "INC-2041" in ids
    top = r.data["incidents"][0]
    assert top["incident_id"] == "INC-2041"
    assert top["similarity"] > 0.5
    assert "connection-pool.ts" in top["lesson"]


def test_who_knows_beats_the_on_call_rotation():
    r = tools.who_knows(TENANT, "src/db/connection-pool.ts")
    assert r.data["recommended"]["name"] == "Priya Raghavan"
    assert r.data["recommended"]["commits"] == 47
    assert r.data["recommended"]["prior_incidents_on_file"] >= 1
    assert r.data["on_call_default"]["name"] == "Marcus Webb"
    assert r.data["differs_from_rotation"] is True


def test_get_runbook_prefers_one_that_covers_the_service():
    r = tools.get_runbook(TENANT, "ledger-service", "connection pool exhausted acquire timeouts")
    assert r.data["best"]["covers_target"] is True
    assert "Connection pool exhaustion" in r.data["best"]["title"]


def test_criticality_rank_runs_pagerank_and_ranks_shared_infra_highest():
    r = tools.criticality_rank(TENANT, top=10)
    assert len(r.data["ranking"]) == 10
    names = [x["name"] for x in r.data["ranking"]]
    assert "postgres-primary" in names[:5]
    assert r.data["ranking"][0]["pagerank"] >= r.data["ranking"][-1]["pagerank"]


def test_write_finding_creates_causal_edge_postmortem_and_resolution():
    inc = "INC-TEST-0001"
    db.run_rw(TENANT, """
      CREATE (:Incident {id:$i, title:'test', symptom:'connection pool exhausted test',
                         started_at:0, status:'open'})""", {"i": inc})
    try:
        rc = tools.write_finding(TENANT, inc, "root_cause", {"pr_number": 4471})
        assert rc.data["written"] == "CAUSED_BY"
        assert rc.data["service"] == "ledger-service"

        pm = tools.write_finding(TENANT, inc, "postmortem",
                                 {"lesson": "pool ceiling too low under retry amplification",
                                  "service": "ledger-service"})
        assert pm.data["written"] == "Postmortem"
        assert pm.data["created_by"] == "blackbox"

        res = tools.write_finding(TENANT, inc, "resolution", {"person": "Priya Raghavan"})
        assert res.data["written"] == "RESOLVED_BY"

        # the written postmortem must now be retrievable by vector search --
        # this is the memory loop, asserted end to end
        found = tools.similar_incidents(TENANT, "connection pool exhausted test", k=5)
        assert any(p.get("self_authored") for p in found.data["postmortems"])
    finally:
        db.run_rw(TENANT, """
          MATCH (i:Incident {id:$i}) OPTIONAL MATCH (i)-[:PRODUCED]->(pm:Postmortem)
          DETACH DELETE i, pm""", {"i": inc})


def test_log_step_writes_a_chained_provenance_trail():
    inc = "INC-TEST-0002"
    s1 = tools.log_step(TENANT, inc, "Triage", "resolve_entity", {"text": "x"}, 1.2,
                        touched=["checkout-api"])
    s2 = tools.log_step(TENANT, inc, "Investigator", "recent_changes", {}, 3.4,
                        touched=["ledger-service"], prev_step_id=s1)
    try:
        steps = tools.trace(TENANT, inc)
        assert [s["agent"] for s in steps] == ["Triage", "Investigator"]
        assert "checkout-api" in steps[0]["touched"]
        rows, _ = db.run(TENANT,
                         "MATCH (:AgentStep {id:$a})-[:NEXT]->(:AgentStep {id:$b}) RETURN 1",
                         {"a": s1, "b": s2})
        assert rows, "NEXT handoff edge missing"
    finally:
        db.run_rw(TENANT, "MATCH (a:AgentStep {incident_id:$i}) DETACH DELETE a", {"i": inc})


def test_tenants_are_isolated():
    acme, _ = db.run("acme", "MATCH (s:Service {name:'checkout-api'}) RETURN count(s)")
    globex, _ = db.run("globex", "MATCH (s:Service {name:'checkout-api'}) RETURN count(s)")
    assert acme[0][0] == 1
    assert globex[0][0] == 0


def test_depth_is_clamped_not_interpolated():
    """Depth is the one value that reaches Cypher as a literal; it is bounded."""
    assert tools._depth("4") == 4
    assert tools._depth(99) == tools.MAX_DEPTH
    assert tools._depth(0) == 1
    assert tools._depth("'; MATCH (n) DETACH DELETE n //") == 4
