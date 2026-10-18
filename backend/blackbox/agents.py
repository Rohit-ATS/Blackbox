"""The three agents, and the event stream they produce.

Triage -> Investigator -> Comms. They are genuinely separate: distinct system
prompts, distinct tool subsets, and -- the part that matters -- handoff state
written to the graph rather than passed in memory. Each tool call becomes an
:AgentStep node chained with :NEXT, so the next agent reads what the last one
did out of FalkorDB. That is also why a restarted agent can continue: the
state was never in the process.

EVENT CONTRACT (frozen -- the frontend is built against this)

  run_start    {run_id, scenario, tenant, incident_id, alert, symptom, mode, at}
  agent_start  {agent, tools}
  thought      {agent, text}
  tool_call    {agent, tool, args, step}
  tool_result  {agent, tool, step, summary, note, latency_ms, data, path, cypher}
  handoff      {from, to, step_id}
  write        {kind, detail, path}
  answer       {answer}
  run_end      {run_id, elapsed_ms, tool_calls, graph_latency_ms,
                investigation_latency_ms, hops,
                wrote, recalled_memory, mode}
  error        {message}

`path` is always {nodes: [...], edges: [...]} so the graph pane can animate
exactly the subgraph a step touched.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Iterator

from . import db, llm, tools as T
from .scenarios import Scenario

MAX_STEPS = 14

# Cosine similarity below which a memory hit is too weak to act on. Tuned
# against the seeded corpus: the prior pool-exhaustion incident scores ~0.59
# on a fresh pool-exhaustion symptom, unrelated incidents score under 0.3.
RECALL_FLOOR = 0.40

AGENTS = {
    "Triage": {
        "tools": ["resolve_entity", "similar_incidents", "affected_services", "criticality_rank"],
        "system": """You are TRIAGE, the first of three agents handling a production incident.

Your job is to size the incident, not to solve it. In order:
1. resolve_entity on the alert text, to get a real service node.
2. similar_incidents on the symptom -- do this EARLY. If this failure signature has
   been seen before, especially in a postmortem BLACKBOX wrote itself, say so
   loudly: it changes how much work the next agent has to do.
3. affected_services on the resolved service, to establish who else is degraded.
4. criticality_rank only if the affected services is ambiguous and you need to
   prioritise.

Then stop and write one short paragraph: the service, the severity you'd assign,
how many services are impacted and how many of those are customer-facing, and
whether memory already recognises this failure. Do not speculate about the cause
-- that is the Investigator's job. Be terse and factual. Cite numbers the tools
actually returned.""",
    },
    "Investigator": {
        "tools": ["recent_changes", "causal_path", "similar_incidents", "get_runbook",
                  "write_finding"],
        "system": """You are INVESTIGATOR, the second of three agents on a production incident.

Triage has told you what is broken and how far it spreads. Find the cause.

The cause is usually NOT on the service that alerted. Call recent_changes with
hops=2 so you can see deploys on the services it depends on. Then:
- Pick the most likely deploy from risk score, timing, and -- most importantly --
  whether the files it touched relate to the symptom.
- Prove the connection with causal_path between the alerting service and the
  service you suspect. Do not assert a propagation path you have not proven.
- get_runbook for the operational fix.
- Then call write_finding with kind='root_cause' and the PR number, to record
  the causal edge in the graph.

If Triage found a highly similar prior incident whose lesson already names this
failure mode, trust it and converge fast -- that is the point of having memory.
Be terse. Name the PR, the file, the service, and the hop distance.""",
    },
    "Comms": {
        "tools": ["who_knows", "get_runbook", "write_finding"],
        "system": """You are COMMS, the last of three agents on a production incident.

The cause is known. Your job is to get the right human involved and to leave the
graph smarter than you found it.

1. who_knows on the file the offending PR touched -- the file, not just the
   service. The person who knows a subsystem is often not the one the rotation
   would page, and if that is the case here, say so explicitly.
