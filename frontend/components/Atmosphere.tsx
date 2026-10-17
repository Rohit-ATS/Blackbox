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
export function Intro() {
  const [pct, setPct] = useState(0);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setDone(true);
      document.body.style.overflow = "";
      return;
    }

    document.body.style.overflow = "hidden";

    // Climb to 100 over ~1.5s, pausing a beat at the end so the mark registers.
    const started = performance.now();
    const span = 1500;
    let raf = 0;

    const tick = (now: number) => {
      const p = Math.min(1, (now - started) / span);
      // ease-out: fast, then settles
      setPct(Math.round((1 - Math.pow(1 - p, 2.2)) * 100));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    const lift = setTimeout(() => {
      setDone(true);
      document.body.style.overflow = "";
    }, span + 320);

    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(lift);
      document.body.style.overflow = "";
    };
  }, []);

  return (
    <div className="intro" data-done={done} aria-hidden="true">
      <div className="intro-curtain top" />
      <div className="intro-curtain bottom" />
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
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" },
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
