import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink:    "#080510",
        panel:  "#110b20",
        panel2: "#1b1032",
        line:   "#2b1d48",
        line2:  "#4a3470",
        dim:    "#8d81a5",
        fg:     "#c8bddc",
        bright: "#f5f1ff",
        amber:  "#e9bd77",
        red:    "#ee8aa8",
        green:  "#b9a2ff",
        cyan:   "#bda1ff",
        violet: "#9d7bff",
      },
      fontFamily: {
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
