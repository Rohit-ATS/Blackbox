"""Deterministic seed generator for the BLACKBOX graph.

    python -m blackbox.seed --all          # both tenants, from scratch
    python -m blackbox.seed --tenant acme

Deterministic (random.Random(42)) so the demo is identical on every machine.
Timestamps are anchored to seed time, so "23 minutes ago" is actually 23
minutes ago when you run it.
"""
from __future__ import annotations

import argparse
import random
import time
from datetime import datetime, timedelta, timezone

from . import config, db, schema, topology as topo
from .embeddings import embed

MINUTE = 60_000
HOUR = 60 * MINUTE
DAY = 24 * HOUR


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# Historical incidents for acme. Hand-written: the agent's memory is only as
# good as what is in here, and INC-2041 is the one the cold run should find
# partially relevant.
# --------------------------------------------------------------------------- #
HISTORICAL = [
    dict(id="INC-2041", days_ago=18, severity="SEV1", service="ledger-service",
         title="ledger-service connection pool exhaustion under checkout retry storm",
         symptom="ledger-service p99 latency 6100ms, connection pool exhausted, "
                 "acquire timeouts, waiters queueing, checkout retries amplifying load",
         resolved_by="Priya Raghavan", minutes=74,
         lesson="ledger-service ran a fixed Postgres pool of 20 connections. A retry storm "
                "from checkout-api saturated it and every caller queued on acquire, so p99 "
                "latency climbed while CPU stayed flat -- the signature of pool exhaustion "
                "rather than compute pressure. Fix was to raise the pool ceiling to 60 and "
                "add a per-caller bulkhead in src/db/connection-pool.ts so one noisy "
                "upstream cannot consume the whole pool. Check pool saturation before "
                "chasing CPU whenever latency rises with flat utilisation.",
         file="src/db/connection-pool.ts"),
    dict(id="INC-2029", days_ago=26, severity="SEV2", service="redis-cache",
         title="redis-cache eviction storm degraded session lookups",
         symptom="auth-service token introspection errors, redis-cache evicting hot keys, "
                 "session lookups missing, login failures elevated",
         resolved_by="Grace Mbeki", minutes=52,
         lesson="maxmemory-policy was allkeys-lru across shared cache namespaces, so a batch "
                "job filled redis-cache and evicted live session keys. Namespace isolation "
                "with per-prefix memory budgets prevented recurrence.",
         file=None),
    dict(id="INC-2033", days_ago=23, severity="SEV2", service="payments-api",
         title="payments-api capture timeouts after gRPC deadline change",
         symptom="payments-api capture calls timing out, gRPC DEADLINE_EXCEEDED to "
                 "ledger-service, order completion rate down 12%",
         resolved_by="Tomas Lindqvist", minutes=38,
         lesson="A deadline reduction from 5s to 800ms in LedgerClient.java was shipped "
                "without measuring the ledger p99. Deadlines must be set from observed "
                "downstream p99 times 1.5, never from a round number.",
         file="src/client/LedgerClient.java"),
    dict(id="INC-2018", days_ago=34, severity="SEV3", service="search-api",
         title="search-api index rebuild saturated catalog-api reads",
         symptom="search-api returning stale results, catalog-api read latency elevated, "
                 "index rebuild running during peak traffic",
         resolved_by="Chen Wei", minutes=95,
         lesson="Index rebuilds had no rate limit and ran on a cron that overlapped peak "
                "hours. Rebuilds are now token-bucket limited and scheduled off-peak.",
         file=None),
    dict(id="INC-2037", days_ago=21, severity="SEV1", service="postgres-primary",
         title="postgres-primary failover left replicas lagging 40 minutes",
         symptom="postgres-primary failover triggered, replica lag 40 minutes, read-after-write "
                 "inconsistency across catalog-api and user-profile",
         resolved_by="Marcus Webb", minutes=140,
         lesson="Synchronous replication was configured on one replica only. Promotion picked "
                "an async replica. Quorum commit across two replicas is now required.",
         file=None),
    dict(id="INC-2044", days_ago=14, severity="SEV2", service="fraud-screen",
         title="fraud-screen model rollout blocked checkout for low-risk customers",
         symptom="fraud-screen decline rate up 8x, checkout-api conversion dropped, "
                 "model v7 rolled to 100% without shadow comparison",
         resolved_by="Ingrid Vos", minutes=47,
         lesson="Scoring model rollouts had no shadow-mode gate. All model versions now run "
                "in shadow against production traffic for 24h before any live share.",
         file=None),
    dict(id="INC-2051", days_ago=9, severity="SEV3", service="notifications-api",
         title="notifications-api fan-out backlog after template-renderer deploy",
         symptom="notifications-api queue depth growing, template-renderer 5xx rate elevated, "
                 "push delivery delayed 20 minutes",
         resolved_by="Mei Tanaka", minutes=33,
         lesson="template-renderer shipped a breaking template schema without a version "
                "negotiation. Renderer responses are now versioned and the fan-out worker "
                "falls back to the previous template on schema mismatch.",
         file="src/fanout/dispatch.ts"),
    dict(id="INC-2048", days_ago=11, severity="SEV2", service="edge-gateway",
         title="edge-gateway TLS session cache misconfiguration spiked handshake latency",
         symptom="edge-gateway handshake latency 900ms, TLS session resumption rate near zero, "
                 "all customer-facing surfaces slower",
         resolved_by="Noor Haddad", minutes=29,
         lesson="A config rollout zeroed the TLS session cache size. Handshake cost is now a "
                "gated SLO on every edge-gateway config change.",
         file=None),
    dict(id="INC-2022", days_ago=30, severity="SEV3", service="inventory-service",
         title="inventory-service reservation leak oversold limited stock",
         symptom="inventory-service reservations not released, oversell on limited stock items, "
                 "order-orchestrator saga compensation failing",
         resolved_by="Yusuf Demir", minutes=112,
         lesson="Saga compensation did not run when the orchestrator crashed mid-transaction. "
                "Reservations now carry a TTL so a lost compensation self-heals.",
         file=None),
    dict(id="INC-2056", days_ago=5, severity="SEV3", service="currency-oracle",
         title="currency-oracle stale FX rates mispriced international carts",
         symptom="currency-oracle serving rates 6 hours stale, pricing-engine quoting wrong "
                 "totals for non-USD carts",
         resolved_by="Liam Doyle", minutes=41,
         lesson="The rate refresher failed silently when the upstream returned 304. Staleness "
                "is now an alerting metric rather than a log line.",
         file=None),
    dict(id="INC-2012", days_ago=38, severity="SEV2", service="auth-service",
         title="auth-service key rotation invalidated in-flight tokens",
         symptom="auth-service introspection rejecting valid tokens, mass logout across "
                 "web-bff and mobile-bff, permissions-api cache thrash",
         resolved_by="Hugo Silva", minutes=58,
         lesson="JWKS rotation removed the previous key immediately. Rotation now keeps the "
                "prior key for two token lifetimes.",
         file=None),
]

