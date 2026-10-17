import Link from "next/link";
import {
  BrandMark,
  ClipLine,
  Intro,
  Nebula,
  Particles,
  Reveal,
} from "@/components/Atmosphere";

/* ───────────────────────────── content ───────────────────────────── */

const steps = [
  {
    n: "01",
    icon: "◴",
    title: "An alert fires",
    body: "p99 latency on checkout-api crosses threshold. One signal, no context, 3am.",
  },
  {
    n: "02",
    icon: "◈",
    title: "The graph answers",
    body: "One traversal returns every service, dependency and customer path degrading with it.",
  },
  {
    n: "03",
    icon: "◉",
    title: "The cause surfaces",
    body: "It walks upstream through deploys and ownership until the signal becomes a causal story.",
  },
  {
    n: "04",
    icon: "✦",
    title: "It writes back",
    body: "The resolved incident lands in the graph as a node. The next one of this shape starts ahead.",
  },
];

const features = [
  {
    n: "01",
    title: "Blast radius in one traversal",
    body:
      "Alerts tell you which service is loud. BLACKBOX returns the whole degrading subgraph — every dependency, every customer-facing path, ranked by hops from the origin — before the incident spreads.",
  },
  {
    n: "02",
    title: "Cause, not correlation",
    body:
      "It walks upstream through recent deploys, pull requests, config changes and service ownership. The answer is not “these metrics moved together.” It is “this deploy, two hops up, at 02:14.”",
  },
  {
    n: "03",
    title: "Memory that compounds",
    body:
      "Every resolved incident is written back as a (:Postmortem) attached to the services it touched. The second incident of a shape resolves in a fraction of the hops, because the graph remembers the first.",
    hot: true,
  },
];

const metrics = [
  { v: "42", l: "services mapped" },
  { v: "09", l: "typed graph tools" },
  { v: "03", l: "agents in the loop" },
  { v: "∞", l: "incidents remembered" },
];

const marquee = [
  "blast radius",
  "causal path",
  "owner on call",
  "prior incident",
  "postmortem written back",
];

/* ───────────────────────────── page ───────────────────────────── */

export default function Landing() {
  return (
    <>
      <Intro />
      <main className="shell">
        <Nav />
        <Hero />
        <Marquee />
        <Statement />
        <Steps />
        <Features />
        <Memory />
        <Metrics />
        <Cta />
        <Footer />
      </main>
    </>
  );
}

/* ───────────────────────────── nav ───────────────────────────── */

function Nav() {
  return (
    <nav className="nav">
      <Link href="/" className="brand" aria-label="BLACKBOX home">
        <BrandMark />
        <span className="brand-name">BLACKBOX</span>
      </Link>
      <div className="nav-links">
        <a className="masklink" href="#how">
          <i>How it works</i>
          <i aria-hidden="true">How it works</i>
        </a>
        <a className="masklink" href="#memory">
          <i>Memory</i>
          <i aria-hidden="true">Memory</i>
        </a>
        <a
          className="masklink"
          href="https://github.com/Rohit-ATS/GraphHacks"
          target="_blank"
          rel="noreferrer"
        >
          <i>Source</i>
          <i aria-hidden="true">Source</i>
        </a>
        <Link href="/console" className="btn btn-primary nav-cta" style={{ marginLeft: 8 }}>
          <span>Open console</span>
          <span className="arr" aria-hidden="true">↗</span>
        </Link>
      </div>
    </nav>
  );
}

/* ───────────────────────────── hero ───────────────────────────── */

