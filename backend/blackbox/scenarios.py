"""The two replayable scenarios.

Both are deterministic and runnable with one button, because a demo cannot
depend on improvisation.

SCENARIO_COLD  checkout-api latency, caused by a deploy to ledger-service two
               hops upstream. One partially-relevant historical incident
               exists (INC-2041, a prior pool exhaustion on the same file), so
               memory helps a little but the agent still has to do the work:
               it must find *which* deploy, prove the path, and name the owner.

SCENARIO_WARM  notifications-api, a different service with the same failure
               signature, run after the cold run has written its postmortem.
               Now the first memory lookup returns BLACKBOX's own lesson and
               the investigation collapses to a few hops.

`prepare()` resets a scenario so it can be replayed: it removes anything a
previous run wrote for that incident and re-anchors the causing deploy to
"23 minutes ago" relative to now.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import db

MINUTE_MS = 60_000


@dataclass
class Scenario:
    key: str
    incident_id: str
    title: str
    service: str
    alert: dict
    symptom: str
    severity: str
    narrative: str
    expect: dict = field(default_factory=dict)


SCENARIO_COLD = Scenario(
    key="cold",
    incident_id="INC-3001",
    title="checkout-api p99 latency breach",
    service="checkout-api",
    alert={
        "id": "ALRT-3001",
        "metric": "p99_latency_ms",
        "value": 4200.0,
        "threshold": 1500.0,
        "service": "checkout-api",
    },
    symptom=("checkout-api p99 latency 4200ms, threshold 1500ms, error rate climbing, "
             "payment intent creation slow, CPU flat across replicas"),
    severity="SEV1",
    narrative="Cold run. Nothing in memory names this deploy; the agent has to traverse.",
    expect={"root_cause_pr": 4471, "cause_service": "ledger-service",
            "affected_services": 11, "owner": "Priya Raghavan"},
)

SCENARIO_WARM = Scenario(
    key="warm",
    incident_id="INC-3002",
    title="notifications-api p99 latency breach",
    service="notifications-api",
    alert={
        "id": "ALRT-3002",
        "metric": "p99_latency_ms",
        "value": 3800.0,
        "threshold": 1500.0,
        "service": "notifications-api",
    },
    symptom=("notifications-api p99 latency 3800ms, connection pool exhausted, acquire "
             "timeouts, waiters queueing, CPU flat"),
    severity="SEV2",
    narrative=("Warm run. Same failure signature as the cold run, different service. "
               "The first memory lookup should return the postmortem BLACKBOX wrote."),
    expect={"recalls_own_postmortem": True, "max_tool_calls": 5},
)

ALL = {"cold": SCENARIO_COLD, "warm": SCENARIO_WARM}


def prepare(tenant: str, scenario: Scenario) -> dict:
    """Make the scenario runnable from a clean slate. Idempotent."""
    # drop everything a previous run of THIS scenario wrote
    db.run_rw(tenant, """
    MATCH (i:Incident {id:$inc})
    OPTIONAL MATCH (i)-[:PRODUCED]->(pm:Postmortem)
    DETACH DELETE i, pm
    """, {"inc": scenario.incident_id})
    db.run_rw(tenant, "MATCH (a:AgentStep {incident_id:$inc}) DETACH DELETE a",
              {"inc": scenario.incident_id})
    db.run_rw(tenant, "MATCH (a:Alert {id:$a}) DETACH DELETE a", {"a": scenario.alert["id"]})

    now = int(time.time() * 1000)

    # re-anchor the causing deploy so "23 minutes ago" stays true however long
    # the container has been up
    deploy_id, age = (("dep-cause", 23) if scenario.key == "cold" else ("dep-warm", 14))
    db.run_rw(tenant, """
    MATCH (d:Deploy {id:$id})
    SET d.at = $at
    WITH d MATCH (d)-[:SHIPS]->(pr:PullRequest) SET pr.merged_at = $merged
    """, {"id": deploy_id, "at": now - age * MINUTE_MS,
          "merged": now - (age + 4) * MINUTE_MS})

    # create the live alert and the open incident
    db.run_rw(tenant, """
    CREATE (a:Alert {id:$aid, metric:$metric, value:$value, threshold:$threshold,
                     fired_at:$now})
    WITH a MATCH (s:Service {name:$svc}) CREATE (a)-[:FIRED_ON]->(s)
    """, {"aid": scenario.alert["id"], "metric": scenario.alert["metric"],
          "value": scenario.alert["value"], "threshold": scenario.alert["threshold"],
          "now": now, "svc": scenario.alert["service"]})

    from .embeddings import embed
    db.run_rw(tenant, """
    CREATE (i:Incident {id:$inc, title:$title, symptom:$symptom, started_at:$now,
                        started_iso:$iso, severity:$sev, status:'open',
                        embedding:vecf32($vec)})
    WITH i MATCH (a:Alert {id:$aid}) CREATE (i)-[:TRIGGERED_BY]->(a)
    WITH i MATCH (s:Service {name:$svc}) CREATE (i)-[:AFFECTED]->(s)
    """, {"inc": scenario.incident_id, "title": scenario.title, "symptom": scenario.symptom,
          "now": now, "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now / 1000)),
          "sev": scenario.severity, "aid": scenario.alert["id"],
          "svc": scenario.service, "vec": embed(f"{scenario.title} {scenario.symptom}")})

    return {"incident_id": scenario.incident_id, "prepared_at": now}


def reset_memory(tenant: str) -> dict:
    """Forget everything BLACKBOX has learned, keeping the seeded history.

    Lets you run the cold/warm pair repeatedly on stage: the warm run is only
    fast because of what the cold run wrote, so proving that means being able
    to take it away again.
    """
    rows, _ = db.run(tenant, """
    MATCH (pm:Postmortem {created_by:'blackbox'}) RETURN count(pm)
    """)
    removed = rows[0][0] if rows else 0
    db.run_rw(tenant, "MATCH (pm:Postmortem {created_by:'blackbox'}) DETACH DELETE pm")
    db.run_rw(tenant, "MATCH (a:AgentStep) DETACH DELETE a")
    for s in ALL.values():
        db.run_rw(tenant, "MATCH (i:Incident {id:$i}) DETACH DELETE i", {"i": s.incident_id})
    db.run_rw(tenant, "MATCH (i:Incident)-[r:CAUSED_BY]->() DELETE r")
    return {"postmortems_removed": removed}


def memory_state(tenant: str) -> dict:
    """What BLACKBOX currently remembers, for the UI badge."""
    rows, _ = db.run(tenant, """
    MATCH (pm:Postmortem) RETURN pm.created_by = 'blackbox' AS own, count(pm)
    """)
    own = sum(r[1] for r in rows if r[0])
    seeded = sum(r[1] for r in rows if not r[0])
    steps, _ = db.run(tenant, "MATCH (a:AgentStep) RETURN count(a)")
    return {"self_authored_postmortems": own, "seeded_postmortems": seeded,
            "agent_steps": steps[0][0] if steps else 0}
