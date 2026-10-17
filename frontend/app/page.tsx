import Link from "next/link";
import LiveStat from "@/components/LiveStat";

export default function Landing() {
  return (
    <div className="min-h-screen bg-ink">
      {/* ───────────────────────────── nav ───────────────────────────── */}
      <nav className="sticky top-0 z-20 border-b border-line bg-ink/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-3">
          <span className="text-sm font-bold tracking-[0.22em] text-bright">BLACKBOX</span>
          <span className="hidden text-[10px] text-dim md:inline">
            Graph Hacks · FalkorDB × WeMakeDevs
          </span>
          <div className="ml-auto flex items-center gap-4 text-[11px]">
            <a href="#how" className="text-dim hover:text-bright">how</a>
            <a href="#graph" className="text-dim hover:text-bright">graph</a>
            <a href="#tracks" className="hidden text-dim hover:text-bright sm:inline">tracks</a>
            <a
              href="https://github.com/Rohit-ATS/GraphHacks"
              className="hidden text-dim hover:text-bright sm:inline"
            >
              source
            </a>
            <Link
              href="/console"
              className="hair border-cyan/50 bg-cyan/10 px-3 py-1.5 text-cyan hover:bg-cyan/20"
            >
              open console ▸
            </Link>
          </div>
        </div>
      </nav>

      {/* ───────────────────────────── hero ───────────────────────────── */}
      <header className="relative overflow-hidden border-b border-line grid-bg">
        <div className="pointer-events-none absolute -right-40 -top-40 h-[520px] w-[520px] rounded-full bg-red/[0.07] blur-3xl" />
        <div className="pointer-events-none absolute -bottom-52 left-1/4 h-[420px] w-[420px] rounded-full bg-cyan/[0.05] blur-3xl" />

        <div className="relative mx-auto max-w-6xl px-6 py-20 md:py-28">
          <div className="mb-5 inline-flex items-center gap-2 border border-line2 bg-panel/70 px-2.5 py-1 text-[10px] text-dim">
            <span className="inline-block h-1.5 w-1.5 animate-pulse-node bg-red" />
            incident response, as a graph problem
          </div>

          <h1 className="max-w-[17ch] text-4xl font-bold leading-[1.06] tracking-tight text-bright md:text-6xl">
            The on-call agent that knows what breaks next
            <span className="text-dim"> — and gets smarter every incident.</span>
          </h1>

          <p className="mt-7 max-w-2xl text-[13.5px] leading-relaxed text-fg md:text-[15px]">
            Production breaks. BLACKBOX reads your service graph, maps everything
            degrading with it, finds the change that caused it two hops upstream, recalls the last
            time this happened, pages the human who actually knows — then{" "}
            <span className="text-bright">writes what it learned back into the graph</span>,
            so the next incident resolves in one hop instead of six.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link
              href="/console"
              className="hair border-cyan/60 bg-cyan/10 px-5 py-2.5 text-[12.5px] text-cyan transition-colors hover:bg-cyan/20"
            >
              ▸ run the live demo
            </Link>
            <a
              href="#money"
              className="hair px-5 py-2.5 text-[12.5px] text-fg transition-colors hover:bg-panel2"
            >
              see the 11 → 8 moment
            </a>
            <span className="text-[11px] text-dim">no sign-up, no auth, nothing to configure</span>
          </div>

          <LiveStat />
        </div>
      </header>

      {/* ───────────────────── the problem, as a cost ───────────────────── */}
      <section className="border-b border-line">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-16 md:grid-cols-[1.1fr_1fr]">
          <div>
            <SectionLabel>the first twenty minutes</SectionLabel>
            <h2 className="mt-3 text-2xl font-bold leading-snug text-bright md:text-3xl">
              Nobody is confused about <span className="text-dim">what</span> is broken.
              They are confused about <span className="text-red">what else</span>, and{" "}
              <span className="text-amber">who to call</span>.
            </h2>
            <p className="mt-5 text-[13px] leading-relaxed text-fg">
              An alert tells you one service is slow. It does not tell you that eleven
              services sit downstream of it, that three of those are customer-facing, or
              that the actual cause was a pull request merged twenty-three minutes ago
              against a <em className="not-italic text-bright">different service, two hops away</em>.
            </p>
            <p className="mt-4 text-[13px] leading-relaxed text-fg">
              That is not a retrieval problem. No amount of embedding your runbooks
              answers it, because the answer is not written down anywhere — it lives in
              how things connect. Ask a vector store &ldquo;what breaks if ledger-service goes
              down&rdquo; and it will cheerfully explain what a connection pool is.
            </p>
          </div>

          <div className="hair bg-panel p-5">
            <div className="mb-3 text-[10px] uppercase tracking-[0.18em] text-line2">
              the questions that need a traversal
            </div>
            <ul className="space-y-3 text-[12.5px]">
              {[
                ["What breaks if this service goes down?", "reachability over DEPENDS_ON, weighted by criticality"],
                ["What changed near this, recently?", "variable-length upstream walk, time-filtered"],
                ["How did a failure there surface here?", "criticality-weighted shortest path"],
                ["Who has actually worked on this system?", "WORKED_ON → BELONGS_TO, ranked by commits and prior incidents"],
                ["Have we seen this exact failure before?", "vector search over incidents and postmortems"],
              ].map(([q, how]) => (
                <li key={q} className="border-l-2 border-line2 pl-3">
                  <div className="text-bright">{q}</div>
                  <div className="text-[11px] text-dim">{how}</div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ───────────────────────── the money moment ───────────────────────── */}
      <section id="money" className="border-b border-line bg-panel/40">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <SectionLabel>the part that matters</SectionLabel>
          <h2 className="mt-3 max-w-3xl text-2xl font-bold leading-snug text-bright md:text-3xl">
            We run the same class of incident twice. The second time, the agent reads
            its own handwriting.
          </h2>

          <div className="mt-10 grid gap-5 md:grid-cols-[1fr_auto_1fr]">
            <RunPanel
              tag="run 1 — cold"
              tone="red"
              service="checkout-api"
              symptom="p99 latency 4200ms, CPU flat"
              steps={[
                ["resolve_entity", "→ checkout-api"],
                ["similar_incidents", "→ a related incident, not conclusive"],
                ["affected_services", "→ 11 services, 3 customer-facing"],
                ["criticality_rank", "→ PageRank over 42 services"],
                ["recent_changes hops=2", "→ PR #4471 on ledger-service"],
                ["causal_path", "→ ledger → payments → checkout"],
                ["get_runbook", "→ connection pool exhaustion"],
                ["who_knows", "→ Priya, not the rotation"],
                ["write_finding ×3", "→ CAUSED_BY, Postmortem, RESOLVED_BY"],
              ]}
              footer="11 tool calls · it had to traverse for all of it"
            />

            <div className="flex items-center justify-center">
              <div className="text-center">
                <div className="text-[10px] uppercase tracking-[0.15em] text-line2">
                  it writes
                </div>
                <div className="my-2 text-3xl text-green">↓</div>
                <div className="hair max-w-[150px] border-green/40 bg-green/[0.07] px-2 py-1.5 text-[10px] leading-relaxed text-green">
                  (:Postmortem)
                  <br />
                  created_by:
                  <br />
                  &apos;blackbox&apos;
                  <br />
                  + embedding
                </div>
              </div>
            </div>

            <RunPanel
              tag="run 2 — warm"
              tone="green"
              service="notifications-api"
              symptom="p99 latency 3800ms, pool exhausted"
              steps={[
                ["resolve_entity", "→ notifications-api"],
                ["similar_incidents", "→ its own postmortem, 0.59"],
                ["affected_services depth=2", "→ impact only; mechanism known"],
                ["recent_changes hops=1", "→ PR #4525, one hop"],
                ["who_knows", "→ Mei Tanaka"],
                ["write_finding ×3", "→ the lesson, extended"],
              ]}
              footer="8 tool calls · the investigation collapsed from 4 steps to 2"
              highlight
            />
          </div>

          <p className="mt-8 max-w-3xl text-[12.5px] leading-relaxed text-dim">
            The second run is not faster because of a cache. It is faster because the
            first run left a node behind, with an embedding on it, and the second run
            found it on its first memory lookup. Delete that node — the{" "}
            <span className="text-fg">forget</span> button in the console does exactly
            that — and the warm run becomes a cold one again.
          </p>
        </div>
      </section>

      {/* ───────────────────────────── how ───────────────────────────── */}
      <section id="how" className="border-b border-line">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <SectionLabel>how it is built</SectionLabel>
          <h2 className="mt-3 text-2xl font-bold text-bright md:text-3xl">
            Nine typed tools. The model never writes Cypher.
          </h2>
          <p className="mt-4 max-w-3xl text-[13px] leading-relaxed text-fg">
            Text-to-Cypher demos beautifully right up until it does not, and when it
            fails you cannot tell whether the model was wrong or the data was. So the
            graph is exposed as nine typed tools instead — traversals and FalkorDB&apos;s
            own algorithms, called as functions. Every one returns the data, the
            subgraph it touched, the exact query that ran, and its latency in
            milliseconds.
          </p>

          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[
              ["resolve_entity", "fulltext", "an alert string becomes a node"],
              ["affected_services", "algo.BFS", "who degrades with it, by hop depth"],
              ["recent_changes", "variable-length walk", "deploys up to N hops upstream"],
              ["causal_path", "algo.SPpaths", "weighted by criticality, not hop count"],
              ["similar_incidents", "vector / HNSW", "the memory tool"],
              ["who_knows", "WORKED_ON ranking", "beats the on-call rotation"],
              ["get_runbook", "fulltext + vector", "hybrid, because either alone misses"],
              ["criticality_rank", "algo.pageRank", "structural, not a spreadsheet tier"],
              ["write_finding", "MERGE + vecf32", "the write-back loop"],
            ].map(([name, how, what]) => (
              <div key={name} className="hair bg-panel p-3.5 transition-colors hover:border-line2">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-[12px] font-bold text-bright">{name}</span>
                  <span className="shrink-0 text-[9.5px] text-cyan">{how}</span>
                </div>
                <div className="mt-1 text-[11px] leading-relaxed text-dim">{what}</div>
              </div>
            ))}
          </div>

          <div className="mt-10 grid gap-5 md:grid-cols-3">
            <Pillar
              title="Three agents, one graph"
              body="Triage → Investigator → Comms, with different prompts and different tools. Handoff state is written to FalkorDB as :AgentStep nodes chained with :NEXT — not passed in process memory. The trace panel is a Cypher query, which is also why a restarted agent could pick up where the last one stopped."
            />
            <Pillar
              title="Memory is data, not a session"
              body="Episodic (what happened), semantic (what it means, as embeddings), procedural (the runbooks). All three are nodes. A postmortem the agent wrote is indistinguishable in kind from one a human wrote — which is the point."
            />
            <Pillar
              title="One instance, isolated graphs"
              body="tenant:acme and tenant:globex are separate graphs on the same FalkorDB. A query against one cannot see the other. Flip the switch in the console: different company, different topology, same engine."
            />
          </div>
        </div>
      </section>

      {/* ───────────────────────────── graph ───────────────────────────── */}
      <section id="graph" className="border-b border-line bg-panel/40">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <SectionLabel>the company, as a graph</SectionLabel>
          <h2 className="mt-3 text-2xl font-bold text-bright md:text-3xl">
            Services, deploys, people, decisions — in one place, with provenance.
          </h2>
          <p className="mt-4 max-w-3xl text-[13px] leading-relaxed text-fg">
            Seeded deterministically, so the demo is identical on every machine. The
            dependency topology is hand-authored rather than random, because the
            interesting questions only have interesting answers if the shape is real:
            there are chains eight hops deep, and two different two-hop routes between
            checkout and the ledger, of which only one is a hard synchronous call.
          </p>

          <div className="mt-8 grid grid-cols-2 gap-px border border-line bg-line sm:grid-cols-4 lg:grid-cols-7">
            {[
              ["42", "services"],
              ["97", "dependencies"],
              ["18", "people"],
              ["320", "deploys"],
              ["11", "past incidents"],
              ["40", "runbooks"],
              ["600", "messages"],
            ].map(([n, label]) => (
              <div key={label} className="bg-panel px-3 py-4 text-center">
                <div className="tnum text-xl font-bold text-bright">{n}</div>
                <div className="mt-0.5 text-[10px] text-dim">{label}</div>
              </div>
            ))}
          </div>

          <div className="mt-6 hair overflow-x-auto bg-ink p-4">
            <div className="mb-2 text-[10px] uppercase tracking-[0.15em] text-line2">
              the traversal behind &ldquo;what breaks if checkout-api degrades&rdquo;
            </div>
            <pre className="text-[11px] leading-relaxed text-cyan">{`MATCH (s:Service {name: $name})
CALL algo.BFS(s, $level, 'IMPACTS') YIELD nodes
UNWIND nodes AS n
RETURN n`}</pre>
            <div className="mt-2 text-[11px] text-dim">
              → 11 services, 3 customer-facing, in{" "}
              <span className="text-green">under 4ms</span>. Run level by level and
              differenced, so every service comes back with the hop count it was
              reached at — which is what the UI prints on the edges.
            </div>
          </div>
        </div>
      </section>

      {/* ───────────────────────────── tracks ───────────────────────────── */}
      <section id="tracks" className="border-b border-line">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <SectionLabel>all three tracks</SectionLabel>
          <h2 className="mt-3 text-2xl font-bold text-bright md:text-3xl">
            Not bolted on. Incident response genuinely needs all three.
          </h2>
          <div className="mt-8 space-y-px border border-line bg-line">
            {[
              ["01", "Agents that act on connected data",
               "Impact BFS, criticality-weighted SPpaths, PageRank — called as agent tools, not reimplemented. Exposed over MCP so you can drive the same nine tools from your own Claude."],
              ["02", "Memory and coordination",
               "Three agents handing off through the graph. Episodic, semantic and procedural memory as nodes. Every tool call is an :AgentStep with provenance edges, and the write-back loop is measurable on screen."],
              ["03", "The company brain",
               "Services, deploys, PRs, files, people, teams, runbooks, Slack threads and ADRs in one graph, with ownership and citations. Every claim on the answer card links back to the node that produced it."],
            ].map(([n, title, body]) => (
              <div key={n} className="grid gap-3 bg-panel p-5 md:grid-cols-[auto_1fr]">
                <div className="text-2xl font-bold text-line2">{n}</div>
                <div>
                  <div className="text-[13px] font-bold text-bright">{title}</div>
                  <div className="mt-1.5 text-[12px] leading-relaxed text-dim">{body}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ───────────────────────────── cta ───────────────────────────── */}
      <section className="border-b border-line grid-bg">
        <div className="mx-auto max-w-6xl px-6 py-20 text-center">
          <h2 className="text-2xl font-bold leading-snug text-bright md:text-4xl">
            The graph isn&apos;t where the agent
            <br className="hidden md:block" /> looks things up.
            <span className="text-dim"> It&apos;s where the agent thinks.</span>
          </h2>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/console"
              className="hair border-cyan/60 bg-cyan/10 px-6 py-3 text-[13px] text-cyan hover:bg-cyan/20"
            >
              ▸ open the console
            </Link>
            <a
              href="https://github.com/Rohit-ATS/GraphHacks"
              className="hair px-6 py-3 text-[13px] text-fg hover:bg-panel2"
            >
              read the source
            </a>
          </div>
          <div className="mx-auto mt-8 max-w-xl hair bg-ink p-3 text-left">
            <pre className="overflow-x-auto text-[11px] leading-relaxed text-green">{`git clone … && cd blackbox
docker compose up          # that is the whole setup`}</pre>
          </div>
        </div>
      </section>

      <footer className="mx-auto max-w-6xl px-6 py-10">
        <div className="flex flex-wrap items-center justify-between gap-3 text-[10.5px] text-dim">
          <span>
            BLACKBOX · built for Graph Hacks (FalkorDB × WeMakeDevs) by{" "}
            <span className="text-fg">Rohit Maruri</span> · @Rohit-ATS
          </span>
          <span>FalkorDB · FastAPI · Next.js · Cytoscape · MIT</span>
        </div>
      </footer>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-[10px] uppercase tracking-[0.2em] text-line2">{children}</span>
      <span className="h-px w-16 bg-line" />
    </div>
  );
}

function Pillar({ title, body }: { title: string; body: string }) {
  return (
    <div className="hair bg-panel p-5">
      <div className="text-[13px] font-bold text-bright">{title}</div>
      <div className="mt-2 text-[12px] leading-relaxed text-dim">{body}</div>
    </div>
  );
}

function RunPanel({
  tag,
  tone,
  service,
  symptom,
  steps,
  footer,
  highlight,
}: {
  tag: string;
  tone: "red" | "green";
  service: string;
  symptom: string;
  steps: string[][];
  footer: string;
  highlight?: boolean;
}) {
  const accent = tone === "red" ? "text-red" : "text-green";
  return (
    <div className={`hair bg-panel p-4 ${highlight ? "border-green/40" : ""}`}>
      <div className="flex items-baseline justify-between gap-2">
        <span className={`text-[11px] font-bold uppercase tracking-wider ${accent}`}>
          {tag}
        </span>
        <span className="text-[11px] text-bright">{service}</span>
      </div>
      <div className="mt-0.5 text-[10.5px] text-dim">{symptom}</div>
      <div className="mt-3 space-y-1">
        {steps.map(([tool, result], i) => (
          <div key={i} className="flex items-baseline gap-2 text-[11px]">
            <span className="tnum w-3.5 shrink-0 text-right text-[9px] text-line2">
              {i + 1}
            </span>
            <span className="shrink-0 text-fg">{tool}</span>
            <span className="min-w-0 flex-1 truncate text-dim">{result}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 border-t border-line pt-2 text-[10.5px] text-dim">{footer}</div>
    </div>
  );
}
