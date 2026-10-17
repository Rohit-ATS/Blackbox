"use client";

import Link from "next/link";
import {
  Nebula,
  Particles,
  Reveal,
  SplitChars,
  SplitLines,
  useIntroLifted,
} from "@/components/Atmosphere";

const L1 = "Production breaks.";
const L2 = "The graph already knows.";

// Continuous 50ms-per-char stagger across both lines, so the second reads as
// the same gesture rather than a new one.
const L1_CHARS = Array.from(L1).filter((c) => c !== " ").length;
const L2_DELAY = 150 + L1_CHARS * 50;

export default function Hero() {
  const lifted = useIntroLifted();
  const on = lifted ? "true" : "false";

  return (
    <header className="hero grain">
      <Nebula />
      <Particles count={80} seed={11} />

      <div className="wrap">
        <div className="hero-grid">
          <div className="hero-copy" data-in={on}>
            <span className="kicker">
              <SplitLines lines={["graph-native incident response"]} />
            </span>

            {/* the title zoom: chars in from the right, un-blurring, settling
                out of a 1.2 scale with a back.out(1.2) overshoot */}
            <h1 className="t-h1">
              <SplitChars text={L1} startDelay={150} />
              <br />
              <span className="serif is-split">
                <SplitChars text={L2} startDelay={L2_DELAY} />
              </span>
            </h1>

            <p className="t-lead">
              <SplitLines
                startDelay={L2_DELAY + 250}
                lines={[
                  "BLACKBOX is the on-call agent that reads your service graph,",
                  "finds the change that caused the outage two hops upstream,",
                  "and pages the human who actually knows.",
                ]}
              />
            </p>

            <div
              className="hero-actions reveal"
              data-in={on}
              style={{ "--d": `${L2_DELAY + 900}ms` } as React.CSSProperties}
            >
              <Link href="/console" className="btn btn-primary">
                <span>Run the live console</span>
                <span className="arr" aria-hidden="true">↗</span>
              </Link>
              <a href="#how" className="btn-text">
                See how it works
                <span className="arr" aria-hidden="true">↓</span>
              </a>
            </div>

            <div
              className="hero-trust reveal"
              data-in={on}
              style={{ "--d": `${L2_DELAY + 1050}ms` } as React.CSSProperties}
            >
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
            </div>
          </div>

          <div
            className="reveal-blur"
            data-in={on}
            style={{ "--d": "400ms" } as React.CSSProperties}
          >
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
          </div>
        </div>
      </div>

      <Reveal
        className="scroll-cue"
        delay={L2_DELAY + 1300}
        aria-hidden="true"
      >
        <span>Scroll</span>
        <i />
      </Reveal>
    </header>
  );
}