RUNBOOK_SEEDS = [
    ("Connection pool exhaustion", "ledger-service",
     "Symptom: p99 latency climbing while CPU stays flat, acquire timeouts in logs, "
     "waiters queueing on the connection pool.\n"
     "1. Check pool saturation: pg_stat_activity count vs the configured ceiling in "
     "src/db/connection-pool.ts.\n"
     "2. If saturated, raise the ceiling and restart rolling. Do not restart all replicas.\n"
     "3. Identify the noisy upstream from per-caller acquire metrics and rate limit it.\n"
     "4. Add or verify the per-caller bulkhead so one upstream cannot take the whole pool.\n"
     "Escalate to Payments Platform if the ledger balance endpoint is affected."),
    ("gRPC deadline tuning", "payments-api",
     "Set client deadlines from observed downstream p99 times 1.5. Never use round numbers. "
     "Check LedgerClient.java deadline config before changing retry policy."),
    ("Postgres failover", "postgres-primary",
     "Verify quorum commit across two synchronous replicas before promoting. Check replica "
     "lag, then promote, then re-point the pgbouncer pool."),
    ("Redis eviction storm", "redis-cache",
     "Check maxmemory-policy and per-namespace memory budgets. Session keys must never share "
     "an eviction namespace with batch job output."),
    ("Checkout retry storm", "checkout-api",
     "Retries in src/http/retry.ts use exponential backoff with jitter. If downstream latency "
     "rises, cap the retry budget before it amplifies load onto payments-api and ledger-service."),
]

DECISIONS = [
    ("ADR-014 Double-entry ledger as the single source of financial truth", "ledger-service",
     "Priya Raghavan",
     "Every money movement posts a balanced pair of entries. Services read balances from "
     "ledger-service rather than deriving them, so reconciliation has one authority."),
    ("ADR-021 Criticality on dependency edges, not on services", "checkout-api", "Dana Okonkwo",
     "A service is not uniformly critical. checkout-api depends hard on payments-api and "
     "softly on feature-flags. Criticality belongs on the edge so affected services can be weighted."),
    ("ADR-008 Saga orchestration over two-phase commit", "order-orchestrator", "Chen Wei",
     "Order placement spans five services. We accept compensating transactions over "
     "distributed locks, with TTLs on every reservation."),
    ("ADR-030 Shadow mode gate for all scoring models", "fraud-screen", "Ingrid Vos",
     "Models run against live traffic without affecting decisions for 24h before any share."),
    ("ADR-005 Single Postgres primary with quorum commit", "postgres-primary", "Marcus Webb",
     "Two synchronous replicas, quorum commit. Promotion must never select an async replica."),
    ("ADR-017 Versioned template contracts", "template-renderer", "Mei Tanaka",
     "Renderer responses carry a schema version and consumers fall back one version."),
    ("ADR-011 BFF per client surface", "web-bff", "Aisha Bello",
     "Web and mobile diverge enough in payload shape that one BFF would fossilise both."),
    ("ADR-025 Bulkheads on every shared pool", "ledger-service", "Priya Raghavan",
     "Connection pools, thread pools and rate limiters are partitioned per caller. One noisy "
     "upstream must not be able to consume a shared resource entirely."),
    ("ADR-002 Kafka as the only cross-service event path", "kafka-bus", "Noor Haddad",
     "No service-to-service webhooks internally. One backbone, one replay story."),
    ("ADR-019 Flag evaluation at the edge", "feature-flags", "Yusuf Demir",
     "Flags resolve at edge-gateway and ride the request as a header, so downstream services "
     "do not each take a dependency on the flag service."),
    ("ADR-027 Deadlines derived from measured p99", "payments-api", "Tomas Lindqvist",
     "Every gRPC client deadline is generated from the downstream p99 in the service catalog."),
    ("ADR-033 Reconciliation reads replicas only", "reconciliation-job", "Dana Okonkwo",
     "The nightly job must never contend with live traffic on the primary."),
]

