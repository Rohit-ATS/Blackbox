"""Central configuration. Everything reads from here."""
import os

FALKOR_HOST = os.getenv("FALKOR_HOST", "localhost")
FALKOR_PORT = int(os.getenv("FALKOR_PORT", "6379"))

DEFAULT_TENANT = os.getenv("BLACKBOX_TENANT", "acme")
TENANTS = ["acme", "globex"]

EMBED_DIM = 384

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
MODEL = os.getenv("BLACKBOX_MODEL", "claude-sonnet-4-6")

SEED = 42


def graph_key(tenant: str) -> str:
    return f"tenant:{tenant}"
