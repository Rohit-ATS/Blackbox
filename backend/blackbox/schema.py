"""Index definitions. Applied at seed time, idempotent."""
from __future__ import annotations

from . import db
from .config import EMBED_DIM

RANGE_INDEXES = [
    "CREATE INDEX FOR (s:Service) ON (s.name)",
    "CREATE INDEX FOR (s:Service) ON (s.id)",
    "CREATE INDEX FOR (d:Deploy) ON (d.at)",
    "CREATE INDEX FOR (i:Incident) ON (i.started_at)",
    "CREATE INDEX FOR (f:File) ON (f.path)",
    "CREATE INDEX FOR (p:Person) ON (p.name)",
    "CREATE INDEX FOR (pr:PullRequest) ON (pr.number)",
    "CREATE INDEX FOR (a:AgentStep) ON (a.incident_id)",
]

FULLTEXT_INDEXES = [
    "CALL db.idx.fulltext.createNodeIndex('Service', 'name', 'description')",
    "CALL db.idx.fulltext.createNodeIndex('Runbook', 'title', 'body')",
    "CALL db.idx.fulltext.createNodeIndex('Message', 'text')",
    "CALL db.idx.fulltext.createNodeIndex('File', 'path')",
]

VECTOR_INDEXES = [
    f"CREATE VECTOR INDEX FOR (i:Incident) ON (i.embedding) "
    f"OPTIONS {{dimension:{EMBED_DIM}, similarityFunction:'cosine'}}",
    f"CREATE VECTOR INDEX FOR (p:Postmortem) ON (p.embedding) "
    f"OPTIONS {{dimension:{EMBED_DIM}, similarityFunction:'cosine'}}",
    f"CREATE VECTOR INDEX FOR (r:Runbook) ON (r.embedding) "
    f"OPTIONS {{dimension:{EMBED_DIM}, similarityFunction:'cosine'}}",
]

ALL = RANGE_INDEXES + FULLTEXT_INDEXES + VECTOR_INDEXES


def apply(tenant: str) -> list[str]:
    """Create every index. Already-exists errors are swallowed."""
    applied = []
    for stmt in ALL:
        try:
            db.run_rw(tenant, stmt)
            applied.append(stmt)
        except Exception as exc:
            if "already" not in str(exc).lower():
                raise
    return applied


def describe(tenant: str) -> list[dict]:
    rows, _ = db.run(tenant, "CALL db.indexes()")
    out = []
    for r in rows:
        out.append({"label": r[0], "properties": r[1], "types": str(r[2])})
    return out
