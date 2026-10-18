"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useState } from "react";
import AgentStream from "@/components/AgentStream";
import AnswerCard from "@/components/AnswerCard";
import TimerBar from "@/components/TimerBar";
import { BrandMark } from "@/components/Atmosphere";
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
    cold, warm, topology, memory, tenant, setTenant, health, replay,
    run, resetMemory, stop,
  } = useRuns();

  const [active, setActive] = useState<"cold" | "warm">("cold");
  const [useLlm, setUseLlm] = useState<boolean | null>(null);
  // playback pacing: delivery only, never the measured work
  const [pace, setPace] = useState(450);
  const [focus, setFocus] = useState<string[]>([]);
  const [mobilePane, setMobilePane] = useState<"graph" | "trace" | "answer">("graph");

  const shown = active === "cold" ? cold : warm;
  const busy = cold.running || warm.running;

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-ink">
      {/* ───────────────────────── top bar ───────────────────────── */}
      <header className="console-bar console-topbar flex shrink-0 items-center gap-4 px-4 py-2">
        <Link href="/" className="brand group" title="back to the landing page">
          <BrandMark size={22} />
          <span className="console-brand group-hover:text-lilac">BLACKBOX</span>
        </Link>
        <span className="hidden text-[10px] text-dim lg:inline">
          on-call agent · FalkorDB
        </span>

        <div className="ml-2 flex items-center gap-2">
          <ScenarioButton
            label="run cold"
            hint="checkout-api latency — no prior memory"
            disabled={busy}
            active={active === "cold"}
            onClick={() => {
              setActive("cold");
              void run("cold", useLlm, pace);
            }}
          />
          <ScenarioButton
            label="run warm"
            hint="same signature, new service — memory in play"
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
              className="rounded-full border border-amber/40 px-3 py-1 text-[10px] text-amber transition-colors hover:bg-amber/10"
            >
              stop
            </button>
          )}
        </div>

        <div className="ml-auto flex items-center gap-2.5 text-[10px]">
          {/* which run the panes are showing */}
          <Seg
            title="which run the panes are showing"
            options={[["cold", "cold"], ["warm", "warm"]]}
            value={active}
            onChange={(v) => setActive(v as "cold" | "warm")}
          />

          {/* brain selector */}
          <div className="seg" title="what drives tool selection">
            {([
              [null, "auto", "use the model if a key is configured"],
              [true, "model", "drive tool selection with Claude"],
              [false, "planner", "deterministic planner: no API calls, same nine tools"],
            ] as const).map(([v, label, tip]) => (
              <button
                key={label}
                onClick={() => setUseLlm(v)}
                disabled={busy}
                data-on={useLlm === v}
                title={tip}
              >
                {label}
              </button>
            ))}
          </div>

          {/* playback speed: how fast the stream is drawn, not how fast it runs */}
          <div
            className="seg"
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
                data-on={pace === v}
              >
                {label}
              </button>
            ))}
          </div>

          {/* tenant switcher: separate graph on the same FalkorDB instance */}
          <div className="seg" title="separate graph per tenant">
            {(["acme", "globex"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTenant(t)}
                disabled={busy}
                data-on={tenant === t}
              >
                tenant:{t}
              </button>
            ))}
          </div>

          <button
            onClick={() => void resetMemory()}
            disabled={busy || replay}
            className="rounded-full border border-line px-3 py-1 text-dim transition-colors hover:border-line2 hover:text-fg disabled:opacity-40"
            title="delete the postmortems BLACKBOX wrote, keep the seeded history"
          >
            forget
          </button>

          <span
            className={`pill ${
              replay ? "violet" : health?.ok ? "live" : "ember"
            }`}
          >
            <i />
            {replay ? (
              "recorded run"
            ) : memory ? (
              <span className="tnum">
                {memory.self_authored_postmortems} learned ·{" "}
                {memory.seeded_postmortems} seeded
              </span>
            ) : (
              <span>{health?.ok ? "connected" : "offline"}</span>
            )}
          </span>
        </div>
      </header>

      {replay && <ReplayBanner />}

      {/* ───────────────────────── alert strip ───────────────────────── */}
      <AlertStrip events={shown.events} mode={shown.mode} error={shown.error} />

      <nav className="console-mobile-tabs" aria-label="Investigation view">
        {(["graph", "trace", "answer"] as const).map((pane) => (
          <button
            key={pane}
            type="button"
            aria-selected={mobilePane === pane}
            onClick={() => setMobilePane(pane)}
          >
            {pane === "trace" ? "agent stream" : pane}
          </button>
        ))}
      </nav>

      {/* ───────────────────────── three panes ───────────────────────── */}
      <main className="console-main flex min-h-0 flex-1" data-pane={mobilePane}>
        <section className="console-graph relative min-w-0 flex-[55] border-r border-line">
          <GraphPane
            topology={topology}
            events={shown.events}
            running={shown.running}
            focusNodes={focus}
          />
        </section>

        <aside className="console-insights flex min-h-0 w-[clamp(340px,42%,560px)] flex-col">
          <div className="console-trace min-h-0 flex-[60] border-b border-line">
            <AgentStream events={shown.events} running={shown.running} />
          </div>
          <div className="console-answer min-h-0 flex-[40]">
            <AnswerCard answer={shown.answer} metrics={shown.metrics} onFocus={setFocus} />
          </div>
        </aside>
      </main>

      {/* ───────────────────────── cold / warm ───────────────────────── */}
      <TimerBar cold={cold} warm={warm} />
    </div>
  );
}

