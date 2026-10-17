"""LLM adapter.

Two brains behind one interface:

  * `AnthropicBrain` -- a real tool-calling loop against the Messages API.
    Used whenever ANTHROPIC_API_KEY is set.
  * `DeterministicBrain` -- a rule-based policy over the same nine tools,
    used when there is no key.

The second one exists because a live demo cannot depend on a network call, and
because every graph claim in this project comes from the graph rather than from
the model. The model chooses which traversal to run and writes the prose; the
findings are the database's. That means the deterministic brain reaches the
same root cause by the same tool calls -- it just does not narrate as well.

Which brain ran is reported in the run's `mode` field and shown in the UI. It
is never implied that a model ran when one did not.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from . import config

# The build plan named claude-sonnet-4-5; that id is retired, so the default
# is the current Opus. Override with BLACKBOX_MODEL.
DEFAULT_MODEL = "claude-opus-5-5"


@dataclass
class Turn:
    """One model turn, normalized across brains."""
    text: str = ""
    thinking: str = ""
    tool_calls: list[dict] = field(default_factory=list)   # {id, name, input}
    stop_reason: str = "end_turn"


def model_name() -> str:
    name = os.getenv("BLACKBOX_MODEL", "").strip() or config.MODEL
    # the plan's placeholder, mapped forward
    if name in ("claude-sonnet-4-5", ""):
        return DEFAULT_MODEL
    return name


def api_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "").strip()


def available() -> bool:
    if not api_key():
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def mode_name() -> str:
    return model_name() if available() else "deterministic-planner"


class AnthropicBrain:
    """Manual tool-use loop.

    Manual rather than the SDK tool runner because every tool call has to be
    surfaced as an SSE event, timed, and written to the graph as an
    :AgentStep before the result goes back to the model. The runner does not
    expose that seam.
    """

    def __init__(self, model: str | None = None):
        import anthropic

        self.model = model or model_name()
        self.client = anthropic.Anthropic(api_key=api_key())

    def probe(self) -> None:
        """Cheapest possible call, to fail fast on a bad key or no network."""
        import anthropic

        try:
            self.client.messages.create(
                model=self.model, max_tokens=1,
                messages=[{"role": "user", "content": "ok"}],
            )
        except anthropic.APIStatusError as exc:
            raise RuntimeError(f"HTTP {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise RuntimeError(f"connection failed: {exc}") from exc

    def turn(self, system: str, messages: list[dict], tools: list[dict]) -> Turn:
        import anthropic

        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                system=system,
                messages=messages,
                tools=[{**t, "strict": True} for t in tools],
                # tool_choice stays auto: forcing a call is a 400 on current models
                thinking={"type": "adaptive", "display": "summarized"},
                output_config={"effort": "medium"},
            )
        except anthropic.APIStatusError as exc:
            raise RuntimeError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise RuntimeError(f"Anthropic connection error: {exc}") from exc

        out = Turn(stop_reason=resp.stop_reason or "end_turn")
        for block in resp.content:
            if block.type == "text":
                out.text += block.text
            elif block.type == "thinking":
                out.thinking += getattr(block, "thinking", "") or ""
            elif block.type == "tool_use":
                out.tool_calls.append({"id": block.id, "name": block.name,
                                       "input": dict(block.input or {})})
        self._last_content = resp.content
        return out

    @property
    def last_content(self):
        return getattr(self, "_last_content", [])


# --------------------------------------------------------------------------- #
def tool_schemas(names: list[str]) -> list[dict]:
    """JSON schemas for the tools an agent is allowed to call.

    Deliberately narrow: the model picks a tool and a couple of scalars. It
    never sees Cypher and never sees a free-text query field that could
    smuggle one in.
    """
    all_schemas = {
        "resolve_entity": {
            "name": "resolve_entity",
            "description": (
                "Resolve a free-text alert or symptom string to a concrete node in the "
                "service graph. Always call this first so later tools have a real service "
                "name to work from."),
            "input_schema": {
                "type": "object", "additionalProperties": False,
                "properties": {"text": {"type": "string",
                                        "description": "The alert text or symptom description."}},
                "required": ["text"],
            },
        },
        "affected_services": {
            "name": "affected_services",
            "description": (
                "Everything that degrades if this service degrades, by dependency depth. "
                "Returns the impacted services with hop counts, which of them are "
                "customer-facing, and which are revenue-critical. Use this to size the "
                "incident before investigating its cause."),
            "input_schema": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "service": {"type": "string"},
                    "max_depth": {"type": "integer", "minimum": 1, "maximum": 6,
                                  "description": "Dependency hops to walk. 4 is usually right."},
                },
                "required": ["service"],
            },
        },
        "recent_changes": {
            "name": "recent_changes",
            "description": (
                "Deploys that landed near this service recently, including on services it "
                "depends on up to `hops` away. The cause of an incident is usually NOT on "
                "the service that alerted, so use hops=2 or more. Results are ranked by "
                "risk score."),
            "input_schema": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "service": {"type": "string"},
                    "window_minutes": {"type": "integer", "minimum": 5, "maximum": 1440},
                    "hops": {"type": "integer", "minimum": 1, "maximum": 4},
                },
                "required": ["service"],
            },
        },
        "causal_path": {
            "name": "causal_path",
            "description": (
                "The dependency chain linking two services, weighted by how hard each "
                "dependency is. Use this to prove how a failure in one service reaches "
                "another, rather than asserting it."),
            "input_schema": {
                "type": "object", "additionalProperties": False,
                "properties": {"from_service": {"type": "string"},
                               "to_service": {"type": "string"}},
                "required": ["from_service", "to_service"],
            },
        },
        "similar_incidents": {
            "name": "similar_incidents",
            "description": (
                "Semantic search over past incidents AND the postmortems written about "
                "them, including postmortems BLACKBOX wrote itself on earlier runs. Call "
                "this early: if this failure has been seen before, the lesson already "
                "names the cause and the fix and you can skip most of the investigation."),
            "input_schema": {
                "type": "object", "additionalProperties": False,
                "properties": {"symptom_text": {"type": "string"},
                               "k": {"type": "integer", "minimum": 1, "maximum": 10}},
                "required": ["symptom_text"],
            },
        },
        "who_knows": {
            "name": "who_knows",
            "description": (
                "Who actually knows this service or file, ranked by commits on it and "
                "incidents they have resolved on it. Also returns the on-call default so "
                "you can say when the right person is not the one the rotation would page."),
            "input_schema": {
                "type": "object", "additionalProperties": False,
                "properties": {"service_or_file": {"type": "string",
                                                   "description": "A service name or a file path."}},
                "required": ["service_or_file"],
            },
        },
        "get_runbook": {
            "name": "get_runbook",
            "description": "The operational runbook that applies to this service and symptom.",
            "input_schema": {
                "type": "object", "additionalProperties": False,
                "properties": {"service": {"type": "string"}, "symptom": {"type": "string"}},
                "required": ["service"],
            },
        },
        "criticality_rank": {
            "name": "criticality_rank",
            "description": (
                "PageRank over the dependency graph: which services the rest of the system "
                "structurally leans on. Use to prioritise when several things look broken."),
            "input_schema": {
                "type": "object", "additionalProperties": False,
                "properties": {"top": {"type": "integer", "minimum": 1, "maximum": 42}},
                "required": [],
            },
        },
        "write_finding": {
            "name": "write_finding",
            "description": (
                "Write what you learned back into the graph. kind='root_cause' links the "
                "incident to the deploy that caused it; kind='postmortem' stores the lesson "
                "so a future incident with this signature retrieves it; kind='resolution' "
                "closes the incident against a person. You MUST call this before finishing "
                "-- at minimum a postmortem. Make the lesson specific: name the failure "
                "mode, the file, and the fix, so it is useful to a future run that has only "
                "this text to go on."),
            "input_schema": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "kind": {"type": "string", "enum": ["root_cause", "postmortem", "resolution"]},
                    "pr_number": {"type": "integer"},
                    "deploy_id": {"type": "string"},
                    "lesson": {"type": "string"},
                    "service": {"type": "string"},
                    "person": {"type": "string"},
                },
                "required": ["kind"],
            },
        },
    }
    return [all_schemas[n] for n in names if n in all_schemas]


def compact(obj: Any, limit: int = 3000) -> str:
    """Tool results go back to the model as JSON, trimmed."""
    text = json.dumps(obj, default=str)
    if len(text) <= limit:
        return text
    return text[:limit] + f'... [truncated, {len(text)} chars total]'