MSG_TEMPLATES = [
    "anyone else seeing {svc} p99 creep up in the last hour?",
    "deploying {svc} now, PR #{pr}, should be a no-op",
    "{svc} dashboards look clean after the rollout",
    "rolling back {svc}, error rate doubled",
    "who owns {svc} these days? need a review on a pool config change",
    "reminder: {svc} has a freeze window during the sale",
    "{svc} alert was a flap, threshold is too tight",
    "pairing on the {svc} retry budget this afternoon if anyone wants in",
    "{svc} is at 70% of its connection pool ceiling at peak, worth raising",
    "added a runbook entry for {svc} acquire timeouts",
    "{svc} canary is green, promoting to 100%",
    "heads up: {svc} will restart rolling in 10 min",
]


def _files_for(svc: str, lang: str, rnd: random.Random) -> list[str]:
    files = list(topo.KEY_FILES.get(svc, []))
    ext = topo.EXT.get(lang, ".ts")
    for base in rnd.sample(topo.GENERIC_FILES, k=rnd.randint(3, 5)):
        files.append(base + ext)
    return files


# --------------------------------------------------------------------------- #
def seed_acme(tenant: str = "acme", verbose: bool = True) -> dict:
    rnd = random.Random(config.SEED)
    now = int(time.time() * 1000)
    g = db.graph(tenant)

    def w(cypher, params=None):
        return g.query(cypher, params or {})

    # ---- services -------------------------------------------------------- #
    services = [
        dict(id=f"svc-{i:03d}", name=name, tier=meta[0], revenue_critical=meta[1],
             customer_facing=meta[2], language=meta[3], description=meta[4],
             repo=f"acme/{name}")
        for i, (name, meta) in enumerate(topo.SERVICES.items())
    ]
    w("""UNWIND $rows AS r
         CREATE (:Service {id:r.id, name:r.name, tier:r.tier, language:r.language,
                           repo:r.repo, description:r.description,
                           revenue_critical:r.revenue_critical,
                           customer_facing:r.customer_facing})""", {"rows": services})

    # DEPENDS_ON, plus its materialised inverse IMPACTS.
    #
    # Why both: DEPENDS_ON is the semantically honest edge (a consumer depends
    # on a provider). But "what breaks if X goes down" walks that edge
    # backwards, and algo.BFS only traverses outgoing edges. Rather than
    # hand-rolling a reverse traversal in Cypher and losing the algorithm, we
    # materialise the inverse. cost = 6 - criticality so that shortest-path
    # over cost prefers hard synchronous dependencies over soft ones.
    deps = [
        dict(src=consumer, dst=provider, criticality=crit, protocol=proto,
             cost=float(6 - crit))
        for consumer, providers in topo.DEPENDS_ON.items()
        for provider, crit, proto in providers
    ]
    w("""UNWIND $rows AS r
         MATCH (a:Service {name:r.src}), (b:Service {name:r.dst})
         CREATE (a)-[:DEPENDS_ON {criticality:r.criticality, protocol:r.protocol,
                                  cost:r.cost}]->(b)
         CREATE (b)-[:IMPACTS {criticality:r.criticality, protocol:r.protocol,
                               cost:r.cost}]->(a)""", {"rows": deps})

    # ---- teams, people --------------------------------------------------- #
    teams = [dict(id=f"team-{i}", name=n) for i, n in enumerate(topo.TEAMS)]
    w("UNWIND $rows AS r CREATE (:Team {id:r.id, name:r.name})", {"rows": teams})

    people = [
        dict(id=f"p-{i:02d}", name=n, handle=h, role=role, timezone=tz, team=team,
             on_call=on_call)
        for i, (n, h, role, tz, team, on_call) in enumerate(topo.PEOPLE)
    ]
    w("""UNWIND $rows AS r
         CREATE (:Person {id:r.id, name:r.name, handle:r.handle, role:r.role,
                          timezone:r.timezone, on_call:r.on_call})""", {"rows": people})
    w("""UNWIND $rows AS r
         MATCH (p:Person {id:r.id}), (t:Team {name:r.team})
         CREATE (p)-[:MEMBER_OF]->(t)""", {"rows": people})

    ownership = [dict(svc=s, team=t) for t, svcs in topo.TEAMS.items() for s in svcs]
    w("""UNWIND $rows AS r
         MATCH (s:Service {name:r.svc}), (t:Team {name:r.team})
         CREATE (s)-[:OWNED_BY]->(t)""", {"rows": ownership})

    # ---- files ----------------------------------------------------------- #
    files, fid = [], 0
    by_service: dict[str, list[str]] = {}
    for name, meta in topo.SERVICES.items():
        paths = _files_for(name, meta[3], rnd)
        by_service[name] = paths
        for path in paths:
            fid += 1
            files.append(dict(id=f"file-{fid:04d}", path=path, repo=f"acme/{name}", svc=name))
    w("""UNWIND $rows AS r
         CREATE (f:File {id:r.id, path:r.path, repo:r.repo})
         WITH f, r MATCH (s:Service {name:r.svc})
         CREATE (f)-[:BELONGS_TO]->(s)""", {"rows": files})

    # ---- WORKED_ON ------------------------------------------------------- #
    # Priya is the deliberate non-obvious expert on the ledger pool file.
    team_members: dict[str, list[dict]] = {}
    for p in people:
        team_members.setdefault(p["team"], []).append(p)
    svc_team = {s: t for t, svcs in topo.TEAMS.items() for s in svcs}

    # Fixed so the demo always names the same people.
    worked = [
        dict(person="Priya Raghavan", path="src/db/connection-pool.ts",
             repo="acme/ledger-service", commits=47, last_at=now - 6 * DAY),
        dict(person="Mei Tanaka", path="src/db/pool.ts",
             repo="acme/notifications-api", commits=31, last_at=now - 9 * DAY),
    ]
    pinned = {("src/db/connection-pool.ts", "acme/ledger-service"),
              ("src/db/pool.ts", "acme/notifications-api")}
    for f in files:
        if (f["path"], f["repo"]) in pinned:
            continue
        pool = team_members[svc_team[f["svc"]]]
        for p in rnd.sample(pool, k=min(len(pool), rnd.randint(1, 3))):
            worked.append(dict(person=p["name"], path=f["path"], repo=f["repo"],
                               commits=rnd.randint(1, 22),
                               last_at=now - rnd.randint(1, 60) * DAY))
    # a second, much lighter contributor to the pool file -- so ranking has to work
    worked.append(dict(person="Tomas Lindqvist", path="src/db/connection-pool.ts",
                       repo="acme/ledger-service", commits=6, last_at=now - 40 * DAY))
    w("""UNWIND $rows AS r
         MATCH (p:Person {name:r.person}), (f:File {path:r.path, repo:r.repo})
         CREATE (p)-[:WORKED_ON {commits:r.commits, last_at:r.last_at}]->(f)""",
      {"rows": worked})

    # ---- deploys + PRs --------------------------------------------------- #
    svc_names = list(topo.SERVICES)
    prs, deploys, touches = [], [], []
    pr_number = 4200
    # created by hand below: the cold-run root cause and the warm-run trigger
    RESERVED_PR = {4471, 4525}

    def next_pr() -> int:
        nonlocal pr_number
        pr_number += 1
        while pr_number in RESERVED_PR:
            pr_number += 1
        return pr_number

    # 315 historical deploys over 30 days, then 5 inside the alert window.
    for i in range(315):
        svc = rnd.choice(svc_names)
        next_pr()
        at = now - rnd.randint(3 * HOUR, 30 * DAY)
        author = rnd.choice(team_members[svc_team[svc]])
        touched = rnd.sample(by_service[svc], k=min(len(by_service[svc]), rnd.randint(1, 3)))
        adds, dels = rnd.randint(3, 400), rnd.randint(0, 180)
        prs.append(dict(id=f"pr-{pr_number}", number=pr_number,
                        title=f"{rnd.choice(['fix', 'refactor', 'chore', 'feat', 'perf'])}({svc}): "
                              f"{rnd.choice(['tighten timeouts', 'drop dead code', 'bump deps', 'add metric', 'cache lookup', 'simplify handler', 'guard nil case', 'widen test'])}",
                        merged_at=at - rnd.randint(5, 90) * MINUTE,
                        additions=adds, deletions=dels, author=author["name"]))
        deploys.append(dict(id=f"dep-{i:04d}", sha=f"{rnd.getrandbits(80):020x}"[:12], at=at,
                            at_iso=iso(at), status="success" if rnd.random() > 0.08 else "failed",
                            pr_number=pr_number, svc=svc,
                            risk_score=round(min(0.95, (adds + dels) / 900 + rnd.random() * 0.25), 2)))
        for path in touched:
            touches.append(dict(pr=pr_number, path=path, repo=f"acme/{svc}"))

    # ---- the cold-run root cause ---------------------------------------- #
    # A Storefront engineer changed a Payments-owned file. 23 minutes ago.
    cause_at = now - 23 * MINUTE
    prs.append(dict(id="pr-4471", number=4471,
                    title="perf(ledger-service): reuse pooled client in post-entry hot path",
                    merged_at=cause_at - 4 * MINUTE, additions=96, deletions=41,
                    author="Ben Ortiz"))
    deploys.append(dict(id="dep-cause", sha="9f2c41ab77de", at=cause_at, at_iso=iso(cause_at),
                        status="success", pr_number=4471, svc="ledger-service", risk_score=0.87))
    touches.append(dict(pr=4471, path="src/db/connection-pool.ts", repo="acme/ledger-service"))
    touches.append(dict(pr=4471, path="src/ledger/post-entry.ts", repo="acme/ledger-service"))

    # ---- the warm-run trigger -------------------------------------------- #
    # The warm scenario fires on notifications-api with the same failure
    # signature. It needs a real local change to point at, so the fast answer
    # is a complete one and not just a recalled lesson.
    warm_at = now - 14 * MINUTE
    prs.append(dict(id="pr-warm", number=4525,
                    title="perf(notifications-api): share pooled client across fanout workers",
                    merged_at=warm_at - 6 * MINUTE, additions=61, deletions=28,
                    author="Kofi Mensah"))
    deploys.append(dict(id="dep-warm", sha="c40b8e19ff23", at=warm_at, at_iso=iso(warm_at),
                        status="success", pr_number=4525, svc="notifications-api",
                        risk_score=0.72))
    touches.append(dict(pr=4525, path="src/db/pool.ts", repo="acme/notifications-api"))

    # three decoys in the same window, deliberately lower risk and off the
    # revenue-critical path, so ranking has to do real work
    for j, (svc, title, risk, mins) in enumerate([
        ("recommendation-api", "chore(recommendation-api): bump model artifact", 0.21, 11),
        ("status-page", "feat(status-page): add component history widget", 0.14, 47),
        ("catalog-api", "chore(catalog-api): regenerate openapi client", 0.33, 68),
    ]):
        next_pr()
        at = now - mins * MINUTE
        prs.append(dict(id=f"pr-{pr_number}", number=pr_number, title=title,
                        merged_at=at - 7 * MINUTE, additions=rnd.randint(5, 60),
                        deletions=rnd.randint(0, 30),
                        author=rnd.choice(team_members[svc_team[svc]])["name"]))
        deploys.append(dict(id=f"dep-decoy-{j}", sha=f"{rnd.getrandbits(80):020x}"[:12], at=at,
                            at_iso=iso(at), status="success", pr_number=pr_number, svc=svc,
                            risk_score=risk))
        touches.append(dict(pr=pr_number, path=by_service[svc][0], repo=f"acme/{svc}"))

    # PR numbers are the join key between Deploy and PullRequest, so a
    # collision silently fans out every SHIPS edge. Fail loudly instead.
    numbers = [p["number"] for p in prs]
    assert len(numbers) == len(set(numbers)), "duplicate PR numbers in seed"

    w("""UNWIND $rows AS r
         CREATE (:PullRequest {id:r.id, number:r.number, title:r.title,
                               merged_at:r.merged_at, additions:r.additions,
                               deletions:r.deletions})""", {"rows": prs})
    w("""UNWIND $rows AS r
         MATCH (pr:PullRequest {number:r.number}), (p:Person {name:r.author})
         CREATE (p)-[:AUTHORED]->(pr)""", {"rows": prs})
    w("""UNWIND $rows AS r
         CREATE (d:Deploy {id:r.id, sha:r.sha, at:r.at, at_iso:r.at_iso, status:r.status,
                           pr_number:r.pr_number, risk_score:r.risk_score})
         WITH d, r
         MATCH (s:Service {name:r.svc}) CREATE (d)-[:DEPLOYED_TO]->(s)
         WITH d, r
         MATCH (pr:PullRequest {number:r.pr_number}) CREATE (d)-[:SHIPS]->(pr)""",
      {"rows": deploys})
    w("""UNWIND $rows AS r
         MATCH (pr:PullRequest {number:r.pr}), (f:File {path:r.path, repo:r.repo})
         CREATE (pr)-[:TOUCHES]->(f)""", {"rows": touches})

    # ---- historical incidents + postmortems ------------------------------ #
    inc_rows, pm_rows, alert_rows, affected = [], [], [], []
    for n, h in enumerate(HISTORICAL):
        started = now - h["days_ago"] * DAY
        resolved = started + h["minutes"] * MINUTE
        inc_rows.append(dict(id=h["id"], title=h["title"], symptom=h["symptom"],
                             started_at=started, started_iso=iso(started),
                             resolved_at=resolved, severity=h["severity"], status="resolved",
                             service=h["service"], resolved_by=h["resolved_by"],
                             embedding=embed(h["title"] + " " + h["symptom"])))
        pm_rows.append(dict(id=f"PM-{h['id']}", incident=h["id"], lesson=h["lesson"],
                            created_at=resolved + 2 * HOUR, created_by=h["resolved_by"],
                            service=h["service"],
                            embedding=embed(h["title"] + " " + h["lesson"])))
        alert_rows.append(dict(id=f"ALRT-{h['id']}", metric="p99_latency_ms",
                               value=float(rnd.randint(1800, 6400)), threshold=1500.0,
                               fired_at=started - 2 * MINUTE, service=h["service"],
                               incident=h["id"]))
        affected.append(dict(incident=h["id"], service=h["service"]))
        # a couple of collateral services per incident, for realism
        for extra in rnd.sample(svc_names, k=2):
            if extra != h["service"]:
                affected.append(dict(incident=h["id"], service=extra))

    w("""UNWIND $rows AS r
         CREATE (:Incident {id:r.id, title:r.title, symptom:r.symptom,
                            started_at:r.started_at, started_iso:r.started_iso,
                            resolved_at:r.resolved_at, severity:r.severity,
                            status:r.status, embedding:vecf32(r.embedding)})""",
      {"rows": inc_rows})
    w("""UNWIND $rows AS r
         MATCH (i:Incident {id:r.id}), (p:Person {name:r.resolved_by})
         CREATE (i)-[:RESOLVED_BY]->(p)""", {"rows": inc_rows})
    w("""UNWIND $rows AS r
         MATCH (i:Incident {id:r.incident}), (s:Service {name:r.service})
         CREATE (i)-[:AFFECTED]->(s)""", {"rows": affected})
    w("""UNWIND $rows AS r
         CREATE (a:Alert {id:r.id, metric:r.metric, value:r.value, threshold:r.threshold,
                          fired_at:r.fired_at})
         WITH a, r MATCH (s:Service {name:r.service}) CREATE (a)-[:FIRED_ON]->(s)
         WITH a, r MATCH (i:Incident {id:r.incident}) CREATE (i)-[:TRIGGERED_BY]->(a)""",
      {"rows": alert_rows})
    w("""UNWIND $rows AS r
         CREATE (pm:Postmortem {id:r.id, lesson:r.lesson, created_at:r.created_at,
                                created_by:r.created_by, embedding:vecf32(r.embedding)})
         WITH pm, r MATCH (i:Incident {id:r.incident}) CREATE (i)-[:PRODUCED]->(pm)
         WITH pm, r MATCH (s:Service {name:r.service}) CREATE (pm)-[:APPLIES_TO]->(s)""",
      {"rows": pm_rows})

    # link the prior pool incident to the file it lived in, so who_knows can
    # rank by "has resolved an incident on this file before"
    w("""MATCH (i:Incident {id:'INC-2041'}), (f:File {path:'src/db/connection-pool.ts',
                                                      repo:'acme/ledger-service'})
         CREATE (i)-[:IMPLICATED]->(f)""")

    # ---- runbooks -------------------------------------------------------- #
    runbooks = []
    for i, (title, svc, body) in enumerate(RUNBOOK_SEEDS):
        runbooks.append(dict(id=f"rb-{i:03d}", title=f"{title} -- {svc}", body=body, svc=svc,
                             embedding=embed(title + " " + body)))
    i = len(RUNBOOK_SEEDS)
    for svc in svc_names:
        for kind, body in [
            ("Elevated error rate",
             f"Check the {svc} deploy history first. If a deploy landed in the last 30 minutes, "
             f"roll it back before investigating further. Then check downstream dependency "
             f"health and saturation of any shared pool."),
            ("Restart procedure",
             f"Restart {svc} rolling, one replica at a time, waiting for readiness. Never "
             f"restart all replicas: in-flight requests will fail and upstreams will retry, "
             f"amplifying load."),
        ]:
            if i >= 40:
                break
            runbooks.append(dict(id=f"rb-{i:03d}", title=f"{kind} -- {svc}", body=body, svc=svc,
                                 embedding=embed(kind + " " + svc + " " + body)))
            i += 1
        if i >= 40:
            break
    w("""UNWIND $rows AS r
         CREATE (rb:Runbook {id:r.id, title:r.title, body:r.body,
                             embedding:vecf32(r.embedding)})
         WITH rb, r MATCH (s:Service {name:r.svc}) CREATE (rb)-[:COVERS]->(s)""",
      {"rows": runbooks})

    # ---- messages -------------------------------------------------------- #
    channels = ["#incidents", "#eng-general", "#payments", "#storefront", "#sre", "#deploys"]
    messages = []
    for i in range(600):
        svc = rnd.choice(svc_names)
        text = rnd.choice(MSG_TEMPLATES).format(svc=svc, pr=rnd.randint(4200, 4520))
        at = now - rnd.randint(1 * HOUR, 30 * DAY)
        messages.append(dict(id=f"msg-{i:04d}", channel=rnd.choice(channels), text=text,
                             at=at, at_iso=iso(at),
                             author=rnd.choice(people)["name"],
                             embedding=embed(text),
                             incident=rnd.choice(HISTORICAL)["id"] if rnd.random() < 0.18 else None))
    w("""UNWIND $rows AS r
         CREATE (m:Message {id:r.id, channel:r.channel, text:r.text, at:r.at,
                            at_iso:r.at_iso, author:r.author,
                            embedding:vecf32(r.embedding)})""", {"rows": messages})
    w("""UNWIND [m IN $rows WHERE m.incident IS NOT NULL] AS r
         MATCH (m:Message {id:r.id}), (i:Incident {id:r.incident})
         CREATE (m)-[:ABOUT]->(i)""", {"rows": messages})

    # ---- decisions ------------------------------------------------------- #
    decisions = [dict(id=f"adr-{i:03d}", title=t, rationale=rat, svc=svc, person=who,
                      at=now - rnd.randint(40, 400) * DAY)
                 for i, (t, svc, who, rat) in enumerate(DECISIONS)]
    w("""UNWIND $rows AS r
         CREATE (d:Decision {id:r.id, title:r.title, rationale:r.rationale, at:r.at})
         WITH d, r MATCH (s:Service {name:r.svc}) CREATE (d)-[:CONCERNS]->(s)
         WITH d, r MATCH (p:Person {name:r.person}) CREATE (d)-[:MADE_BY]->(p)""",
      {"rows": decisions})

    stats = counts(tenant)
    if verbose:
        print(f"[seed] tenant:{tenant} seeded -> {stats}")
    return stats


