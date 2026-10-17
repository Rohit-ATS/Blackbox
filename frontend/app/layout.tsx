import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BLACKBOX — the on-call agent that gets smarter every incident",
  description:
    "Production breaks. BLACKBOX reads your service graph, traces the blast radius, " +
    "finds the change that caused it, recalls the last time this happened, pages the " +
    "human who actually knows, and writes what it learned back into the graph. " +
    "Built on FalkorDB for Graph Hacks.",
  applicationName: "BLACKBOX",
  authors: [{ name: "Rohit Maruri", url: "https://github.com/Rohit-ATS" }],
  keywords: ["FalkorDB", "graph database", "incident response", "agent memory",
             "Cypher", "blast radius", "Graph Hacks"],
  openGraph: {
    title: "BLACKBOX — an on-call agent with a graph for a memory",
    description:
      "Same class of incident, twice. Six hops the first time, two the second — " +
      "because it wrote down what it learned.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#05070a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-mono antialiased">{children}</body>
    </html>
  );
}
