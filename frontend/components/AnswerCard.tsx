"use client";

import type { Answer } from "@/lib/types";
import { PaneHeader } from "./AgentStream";

/**
 * The answer card. Every claim carries a superscript citation; hovering one
 * pulses the nodes it came from in the graph pane. Nothing here is asserted
 * without a node behind it.
 */
export default function AnswerCard({
  answer,
  onFocus,
}: {
  answer: Answer | null;
  onFocus: (nodes: string[]) => void;
}) {
  if (!answer) {
    return (
      <div className="flex h-full flex-col">
        <PaneHeader title="answer" />
        <div className="flex flex-1 items-center justify-center px-4 text-center text-[11px] text-dim">
          the answer card fills in as the agents finish
        </div>
      </div>
    );
  }

  const cite = (n?: number) => {
    if (!n) return null;
    const c = answer.citations.find((x) => x.n === n);
    return (
      <sup
        onMouseEnter={() => onFocus((c?.nodes.filter(Boolean) as string[]) ?? [])}
        onMouseLeave={() => onFocus([])}
        className="ml-0.5 cursor-help text-[9px] text-cyan hover:text-bright"
        title={c?.label ? `${c.label}  ·  via ${c.tool}` : undefined}
      >
        [{n}]
      </sup>
    );
  };

  const rc = answer.root_cause;
  const page = answer.page;
  const mem = answer.memory;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PaneHeader
        title="answer"
        right={
          <span className="text-[10px] text-dim">
            {answer.incident_id} · {answer.severity}
          </span>
        }
      />
      <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto px-3 py-2.5 text-[11.5px] leading-relaxed">
        {rc && (
          <Field label="root cause" tone="red">
            <div className="text-bright">
              PR <span className="font-bold">#{rc.pr_number}</span> → {rc.service}
              {cite(rc.citation)}
            </div>
            <div className="text-dim">
              {rc.file && <span className="text-fg">{rc.file}</span>}
              {rc.file && " · "}
              {rc.author}
              {" · "}
              {rc.hops_upstream
                ? `${rc.hops_upstream} hop${rc.hops_upstream === 1 ? "" : "s"} upstream`
                : "on the alerting service"}
            </div>
          </Field>
        )}

        {answer.propagation && (
          <Field label="propagation" tone="amber">
            <div className="flex flex-wrap items-center gap-x-1 gap-y-0.5">
              {answer.propagation.chain.map((s, i) => (
                <span key={s} className="flex items-center gap-1">
                  {i > 0 && <span className="text-amber">→</span>}
                  <span className="text-bright">{s}</span>
                </span>
              ))}
              {cite(answer.propagation.citation)}
            </div>
          </Field>
        )}

        {answer.blast_radius && (
          <Field label="blast radius" tone="red">
            <div>
              <span className="tnum font-bold text-bright">
                {answer.blast_radius.count}
              </span>{" "}
              <span className="text-dim">services degrade with it</span>
              {cite(answer.blast_radius.citation)}
            </div>
            {answer.blast_radius.customer_facing.length > 0 && (
              <div className="text-dim">
                customer-facing:{" "}
                <span className="text-amber">
                  {answer.blast_radius.customer_facing.join(", ")}
                </span>
              </div>
            )}
          </Field>
        )}

        {page && (
          <Field label="page" tone="cyan">
            <div className="text-bright">
              {page.name}
              <span className="text-dim">
                {page.handle ? ` @${page.handle}` : ""}
                {page.timezone ? ` · ${page.timezone}` : ""}
              </span>
              {cite(page.citation)}
            </div>
            <div className="text-dim">
              {page.commits} commits on the file
              {page.prior_incidents_on_file
                ? ` · ${page.prior_incidents_on_file} prior incident${page.prior_incidents_on_file === 1 ? "" : "s"} on it`
                : ""}
            </div>
            {page.instead_of_on_call && page.instead_of_on_call !== page.name && (
              <div className="text-amber">
                not the rotation default ({page.instead_of_on_call})
              </div>
            )}
          </Field>
        )}

        {mem && (
          <Field label="memory" tone={mem.self_authored ? "green" : "violet"}>
            <div className="text-bright">
              {mem.postmortem_id}
              {cite(mem.citation)}
            </div>
            <div className="text-dim">
              {mem.self_authored ? (
                <span className="text-green">
                  written by BLACKBOX on {mem.incident_id}
                </span>
              ) : (
                <span>from seeded history ({mem.incident_id})</span>
              )}
              {mem.similarity !== undefined && (
                <span className="tnum"> · similarity {mem.similarity.toFixed(3)}</span>
              )}
            </div>
            {mem.lesson && (
              <div className="mt-1 border-l border-line2 pl-2 text-[10.5px] text-dim">
                {mem.lesson}
              </div>
            )}
          </Field>
        )}

        {answer.fix && (
          <Field label="runbook" tone="violet">
            <div className="text-bright">
              {answer.fix.runbook}
              {cite(answer.fix.citation)}
            </div>
            {answer.fix.body && (
              <pre className="mt-1 whitespace-pre-wrap border-l border-line2 pl-2 text-[10px] leading-relaxed text-dim">
                {answer.fix.body}
              </pre>
            )}
          </Field>
        )}

        {answer.wrote.length > 0 && (
          <Field label="written back to the graph" tone="green">
            <div className="flex flex-wrap gap-1">
              {answer.wrote.map((w) => (
                <span key={w} className="hair border-green/40 bg-green/10 px-1.5 py-px text-[10px] text-green">
                  {w}
                </span>
              ))}
            </div>
          </Field>
        )}

        {Object.entries(answer.narration).length > 0 && (
          <Field label="status update" tone="dim">
            <div className="space-y-1.5">
              {Object.entries(answer.narration).map(([agent, text]) => (
                <div key={agent}>
                  <span className="text-[9px] uppercase tracking-wider text-line2">
                    {agent}
                  </span>
                  <div className="text-dim">{text}</div>
                </div>
              ))}
            </div>
          </Field>
        )}
      </div>
    </div>
  );
}

const TONE: Record<string, string> = {
  red: "border-red/50",
  amber: "border-amber/50",
  cyan: "border-cyan/50",
  green: "border-green/50",
  violet: "border-violet/50",
  dim: "border-line2",
};

function Field({
  label,
  tone,
  children,
}: {
  label: string;
  tone: keyof typeof TONE;
  children: React.ReactNode;
}) {
  return (
    <div className={`border-l-2 pl-2.5 animate-slide-in ${TONE[tone]}`}>
      <div className="mb-0.5 text-[9px] uppercase tracking-[0.15em] text-line2">
        {label}
      </div>
      {children}
    </div>
  );
}
