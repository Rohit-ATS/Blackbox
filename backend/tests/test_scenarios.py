"""Gate tests for the two scenarios.

These assert the demo itself, not just the tools. They run on the
deterministic planner so they are hermetic -- no API key, no network.
"""
from __future__ import annotations

import pytest

from blackbox import agents, db, scenarios, seed

TENANT = "acme"


@pytest.fixture(scope="module", autouse=True)
def seeded():
    rows, _ = db.run(TENANT, "MATCH (s:Service) RETURN count(s)")
    if not rows or rows[0][0] != 42:
        seed.build(TENANT, verbose=False)
    scenarios.reset_memory(TENANT)
    yield


@pytest.fixture(scope="module")
def runs(seeded):
    """Cold then warm, in that order. The warm run depends on the cold one."""
    cold = agents.run_sync(TENANT, scenarios.SCENARIO_COLD, use_llm=False)
    warm = agents.run_sync(TENANT, scenarios.SCENARIO_WARM, use_llm=False)
    return {"cold": cold, "warm": warm}


# --------------------------------------------------------------------- cold
def test_cold_run_finds_the_right_root_cause(runs):
    a = runs["cold"]["answer"]
    assert a["root_cause"]["pr_number"] == 4471
    assert a["root_cause"]["service"] == "ledger-service"
    assert a["root_cause"]["file"] == "src/db/connection-pool.ts"
    assert a["root_cause"]["hops_upstream"] == 2


def test_cold_run_reaches_the_root_cause_within_eight_calls(runs):
    """Phase 3 gate: root cause identified in <= 8 tool calls."""
    events = runs["cold"]["events"]
    found_at = next(e["step"] for e in events
                    if e["type"] == "tool_result" and e["tool"] == "recent_changes"
                    and any(d["pr_number"] == 4471 for d in e["data"]["deploys"]))
    assert found_at <= 8, f"took {found_at} calls to see the cause"


def test_cold_run_sizes_the_blast_radius(runs):
    b = runs["cold"]["answer"]["blast_radius"]
    assert b["count"] == 11
    assert sorted(b["customer_facing"]) == ["mobile-bff", "partner-api", "web-bff"]


def test_cold_run_proves_the_propagation_path(runs):
    assert runs["cold"]["answer"]["propagation"]["chain"] == [
        "ledger-service", "payments-api", "checkout-api"]


def test_cold_run_pages_the_expert_not_the_rotation(runs):
    p = runs["cold"]["answer"]["page"]
    assert p["name"] == "Priya Raghavan"
    assert p["instead_of_on_call"] == "Marcus Webb"


def test_cold_run_writes_back_to_the_graph(runs):
    wrote = runs["cold"]["metrics"]["wrote"]
    assert "CAUSED_BY" in wrote
    assert "Postmortem" in wrote
    rows, _ = db.run(TENANT, """
      MATCH (:Incident {id:'INC-3001'})-[:CAUSED_BY]->(d:Deploy)-[:SHIPS]->(pr:PullRequest)
      RETURN pr.number""")
    assert rows and rows[0][0] == 4471


def test_every_claim_on_the_answer_card_has_a_citation(runs):
    a = runs["cold"]["answer"]
    cited = {c["n"] for c in a["citations"]}
    for key in ("root_cause", "blast_radius", "propagation", "page"):
        assert a[key]["citation"] in cited, key


# --------------------------------------------------------------------- warm
def test_warm_run_recalls_the_postmortem_the_cold_run_wrote(runs):
    """Phase 4 gate, part one: it must cite its own postmortem."""
    m = runs["warm"]["answer"]["memory"]
    assert m["self_authored"] is True
    assert m["written_by"] == "blackbox"
    assert m["postmortem_id"] == "PM-INC-3001-BB"
    assert m["incident_id"] == "INC-3001"
    assert runs["warm"]["metrics"]["recalled_own_postmortem"] is True