function Hero() {
  return (
    <header className="hero grain">
      <Nebula />
      <Particles count={80} seed={11} />

      <div className="wrap">
        <Reveal className="hero-grid" variant="none">
          <div className="hero-copy">
            <Reveal delay={120}>
              <span className="kicker">graph-native incident response</span>
            </Reveal>

            <h1 className="t-h1">
              <ClipLine delay={240}>Production breaks.</ClipLine>
              <ClipLine delay={360}>
                <span className="serif">The graph already knows.</span>
              </ClipLine>
            </h1>

            <Reveal delay={520}>
              <p className="t-lead">
                BLACKBOX is the on-call agent that reads your service graph,
                finds the change that caused the outage two hops upstream, and
                pages the human who actually knows.
              </p>
            </Reveal>

            <Reveal delay={640} className="hero-actions">
              <Link href="/console" className="btn btn-primary">
                <span>Run the live console</span>
                <span className="arr" aria-hidden="true">↗</span>
              </Link>
              <a href="#how" className="btn-text">
                See how it works
                <span className="arr" aria-hidden="true">↓</span>
              </a>
            </Reveal>

            <Reveal delay={760} className="hero-trust">
              <div>
                <b>2 hops</b>
                warm path to cause
              </div>
              <div>
                <b>9</b>
                typed graph tools
              </div>
              <div>
                <b>FalkorDB</b>
                graph engine
              </div>
            </Reveal>
          </div>

          <Reveal delay={420} variant="reveal-blur">
            <div className="orb-stage" aria-label="BLACKBOX service graph, visualised">
              <div className="orb-halo" />
              <div className="orbit two" />
              <div className="orbit" />
              <div className="orbit three" />
              <div className="orb">
                <div className="orb-lat" />
                <div className="orb-sheen" />
              </div>
              <div className="orb-core" />

              <div className="chip a">
                <span className="chip-ico ember" aria-hidden="true">!</span>
                <span>
                  <b>checkout-api</b>
                  <small>p99 1840ms · threshold 800ms</small>
                </span>
              </div>
              <div className="chip b">
                <span className="chip-ico" aria-hidden="true">◈</span>
                <span>
                  <b>cause found · 2 hops</b>
                  <small>deploy #4471 → payments-db</small>
                </span>
              </div>
              <div className="chip c">
                <span className="chip-ico lilac" aria-hidden="true">✦</span>
                <span>
                  <b>Priya owns this</b>
                  <small>paged · prior incident attached</small>
                </span>
              </div>
            </div>
          </Reveal>
        </Reveal>
      </div>

      <div className="scroll-cue" aria-hidden="true">
        <span>Scroll</span>
        <i />
      </div>
    </header>
  );
}

/* ───────────────────────────── marquee ───────────────────────────── */

function Marquee() {
  const row = (
    <span>
      {marquee.map((m) => (
        <span key={m} style={{ display: "inline-flex", alignItems: "center", gap: 30 }}>
          {m === "postmortem written back" ? <em>{m}</em> : m}
          <span className="dot" aria-hidden="true">●</span>
        </span>
      ))}
    </span>
  );

  return (
    <section className="marquee mask-x" aria-hidden="true">
      <div className="marquee-track">
        {row}
        {row}
      </div>
    </section>
  );
}

/* ───────────────────────────── statement ───────────────────────────── */

function Statement() {
  return (
    <section className="sec">
      <div className="wrap split">
        <Reveal>
          <span className="kicker">the missing layer</span>
          <h2 className="t-h2" style={{ marginTop: 20 }}>
            <ClipLine delay={100}>Alerts tell you</ClipLine>
            <ClipLine delay={200}>what is loud.</ClipLine>
            <ClipLine delay={300}>
              <span className="serif">We tell you what matters.</span>
            </ClipLine>
          </h2>
        </Reveal>
        <Reveal delay={240}>
          <p className="t-body">
            Production systems are a graph. Your incident tooling is a list of
            metrics. That gap is why 3am takes four hours.
          </p>
          <p className="t-body" style={{ marginTop: 20 }}>
            BLACKBOX puts topology, deploys, people and prior decisions into one
            FalkorDB graph and lets an agent traverse it. Not a dashboard to
            read — a surface to think on.
          </p>
          <p
            className="t-small"
            style={{ marginTop: 28, paddingLeft: 18, borderLeft: "1px solid var(--stroke)" }}
          >
            The graph isn&apos;t where the agent looks things up.
            <br />
            It&apos;s where the agent thinks.
          </p>
        </Reveal>
      </div>
    </section>
  );
}