/** Generic segmented control, styled by `.seg` in globals.css. */
function Seg({
  options,
  value,
  onChange,
  title,
  disabled,
}: {
  options: readonly (readonly [string, string])[];
  value: string;
  onChange: (v: string) => void;
  title?: string;
  disabled?: boolean;
}) {
  return (
    <div className="seg" title={title}>
      {options.map(([v, label]) => (
        <button
          key={v}
          onClick={() => onChange(v)}
          disabled={disabled}
          data-on={value === v}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function ReplayBanner() {
  return (
    <div className="shrink-0 border-b border-violet/25 bg-violet/[0.07] px-4 py-1.5 text-[11px] text-violet">
      <span className="font-semibold">recorded run</span>
      <span className="text-dim">
        {" "}— this page is served as static files, so there is no FalkorDB
        behind it. Every step, latency and answer below is real output from a
        real run, replayed from{" "}
        <span className="text-fg">fixtures/</span>. For the live thing:{" "}
        <span className="text-fg">docker compose up</span>.
      </span>
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
      data-on={active}
      className="runbtn"
    >
      <i aria-hidden="true">▸</i>
      {label}
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
      <div className="shrink-0 border-b border-line bg-panel px-4 py-1.5 text-[11px] text-dim">
        no incident running — press{" "}
        <span className="text-lilac">run cold</span> to fire the first alert
      </div>
    );
  }

  return (
    <div className="alert-strip shrink-0 px-4 py-1.5">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 pl-1.5 text-[11px]">
        <span className="font-semibold tracking-[0.14em] text-ember">ALERT</span>
        <span className="text-bright">{start.alert.service}</span>
        <span className="tnum text-dim">
          {start.alert.metric} = {start.alert.value.toFixed(0)}
          <span className="text-line2"> / {start.alert.threshold.toFixed(0)}</span>
        </span>
        <span className="text-line2">│</span>
        <span className="min-w-0 flex-1 truncate text-dim">{start.symptom}</span>
        <span className="text-line2">│</span>
        <span className="text-dim">{start.incident_id}</span>
        <span className="pill violet">{mode ?? start.mode}</span>
      </div>
      {error && (
        <div className="mt-0.5 truncate pl-1.5 text-[10px] text-amber" title={error}>
          {error}
        </div>
      )}
    </div>
  );
}
