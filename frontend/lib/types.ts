// Mirrors the SSE event contract frozen in backend/blackbox/agents.py.
// Changing anything here means changing it there too.

export type AgentName = "Triage" | "Investigator" | "Comms";

export interface GraphNode {
  name?: string;
  id?: string;
  _label?: string;
  tier?: number;
  revenue_critical?: boolean;
  customer_facing?: boolean;
  language?: string;
  description?: string;
  team?: string;
  hops?: number;
  [k: string]: unknown;
}

export interface GraphEdge {
  source: string;
  target: string;
  rel: string;
  criticality?: number;
  protocol?: string;
}

export interface TouchedPath {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Topology {
  tenant: string;
  latency_ms: number;
  nodes: GraphNode[];
  edges: { source: string; target: string; criticality: number; protocol: string }[];
}

export interface Alert {
  id: string;
  metric: string;
  value: number;
  threshold: number;
  service: string;
}

export interface MemoryState {
  self_authored_postmortems: number;
  seeded_postmortems: number;
  agent_steps: number;
}

export interface Citation {
  n: number;
  label: string;
  nodes: (string | null)[];
  tool: string;
}

export interface Answer {
  incident_id: string;
  title: string;
  service?: string;
  severity: string;
  root_cause?: {
    text: string; pr_number: number; service: string; file?: string;
    author?: string; hops_upstream?: number; citation: number;
  } | null;
  affected_services?: { count: number; customer_facing: string[]; citation: number } | null;
  propagation?: { chain: string[]; citation: number } | null;
  page?: {
    name: string; handle?: string; role?: string; timezone?: string; team?: string;
    commits?: number; prior_incidents_on_file?: number;
    instead_of_on_call?: string; citation: number;
  } | null;
  memory?: {
    postmortem_id: string; incident_id?: string; lesson?: string;
    similarity?: number; self_authored?: boolean; written_by?: string; citation: number;
  } | null;
  fix?: { runbook: string; body?: string; citation: number } | null;
  narration: Record<string, string>;
  wrote: string[];
  citations: Citation[];
}

export interface RunMetrics {
  run_id: string;
  elapsed_ms: number;
  tool_calls: number;
  graph_latency_ms: number;
  hops: number;
  wrote: string[];
  recalled_memory: boolean;
  recalled_own_postmortem: boolean;
  mode: string;
  memory: MemoryState;
}

export type Event =
  | ({ type: "run_start"; at: number; run_id: string; scenario: string; tenant: string;
       incident_id: string; alert: Alert; symptom: string; title: string; severity: string;
       mode: string; narrative: string; memory: MemoryState })
  | ({ type: "agent_start"; at: number; agent: AgentName; tools: string[] })
  | ({ type: "thought"; at: number; agent: AgentName; text: string })
  | ({ type: "tool_call"; at: number; agent: AgentName; tool: string;
       args: Record<string, unknown>; step: number })
  | ({ type: "tool_result"; at: number; agent: AgentName; tool: string; step: number;
       summary: string; note: string; latency_ms: number; data: any;
       path: TouchedPath; cypher: string; step_id: string })
  | ({ type: "handoff"; at: number; from: AgentName; to: AgentName; step_id: string })
  | ({ type: "write"; at: number; kind: string; detail: any; path: TouchedPath })
  | ({ type: "answer"; at: number; answer: Answer })
  | ({ type: "run_end"; at: number } & RunMetrics)
  | ({ type: "error"; at: number; message: string });

export const AGENT_COLOR: Record<AgentName, string> = {
  Triage: "text-cyan",
  Investigator: "text-amber",
  Comms: "text-green",
};

export const AGENT_BG: Record<AgentName, string> = {
  Triage: "bg-cyan/10 border-cyan/40 text-cyan",
  Investigator: "bg-amber/10 border-amber/40 text-amber",
  Comms: "bg-green/10 border-green/40 text-green",
};

export const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

/** Set at build time for the GitHub Pages deployment (a project page). */
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

/**
 * Replay mode.
 *
 * GitHub Pages serves static files, so there is no FastAPI backend and no
 * FalkorDB behind the published site. Rather than ship a console that errors,
 * the build flips this on and the UI replays `fixtures/*.json` -- the runs
 * recorded by `python -m blackbox.record_fixtures`, which are byte-identical
 * to what the SSE endpoint sends.
 *
 * Everything on screen is then real output from a real run against a real
 * graph; it just happened earlier, on someone else's machine. The UI says so.
 */
export const REPLAY_BUILD = process.env.NEXT_PUBLIC_REPLAY === "1";

export const fixtureUrl = (name: string) => `${BASE_PATH}/fixtures/${name}`;
