"use client";

import { useEffect, useState } from "react";
import { BACKEND } from "@/lib/types";

/**
 * A live readout on the landing page: if the backend is up, it says so with
 * real numbers from the graph. If it is not, it says that plainly rather than
 * showing invented figures.
 */
export default function LiveStat() {
  const [health, setHealth] = useState<any>(null);
  const [state, setState] = useState<"loading" | "up" | "down">("loading");

  useEffect(() => {
    let alive = true;
    fetch(`${BACKEND}/api/health`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((j) => {
        if (!alive) return;
        setHealth(j);
        setState("up");
      })
      .catch(() => alive && setState("down"));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="mt-12 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-line pt-5 text-[11px]">
      <span className="flex items-center gap-2">
        <span
          className={`inline-block h-1.5 w-1.5 ${
            state === "up" ? "animate-pulse-node bg-green" : state === "down" ? "bg-red" : "bg-dim"
          }`}
        />
        <span className="text-dim">
          {state === "loading" && "checking backend…"}
          {state === "down" && (
            <>
              backend not running — <span className="text-fg">docker compose up</span>
            </>
          )}
          {state === "up" && (
            <>
              FalkorDB connected in{" "}
              <span className="tnum text-green">
                {health.falkordb.ping_ms?.toFixed?.(2) ?? health.falkordb.ping_ms}ms
              </span>
            </>
          )}
        </span>
      </span>

      {state === "up" && (
        <>
          <Stat n={health.services} label="services in tenant:acme" />
          <Stat n={health.tools?.length} label="graph tools" />
          <Stat n={health.tenants?.length} label="isolated tenant graphs" />
          <span className="text-dim">
            brain <span className="text-violet">{health.brain}</span>
          </span>
        </>
      )}
    </div>
  );
}

function Stat({ n, label }: { n: number | undefined; label: string }) {
  if (n === undefined) return null;
  return (
    <span className="text-dim">
      <span className="tnum font-bold text-bright">{n}</span> {label}
    </span>
  );
}
