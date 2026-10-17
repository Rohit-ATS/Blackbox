"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Core, ElementDefinition } from "cytoscape";
import type { Event, Topology } from "@/lib/types";

/**
 * The live service graph.
 *
 * All 42 services sit faint in the background. As the agent calls tools, the
 * subgraph each call touched is lit: affected services fills red by hop depth, the
 * causal path glows amber and draws in sequence, deploys and people appear as
 * satellites. Traversed edges carry the measured per-hop latency in ms, which
 * is the thing worth staring at -- those are real FalkorDB timings.
 */

type Highlight = {
  tool: string;
  nodes: string[];
  edges: { source: string; target: string; rel: string; criticality?: number }[];
  latencyMs: number;
  byHop?: { hops: number; new_services: string[]; latency_ms: number }[];
  chain?: string[];
};

const TIER_SIZE: Record<number, number> = { 1: 26, 2: 21, 3: 16 };

export default function GraphPane({
  topology,
  events,
  running,
  focusNodes,
}: {
  topology: Topology | null;
  events: Event[];
  running: boolean;
  focusNodes: string[];
}) {
  const container = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [ready, setReady] = useState(false);
  const [epoch, setEpoch] = useState(0);
  const [hover, setHover] = useState<string | null>(null);

  // ---- derive what should be lit, from the event stream ------------------ //
  const highlight = useMemo<Highlight | null>(() => {
    const results = events.filter((e) => e.type === "tool_result") as Extract<
      Event,
      { type: "tool_result" }
    >[];
    const last = results[results.length - 1];
    if (!last) return null;
    return {
      tool: last.tool,
      nodes: (last.path?.nodes ?? [])
        .map((n) => (n.name ?? n.id) as string)
        .filter(Boolean),
      edges: (last.path?.edges ?? []) as Highlight["edges"],
      latencyMs: last.latency_ms,
      byHop: last.tool === "affected_services" ? last.data?.by_hop : undefined,
      chain: last.tool === "causal_path" ? last.data?.propagation : undefined,
    };
  }, [events]);

  // everything touched across the whole run, so earlier steps stay visible
  const touchedAll = useMemo(() => {
    const set = new Set<string>();
    for (const e of events) {
      if (e.type === "tool_result") {
        for (const n of e.path?.nodes ?? []) {
          const key = (n.name ?? n.id) as string;
          if (key) set.add(key);
        }
      }
    }
    return set;
  }, [events]);

  const affected = useMemo(() => {
    const r = [...events].reverse().find(
      (e) => e.type === "tool_result" && e.tool === "affected_services",
    ) as Extract<Event, { type: "tool_result" }> | undefined;
    if (!r) return null;
    const byHop = new Map<string, number>();
    for (const s of r.data?.services ?? []) byHop.set(s.name, s.hops);
    return { source: r.data?.source as string, byHop, data: r.data };
  }, [events]);

  const causal = useMemo(() => {
    const r = [...events].reverse().find(
      (e) => e.type === "tool_result" && e.tool === "causal_path",
    ) as Extract<Event, { type: "tool_result" }> | undefined;
    return (r?.data?.propagation as string[] | undefined) ?? null;
  }, [events]);

  // ---- build the graph once -------------------------------------------- //
  useEffect(() => {
    if (!container.current || !topology) return;
    let destroyed = false;
    let cy: Core | null = null;

    (async () => {
      const cytoscape = (await import("cytoscape")).default;
      const coseBilkent = (await import("cytoscape-cose-bilkent")).default as any;
      try {
        cytoscape.use(coseBilkent);
      } catch {
        /* already registered on a fast refresh */
      }
      if (destroyed || !container.current) return;

      const elements: ElementDefinition[] = [
        ...topology.nodes.map((n) => ({
          data: {
            id: n.name as string,
            label: n.name as string,
            tier: n.tier ?? 3,
            rc: n.revenue_critical ? 1 : 0,
            cf: n.customer_facing ? 1 : 0,
            team: n.team ?? "",
            lang: n.language ?? "",
            kind: "service",
          },
        })),
        ...topology.edges.map((e) => ({
          data: {
            id: `${e.source}->${e.target}`,
            source: e.source,
            target: e.target,
            criticality: e.criticality,
            protocol: e.protocol,
            label: "",
          },
        })),
      ];

      cy = cytoscape({
        container: container.current,
        elements,
        minZoom: 0.25,
        maxZoom: 3,
        style: [
          {
            selector: "node",
            style: {
              "background-color": "#1c1b1c",
              "border-width": 1,
              "border-color": "#3a373a",
              width: (el: any) => TIER_SIZE[el.data("tier")] ?? 16,
              height: (el: any) => TIER_SIZE[el.data("tier")] ?? 16,
              label: "data(label)",
              color: "#6e6a6e",
              "font-family": "ui-monospace, Menlo, Consolas, monospace",
              "font-size": 7.5,
              "text-valign": "bottom",
              "text-margin-y": 4,
              "text-opacity": 0.75,
              "transition-property": "background-color, border-color, width, height, color",
              "transition-duration": 220,
            } as any,
          },
          {
            selector: 'node[rc = 1]',
            style: { "border-color": "#4a494b" } as any,
          },
          {
            selector: "edge",
            style: {
              width: (el: any) => 0.4 + (el.data("criticality") ?? 1) * 0.18,
              "line-color": "#2a2729",
              "curve-style": "bezier",
              "target-arrow-shape": "triangle",
              "target-arrow-color": "#2a2729",
              "arrow-scale": 0.5,
              opacity: 0.55,
              "transition-property": "line-color, width, opacity, target-arrow-color",
              "transition-duration": 220,
            } as any,
          },
          // ---- the alerting service
          {
            selector: "node.origin",
            style: {
              "background-color": "#ff1900",
              "border-color": "#ff9b8d",
              "border-width": 2.5,
              color: "#ffd8d2",
              "font-size": 10,
              "font-weight": "bold",
              width: 34, height: 34,
              "text-valign": "bottom",
            } as any,
          },
          // ---- affected services, shaded by hop distance
          { selector: "node.hop1", style: { "background-color": "#e73825", "border-color": "#f0836f", color: "#f5c0b6", "font-size": 9 } as any },
          { selector: "node.hop2", style: { "background-color": "#a82a18", "border-color": "#c9705f", color: "#dfa89c", "font-size": 8.5 } as any },
          { selector: "node.hop3", style: { "background-color": "#6e2616", "border-color": "#a05c4c", color: "#c59a8f" } as any },
          { selector: "node.hop4", style: { "background-color": "#482013", "border-color": "#7a483c", color: "#ab8a81" } as any },
          {
            selector: "node.customer-facing",
            style: { "border-width": 3, "border-color": "#fafafa", "border-style": "double" } as any,
          },
          // ---- causal chain
          {
            selector: "node.causal",
            style: {
              "background-color": "#9780ff",
              "border-color": "#c8c8c8",
              "border-width": 2.5,
              color: "#ded4ff",
              "font-size": 10,
              "font-weight": "bold",
              width: 30, height: 30,
            } as any,
          },
          {
            selector: "edge.causal",
            style: {
              "line-color": "#9780ff",
              "target-arrow-color": "#9780ff",
              width: 3,
              opacity: 1,
              label: "data(label)",
              color: "#b9a6ff",
              "font-size": 8,
              "text-background-color": "#0c0b0c",
              "text-background-opacity": 0.95,
              "text-background-padding": 2,
              "text-rotation": "autorotate",
            } as any,
          },
          // ---- generic traversed edge, carries the latency label
          {
            selector: "edge.traversed",
            style: {
              "line-color": "#e73825",
              "target-arrow-color": "#e73825",
              width: 1.9,
              opacity: 0.95,
              label: "data(label)",
              color: "#ff9b8d",
              "font-size": 7,
              "text-background-color": "#0c0b0c",
              "text-background-opacity": 0.92,
              "text-background-padding": 2,
              "text-rotation": "autorotate",
            } as any,
          },
          // ---- satellites: deploys, PRs, people, postmortems
          {
            // `width: "label"` is deprecated in cytoscape 3 and renders as an
            // oversized blob, so the width is computed from the text instead.
            selector: "node.satellite",
            style: {
              "background-color": "#141314",
              "background-opacity": 0.95,
              "border-color": "#4a494b",
              "border-width": 1.5,
              shape: "round-rectangle",
              width: (el: any) =>
                Math.max(44, String(el.data("label") ?? "").length * 5.1 + 12),
              height: 16,
              label: "data(label)",
              color: "#c8c8c8",
              "font-size": 7.5,
              "text-valign": "center",
              "text-halign": "center",
            } as any,
          },
          {
            selector: "node.satellite-write",
            style: { "border-color": "#edc5fc", color: "#edc5fc" } as any,
          },
          {
            selector: "edge.satellite",
            style: {
              "line-color": "#3a373a",
              "target-arrow-color": "#3a373a",
              "line-style": "dashed",
              width: 1,
              opacity: 0.8,
            } as any,
          },
          { selector: "node.faded", style: { opacity: 0.18 } as any },
          { selector: "edge.faded", style: { opacity: 0.08 } as any },
          {
            selector: "node.pulse",
            style: { "border-width": 4, "border-opacity": 0.9 } as any,
          },
        ],
        layout: {
          name: "cose-bilkent",
          animate: false,
          nodeDimensionsIncludeLabels: true,
          idealEdgeLength: 62,
          nodeRepulsion: 7000,
          gravity: 0.3,
          numIter: 2500,
          randomize: false,
        } as any,
      });

      cy.on("mouseover", "node", (e) => setHover(e.target.id()));
      cy.on("mouseout", "node", () => setHover(null));

      cyRef.current = cy;
      // Handy when poking at the instrument from the devtools console.
      (window as unknown as { __cy?: Core }).__cy = cy;
      setReady(true);
      setEpoch((e) => e + 1);
    })().catch((err) => {
      console.error("[GraphPane] could not build the graph", err);
    });

    return () => {
      destroyed = true;
      cy?.destroy();
      cyRef.current = null;
      setReady(false);
    };
  }, [topology]);

  // ---- repaint on every new event --------------------------------------- //
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !ready) return;

    cy.batch(() => {
      cy.elements().removeClass(
        "origin hop1 hop2 hop3 hop4 customer-facing causal traversed faded pulse",
      );
      // drop satellites from the previous step
      cy.nodes(".satellite").remove();

      if (affected) {
        const origin = cy.getElementById(affected.source);
        origin.addClass("origin");
        affected.byHop.forEach((hops, name) => {
          const n = cy.getElementById(name);
          if (n.nonempty()) {
            n.addClass(`hop${Math.min(hops, 4)}`);
            const cf = (affected.data?.customer_facing ?? []) as string[];
            if (cf.includes(name)) n.addClass("customer-facing");
          }
        });

        // label the IMPACTS edges inside the affected set with the per-hop time
        const hopLatency = new Map<number, number>();
        for (const lvl of (affected.data?.by_hop ?? []) as any[]) {
          hopLatency.set(lvl.hops, lvl.latency_ms);
        }
        for (const [name, hops] of affected.byHop) {
          const n = cy.getElementById(name);
          if (n.empty()) continue;
          n.connectedEdges().forEach((edge: any) => {
            const other =
              edge.source().id() === name ? edge.target().id() : edge.source().id();
            if (other === affected.source || affected.byHop.has(other)) {
              edge.addClass("traversed");
              const ms = hopLatency.get(hops);
              if (ms !== undefined && !edge.data("label")) {
                edge.data("label", `${ms.toFixed(1)}ms`);
              }
            }
          });
        }
      }

      if (causal && causal.length > 1) {
        causal.forEach((name) => {
          const n = cy.getElementById(name);
          if (n.nonempty()) n.addClass("causal");
        });
        for (let i = 0; i < causal.length - 1; i++) {
          // propagation runs cause -> symptom, the DEPENDS_ON edge the other way
          const edge = cy.getElementById(`${causal[i + 1]}->${causal[i]}`);
          if (edge.nonempty()) {
            edge.addClass("causal");
            edge.data("label", "propagates");
          }
        }
      }

      // satellites for the current step: deploys, PRs, people, postmortems
      if (highlight) {
        const anchor = affected?.source ?? highlight.nodes[0];
        const sats = (events
          .filter((e) => e.type === "tool_result")
          .slice(-1)[0] as Extract<Event, { type: "tool_result" }> | undefined)
          ?.path?.nodes ?? [];

        for (const n of sats) {
          const label = n._label;
          if (!label || label === "Service") continue;
          const id = (n.id ?? n.name) as string;
          if (!id || cy.getElementById(id).nonempty()) continue;

          let text = id;
          if (label === "PullRequest") text = `PR #${n.number}`;
          else if (label === "Deploy") text = `deploy ${String(n.sha ?? "").slice(0, 7)}`;
          else if (label === "Person") text = String(n.name ?? id);
          else if (label === "Postmortem") text = `postmortem ${id}`;
          else if (label === "Incident") text = String(id);
          else if (label === "Runbook") text = `runbook`;

          const isWrite = label === "Postmortem";
          cy.add({
            group: "nodes",
            data: { id, label: text, kind: "satellite" },
            classes: `satellite${isWrite ? " satellite-write" : ""}`,
            position: anchorPosition(cy, anchor),
          });
          const near = nearestService(n, highlight, affected?.source);
          if (near && cy.getElementById(near).nonempty()) {
            cy.add({
              group: "edges",
              data: { id: `sat-${id}`, source: id, target: near, label: "" },
              classes: "satellite",
            });
          }
        }
      }

      // fade anything the run has not touched, once it has touched something
      if (touchedAll.size > 0) {
        cy.nodes().forEach((n: any) => {
          const id = n.id();
          const lit =
            n.hasClass("origin") || n.hasClass("causal") || n.hasClass("satellite") ||
            /hop[1-4]/.test(n.classes().join(" ")) || touchedAll.has(id);
          if (!lit) n.addClass("faded");
        });
        cy.edges().forEach((e: any) => {
          if (!e.hasClass("traversed") && !e.hasClass("causal") && !e.hasClass("satellite")) {
            e.addClass("faded");
          }
        });
      }
    });

    // gently keep the lit region in frame
    const lit = cy.elements(".origin, .causal, .hop1, .hop2, .satellite");
    if (lit.nonempty()) {
      cy.animate({ fit: { eles: lit.union(lit.connectedEdges()), padding: 70 } },
                 { duration: 420 });
    }
  }, [highlight, affected, causal, touchedAll, events, ready, epoch]);

  // focus a node when a citation is hovered in the answer card
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !ready) return;
    cy.nodes().removeClass("pulse");
    for (const name of focusNodes) {
      const n = cy.getElementById(name);
      if (n.nonempty()) n.addClass("pulse");
    }
  }, [focusNodes, ready, epoch]);

  const hovered = topology?.nodes.find((n) => n.name === hover);

  return (
    <div className="relative h-full w-full grid-bg">
      <div ref={container} className="absolute inset-0" />

      {!topology && (
        <div className="absolute inset-0 flex items-center justify-center text-dim text-xs">
          <div className="text-center">
            <div className="mb-2 text-red">backend unreachable</div>
            <div>start it with <span className="text-fg">docker compose up</span></div>
          </div>
        </div>
      )}

      {/* legend */}
      <div className="absolute bottom-3 left-3 hair bg-panel/90 px-3 py-2 text-[10px] leading-relaxed backdrop-blur">
        <div className="mb-1 text-dim uppercase tracking-wider">legend</div>
        <Row color="#ff1900" label="alerting service" />
        <Row color="#e73825" label="affected services (shade = hops)" />
        <Row color="#fafafa" label="customer-facing" ring />
        <Row color="#9780ff" label="causal path" />
        <Row color="#4a494b" label="deploy / PR / person" />
        <Row color="#edc5fc" label="written back by BLACKBOX" />
      </div>

      {/* hovered node inspector */}
      {hovered && (
        <div className="absolute right-3 top-3 hair max-w-[260px] bg-panel/95 px-3 py-2 text-[11px] backdrop-blur animate-fade-in">
          <div className="font-bold text-bright">{hovered.name}</div>
          <div className="mt-1 text-dim">{hovered.description}</div>
          <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-dim">
            <span>tier {hovered.tier}</span>
            <span>{hovered.language}</span>
            {hovered.team && <span>{hovered.team}</span>}
            {hovered.revenue_critical && <span className="text-red">revenue-critical</span>}
            {hovered.customer_facing && <span className="text-amber">customer-facing</span>}
          </div>
        </div>
      )}

      {/* what the last tool call did */}
      {highlight && (
        <div className="absolute left-3 top-3 hair bg-panel/90 px-3 py-1.5 text-[11px] backdrop-blur">
          <span className="text-dim">traversal</span>{" "}
          <span className="text-bright">{highlight.tool}</span>
          <span className="mx-2 text-line2">│</span>
          <span className="tnum text-green">{highlight.latencyMs.toFixed(2)}ms</span>
          {running && <span className="ml-2 text-amber animate-blink">▌</span>}
        </div>
      )}
    </div>
  );
}

function Row({ color, label, ring }: { color: string; label: string; ring?: boolean }) {
  return (
    <div className="flex items-center gap-2 text-dim">
      <span
        className="inline-block h-2 w-2 shrink-0"
        style={ring
          ? { border: `2px double ${color}` }
          : { background: color }}
      />
      {label}
    </div>
  );
}

function anchorPosition(cy: Core, anchor?: string) {
  if (anchor) {
    const n = cy.getElementById(anchor);
    if (n.nonempty()) {
      const p = n.position();
      return { x: p.x + (Math.random() - 0.5) * 150, y: p.y + (Math.random() - 0.5) * 150 };
    }
  }
  const ext = cy.extent();
  return { x: (ext.x1 + ext.x2) / 2, y: (ext.y1 + ext.y2) / 2 };
}

/** Attach a satellite to the service it is about, when we can tell. */
function nearestService(node: any, highlight: Highlight, fallback?: string) {
  for (const e of highlight.edges) {
    if (e.source === (node.id ?? node.name)) return e.target;
    if (e.target === (node.id ?? node.name)) return e.source;
  }
  return fallback;
}