/* ───────────────────────────── steps ───────────────────────────── */

function Steps() {
  return (
    <section id="how" className="sec" style={{ paddingTop: 0 }}>
      <div className="wrap">
        <Reveal style={{ maxWidth: 620 }}>
          <span className="kicker">how it works</span>
          <h2 className="t-h2" style={{ marginTop: 20 }}>
            <ClipLine delay={100}>From one alert</ClipLine>
            <ClipLine delay={200}>
              to <span className="serif">the next move.</span>
            </ClipLine>
          </h2>
        </Reveal>

        <div className="steps">
          {steps.map((s, i) => (
            <Reveal key={s.n} className="step" delay={i * 110} variant="reveal">
              <div className="step-n">{s.n}</div>
              <div className="step-ico" aria-hidden="true">
                {s.icon}
              </div>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ───────────────────────────── features ───────────────────────────── */

function Features() {
  return (
    <section className="sec" style={{ paddingTop: 0 }}>
      <div className="wrap feat-grid">
        <Reveal>
          <span className="kicker">what it actually does</span>
          <h2 className="t-h2" style={{ marginTop: 20, marginBottom: 24 }}>
            <ClipLine delay={100}>Three things,</ClipLine>
            <ClipLine delay={200}>
              <span className="serif">done properly.</span>
            </ClipLine>
          </h2>
          <p className="t-body">
            One graph. Nine typed tools. Three agents in the loop — and a
            shorter path from first alert to confident action.
          </p>
        </Reveal>

        <div className="feat-list">
          {features.map((f, i) => (
            <Reveal
              key={f.n}
              delay={i * 120}
              variant="reveal"
              className={`feat${f.hot ? " hot" : ""}`}
            >
              <div className="feat-n">{f.n}</div>
              <div>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </div>
              <div className="feat-arr" aria-hidden="true">
                ↗
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ───────────────────────────── memory ───────────────────────────── */

function Memory() {
  return (
    <section id="memory" className="sec grain" style={{ position: "relative" }}>
      <Nebula />
      <Particles count={38} seed={23} />
      <hr className="rule" style={{ position: "absolute", top: 0, left: 0, right: 0 }} />

      <div className="wrap split" style={{ position: "relative", zIndex: 5 }}>
        <Reveal>
          <span className="kicker">the compounding advantage</span>
          <h2 className="t-h2" style={{ marginTop: 20, marginBottom: 24 }}>
            <ClipLine delay={100}>The second incident</ClipLine>
            <ClipLine delay={200}>
              <span className="serif">starts ahead.</span>
            </ClipLine>
          </h2>
          <p className="t-body" style={{ maxWidth: 420 }}>
            Run the same class of incident twice. The cold run walks the graph
            from nothing. The warm run finds the postmortem BLACKBOX wrote the
            first time, attached to the services involved, and skips straight to
            the cause.
          </p>
          <div style={{ marginTop: 32 }}>
            <Link href="/console" className="btn-text">
              Watch the warm run
              <span className="arr" aria-hidden="true">↗</span>
            </Link>
          </div>
        </Reveal>

        <Reveal delay={200} variant="reveal-blur">
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">agent memory</span>
              <span className="pill live">
                <i />
                LIVE
              </span>
            </div>

            <div className="delta">
              <span className="delta-n">11</span>
              <small>cold</small>
              <span className="to-arr" aria-hidden="true">→</span>
              <span className="delta-n to">8</span>
              <small>warm · tool calls</small>
            </div>

            <Bar label="hops to cause" value="6 → 2" w="68%" d={200} />
            <Bar label="context recovered" value="0.91" w="91%" d={360} />
            <Bar label="time to answer" value="−42%" w="58%" d={520} />

            <div className="panel-foot">
              <span style={{ color: "var(--lilac)" }}>(:Postmortem)</span>
              <span>created_by: blackbox</span>
            </div>
          </div>
        </Reveal>
      </div>

      <hr className="rule" style={{ position: "absolute", bottom: 0, left: 0, right: 0 }} />
    </section>
  );
}

function Bar({
  label,
  value,
  w,
  d,
}: {
  label: string;
  value: string;
  w: string;
  d: number;
}) {
  return (
    <div className="bar">
      <div className="bar-top">
        <span>{label}</span>
        <b className="tnum">{value}</b>
      </div>
      <div className="bar-rail">
        <div
          className="bar-fill"
          style={{ "--w": w, "--d": `${d}ms` } as React.CSSProperties}
        />
      </div>
    </div>
  );
}

/* ───────────────────────────── metrics ───────────────────────────── */

function Metrics() {
  return (
    <section className="sec-tight">
      <div className="wrap">
        <Reveal>
          <span className="kicker">connected by design</span>
        </Reveal>
        <div className="metrics">
          {metrics.map((m, i) => (
            <Reveal key={m.l} className="metric" delay={i * 100}>
              <b className="tnum">{m.v}</b>
              <span>{m.l}</span>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ───────────────────────────── cta ───────────────────────────── */

function Cta() {
  return (
    <section className="cta grain mask-y">
      <Nebula />
      <Particles count={56} seed={41} />
      <div className="wrap">
        <Reveal>
          <span className="kicker">your next incident is already connected</span>
          <h2 className="t-display" style={{ marginTop: 28 }}>
            <ClipLine delay={120}>Let the graph</ClipLine>
            <ClipLine delay={240}>
              <span className="serif">do the thinking.</span>
            </ClipLine>
          </h2>
        </Reveal>
        <Reveal delay={420}>
          <p className="t-lead">
            Open the working console and watch BLACKBOX trace a real incident
            from alert to answer — then do it again, with memory.
          </p>
        </Reveal>
        <Reveal delay={540} className="cta-actions">
          <Link href="/console" className="btn btn-primary">
            <span>Open BLACKBOX console</span>
            <span className="arr" aria-hidden="true">↗</span>
          </Link>
          <a
            href="https://github.com/Rohit-ATS/GraphHacks"
            target="_blank"
            rel="noreferrer"
            className="btn btn-ghost"
          >
            <span>Read the source</span>
            <span className="arr" aria-hidden="true">↗</span>
          </a>
        </Reveal>
      </div>
    </section>
  );
}

/* ───────────────────────────── footer ───────────────────────────── */

function Footer() {
  return (
    <footer className="foot">
      <div className="wrap">
        <div className="foot-grid">
          <div className="foot-col">
            <Link href="/" className="brand" style={{ marginBottom: 10 }}>
              <BrandMark />
              <span className="brand-name">BLACKBOX</span>
            </Link>
            <span style={{ maxWidth: 260, lineHeight: 1.6 }}>
              The on-call agent that knows what breaks next — and gets smarter
              every incident.
            </span>
          </div>

          <div className="foot-col">
            <strong>Product</strong>
            <Link href="/console">Console</Link>
            <a href="#how">How it works</a>
            <a href="#memory">Memory</a>
          </div>

          <div className="foot-col">
            <strong>Built with</strong>
            <a href="https://falkordb.com" target="_blank" rel="noreferrer">
              FalkorDB
            </a>
            <span>Next.js · MCP</span>
            <span>Cypher · SSE</span>
          </div>

          <div className="foot-col">
            <strong>Source</strong>
            <a
              href="https://github.com/Rohit-ATS/GraphHacks"
              target="_blank"
              rel="noreferrer"
            >
              GitHub
            </a>
            <a
              href="https://github.com/Rohit-ATS/GraphHacks/blob/main/schema.md"
              target="_blank"
              rel="noreferrer"
            >
              Graph schema
            </a>
            <a
              href="https://github.com/Rohit-ATS/GraphHacks/tree/main/mcp"
              target="_blank"
              rel="noreferrer"
            >
              MCP server
            </a>
          </div>
        </div>

        <div className="foot-base">
          <span>Graph Hacks 2026 · FalkorDB × WeMakeDevs</span>
          <span>Graph-native incident intelligence</span>
        </div>
      </div>
    </footer>
  );
}
