"use client";

import { useEffect, useRef, useState } from "react";
import { AGENT_BG, type AgentName, type Event } from "@/lib/types";

/**
 * The agent stream. Every step, in order, with the tool, its arguments, what
 * came back, and how long the graph took. Each row expands to the exact Cypher
 * that ran -- transparent, not magic.
 */
export default function AgentStream({
  events,
  running,
}: {
  events: Event[];
  running: boolean;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState<Record<number, boolean>>({});
  const [pinned, setPinned] = useState(true);

  useEffect(() => {
    if (!pinned || !scroller.current) return;
    scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [events, pinned]);

  // pair each tool_call with its result
  const rows: JSX.Element[] = [];
  const resultFor = new Map<number, Extract<Event, { type: "tool_result" }>>();
  for (const e of events) if (e.type === "tool_result") resultFor.set(e.step, e);

  events.forEach((e, i) => {
    if (e.type === "agent_start") {
      rows.push(
        <div key={i} className="mt-3 flex items-center gap-2 animate-slide-in first:mt-0">
          <span className={`hair px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${AGENT_BG[e.agent]}`}>
            {e.agent}
          </span>
          <span className="truncate text-[10px] text-dim">{e.tools.join(" · ")}</span>
          <span className="h-px flex-1 bg-line" />
        </div>,
      );
    } else if (e.type === "thought") {
      rows.push(
        <div key={i} className="mt-1.5 border-l border-line2 pl-2.5 text-[11px] leading-relaxed text-dim animate-fade-in">
          {e.text}
        </div>,
      );
    } else if (e.type === "tool_call") {
      const res = resultFor.get(e.step);
      const isOpen = open[e.step];
      rows.push(
        <div key={i} className="mt-1.5 animate-slide-in">
          <button
            onClick={() => setOpen((o) => ({ ...o, [e.step]: !o[e.step] }))}
            className="group flex w-full items-baseline gap-2 text-left hover:bg-panel2"
          >
            <span className="tnum w-5 shrink-0 text-right text-[10px] text-line2">
              {e.step}
            </span>
            <span className="shrink-0 text-[11px] font-bold text-bright">{e.tool}</span>
            <span className="min-w-0 flex-1 truncate text-[10px] text-dim">
              {Object.entries(e.args)
                .map(([k, v]) => `${k}=${fmt(v)}`)
                .join(" ")}
            </span>
            {res ? (
              <span className="tnum shrink-0 text-[10px] text-green">
                {res.latency_ms.toFixed(1)}ms
              </span>
            ) : (
              <span className="shrink-0 text-[10px] text-amber animate-blink">▌</span>
            )}
            <span className="shrink-0 text-[9px] text-line2 group-hover:text-dim">
              {isOpen ? "▾" : "▸"}
            </span>
          </button>

          {res && (
            <div className="ml-7 text-[11px] text-fg">
              <span className="text-line2">→ </span>
              {res.note || res.summary}
            </div>
          )}

          {isOpen && res && (
            <div className="ml-7 mt-1.5 space-y-1.5 animate-fade-in">
              <Labelled label="cypher">
                <pre className="hair overflow-x-auto bg-ink px-2 py-1.5 text-[10px] leading-relaxed text-cyan">
                  {res.cypher}
                </pre>
              </Labelled>
              <Labelled label={`touched ${res.path.nodes.length} nodes, ${res.path.edges.length} edges`}>
                <div className="flex flex-wrap gap-1">
                  {res.path.nodes.slice(0, 18).map((n, k) => (
                    <span key={k} className="hair bg-panel2 px-1 py-px text-[9px] text-dim">
                      {String(n.name ?? n.id)}
                    </span>
                  ))}
                </div>
              </Labelled>
              <Labelled label="result">
                <pre className="hair max-h-44 overflow-auto bg-ink px-2 py-1.5 text-[9.5px] leading-relaxed text-dim">
                  {JSON.stringify(res.data, null, 2)}
                </pre>
              </Labelled>
            </div>
          )}
        </div>,
      );
    } else if (e.type === "handoff") {
      rows.push(
        <div key={i} className="my-2 flex items-center gap-2 text-[10px] text-violet animate-fade-in">
          <span className="h-px flex-1 bg-violet/25" />
          <span>
            handoff {e.from} → {e.to} · written to graph as {e.step_id?.slice(0, 22)}
          </span>
          <span className="h-px flex-1 bg-violet/25" />
        </div>,
      );
    } else if (e.type === "write") {
      rows.push(
        <div key={i} className="mt-1.5 flex items-center gap-2 border-l-2 border-green pl-2 text-[11px] text-green animate-slide-in">
          <span>✎</span>
          <span>
            wrote <span className="font-bold">{e.kind}</span> to the graph
          </span>
        </div>,
      );
    } else if (e.type === "error") {
      rows.push(
        <div key={i} className="mt-1.5 border-l-2 border-amber bg-amber/5 pl-2 text-[10.5px] leading-relaxed text-amber animate-fade-in">
          {e.message}
        </div>,
      );
    }
  });

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PaneHeader title="agent stream" right={
        <label className="flex cursor-pointer items-center gap-1.5 text-[10px] text-dim">
          <input
            type="checkbox"
            checked={pinned}
            onChange={(e) => setPinned(e.target.checked)}
            className="h-2.5 w-2.5 accent-cyan"
          />
          follow
        </label>
      } />
      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
        {rows.length === 0 ? (
          <div className="py-10 text-center text-[11px] text-dim">
            {running ? "waiting for the first step…" : "no run yet"}
          </div>
        ) : (
          rows
        )}
      </div>
    </div>
  );
}

export function PaneHeader({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <div className="flex shrink-0 items-center justify-between border-b border-line bg-panel2 px-3 py-1.5">
      <span className="text-[10px] uppercase tracking-[0.18em] text-dim">{title}</span>
      {right}
    </div>
  );
}

function Labelled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-0.5 text-[9px] uppercase tracking-wider text-line2">{label}</div>
      {children}
    </div>
  );
}

function fmt(v: unknown) {
  const s = typeof v === "string" ? v : JSON.stringify(v);
  return s && s.length > 46 ? `${s.slice(0, 46)}…` : s;
}
