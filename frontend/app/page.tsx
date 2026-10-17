import Link from "next/link";

const features = [
  { number: "01", title: "See the blast radius", body: "Trace every service, dependency, and customer path touched by an alert—before the incident spreads.", tone: "lilac" },
  { number: "02", title: "Find the real cause", body: "Walk upstream through recent deploys, ownership, and topology until the signal becomes a causal story.", tone: "violet" },
  { number: "03", title: "Remember what worked", body: "Every resolved incident becomes graph-native memory, so the next investigation starts with context.", tone: "pink" },
];

export default function Landing() {
  return (
    <main className="site-shell">
      <nav className="floating-nav"><Link href="/" className="brand-lockup"><span className="brand-mark">✦</span><span>BLACKBOX</span></Link><div className="nav-links"><a href="#how">How it works</a><a href="#memory">Memory</a><Link href="/console" className="nav-cta">Open console <span>↗</span></Link></div></nav>

      <section className="hero cosmic-bg"><div className="stars stars-a" /><div className="stars stars-b" /><div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" />
        <div className="hero-copy"><div className="eyebrow"><span className="eyebrow-dot" /> graph-native incident intelligence</div><h1>Make sense<br /><span>of the signal.</span></h1><p className="hero-subtitle">BLACKBOX gives your on-call team the missing context between an alert and an answer.</p><div className="hero-actions"><Link href="/console" className="primary-button">Run the live console <span>↗</span></Link><a href="#how" className="text-button">See how it works <span>↓</span></a></div></div>
        <div className="hero-visual" aria-label="BLACKBOX incident graph preview"><div className="orb-glow" /><div className="graph-orb"><div className="orb-grid" /><div className="orb-core" /></div><div className="phone-card"><div className="phone-top"><span className="tiny-brand">BLACKBOX</span><span className="live-pill"><i /> LIVE</span></div><div className="phone-title">Good evening,<br /><strong>your graph is awake.</strong></div><div className="signal-ring"><div className="ring-dot" /><span>12</span><small>active paths</small></div><div className="phone-row"><span><b>◈</b> causal path found</span><em>2 hops</em></div><div className="phone-row"><span><b>◌</b> memory attached</span><em>0.91</em></div></div><div className="floating-chip chip-top"><span className="chip-icon">↗</span><span><b>checkout-api</b><small>impact detected</small></span></div><div className="floating-chip chip-bottom"><span className="chip-icon green">✦</span><span><b>Priya knows this</b><small>owner surfaced</small></span></div></div><div className="hero-scroll"><span>Scroll to explore</span><i /></div>
      </section>

      <section className="statement section-wrap"><div className="section-kicker">The missing layer</div><h2>Alerts tell you what is loud.<br /><span>BLACKBOX tells you what matters.</span></h2><p>Production systems are connected. Your incident tools should be too. BLACKBOX turns topology, deploys, people, and prior decisions into one living investigation surface.</p></section>

      <section id="how" className="feature-section section-wrap"><div className="feature-intro"><div className="section-kicker">How it works</div><h2>From noise<br /><span>to next move.</span></h2><p>One graph. Three agents. A shorter path from first alert to confident action.</p></div><div className="feature-list">{features.map((feature) => <article key={feature.number} className={`feature-card ${feature.tone}`}><div className="feature-number">{feature.number}</div><div><h3>{feature.title}</h3><p>{feature.body}</p><span className="feature-arrow">↗</span></div></article>)}</div></section>

      <section id="memory" className="memory-section cosmic-bg section-wrap"><div className="memory-copy"><div className="section-kicker">The compounding advantage</div><h2>The second incident<br /><span>starts ahead.</span></h2><p>BLACKBOX writes the investigation back into the graph. The next time a familiar signature appears, it does not start from zero—it starts with your team&apos;s memory.</p><Link href="/console" className="text-button">Watch the warm run <span>↗</span></Link></div><div className="memory-panel"><div className="panel-label">agent memory / live</div><div className="memory-metric"><span>11</span><small>tool calls</small><b>→</b><span className="accent-number">8</span><small>tool calls</small></div><div className="memory-line"><i style={{width: "78%"}} /> <span>investigation time</span></div><div className="memory-line"><i style={{width: "92%"}} /> <span>context recovered</span></div><div className="panel-footer">(:Postmortem) <span>created_by: blackbox</span></div></div></section>

      <section className="metrics-section section-wrap"><div className="section-kicker">Connected by design</div><div className="metrics-grid"><Metric value="42" label="services mapped" /><Metric value="09" label="typed graph tools" /><Metric value="03" label="agents in the loop" /><Metric value="∞" label="incidents remembered" /></div></section>
      <section className="final-cta cosmic-bg"><div className="section-kicker">Your next incident is already connected</div><h2>Let the graph<br /><span>do the thinking.</span></h2><p>Open the working console and see BLACKBOX trace a real incident from alert to answer.</p><Link href="/console" className="primary-button">Open BLACKBOX console <span>↗</span></Link></section>
      <footer className="site-footer section-wrap"><Link href="/" className="brand-lockup"><span className="brand-mark">✦</span><span>BLACKBOX</span></Link><span>Graph-native incident intelligence · Graph Hacks 2026</span><span>Built with FalkorDB · Next.js · MCP</span></footer>
    </main>
  );
}

function Metric({ value, label }: { value: string; label: string }) { return <div className="metric"><strong>{value}</strong><span>{label}</span></div>; }