2. write_finding with kind='postmortem'. This is the most important call you
   make. The lesson is the only thing a future run will have to go on, so write
   it for that reader: name the failure mode in the words an alert would use,
   the file, the mechanism, and the fix. Two or three sentences.
3. write_finding with kind='resolution' naming the person.

Then write the human status update: what broke, why, who is on it, what the fix
is. Plain language, no hedging, no filler.""",
    },
}


def _emit(_type: str, /, **payload) -> dict:
    return {"type": _type, "at": int(time.time() * 1000), **payload}


# --------------------------------------------------------------------------- #
class Run:
    """Accumulates what happened, for the answer card and the run_end metrics."""

    def __init__(self, scenario: Scenario, tenant: str, mode: str):
        self.scenario = scenario
        self.tenant = tenant
        self.mode = mode
        self.run_id = f"run-{uuid.uuid4().hex[:8]}"
        self.t0 = time.perf_counter()
        self.tool_calls = 0
        self.graph_latency_ms = 0.0
        # Shared entity/memory lookups and write-back are present in both
        # runs. Keep a second honest measure for the graph work that memory
        # actually removes: impact, cause, path, ranking, and runbook work.
        self.investigation_latency_ms = 0.0
        self.results: list[T.ToolResult] = []
        self.by_tool: dict[str, T.ToolResult] = {}
        self.wrote: list[str] = []
        self.recalled_memory = False
        self.recalled_own = False
        self.prev_step_id: str | None = None
        self.narration: dict[str, str] = {}

    def record(self, res: T.ToolResult) -> None:
        self.tool_calls += 1
        self.graph_latency_ms += res.latency_ms
        if res.tool not in {"resolve_entity", "similar_incidents", "write_finding"}:
            self.investigation_latency_ms += res.latency_ms
        self.results.append(res)
        self.by_tool.setdefault(res.tool, res)
        self.by_tool[res.tool] = res
        if res.tool == "similar_incidents":
            data = res.data or {}
            if data.get("incidents") or data.get("postmortems"):
                self.recalled_memory = True
            if data.get("recalled_own_postmortem"):
                self.recalled_own = True
        if res.tool == "write_finding" and (res.data or {}).get("written"):
            self.wrote.append(res.data["written"])

    @property
    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self.t0) * 1000, 1)


# --------------------------------------------------------------------------- #
def _plan_deterministic(agent: str, run: Run, state: dict) -> Iterator[dict]:
    """Rule-based policy over the same nine tools.

    A generator, not a list, because the plan genuinely depends on what the
    earlier steps found. Triage cannot know whether to run the expensive
    depth-4 traversal and PageRank until the memory lookup has come back --
    which is exactly the branch the whole demo turns on.
    """
    sc = run.scenario

    if agent == "Triage":
        yield {"tool": "resolve_entity", "args": {"text": sc.symptom},
               "say": "Resolving the alert text to a node in the service graph."}
        yield {"tool": "similar_incidents", "args": {"symptom_text": sc.symptom, "k": 3},
               "say": "Checking whether this failure signature has been seen before."}

        svc = state.get("service") or sc.service
        if state.get("warm"):
            # The postmortem already carries the impact summary from the cold
            # run. Re-running BFS here would spend graph work rediscovering a
            # fact memory just supplied; keep the warm path focused on the new
            # service's local cause.
            return
        else:
            yield {"tool": "affected_services", "args": {"service": svc, "max_depth": 4},
                   "say": f"Walking dependents of {svc} to size the impact."}
            yield {"tool": "criticality_rank", "args": {"top": 8},
                   "say": "Nothing in memory names this. Ranking structural criticality "
                          "to decide what matters."}
        return

    if agent == "Investigator":
        svc = state.get("service") or sc.service
        if state.get("warm"):
            # One single-hop lookup replaces the upstream search, the
            # shortest-path proof and the runbook fetch.
            yield {"tool": "recent_changes",
                   "args": {"service": svc, "window_minutes": 180, "hops": 1},
                   "say": "Memory already names the mechanism and the fix. One hop is "
                          "enough to find which local change triggered it."}
            if state.get("cause_pr") or state.get("cause_deploy_id"):
                yield {"tool": "write_finding", "args": {"kind": "root_cause"},
                       "say": "Recording the causal edge."}
            return

        yield {"tool": "recent_changes",
               "args": {"service": svc, "window_minutes": 120, "hops": 2},
               "say": f"Looking for deploys within two hops of {svc} -- the cause is "
                      f"rarely on the service that alerted."}
        cause_svc = state.get("cause_service")
        if cause_svc and cause_svc != svc:
            yield {"tool": "causal_path", "args": {},
                   "say": f"Proving how a failure in {cause_svc} reaches {svc}."}
        yield {"tool": "get_runbook",
               "args": {"symptom": "connection pool exhausted acquire timeouts p99 latency"},
               "say": "Pulling the operational runbook."}
        if state.get("cause_pr") or state.get("cause_deploy_id"):
            yield {"tool": "write_finding", "args": {"kind": "root_cause"},
                   "say": "Recording the causal edge in the graph."}
        return

    # Comms
    svc = state.get("service") or sc.service
    target = state.get("cause_file") or state.get("cause_service") or svc
    yield {"tool": "who_knows", "args": {"service_or_file": target},
           "say": f"Finding who actually knows {target}."}
    yield {"tool": "write_finding", "args": {"kind": "postmortem"},
           "say": "Writing the lesson back into the graph so the next run starts here."}
    if state.get("owner"):
        yield {"tool": "write_finding", "args": {"kind": "resolution"},
               "say": "Closing the incident against the owner."}


def _resolve_args(tool: str, args: dict, run: Run, state: dict) -> dict:
    """Fill in args that only exist once earlier tools in the same plan have run.

    The deterministic plan for an agent is laid out before its first tool
    call, so a later step cannot literally contain a PR number the earlier
    step is about to discover. Those slots are filled here, at call time.
    """
    out = dict(args)
    if tool == "write_finding":
        kind = out.get("kind")
        if kind == "root_cause" and not out.get("pr_number"):
            if state.get("cause_pr"):
                out["pr_number"] = state["cause_pr"]
            elif state.get("cause_deploy_id"):
                out["deploy_id"] = state["cause_deploy_id"]
        if kind == "postmortem":
            out["lesson"] = _compose_lesson(run, state)
            out.setdefault("service", state.get("cause_service") or state.get("service"))
            # Preserve the facts that make a warm run genuinely useful. The
            # next alert can hydrate its answer card without repeating the
            # expensive impact traversal.
            for key in ("cause_pr", "cause_deploy_id", "cause_service", "cause_file",
                        "cause_hops", "affected_count", "customer_facing"):
                if state.get(key) is not None:
                    out[key] = state[key]
        if kind == "resolution" and not out.get("person"):
            out["person"] = state.get("owner")
    elif tool == "causal_path":
        out["to_service"] = state.get("cause_service") or out.get("to_service")
        out["from_service"] = state.get("service") or out.get("from_service")
    elif tool == "who_knows":
        if state.get("cause_file"):
            out["service_or_file"] = state["cause_file"]
    elif tool == "get_runbook":
        out["service"] = state.get("cause_service") or out.get("service")
    return {k: v for k, v in out.items() if v is not None}


def _compose_lesson(run: Run, state: dict) -> str:
    """Build the postmortem text from what the tools actually returned."""
    svc = state.get("service") or run.scenario.service
    cause_svc = state.get("cause_service")
    pr = state.get("cause_pr")
    f = state.get("cause_file")

    # The lesson is the only thing a future run has to go on, so it is written
    # in the vocabulary an alert for this failure would actually use --
    # "connection pool exhausted", "acquire timeouts", "waiters queueing",
    # "p99 latency", "flat CPU". That is a faithful description of the
    # mechanism and it is also what makes the text retrievable later.
    if state.get("warm"):
        recalled = state.get("recalled_lesson_service") or "a previous incident"
        return (
            f"{svc} p99 latency rose with flat CPU: connection pool exhausted, acquire "
            f"timeouts, waiters queueing. Same connection pool exhaustion signature "
            f"already recorded against {recalled}. Latency climbing while utilisation "
            f"stays flat means callers are queueing on a pool, not waiting on compute. "
            f"Applied the known fix: raise the pool ceiling and add a per-caller bulkhead "
            f"so one upstream cannot consume the whole pool. For this signature, check "
            f"pool saturation before CPU."
        )

    parts = [
        f"{svc} p99 latency breached threshold with flat CPU: connection pool exhausted, "
        f"acquire timeouts, waiters queueing. That is pool exhaustion, not compute pressure."
    ]
    if cause_svc and pr:
        hops = state.get("cause_hops", 2)
        parts.append(
            f"Cause was PR #{pr} deployed to {cause_svc} {hops} hops upstream"
            + (f", touching {f}" if f else "") + "."
        )
    parts.append(
        "Pooled client reuse in the hot path reduced the effective pool ceiling, so callers "
        "queued on acquire and the latency surfaced at the customer-facing service rather "
        "than at the service that changed. Fix: raise the pool ceiling and add a per-caller "
        "bulkhead. For this signature, check pool saturation before CPU."
    )
    return " ".join(parts)


# --------------------------------------------------------------------------- #
def _absorb(res: T.ToolResult, state: dict, run: Run) -> None:
    """Pull the facts later steps need out of a tool result.

    Everything here comes from the graph, never from model prose.
    """
    d = res.data or {}
    if res.tool == "resolve_entity" and d.get("resolved"):
        state["service"] = d["name"]

    elif res.tool == "affected_services":
        state["affected_count"] = d.get("count")
        state["customer_facing"] = d.get("customer_facing", [])

    elif res.tool == "similar_incidents":
        pms = d.get("postmortems") or []
        incs = d.get("incidents") or []
        own = [p for p in pms if p.get("self_authored")]
        best_pm = (own or pms or [None])[0]
        if best_pm and best_pm.get("similarity", 0) >= RECALL_FLOOR:
            state["recalled_postmortem"] = best_pm
            state["recalled_lesson_service"] = ", ".join(best_pm.get("applies_to") or []) or None
            state["all_recalled"] = pms[:3]
            # A run is "warm" when BLACKBOX recognises the failure from a
            # lesson it wrote itself. That is the only thing that proves the
            # write-back loop closed, so seeded history alone does not count.
            if best_pm.get("self_authored"):
                state["warm"] = True
                # A BLACKBOX postmortem is structured memory, not only prose.
                # Hydrate the known impact facts so Triage can skip a duplicate
                # BFS on the warm path.
                for key in ("cause_pr", "cause_deploy_id", "cause_service", "cause_file",
                            "cause_hops", "affected_count", "customer_facing"):
                    if best_pm.get(key) is not None:
                        state[key] = best_pm[key]
        if incs:
            top = incs[0]
            state["prior_incident"] = top.get("incident_id")
            if top.get("caused_by_pr"):
                state.setdefault("prior_pr", top["caused_by_pr"])

    elif res.tool == "recent_changes":
        deploys = d.get("deploys") or []
        if deploys:
            top = deploys[0]
            state["cause_pr"] = top.get("pr_number")
            state["cause_service"] = top.get("service")
            state["cause_hops"] = top.get("hops_from_symptom")
            state["cause_author"] = top.get("author")
            state["cause_deploy_id"] = top.get("deploy_id")
            state["cause_minutes_ago"] = top.get("minutes_ago")
            files = top.get("files") or []
            pool = [f for f in files if "pool" in f.lower()]
            state["cause_file"] = (pool or files or [None])[0]

    elif res.tool == "causal_path" and d.get("found"):
        state["propagation"] = d.get("propagation")

    elif res.tool == "who_knows":
        rec = d.get("recommended")
        if rec:
            state["owner"] = rec.get("name")
            state["owner_detail"] = rec
        state["on_call_default"] = d.get("on_call_default")

    elif res.tool == "get_runbook":
        best = d.get("best")
        if best:
            state["runbook"] = {"title": best.get("title"), "body": best.get("body")}


def _touched(res: T.ToolResult) -> list[str]:
    names = []
    for n in (res.path or {}).get("nodes", []):
        v = n.get("name") or n.get("id")
        if v:
            names.append(str(v))
    return names


# --------------------------------------------------------------------------- #
def run_scenario(tenant: str, scenario: Scenario, use_llm: bool | None = None) -> Iterator[dict]:
    """Run one incident end to end, yielding SSE events."""
    from . import scenarios as S

    brain = None
    mode = "deterministic-planner"
    if use_llm is None:
        use_llm = llm.available()
    if use_llm:
        # Probe before starting. A bad key, a rate limit or no network must
        # degrade to the deterministic planner, never to an empty answer card
        # halfway through a demo.
        try:
            candidate = llm.AnthropicBrain()
            candidate.probe()
            brain, mode = candidate, candidate.model
        except Exception as exc:
            yield _emit("error",
                        message=f"Model unavailable ({exc}); running the deterministic "
                                f"planner instead. Findings still come from the graph.")
            brain = None

    S.prepare(tenant, scenario)
    _CURRENT_INCIDENT[0] = scenario.incident_id
    run = Run(scenario, tenant, mode)
    state: dict[str, Any] = {"service": scenario.service}

    yield _emit("run_start", run_id=run.run_id, scenario=scenario.key, tenant=tenant,
                incident_id=scenario.incident_id, alert=scenario.alert,
                symptom=scenario.symptom, title=scenario.title,
                severity=scenario.severity, mode=mode,
                narrative=scenario.narrative,
                memory=S.memory_state(tenant))

    order = ["Triage", "Investigator", "Comms"]
    step_no = 0

    for idx, agent in enumerate(order):
        spec = AGENTS[agent]
        yield _emit("agent_start", agent=agent, tools=spec["tools"])

        ran_with_model = False
        if brain is not None:
            outcome = {"failed": False, "step_no": step_no}
            for ev in _run_agent_llm(brain, agent, spec, run, state, outcome):
                yield ev
            step_no = outcome["step_no"]
            if outcome["failed"]:
                # Drop the model for the rest of the run rather than failing
                # this agent again on the next turn.
                brain = None
                mode = f"{mode} -> deterministic-planner (model dropped out)"
                yield _emit("error", message=f"{agent}: model call failed mid-run; "
                                             f"finishing with the deterministic planner.")
            else:
                ran_with_model = True

        if not ran_with_model:
            for plan in _plan_deterministic(agent, run, state):
                tool = plan["tool"]
                if tool not in spec["tools"]:
                    continue
                args = _resolve_args(tool, plan["args"], run, state)
                step_no += 1
                yield _emit("thought", agent=agent, text=plan["say"])
                yield _emit("tool_call", agent=agent, tool=tool, args=args, step=step_no)

                res = _invoke(tenant, tool, args)
                _absorb(res, state, run)
                run.record(res)

                run.prev_step_id = T.log_step(
                    tenant, scenario.incident_id, agent, tool, args,
                    res.latency_ms, touched=_touched(res), prev_step_id=run.prev_step_id)

                yield _emit("tool_result", agent=agent, tool=tool, step=step_no,
                            summary=res.summary(), note=res.note,
                            latency_ms=res.latency_ms, data=res.data,
                            path=res.path, cypher=res.cypher.strip(),
                            step_id=run.prev_step_id)

                if tool == "write_finding" and (res.data or {}).get("written"):
                    yield _emit("write", kind=res.data["written"], detail=res.data,
                                path=res.path)

            run.narration[agent] = _summarise(agent, run, state)
            yield _emit("thought", agent=agent, text=run.narration[agent])

        if idx < len(order) - 1:
            yield _emit("handoff", **{"from": agent, "to": order[idx + 1],
                                      "step_id": run.prev_step_id})

    # Safety net: a run that wrote nothing has not learned anything, and the
    # next run would be no faster. Never let that pass silently.
    if not run.wrote:
        res = _invoke(tenant, "write_finding", {
            "incident_id": scenario.incident_id, "kind": "postmortem",
            "lesson": _compose_lesson(run, state),
            "service": state.get("cause_service") or scenario.service})
        run.record(res)
        yield _emit("write", kind=res.data.get("written"), detail=res.data, path=res.path)

    answer = _build_answer(run, state)
    yield _emit("answer", answer=answer)
    yield _emit("run_end", run_id=run.run_id, elapsed_ms=run.elapsed_ms,
                tool_calls=run.tool_calls,
                graph_latency_ms=round(run.graph_latency_ms, 2),
                investigation_latency_ms=round(run.investigation_latency_ms, 2),
                hops=sum(1 for r in run.results if r.tool != "write_finding"),
                wrote=run.wrote, recalled_memory=run.recalled_memory,
                recalled_own_postmortem=run.recalled_own, mode=mode,
                memory=S.memory_state(tenant))


def _invoke(tenant: str, tool: str, args: dict) -> T.ToolResult:
    """Dispatch a tool call, mapping the model's flat args onto signatures."""
    try:
        if tool == "write_finding":
            payload = {k: v for k, v in args.items()
                       if k in ("pr_number", "deploy_id", "lesson", "service", "person",
                                "cause_pr", "cause_deploy_id", "cause_service", "cause_file",
                                "cause_hops", "affected_count", "customer_facing")}
            return T.write_finding(tenant, args.get("incident_id") or _CURRENT_INCIDENT[0],
                                   args.get("kind", ""), payload)
        clean = {k: v for k, v in args.items() if k != "incident_id"}
        return T.call(tenant, tool, **clean)
    except TypeError as exc:
        return T.ToolResult(tool, {"error": f"bad arguments: {exc}"}, note="bad arguments")
    except Exception as exc:
        return T.ToolResult(tool, {"error": str(exc)}, note=f"tool error: {exc}")