def test_warm_run_does_strictly_less_work(runs):
    """Phase 4 gate, part two: the recall has to actually save work."""
    cold, warm = runs["cold"]["metrics"], runs["warm"]["metrics"]
    assert warm["tool_calls"] < cold["tool_calls"]
    assert warm["graph_latency_ms"] < cold["graph_latency_ms"] / 1.8
    # the expensive traversals are skipped entirely
    warm_tools = {e["tool"] for e in runs["warm"]["events"] if e["type"] == "tool_call"}
    assert "criticality_rank" not in warm_tools
    assert "causal_path" not in warm_tools


def test_warm_run_still_produces_a_complete_answer(runs):
    """Faster must not mean thinner."""
    a = runs["warm"]["answer"]
    assert a["root_cause"]["pr_number"] == 4525
    assert a["root_cause"]["file"] == "src/db/pool.ts"
    assert a["blast_radius"]["count"] >= 1
    assert a["page"]["name"] == "Mei Tanaka"
    assert "Postmortem" in runs["warm"]["metrics"]["wrote"]


# ---------------------------------------------------------------- handoffs
def test_agents_hand_off_through_the_graph(runs):
    """Track 02: handoff state is graph data, not process memory."""
    events = runs["cold"]["events"]
    handoffs = [(e["from"], e["to"]) for e in events if e["type"] == "handoff"]
    assert handoffs == [("Triage", "Investigator"), ("Investigator", "Comms")]

    # the provenance chain is readable back out of FalkorDB
    from blackbox import tools as T
    trail = T.trace(TENANT, "INC-3001")
    assert len(trail) == runs["cold"]["metrics"]["tool_calls"]
    assert [s["agent"] for s in trail[:1]] == ["Triage"]
    assert trail[-1]["agent"] == "Comms"

    rows, _ = db.run(TENANT, """
      MATCH (a:AgentStep {incident_id:'INC-3001'})-[:NEXT]->(b:AgentStep)
      RETURN count(*)""")
    assert rows[0][0] == runs["cold"]["metrics"]["tool_calls"] - 1


def test_each_step_records_what_it_touched(runs):
    from blackbox import tools as T
    trail = T.trace(TENANT, "INC-3001")
    touched = {n for s in trail for n in s["touched"]}
    assert "checkout-api" in touched
    assert "ledger-service" in touched


# ----------------------------------------------------------------- replay
def test_scenarios_are_replayable(seeded):
    """Same scenario twice in a row must give the same answer."""
    a = agents.run_sync(TENANT, scenarios.SCENARIO_COLD, use_llm=False)["answer"]
    b = agents.run_sync(TENANT, scenarios.SCENARIO_COLD, use_llm=False)["answer"]
    assert a["root_cause"]["pr_number"] == b["root_cause"]["pr_number"]
    assert a["blast_radius"]["count"] == b["blast_radius"]["count"]
    assert a["page"]["name"] == b["page"]["name"]


def test_reset_memory_actually_forgets(seeded):
    agents.run_sync(TENANT, scenarios.SCENARIO_COLD, use_llm=False)
    assert scenarios.memory_state(TENANT)["self_authored_postmortems"] >= 1
    scenarios.reset_memory(TENANT)
    assert scenarios.memory_state(TENANT)["self_authored_postmortems"] == 0
    # seeded history survives: only what BLACKBOX learned is removed
    assert scenarios.memory_state(TENANT)["seeded_postmortems"] == 11


def test_the_event_contract_is_what_the_frontend_expects(runs):
    kinds = [e["type"] for e in runs["cold"]["events"]]
    assert kinds[0] == "run_start"
    assert kinds[-1] == "run_end"
    assert "answer" in kinds
    for e in runs["cold"]["events"]:
        assert "type" in e and "at" in e
        if e["type"] == "tool_result":
            assert set(e["path"]) == {"nodes", "edges"}
            assert isinstance(e["latency_ms"], (int, float))
            assert e["cypher"]
