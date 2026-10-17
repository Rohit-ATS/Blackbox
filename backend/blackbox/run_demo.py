"""CLI demo runner.

    python -m blackbox.run_demo                 # cold, then warm, with comparison
    python -m blackbox.run_demo --scenario cold
    python -m blackbox.run_demo --reset         # forget what BLACKBOX learned first
"""
from __future__ import annotations

import argparse
import sys

from . import agents, scenarios
from .llm import mode_name

# Windows consoles default to cp1252, which cannot encode the box glyphs.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
RED, GREEN, YELLOW, CYAN = "\033[31m", "\033[32m", "\033[33m", "\033[36m"

AGENT_COLOR = {"Triage": CYAN, "Investigator": YELLOW, "Comms": GREEN}


def render(event: dict) -> None:
    t = event["type"]
    if t == "run_start":
        print(f"\n{BOLD}{'=' * 78}{RESET}")
        print(f"{BOLD}ALERT  {event['alert']['service']}  "
              f"{event['alert']['metric']}={event['alert']['value']:.0f} "
              f"(threshold {event['alert']['threshold']:.0f}){RESET}")
        print(f"{DIM}{event['symptom']}{RESET}")
        print(f"{DIM}incident {event['incident_id']} · scenario {event['scenario']} · "
              f"brain {event['mode']} · memory {event['memory']}{RESET}")
        print(f"{BOLD}{'=' * 78}{RESET}")
    elif t == "agent_start":
        c = AGENT_COLOR.get(event["agent"], "")
        print(f"\n{c}{BOLD}▸ {event['agent'].upper()}{RESET} {DIM}"
              f"tools: {', '.join(event['tools'])}{RESET}")
    elif t == "thought":
        print(f"  {DIM}{event['text']}{RESET}")
    elif t == "tool_call":
        print(f"  {BOLD}[{event['step']}] {event['tool']}{RESET}"
              f"({', '.join(f'{k}={v!r}' for k, v in event['args'].items())})")
    elif t == "tool_result":
        print(f"      → {event['note'] or event['summary']}  "
              f"{DIM}{event['latency_ms']}ms{RESET}")
    elif t == "handoff":
        print(f"  {DIM}── handoff {event['from']} → {event['to']} "
              f"(AgentStep {event['step_id']}){RESET}")
    elif t == "write":
        print(f"  {GREEN}✎ wrote {event['kind']} to the graph{RESET}")
    elif t == "error":
        print(f"  {RED}! {event['message']}{RESET}")
    elif t == "answer":
        a = event["answer"]
        print(f"\n{BOLD}── ANSWER ──{RESET}")
        if a.get("root_cause"):
            rc = a["root_cause"]
            hops = rc.get("hops_upstream") or 0
            where = ("on the alerting service itself" if not hops
                     else f"{hops} hop{'s' if hops != 1 else ''} upstream")
            print(f"  root cause   {rc['text']}  [{rc['citation']}]")
            print(f"               author {rc['author']}, {where}")
        if a.get("blast_radius"):
            b = a["blast_radius"]
            print(f"  blast radius {b['count']} services, customer-facing: "
                  f"{', '.join(b['customer_facing']) or 'none'}  [{b['citation']}]")
        if a.get("propagation"):
            print(f"  propagation  {' → '.join(a['propagation']['chain'])}  "
                  f"[{a['propagation']['citation']}]")
        if a.get("page"):
            p = a["page"]
            line = f"  page         {p['name']} (@{p['handle']}, {p['timezone']})"
            if p.get("instead_of_on_call") and p["instead_of_on_call"] != p["name"]:
                line += f" — not the rotation default {p['instead_of_on_call']}"
            print(f"{line}  [{p['citation']}]")
            print(f"               {p['commits']} commits on the file, "
                  f"{p['prior_incidents_on_file']} prior incident(s) on it")
        if a.get("memory"):
            m = a["memory"]
            tag = "BLACKBOX's own postmortem" if m["self_authored"] else "seeded history"
            print(f"  memory       {m['postmortem_id']} ({tag}, "
                  f"similarity {m['similarity']})  [{m['citation']}]")
            print(f"               {DIM}{(m['lesson'] or '')[:150]}...{RESET}")
        if a.get("fix"):
            print(f"  runbook      {a['fix']['runbook']}  [{a['fix']['citation']}]")
    elif t == "run_end":
        print(f"\n{BOLD}{event['tool_calls']} tool calls · "
              f"{event['elapsed_ms']:.0f}ms wall · "
              f"{event['graph_latency_ms']:.1f}ms in FalkorDB · "
              f"wrote {', '.join(event['wrote']) or 'nothing'}{RESET}")
        if event.get("recalled_own_postmortem"):
            print(f"{GREEN}recalled its own postmortem{RESET}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", default="acme")
    ap.add_argument("--scenario", choices=["cold", "warm", "both"], default="both")
    ap.add_argument("--reset", action="store_true", help="forget learned postmortems first")
    ap.add_argument("--no-llm", action="store_true", help="force the deterministic planner")
    args = ap.parse_args()

    if args.reset:
        print(f"{DIM}reset: {scenarios.reset_memory(args.tenant)}{RESET}")

    use_llm = False if args.no_llm else None
    print(f"{DIM}brain: {mode_name()}{RESET}")

    keys = ["cold", "warm"] if args.scenario == "both" else [args.scenario]
    results = {}
    for key in keys:
        out = agents.run_sync(args.tenant, scenarios.ALL[key], use_llm)
        for ev in out["events"]:
            render(ev)
        results[key] = out["metrics"]

    if len(results) == 2:
        c, w = results["cold"], results["warm"]
        print(f"\n{BOLD}{'=' * 78}{RESET}")
        print(f"{BOLD}COLD vs WARM{RESET}")
        print(f"  run 1 (cold)  {c['tool_calls']} tool calls · "
              f"{c['elapsed_ms']:.0f}ms · {c['graph_latency_ms']:.1f}ms in graph")
        print(f"  run 2 (warm)  {w['tool_calls']} tool calls · "
              f"{w['elapsed_ms']:.0f}ms · {w['graph_latency_ms']:.1f}ms in graph"
              + (f" · recalled its own postmortem"
                 if w.get("recalled_own_postmortem") else ""))
        if w["tool_calls"]:
            print(f"  {BOLD}{c['tool_calls'] / w['tool_calls']:.1f}x fewer tool calls, "
                  f"{c['elapsed_ms'] / max(w['elapsed_ms'], 0.001):.1f}x faster{RESET}")
        print(f"{BOLD}{'=' * 78}{RESET}")


if __name__ == "__main__":
    main()