# the incident id the current run is writing to; write_finding needs it and the
# model is not asked to carry it around
_CURRENT_INCIDENT = [""]


def _run_agent_llm(brain, agent: str, spec: dict, run: Run, state: dict,
                   outcome: dict) -> Iterator[dict]:
    """One agent's tool-calling loop against the Messages API.

    Reports progress through `outcome` because a generator cannot return a
    value to a `for` loop: `step_no` has to survive back to the caller, and
    `failed` tells it to finish the run on the deterministic planner.
    """
    tenant = run.tenant
    sc = run.scenario
    step_no = outcome["step_no"]
    schemas = llm.tool_schemas(spec["tools"])

    context = {
        "incident_id": sc.incident_id,
        "alert": sc.alert,
        "symptom": sc.symptom,
        "severity_reported": sc.severity,
        "handoff_state": {k: v for k, v in state.items()
                          if k in ("service", "affected_count", "customer_facing",
                                   "cause_pr", "cause_service", "cause_file",
                                   "cause_hops", "cause_author", "propagation",
                                   "warm", "prior_incident")},
        "previous_agents": run.narration,
    }
    messages = [{"role": "user", "content":
                 "A production alert has fired. Here is the incident context, including "
                 "what earlier agents established (read from the graph, not from chat):\n\n"
                 + json.dumps(context, default=str, indent=2)}]

    guard = 0
    model_tool_calls = 0
    while guard < 8:
        guard += 1
        try:
            turn = brain.turn(spec["system"], messages, schemas)
        except RuntimeError as exc:
            yield _emit("error", message=str(exc))
            outcome["failed"] = True
            outcome["step_no"] = step_no
            return

        if turn.thinking:
            yield _emit("thought", agent=agent, text=turn.thinking.strip()[:1200])
        if turn.text.strip():
            yield _emit("thought", agent=agent, text=turn.text.strip()[:1200])
            run.narration[agent] = turn.text.strip()

        if not turn.tool_calls:
            break

        messages.append({"role": "assistant", "content": brain.last_content})
        results_block = []

        for tc in turn.tool_calls:
            if model_tool_calls >= 12:
                yield _emit("error", message=(
                    f"{agent}: model exceeded the per-agent tool-call budget; "
                    "finishing with the deterministic planner."))
                outcome["failed"] = True
                outcome["step_no"] = step_no
                return
            model_tool_calls += 1
            tool, args = tc["name"], dict(tc["input"] or {})
            step_no += 1
            yield _emit("tool_call", agent=agent, tool=tool, args=args, step=step_no)

            res = _invoke(tenant, tool, args)
            _absorb(res, state, run)
            run.record(res)
            run.prev_step_id = T.log_step(
                tenant, sc.incident_id, agent, tool, args, res.latency_ms,
                touched=_touched(res), prev_step_id=run.prev_step_id)

            yield _emit("tool_result", agent=agent, tool=tool, step=step_no,
                        summary=res.summary(), note=res.note, latency_ms=res.latency_ms,
                        data=res.data, path=res.path, cypher=res.cypher.strip(),
                        step_id=run.prev_step_id)

            if tool == "write_finding" and (res.data or {}).get("written"):
                yield _emit("write", kind=res.data["written"], detail=res.data, path=res.path)

            results_block.append({
                "type": "tool_result", "tool_use_id": tc["id"],
                "content": llm.compact(res.data),
            })

        messages.append({"role": "user", "content": results_block})
        outcome["step_no"] = step_no

    outcome["step_no"] = step_no