# --------------------------------------------------------------------------- #
def seed_globex(tenant: str = "globex", verbose: bool = True) -> dict:
    """A smaller, completely different company in its own graph.

    Same generator shape, different domain. The point is isolation: a query
    against tenant:acme cannot see any of this.
    """
    rnd = random.Random(7)
    now = int(time.time() * 1000)
    g = db.graph(tenant)

    def w(c, p=None):
        return g.query(c, p or {})

    services = [dict(id=f"svc-{i:03d}", name=n, tier=m[0], revenue_critical=m[1],
                     customer_facing=m[2], language=m[3], description=m[4],
                     repo=f"globex/{n}")
                for i, (n, m) in enumerate(topo.GLOBEX_SERVICES.items())]
    w("""UNWIND $rows AS r
         CREATE (:Service {id:r.id, name:r.name, tier:r.tier, language:r.language,
                           repo:r.repo, description:r.description,
                           revenue_critical:r.revenue_critical,
                           customer_facing:r.customer_facing})""", {"rows": services})

    deps = [dict(src=c, dst=p, criticality=cr, protocol=pr, cost=float(6 - cr))
            for c, provs in topo.GLOBEX_DEPENDS_ON.items() for p, cr, pr in provs]
    w("""UNWIND $rows AS r
         MATCH (a:Service {name:r.src}), (b:Service {name:r.dst})
         CREATE (a)-[:DEPENDS_ON {criticality:r.criticality, protocol:r.protocol, cost:r.cost}]->(b)
         CREATE (b)-[:IMPACTS {criticality:r.criticality, protocol:r.protocol, cost:r.cost}]->(a)""",
      {"rows": deps})

    w("UNWIND $rows AS r CREATE (:Team {id:r.id, name:r.name})",
      {"rows": [dict(id=f"team-{i}", name=n) for i, n in enumerate(topo.GLOBEX_TEAMS)]})
    people = [dict(id=f"p-{i:02d}", name=n, handle=h, role=role, timezone=tz, team=team,
                   on_call=oc)
              for i, (n, h, role, tz, team, oc) in enumerate(topo.GLOBEX_PEOPLE)]
    w("""UNWIND $rows AS r
         CREATE (:Person {id:r.id, name:r.name, handle:r.handle, role:r.role,
                          timezone:r.timezone, on_call:r.on_call})""", {"rows": people})
    w("""UNWIND $rows AS r MATCH (p:Person {id:r.id}), (t:Team {name:r.team})
         CREATE (p)-[:MEMBER_OF]->(t)""", {"rows": people})
    w("""UNWIND $rows AS r MATCH (s:Service {name:r.svc}), (t:Team {name:r.team})
         CREATE (s)-[:OWNED_BY]->(t)""",
      {"rows": [dict(svc=s, team=t) for t, ss in topo.GLOBEX_TEAMS.items() for s in ss]})

    svc_team = {s: t for t, ss in topo.GLOBEX_TEAMS.items() for s in ss}
    team_members: dict[str, list[dict]] = {}
    for p in people:
        team_members.setdefault(p["team"], []).append(p)

    files, fid, by_service = [], 0, {}
    for n, m in topo.GLOBEX_SERVICES.items():
        ext = topo.EXT.get(m[3], ".ts")
        paths = [b + ext for b in rnd.sample(topo.GENERIC_FILES, k=3)]
        by_service[n] = paths
        for path in paths:
            fid += 1
            files.append(dict(id=f"file-{fid:04d}", path=path, repo=f"globex/{n}", svc=n))
    w("""UNWIND $rows AS r
         CREATE (f:File {id:r.id, path:r.path, repo:r.repo})
         WITH f, r MATCH (s:Service {name:r.svc}) CREATE (f)-[:BELONGS_TO]->(s)""",
      {"rows": files})
    w("""UNWIND $rows AS r
         MATCH (p:Person {name:r.person}), (f:File {path:r.path, repo:r.repo})
         CREATE (p)-[:WORKED_ON {commits:r.commits, last_at:r.last_at}]->(f)""",
      {"rows": [dict(person=rnd.choice(team_members[svc_team[f["svc"]]])["name"],
                     path=f["path"], repo=f["repo"], commits=rnd.randint(1, 30),
                     last_at=now - rnd.randint(1, 60) * DAY) for f in files]})

    prs, deploys = [], []
    num = 880
    for i in range(70):
        svc = rnd.choice(list(topo.GLOBEX_SERVICES))
        num += 1
        at = now - rnd.randint(10 * MINUTE, 30 * DAY)
        prs.append(dict(id=f"pr-{num}", number=num, title=f"fix({svc}): tune retry budget",
                        merged_at=at - 20 * MINUTE, additions=rnd.randint(5, 200),
                        deletions=rnd.randint(0, 90),
                        author=rnd.choice(team_members[svc_team[svc]])["name"]))
        deploys.append(dict(id=f"dep-{i:04d}", sha=f"{rnd.getrandbits(80):020x}"[:12], at=at,
                            at_iso=iso(at), status="success", pr_number=num, svc=svc,
                            risk_score=round(rnd.random(), 2)))
    w("""UNWIND $rows AS r
         CREATE (:PullRequest {id:r.id, number:r.number, title:r.title, merged_at:r.merged_at,
                               additions:r.additions, deletions:r.deletions})""", {"rows": prs})
    w("""UNWIND $rows AS r MATCH (pr:PullRequest {number:r.number}), (p:Person {name:r.author})
         CREATE (p)-[:AUTHORED]->(pr)""", {"rows": prs})
    w("""UNWIND $rows AS r
         CREATE (d:Deploy {id:r.id, sha:r.sha, at:r.at, at_iso:r.at_iso, status:r.status,
                           pr_number:r.pr_number, risk_score:r.risk_score})
         WITH d, r MATCH (s:Service {name:r.svc}) CREATE (d)-[:DEPLOYED_TO]->(s)
         WITH d, r MATCH (pr:PullRequest {number:r.pr_number}) CREATE (d)-[:SHIPS]->(pr)""",
      {"rows": deploys})

    gx_inc = [
        ("INC-9001", 12, "SEV2", "dispatch-engine",
         "dispatch-engine assignment latency spiked during morning surge",
         "dispatch-engine p99 assignment latency 5200ms, driver app timeouts, surge traffic",
         "Oksana Petrenko",
         "Assignment ran an O(n^2) scan per load. Spatial index on the driver grid fixed it."),
        ("INC-9002", 20, "SEV1", "cockroach-primary",
         "cockroach-primary hot range throttled freight bookings",
         "cockroach-primary hot range on invoice sequence, write latency 3000ms, booking failures",
         "Raul Jimenez",
         "A monotonic invoice sequence created a single hot range. Hash-sharded the index."),
        ("INC-9003", 6, "SEV3", "eta-predictor",
         "eta-predictor stale model degraded arrival estimates",
         "eta-predictor serving a 9-day-old model artifact, ETA error above threshold",
         "Thabo Nkosi",
         "The model promotion job failed silently. Artifact freshness is now alerted."),
    ]
    inc_rows, pm_rows = [], []
    for iid, days, sev, svc, title, sym, who, lesson in gx_inc:
        st = now - days * DAY
        inc_rows.append(dict(id=iid, title=title, symptom=sym, started_at=st, started_iso=iso(st),
                             resolved_at=st + 40 * MINUTE, severity=sev, status="resolved",
                             service=svc, resolved_by=who, embedding=embed(title + " " + sym)))
        pm_rows.append(dict(id=f"PM-{iid}", incident=iid, lesson=lesson,
                            created_at=st + 3 * HOUR, created_by=who, service=svc,
                            embedding=embed(title + " " + lesson)))
    w("""UNWIND $rows AS r
         CREATE (:Incident {id:r.id, title:r.title, symptom:r.symptom, started_at:r.started_at,
                            started_iso:r.started_iso, resolved_at:r.resolved_at,
                            severity:r.severity, status:r.status,
                            embedding:vecf32(r.embedding)})""", {"rows": inc_rows})
    w("""UNWIND $rows AS r MATCH (i:Incident {id:r.id}), (p:Person {name:r.resolved_by})
         CREATE (i)-[:RESOLVED_BY]->(p)""", {"rows": inc_rows})
    w("""UNWIND $rows AS r MATCH (i:Incident {id:r.id}), (s:Service {name:r.service})
         CREATE (i)-[:AFFECTED]->(s)""", {"rows": inc_rows})
    w("""UNWIND $rows AS r
         CREATE (pm:Postmortem {id:r.id, lesson:r.lesson, created_at:r.created_at,
                                created_by:r.created_by, embedding:vecf32(r.embedding)})
         WITH pm, r MATCH (i:Incident {id:r.incident}) CREATE (i)-[:PRODUCED]->(pm)
         WITH pm, r MATCH (s:Service {name:r.service}) CREATE (pm)-[:APPLIES_TO]->(s)""",
      {"rows": pm_rows})

    rbs = [dict(id=f"rb-{i:03d}", title=f"Elevated error rate -- {s}", svc=s,
                body=f"Check the {s} deploy history, then dependency saturation. Roll back any "
                     f"deploy from the last 30 minutes before deeper investigation.",
                embedding=embed(f"elevated error rate {s}"))
           for i, s in enumerate(topo.GLOBEX_SERVICES)]
    w("""UNWIND $rows AS r
         CREATE (rb:Runbook {id:r.id, title:r.title, body:r.body, embedding:vecf32(r.embedding)})
         WITH rb, r MATCH (s:Service {name:r.svc}) CREATE (rb)-[:COVERS]->(s)""", {"rows": rbs})

    msgs = [dict(id=f"msg-{i:04d}", channel="#ops", at=now - rnd.randint(1, 20) * DAY,
                 text=f"{rnd.choice(list(topo.GLOBEX_SERVICES))} canary looks green",
                 author=rnd.choice(people)["name"])
            for i in range(80)]
    for m in msgs:
        m["at_iso"] = iso(m["at"])
        m["embedding"] = embed(m["text"])
    w("""UNWIND $rows AS r
         CREATE (:Message {id:r.id, channel:r.channel, text:r.text, at:r.at, at_iso:r.at_iso,
                           author:r.author, embedding:vecf32(r.embedding)})""", {"rows": msgs})

    stats = counts(tenant)
    if verbose:
        print(f"[seed] tenant:{tenant} seeded -> {stats}")
    return stats


# --------------------------------------------------------------------------- #
def counts(tenant: str) -> dict:
    out = {}
    for label in ["Service", "Person", "Team", "File", "Deploy", "PullRequest", "Incident",
                  "Postmortem", "Runbook", "Message", "Decision", "Alert", "AgentStep"]:
        rows, _ = db.run(tenant, f"MATCH (n:{label}) RETURN count(n)")
        out[label] = rows[0][0] if rows else 0
    rows, _ = db.run(tenant, "MATCH ()-[r]->() RETURN count(r)")
    out["relationships"] = rows[0][0] if rows else 0
    return out


def build(tenant: str, verbose: bool = True) -> dict:
    db.drop(tenant)
    schema.apply(tenant)
    if tenant == "globex":
        return seed_globex(tenant, verbose)
    return seed_acme(tenant, verbose)


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed the BLACKBOX graph.")
    ap.add_argument("--tenant", default=None)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    targets = config.TENANTS if args.all or not args.tenant else [args.tenant]
    t0 = time.perf_counter()
    for t in targets:
        build(t)
    print(f"[seed] done in {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
