"""FalkorDB access layer.

One graph per tenant -- `tenant:acme`, `tenant:globex` -- on a single FalkorDB
instance. That is FalkorDB's multigraph tenancy and it is the whole isolation
story: a query against one graph cannot see another's data.
"""
from __future__ import annotations

import time
from typing import Any

from falkordb import FalkorDB

from . import config

_client: FalkorDB | None = None


def client() -> FalkorDB:
    global _client
    if _client is None:
        _client = FalkorDB(host=config.FALKOR_HOST, port=config.FALKOR_PORT)
    return _client


def graph(tenant: str = config.DEFAULT_TENANT):
    return client().select_graph(config.graph_key(tenant))


def run(tenant: str, cypher: str, params: dict[str, Any] | None = None):
    """Run a parameterized query. Returns (rows, latency_ms)."""
    g = graph(tenant)
    t0 = time.perf_counter()
    res = g.query(cypher, params or {})
    latency_ms = round((time.perf_counter() - t0) * 1000, 3)
    return res.result_set, latency_ms


def run_rw(tenant: str, cypher: str, params: dict[str, Any] | None = None):
    """Write query. Returns (result, latency_ms)."""
    g = graph(tenant)
    t0 = time.perf_counter()
    res = g.query(cypher, params or {})
    return res, round((time.perf_counter() - t0) * 1000, 3)


def drop(tenant: str) -> None:
    try:
        graph(tenant).delete()
    except Exception:
        pass


def node_props(node) -> dict[str, Any]:
    """falkordb Node -> plain dict, embeddings stripped (they are huge)."""
    props = dict(getattr(node, "properties", {}) or {})
    props.pop("embedding", None)
    labels = getattr(node, "labels", None) or []
    if isinstance(labels, str):
        labels = [labels]
    props["_label"] = labels[0] if labels else None
    return props
