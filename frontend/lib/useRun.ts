"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Answer, Event, MemoryState, RunMetrics, Topology } from "./types";
import { BACKEND, REPLAY_BUILD, fixtureUrl } from "./types";

export interface RunState {
  scenario: string | null;
  running: boolean;
  events: Event[];
  answer: Answer | null;
  metrics: RunMetrics | null;
  mode: string | null;
  error: string | null;
  /** wall clock while the run is in flight, so the timer actually ticks */
  liveMs: number;
}

const EMPTY: RunState = {
  scenario: null, running: false, events: [], answer: null,
  metrics: null, mode: null, error: null, liveMs: 0,
};

export function useRuns() {
  const [cold, setCold] = useState<RunState>(EMPTY);
  const [warm, setWarm] = useState<RunState>(EMPTY);
  const [topology, setTopology] = useState<Topology | null>(null);
  const [memory, setMemory] = useState<MemoryState | null>(null);
  const [tenant, setTenant] = useState("acme");
  const [health, setHealth] = useState<any>(null);
  /** true when runs come from recorded fixtures rather than a live backend */
  const [replay, setReplay] = useState(REPLAY_BUILD);
  const abort = useRef<AbortController | null>(null);
  const ticker = useRef<ReturnType<typeof setInterval> | null>(null);

  const setter = (key: "cold" | "warm") => (key === "cold" ? setCold : setWarm);

  /** The service topology. Fetched once per tenant -- never after a run. */
  const loadTopology = useCallback(async (t: string) => {
    if (!REPLAY_BUILD) {
      try {
        setTopology(await fetch(`${BACKEND}/api/graph?tenant=${t}`).then((r) => r.json()));
        setReplay(false);
        return;
      } catch {
        /* fall through to the recorded snapshot */
      }
    }
    try {
      const snap = await fetch(fixtureUrl("graph_acme.json")).then((r) => r.json());
      setTopology({ tenant: "acme", latency_ms: 0, ...snap });
      setReplay(true);
    } catch {
      setTopology(null);
    }
  }, []);

  /**
   * Only the memory counters change during a run. Refetching the topology
   * instead would hand the graph pane a new object, which rebuilds the
   * Cytoscape instance and wipes the highlight the run just drew.
   */
  const refreshStats = useCallback(async (t: string) => {
    if (REPLAY_BUILD) return;
    try {
      const s = await fetch(`${BACKEND}/api/stats?tenant=${t}`).then((r) => r.json());
      setMemory(s.memory);
    } catch {
      /* the badge stays stale; nothing else depends on it */
    }
  }, []);

  useEffect(() => {
    fetch(`${BACKEND}/api/health`).then((r) => r.json()).then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    void loadTopology(tenant);
    void refreshStats(tenant);
  }, [tenant, loadTopology, refreshStats]);

  const stop = useCallback(() => {
    abort.current?.abort();
    abort.current = null;
    if (ticker.current) clearInterval(ticker.current);
    ticker.current = null;
  }, []);

  const run = useCallback(
    async (scenario: "cold" | "warm", useLlm: boolean | null, paceMs = 0) => {
      stop();
      const set = setter(scenario);
      const started = performance.now();
      set({ ...EMPTY, scenario, running: true });

      ticker.current = setInterval(() => {
        set((s) => (s.running ? { ...s, liveMs: performance.now() - started } : s));
      }, 50);

      const ctrl = new AbortController();
      abort.current = ctrl;

      // ---- replay: re-emit a recorded run, same shape, same order ----------
      if (replay || REPLAY_BUILD) {
        try {
          const rec = await fetch(fixtureUrl(`${scenario}_run.json`)).then((r) => {
            if (!r.ok) throw new Error(`fixture ${scenario}_run.json: ${r.status}`);
            return r.json();
          });
          const events: Event[] = rec.events ?? [];
          for (const ev of events) {
            if (ctrl.signal.aborted) return;
            set((st) => apply(st, ev));
            if (paceMs > 0 && PACED.has(ev.type)) {
              await sleep(paceMs, ctrl.signal);
            }
          }
        } catch (err: any) {
          if (err?.name !== "AbortError") {
            set((st) => ({ ...st, running: false, error: String(err?.message ?? err) }));
          }
        } finally {
          if (ticker.current) clearInterval(ticker.current);
          ticker.current = null;
          set((st) => ({ ...st, running: false }));
        }
        return;
      }

      const qs = new URLSearchParams({ scenario, tenant });
      if (useLlm !== null) qs.set("use_llm", String(useLlm));
      // Presentation pacing only: the server does the work at full speed and
      // reports its own measured timings, then drips the events out so a
      // person can follow the traversal. It never changes what is measured.
      if (paceMs > 0) qs.set("pace_ms", String(paceMs));

      try {
        // EventSource cannot be aborted cleanly or carry a query reliably
        // across reloads, so the stream is read straight off fetch.
        const res = await fetch(`${BACKEND}/api/incident/stream?${qs}`, {
          signal: ctrl.signal,
          headers: { Accept: "text/event-stream" },
        });
        if (!res.ok || !res.body) throw new Error(`backend returned ${res.status}`);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          // SSE frames are separated by a blank line
          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";

          for (const frame of frames) {
            const line = frame.split("\n").find((l) => l.startsWith("data: "));
            if (!line) continue;
            let ev: Event;
            try {
              ev = JSON.parse(line.slice(6));
            } catch {
              continue;
            }
            set((s) => apply(s, ev));
          }
        }
      } catch (err: any) {
        if (err?.name !== "AbortError") {
          set((s) => ({ ...s, running: false, error: String(err?.message ?? err) }));
        }
      } finally {
        if (ticker.current) clearInterval(ticker.current);
        ticker.current = null;
        set((s) => ({ ...s, running: false }));
        void refreshStats(tenant);
      }
    },
    [stop, tenant, refreshStats, replay],
  );

  const resetMemory = useCallback(async () => {
    setCold(EMPTY);
    setWarm(EMPTY);
    if (REPLAY_BUILD) return;      // nothing to forget; the runs are recorded
    try {
      const r = await fetch(`${BACKEND}/api/memory/reset?tenant=${tenant}`, { method: "POST" });
      const j = await r.json();
      setMemory(j.memory);
    } catch {
      /* the badge just stays stale; nothing else depends on it */
    }
  }, [tenant]);

  useEffect(() => () => stop(), [stop]);

  return { cold, warm, topology, memory, tenant, setTenant, health, replay,
           run, resetMemory, stop };
}

/** Event kinds worth pausing on during replay. Mirrors PACED_EVENTS in api.py. */
const PACED = new Set([
  "tool_call", "tool_result", "thought", "handoff", "write", "answer",
]);

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(t);
      reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
    }, { once: true });
  });
}

function apply(s: RunState, ev: Event): RunState {
  const events = [...s.events, ev];
  switch (ev.type) {
    case "run_start":
      return { ...s, events, mode: ev.mode };
    case "answer":
      return { ...s, events, answer: ev.answer };
    case "run_end":
      return { ...s, events, metrics: ev, running: false, liveMs: ev.elapsed_ms };
    case "error":
      // A model dropout is reported but the run continues on the planner, so
      // this is a notice, not a terminal state.
      return { ...s, events, error: ev.message };
    default:
      return { ...s, events };
  }
}
