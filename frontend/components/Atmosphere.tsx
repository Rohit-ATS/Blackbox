"use client";

import { useEffect, useMemo, useRef, useState } from "react";

/* ═══════════════════════════════════════════════════════════════════════════
   Atmosphere — the ambient layer every dark section sits on, plus the two
   motion primitives the page is built from (intro curtain, scroll reveal).
   ═══════════════════════════════════════════════════════════════════════════ */

/** Deterministic PRNG so the server and client agree on particle placement. */
function rand(seed: number) {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s / 4294967296;
  };
}

/**
 * Two-depth particle field: small dim specks behind, brighter flecks in front,
 * all drifting upward on long staggered loops.
 */
export function Particles({
  count = 70,
  seed = 7,
}: {
  count?: number;
  seed?: number;
}) {
  const dots = useMemo(() => {
    const r = rand(seed);
    return Array.from({ length: count }, () => {
      const front = r() > 0.62;
      return {
        left: r() * 100,
        top: 8 + r() * 100,
        dur: 16 + r() * 30,
        delay: -r() * 42,
        dx: (r() - 0.5) * 110,
        opacity: front ? 0.45 + r() * 0.45 : 0.14 + r() * 0.22,
        front,
        lilac: r() > 0.82,
      };
    });
  }, [count, seed]);

  return (
    <div className="particles" aria-hidden="true">
      {dots.map((d, i) => (
        <span
          key={i}
          className={`particle ${d.front ? "front" : "back"}${d.lilac ? " lilac" : ""}`}
          style={
            {
              left: `${d.left}%`,
              top: `${d.top}%`,
              animationDuration: `${d.dur}s`,
              animationDelay: `${d.delay}s`,
              "--dx": `${d.dx}px`,
              "--po": d.opacity,
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
}

/** The slow colour wash that sits under the particles. */
export function Nebula() {
  return <div className="nebula" aria-hidden="true" />;
}

/**
 * Intro: rings spin up over a counter, then the black parts like a curtain.
 * Skipped outright for anyone who asked for reduced motion.
 */
const HOLD_MS = 4000; // the preloader sits for four seconds
const FADE_MS = 1000; // then the layer fades out over one

/* The hero entrance has to start as the preloader begins to lift, or it plays
   out of sight behind it. Module-level so mount order does not matter, with a
   hard backstop in case the intro never reports in. */
let releaseIntro: (() => void) | null = null;
const introLifted = new Promise<void>((resolve) => {
  releaseIntro = resolve;
});
if (typeof window !== "undefined") {
  setTimeout(() => releaseIntro?.(), HOLD_MS + FADE_MS + 1500);
}

/** Resolves when the hero is clear to animate. */
export function useIntroLifted() {
  const [lifted, setLifted] = useState(false);
  useEffect(() => {
    let alive = true;
    void introLifted.then(() => {
      if (alive) setLifted(true);
    });
    return () => {
      alive = false;
    };
  }, []);
  return lifted;
}

/**
 * Shows only on a fresh arrival at the landing page or a reload — coming back
 * from the console does not replay it. Mirrors the reference's session rules.
 */
function shouldPreload(): boolean {
  try {
    const nav = performance.getEntriesByType(
      "navigation",
    )[0] as PerformanceNavigationTiming | undefined;
    const type = nav?.type ?? "navigate";
    const isReload = type === "reload";
    const isBack = type === "back_forward";
    const internal = document.referrer.includes(location.origin);
    const pending = sessionStorage.getItem("bb_pending_preloader") === "true";

    sessionStorage.setItem("bb_visited_home", "true");
    if (pending) sessionStorage.removeItem("bb_pending_preloader");

    return isReload || (!isBack && !internal) || pending;
  } catch {
    return true;
  }
}

export function Intro() {
  const [pct, setPct] = useState(0);
  const [done, setDone] = useState(false);
  const [skip, setSkip] = useState(false);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduced || !shouldPreload()) {
      setSkip(true);
      setDone(true);
      releaseIntro?.();
      return;
    }

    document.body.style.overflow = "hidden";

    // The counter tracks the hold, easing out so it slows as it lands on 100.
    const started = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - started) / HOLD_MS);
      setPct(Math.round((1 - Math.pow(1 - p, 2.4)) * 100));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    const fade = setTimeout(() => {
      setDone(true);
      releaseIntro?.(); // hero starts as the layer begins to clear
    }, HOLD_MS);
    // Scroll unlocks only once the layer is actually gone.
    const unlock = setTimeout(() => {
      document.body.style.overflow = "";
    }, HOLD_MS + FADE_MS);

    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(fade);
      clearTimeout(unlock);
      document.body.style.overflow = "";
    };
  }, []);

  return (
    <div className="intro" data-done={done} data-skip={skip} aria-hidden="true">
      <div className="intro-core">
        <div className="intro-mark">
          <span className="intro-ring" />
          <span className="intro-ring" />
          <span className="intro-ring" />
          <span className="intro-pip" />
        </div>
        <div style={{ textAlign: "center", display: "grid", gap: 9 }}>
          <div className="intro-word">BLACKBOX</div>
          <div className="intro-sub">reading the graph</div>
        </div>
        <div className="intro-meter">
          <i style={{ width: `${pct}%` }} />
        </div>
        <div className="intro-count">{String(pct).padStart(3, "0")}</div>
      </div>
    </div>
  );
}

