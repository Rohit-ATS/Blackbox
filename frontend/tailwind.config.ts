import type { Config } from "tailwindcss";

/* Console tokens, mapped onto the landing page's material: near-black stage,
   warm-grey panels, lilac/violet as the live colour, ember for the alarm. */
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink:    "#0c0b0c",
        panel:  "#171515",
        panel2: "#1c1b1c",
        line:   "#2a2729",
        line2:  "#4a494b",
        dim:    "#8a8589",
        fg:     "#c8c8c8",
        bright: "#fafafa",
        amber:  "#e8a06a",
        red:    "#e73825",
        green:  "#edc5fc",
        cyan:   "#edc5fc",
        violet: "#9780ff",
        lilac:  "#edc5fc",
        ember:  "#e73825",
      },
      fontFamily: {
        sans: ["Wix Madefor Display", "-apple-system", "BlinkMacSystemFont",
               "Segoe UI", "Helvetica", "Arial", "sans-serif"],
        serif: ["Tiro Kannada", "Georgia", "Times New Roman", "serif"],
        mono: ["ui-monospace", "SFMono-Regular", "SF Mono", "Menlo", "Consolas",
               "Liberation Mono", "monospace"],
      },
      animation: {
        "pulse-node": "pulseNode 1.1s ease-out",
        "fade-in": "fadeIn .25s ease-out both",
        "slide-in": "slideIn .28s cubic-bezier(.2,.8,.2,1) both",
        "sweep": "sweep 2.2s linear infinite",
        "blink": "blink 1.1s step-end infinite",
      },
      keyframes: {
        pulseNode: { "0%": { opacity: ".35" }, "50%": { opacity: "1" }, "100%": { opacity: ".8" } },
        fadeIn: { from: { opacity: "0" }, to: { opacity: "1" } },
        slideIn: { from: { opacity: "0", transform: "translateY(6px)" },
                   to: { opacity: "1", transform: "translateY(0)" } },
        sweep: { from: { transform: "translateX(-100%)" }, to: { transform: "translateX(300%)" } },
        blink: { "50%": { opacity: "0" } },
      },
    },
  },
  plugins: [],
} satisfies Config;
