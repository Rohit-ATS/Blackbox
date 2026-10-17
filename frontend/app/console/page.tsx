"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useState } from "react";
import AgentStream from "@/components/AgentStream";
import AnswerCard from "@/components/AnswerCard";
import TimerBar from "@/components/TimerBar";
import { useRuns } from "@/lib/useRun";
import type { Event } from "@/lib/types";

// Cytoscape touches window at import time.
const GraphPane = dynamic(() => import("@/components/GraphPane"), {
  ssr: false,
  loading: () => (
    <div className="grid h-full place-items-center text-[11px] text-dim grid-bg">
      loading graph…
    </div>
  ),
});

export default function Console() {
  const {
    cold, warm, topology, memory, tenant, setTenant, health,
    run, resetMemory, stop,
  } = useRuns();

  const [active, setActive] = useState<"cold" | "warm">("cold");
  const [useLlm, setUseLlm] = useState<boolean | null>(null);
  // playback pacing: delivery only, never the measured work
  const [pace, setPace] = useState(450);
  const [focus, setFocus] = useState<string[]>([]);

  const shown = active === "cold" ? cold : warm;
  const busy = cold.running || warm.running;

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-ink">
      {/* ───────────────────────── top bar ───────────────────────── */}
      <header className="flex shrink-0 items-center gap-4 border-b border-line bg-panel px-4 py-2">
        <Link href="/" className="group flex items-baseline gap-2">
          <span className="text-sm font-bold tracking-[0.2em] text-bright group-hover:text-cyan">
            BLACKBOX
          </span>
          <span className="hidden text-[10px] text-dim sm:inline">
            on-call agent · FalkorDB
          </span>
        </Link>

        <div className="ml-2 flex items-center gap-1.5">
          <ScenarioButton
            label="run cold"
            hint="checkout-api latency"
            disabled={busy}
            active={active === "cold"}
            onClick={() => {
              setActive("cold");
              void run("cold", useLlm, pace);
            }}
          />
          <ScenarioButton
            label="run warm"
            hint="same signature, new service"
            disabled={busy}
            active={active === "warm"}
            onClick={() => {
              setActive("warm");
              void run("warm", useLlm, pace);
            }}
          />
          {busy && (
            <button
              onClick={stop}
              className="hair px-2 py-1 text-[10px] text-amber hover:bg-amber/10"
            >
              stop
            </button>
          )}
        </div>

        <div className="ml-auto flex items-center gap-3 text-[10px]">
          {/* which run the panes are showing */}
          <div className="hair flex overflow-hidden">
            {(["cold", "warm"] as const).map((k) => (
              <button
                key={k}
                onClick={() => setActive(k)}
                className={`px-2 py-1 ${
                  active === k ? "bg-line2 text-bright" : "text-dim hover:bg-panel2"
                }`}
              >
                {k}
              </button>
            ))}
          </div>

          {/* brain selector */}
          <div className="hair flex overflow-hidden">
            {([
              [null, "auto"],
              [true, "model"],
              [false, "planner"],
            ] as const).map(([v, label]) => (
              <button
                key={label}
                onClick={() => setUseLlm(v)}
                disabled={busy}
                className={`px-2 py-1 ${
                  useLlm === v ? "bg-line2 text-bright" : "text-dim hover:bg-panel2"
                } disabled:opacity-40`}
                title={
                  label === "planner"
                    ? "deterministic planner: no API calls, same nine tools"
                    : label === "model"
                      ? "drive tool selection with Claude"
                      : "use the model if a key is configured"
                }
              >
                {label}
              </button>
            ))}
          </div>

          {/* playback speed: how fast the stream is drawn, not how fast it runs */}
          <div
            className="hair flex overflow-hidden"
            title="Playback speed. The agent always runs at full speed; this only spaces out how the steps are drawn."
          >
            {([
              [450, "1×"],
              [180, "2.5×"],
              [0, "max"],
            ] as const).map(([v, label]) => (
              <button
                key={label}
                onClick={() => setPace(v)}
                disabled={busy}
                className={`px-2 py-1 ${
                  pace === v ? "bg-line2 text-bright" : "text-dim hover:bg-panel2"
                } disabled:opacity-40`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* tenant switcher: separate graph on the same FalkorDB instance */}
          <div className="hair flex overflow-hidden" title="separate graph per tenant">
            {(["acme", "globex"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTenant(t)}
                disabled={busy}
                className={`px-2 py-1 ${
                  tenant === t ? "bg-line2 text-bright" : "text-dim hover:bg-panel2"
                } disabled:opacity-40`}
              >
                tenant:{t}
              </button>
            ))}
          </div>

          <button
            onClick={() => void resetMemory()}
            disabled={busy}
            className="hair px-2 py-1 text-dim hover:bg-panel2 disabled:opacity-40"
            title="delete the postmortems BLACKBOX wrote, keep the seeded history"
          >
            forget
          </button>

          <div className="flex items-center gap-1.5 text-dim">
            <span
              className={`inline-block h-1.5 w-1.5 ${
                health?.ok ? "bg-green" : "bg-red"
              }`}
            />
            {memory ? (
              <span className="tnum">
                {memory.self_authored_postmortems} learned ·{" "}
                {memory.seeded_postmortems} seeded
              </span>
            ) : (
              <span>{health?.ok ? "connected" : "offline"}</span>
            )}
          </div>
        </div>
      </header>

      {/* ───────────────────────── alert strip ───────────────────────── */}
      <AlertStrip events={shown.events} mode={shown.mode} error={shown.error} />

      {/* ───────────────────────── three panes ───────────────────────── */}
      <main className="flex min-h-0 flex-1">
        <section className="relative min-w-0 flex-[55] border-r border-line">
          <GraphPane
            topology={topology}
            events={shown.events}
            running={shown.running}
            focusNodes={focus}
          />
        </section>

        <aside className="flex min-h-0 w-[clamp(340px,42%,560px)] flex-col">
          <div className="min-h-0 flex-[60] border-b border-line">
            <AgentStream events={shown.events} running={shown.running} />
          </div>
          <div className="min-h-0 flex-[40]">
            <AnswerCard answer={shown.answer} onFocus={setFocus} />
          </div>
        </aside>
      </main>

      {/* ───────────────────────── cold / warm ───────────────────────── */}
      <TimerBar cold={cold} warm={warm} />
    </div>
  );
}

function ScenarioButton({
  label,
  hint,
  disabled,
  active,
  onClick,
}: {
  label: string;
  hint: string;
  disabled: boolean;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={hint}
      className={`hair px-2.5 py-1 text-[11px] transition-colors disabled:opacity-40 ${
        active
          ? "border-cyan/50 bg-cyan/10 text-cyan"
          : "text-fg hover:bg-panel2"
      }`}
    >
      ▸ {label}
    </button>
  );
}

function AlertStrip({
  events,
  mode,
  error,
}: {
  events: Event[];
  mode: string | null;
  error: string | null;
}) {
  const start = events.find((e) => e.type === "run_start") as
    | Extract<Event, { type: "run_start" }>
    | undefined;

  if (!start) {
    return (
      <div className="shrink-0 border-b border-line bg-panel2 px-4 py-1.5 text-[11px] text-dim">
        no incident running — press{" "}
        <span className="text-fg">run cold</span> to fire the first alert
      </div>
    );
  }

  return (
    <div className="relative shrink-0 overflow-hidden border-b border-line bg-panel2 px-4 py-1.5">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-[11px]">
        <span className="font-bold text-red">ALERT</span>
        <span className="text-bright">{start.alert.service}</span>
        <span className="tnum text-dim">
          {start.alert.metric} = {start.alert.value.toFixed(0)}
          <span className="text-line2"> / {start.alert.threshold.toFixed(0)}</span>
        </span>
        <span className="text-line2">│</span>
        <span className="min-w-0 flex-1 truncate text-dim">{start.symptom}</span>
        <span className="text-line2">│</span>
        <span className="text-dim">{start.incident_id}</span>
        <span className="hair border-line2 px-1.5 text-[10px] text-violet">
          {mode ?? start.mode}
        </span>
      </div>
      {error && (
        <div className="mt-0.5 truncate text-[10px] text-amber" title={error}>
          {error}
        </div>
      )}
    </div>
  );
}