/**
 * Per-character entrance: each char flies in from 6rem right, un-blurs from
 * 0.6rem and settles out of a 1.2 scale on a back.out(1.2), 50ms apart.
 * Spaces stay unwrapped so the browser can still break lines normally.
 */
export function SplitChars({
  text,
  startDelay = 0,
  stagger = 50,
  className = "",
}: {
  text: string;
  startDelay?: number;
  stagger?: number;
  className?: string;
}) {
  let i = 0;
  return (
    <span className={`sp ${className}`.trim()} aria-label={text} role="text">
      {Array.from(text).map((ch, k) => {
        if (ch === " ") return <span key={k}> </span>;
        const idx = i++;
        return (
          <span
            key={k}
            aria-hidden="true"
            className="sp-char"
            style={
              {
                "--i": idx,
                "--d0": `${startDelay}ms`,
                transitionDelay: `calc(${idx} * ${stagger}ms + ${startDelay}ms)`,
              } as React.CSSProperties
            }
          >
            {ch}
          </span>
        );
      })}
    </span>
  );
}

/**
 * A multi-line headline on the char entrance, with the 50ms stagger running
 * continuously across the lines so it reads as a single gesture. Pass a line
 * as `{ text, accent: true }` to render it in the serif accent.
 */
export function SplitHeadline({
  lines,
  startDelay = 0,
  stagger = 50,
}: {
  lines: (string | { text: string; accent?: boolean })[];
  startDelay?: number;
  stagger?: number;
}) {
  let consumed = 0;
  return (
    <>
      {lines.map((line, i) => {
        const text = typeof line === "string" ? line : line.text;
        const accent = typeof line === "string" ? false : line.accent;
        const delay = startDelay + consumed * stagger;
        consumed += Array.from(text).filter((c) => c !== " ").length;

        const chars = (
          <SplitChars text={text} startDelay={delay} stagger={stagger} />
        );

        return (
          <span key={i} style={{ display: "block" }}>
            {accent ? <span className="serif is-split">{chars}</span> : chars}
          </span>
        );
      })}
    </>
  );
}

/**
 * Per-line entrance: rises from 50% down, un-blurs from 0.2rem, on a
 * power2.out, 200ms apart. Lines are authored, not measured.
 */
export function SplitLines({
  lines,
  startDelay = 0,
  stagger = 200,
  className = "",
}: {
  lines: React.ReactNode[];
  startDelay?: number;
  stagger?: number;
  className?: string;
}) {
  return (
    <span className={className}>
      {lines.map((line, i) => (
        <span className="sp-line" key={i}>
          <span
            style={
              {
                "--i": i,
                "--d0": `${startDelay}ms`,
                transitionDelay: `calc(${i} * ${stagger}ms + ${startDelay}ms)`,
              } as React.CSSProperties
            }
          >
            {line}
          </span>
        </span>
      ))}
    </span>
  );
}

/**
 * Reveal: flips `data-in` the first time the element crosses into view, which
 * is what every entrance transition in globals.css keys off.
 */
export function Reveal({
  children,
  delay = 0,
  variant = "reveal",
  as = "div",
  className = "",
  style,
  ...rest
}: {
  children: React.ReactNode;
  delay?: number;
  variant?: "reveal" | "reveal-blur" | "none";
  as?: keyof JSX.IntrinsicElements;
  className?: string;
} & React.HTMLAttributes<HTMLElement>) {
  // Polymorphic `as` needs a loose component type; the prop surface stays typed.
  const Tag = as as React.ElementType;
  const ref = useRef<HTMLElement>(null);
  const [seen, setSeen] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!("IntersectionObserver" in window)) {
      setSeen(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setSeen(true);
            io.disconnect();
          }
        }
      },
      { threshold: 0.2 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const base = variant === "none" ? "" : variant;

  return (
    <Tag
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ref={ref as any}
      data-in={seen}
      className={`${base} ${className}`.trim()}
      style={{ "--d": `${delay}ms`, ...style } as React.CSSProperties}
      {...rest}
    >
      {children}
    </Tag>
  );
}

/** A headline line that rises out of a clipping box. */
export function ClipLine({
  children,
  delay = 0,
}: {
  children: React.ReactNode;
  delay?: number;
}) {
  return (
    <span className="line-clip">
      <span style={{ "--d": `${delay}ms` } as React.CSSProperties}>{children}</span>
    </span>
  );
}

/** The mark: three nested rings around a lit core — the graph, abstracted. */
export function BrandMark({ size = 26 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 26 26"
      fill="none"
      aria-hidden="true"
      style={{ display: "block", flexShrink: 0 }}
    >
      <circle cx="13" cy="13" r="12.25" stroke="#4a494b" strokeWidth="1" />
      <circle cx="13" cy="13" r="7.5" stroke="#9780ff" strokeWidth="1" opacity="0.8" />
      <circle cx="13" cy="13" r="3" fill="#edc5fc" />
      <circle cx="13" cy="0.75" r="1.6" fill="#edc5fc" />
      <circle cx="23.5" cy="18.5" r="1.3" fill="#e73825" />
      <circle cx="3" cy="18" r="1.3" fill="#9780ff" />
    </svg>
  );
}
