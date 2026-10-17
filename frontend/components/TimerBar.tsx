"use client";

import type { RunState } from "@/lib/useRun";

/**
 * The cold-vs-warm comparison, and the whole point of the project.
 *
 * It reports four measured numbers rather than one headline, because they do
 * not all move for the same reason: wall time depends on whether a model is in
 * the loop, while tool calls and graph time are properties of the traversal
 * and are identical either way. Nothing here is estimated.
 */
export default function TimerBar({
  cold,
  warm,
}: {
  cold: RunState;
  warm: RunState;
}) {
  const c = cold.metrics;
  const w = warm.metrics;
  const both = Boolean(c && w);

  const ratio = (a?: number, b?: number) =>
    a && b && b > 0 ? (a / b).toFixed(1) : null;

  return (
    <div className="flex items-stretch divide-x divide-line border-t border-line bg-panel">
      <Run
        tag="run 1"
        name="cold"
        subtitle="nothing in memory names this deploy"
        state={cold}
        tone="red"
      />
      <Run
        tag="run 2"
        name="warm"
        subtitle="same signature, 90 seconds later"
        state={warm}
        tone="green"
        badge={
          w?.recalled_own_postmortem
            ? "recalled its own postmortem"
            : undefined
        }
      />

      <div className="flex min-w-[232px] flex-col justify-center px-4 py-2">
        <div className="mb-1 text-[9px] uppercase tracking-[0.15em] text-line2">
          difference
        </div>
        {both ? (
          <div className="space-y-0.5 text-[11px]">
            <Delta
              label="tool calls"
              from={c!.tool_calls}
              to={w!.tool_calls}
              x={ratio(c!.tool_calls, w!.tool_calls)}
            />
            <Delta
              label="graph time"
              from={`${c!.graph_latency_ms.toFixed(0)}ms`}
              to={`${w!.graph_latency_ms.toFixed(0)}ms`}
              x={ratio(c!.graph_latency_ms, w!.graph_latency_ms)}
            />
            <Delta
              label="wall clock"
              from={fmtMs(c!.elapsed_ms)}
              to={fmtMs(w!.elapsed_ms)}
              x={ratio(c!.elapsed_ms, w!.elapsed_ms)}
            />
          </div>
        ) : (
          <div className="text-[11px] leading-relaxed text-dim">
            run cold, then warm.
            <br />
            the second one is only fast
            <br />
            because the first one wrote.
          </div>
        )}
      </div>
    </div>
  );
}

function Run({
  tag,
  name,
  subtitle,
  state,
  tone,
  badge,
}: {
  tag: string;
  name: string;
  subtitle: string;
  state: RunState;
  tone: "red" | "green";
  badge?: string;
}) {
  const m = state.metrics;
  const live = state.running;
  const ms = live ? state.liveMs : m?.elapsed_ms;
  const accent = tone === "red" ? "text-red" : "text-green";

  return (
    <div className="flex min-w-[246px] flex-1 flex-col justify-center px-4 py-2">
      <div className="flex items-baseline gap-2">
        <span className="text-[9px] uppercase tracking-[0.15em] text-line2">{tag}</span>
        <span className={`text-[11px] font-bold uppercase tracking-wider ${accent}`}>
          {name}
        </span>
        {live && <span className="text-[10px] text-amber animate-blink">running ▌</span>}
      </div>

      <div className="mt-0.5 flex items-baseline gap-3">
        <span className="tnum text-2xl font-bold leading-none text-bright">
          {ms !== undefined ? fmtMs(ms) : "—"}
        </span>
        <span className="text-[9px] uppercase tracking-wider text-line2">
          {live ? "streaming" : "measured"}
        </span>
        <span className="tnum text-[11px] text-dim">
          {m ? `${m.tool_calls} tool calls` : ""}
        </span>
        <span className="tnum text-[11px] text-dim">
          {m ? `${m.graph_latency_ms.toFixed(0)}ms in graph` : ""}
        </span>
      </div>

      <div className="mt-0.5 truncate text-[10px] text-dim">{subtitle}</div>

      {badge && (
        <div className="mt-1 inline-flex w-fit items-center gap-1 border border-green/40 bg-green/10 px-1.5 py-px text-[9.5px] text-green">
          ✎ {badge}
        </div>
      )}

      {m && m.wrote.length > 0 && !badge && (
        <div className="mt-1 text-[9.5px] text-dim">
          wrote {m.wrote.join(", ")}
        </div>
      )}
    </div>
  );
}

function Delta({
  label,
  from,
  to,
  x,
}: {
  label: string;
  from: string | number;
  to: string | number;
  x: string | null;
}) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="w-[62px] shrink-0 text-[9.5px] uppercase tracking-wider text-line2">
        {label}
      </span>
      <span className="tnum text-dim">{from}</span>
      <span className="text-line2">→</span>
      <span className="tnum text-bright">{to}</span>
      {x && Number(x) > 1 && (
        <span className="tnum ml-auto font-bold text-green">{x}×</span>
      )}
    </div>
  );
}

function fmtMs(ms: number) {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms.toFixed(0)}ms`;
}
