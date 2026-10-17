import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink:    "#05070a",
        panel:  "#0a0e14",
        panel2: "#0f141c",
        line:   "#1b2430",
        line2:  "#27333f",
        dim:    "#5a6978",
        fg:     "#c9d4df",
        bright: "#eef4fa",
        amber:  "#f5a623",
        red:    "#ff4d4d",
        green:  "#2ee6a8",
        cyan:   "#35c8f0",
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