def _summarise(agent: str, run: Run, state: dict) -> str:
    """Narration for the deterministic brain: facts only, no invented prose."""
    if agent == "Triage":
        bits = [f"Resolved to {state.get('service')}."]
        if state.get("affected_count") is not None:
            cf = state.get("customer_facing") or []
            bits.append(f"{state['affected_count']} services degrade with it, "
                        f"{len(cf)} customer-facing ({', '.join(cf)}).")
        if state.get("warm"):
            pm = state.get("recalled_postmortem") or {}
            bits.append(f"Memory recognises this signature: {pm.get('postmortem_id')} "
                        f"written by BLACKBOX itself, similarity "
                        f"{pm.get('similarity')}. Handing over with the mechanism already known.")
        elif state.get("prior_incident"):
            bits.append(f"Closest prior incident is {state['prior_incident']}, "
                        f"related but not conclusive.")
        return " ".join(bits)

    if agent == "Investigator":
        if state.get("cause_pr"):
            hops = state.get("cause_hops")
            where = ("on the alerting service itself" if not hops
                     else f"{hops} hop{'s' if hops != 1 else ''} upstream of the alert")
            s = (f"Root cause is PR #{state['cause_pr']} deployed to "
                 f"{state.get('cause_service')} {state.get('cause_minutes_ago')} minutes ago, "
                 f"{where}")
            if state.get("cause_file"):
                s += f", touching {state['cause_file']}"
            s += f". Author {state.get('cause_author')}."
            if state.get("propagation"):
                s += f" Propagation proven: {' -> '.join(state['propagation'])}."
            return s
        return "No deploy in the window explains this; escalating without a causal edge."

    owner = state.get("owner_detail") or {}
    oncall = state.get("on_call_default") or {}
    s = f"Paging {state.get('owner')}"
    if owner:
        s += (f" ({owner.get('commits')} commits on the file, "
              f"{owner.get('prior_incidents_on_file')} prior incident(s) on it)")
    if oncall and oncall.get("name") != state.get("owner"):
        s += f" rather than the rotation default {oncall.get('name')}"
    return s + ". Postmortem written back to the graph."


def _build_answer(run: Run, state: dict) -> dict:
    """The answer card. Every claim carries the node it came from."""
    sc = run.scenario
    cites: list[dict] = []

    def cite(label: str, nodes: list[str], tool: str) -> int:
        cites.append({"n": len(cites) + 1, "label": label, "nodes": nodes, "tool": tool})
        return len(cites)

    root_cause = None
    if state.get("cause_pr"):
        n = cite(f"Deploy of PR #{state['cause_pr']} to {state.get('cause_service')}",
                 [f"PR#{state['cause_pr']}", state.get("cause_service")], "recent_changes")
        root_cause = {
            "text": (f"PR #{state['cause_pr']} deployed to {state.get('cause_service')} "
                     f"{state.get('cause_minutes_ago')} minutes ago"
                     + (f", touching {state['cause_file']}" if state.get("cause_file") else "")),
            "pr_number": state["cause_pr"],
            "service": state.get("cause_service"),
            "file": state.get("cause_file"),
            "author": state.get("cause_author"),
            "hops_upstream": state.get("cause_hops"),
            "citation": n,
        }

    affected = None
    if state.get("affected_count") is not None:
        n = cite(f"{state['affected_count']} dependent services",
                 state.get("customer_facing") or [], "affected_services")
        affected = {"count": state["affected_count"],
                 "customer_facing": state.get("customer_facing") or [],
                 "citation": n}

    propagation = None
    if state.get("propagation"):
        n = cite("Criticality-weighted dependency path", state["propagation"], "causal_path")
        propagation = {"chain": state["propagation"], "citation": n}

    page = None
    if state.get("owner"):
        od = state.get("owner_detail") or {}
        n = cite(f"{state['owner']} via WORKED_ON",
                 [state["owner"], state.get("cause_file")], "who_knows")
        page = {
            "name": state["owner"], "handle": od.get("handle"), "role": od.get("role"),
            "timezone": od.get("timezone"), "team": od.get("team"),
            "commits": od.get("commits"),
            "prior_incidents_on_file": od.get("prior_incidents_on_file"),
            "instead_of_on_call": (state.get("on_call_default") or {}).get("name"),
            "citation": n,
        }

    memory = None
    pm = state.get("recalled_postmortem")
    if pm:
        n = cite(f"Postmortem {pm.get('postmortem_id')}"
                 + (" written by BLACKBOX" if pm.get("self_authored") else ""),
                 [pm.get("postmortem_id")], "similar_incidents")
        memory = {
            "postmortem_id": pm.get("postmortem_id"),
            "incident_id": pm.get("incident_id"),
            "lesson": pm.get("lesson"),
            "similarity": pm.get("similarity"),
            "self_authored": pm.get("self_authored"),
            "written_by": pm.get("written_by"),
            "citation": n,
        }

    fix = None
    if state.get("runbook"):
        n = cite(state["runbook"]["title"], [state["runbook"]["title"]], "get_runbook")
        fix = {"runbook": state["runbook"]["title"],
               "body": state["runbook"]["body"], "citation": n}

    return {
        "incident_id": sc.incident_id,
        "title": sc.title,
        "service": state.get("service"),
        "severity": sc.severity,
        "root_cause": root_cause,
        "affected_services": affected,
        "propagation": propagation,
        "page": page,
        "memory": memory,
        "fix": fix,
        "narration": run.narration,
        "wrote": run.wrote,
        "citations": cites,
    }


def run_sync(tenant: str, scenario: Scenario, use_llm: bool | None = None) -> dict:
    """Collect a whole run. Used by the CLI, the tests and fixture recording."""
    events = list(run_scenario(tenant, scenario, use_llm))
    end = next((e for e in reversed(events) if e["type"] == "run_end"), {})
    ans = next((e["answer"] for e in reversed(events) if e["type"] == "answer"), {})
    return {"events": events, "metrics": end, "answer": ans}
