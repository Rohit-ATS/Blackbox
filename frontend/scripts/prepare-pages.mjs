// Copy the recorded runs into public/ so the static export can serve them.
// The GitHub Pages build has no backend, so these fixtures ARE the demo.
import { cpSync, existsSync, mkdirSync, writeFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../../fixtures");
const dest = resolve(here, "../public/fixtures");

if (!existsSync(src)) {
  console.error(
    `[prepare-pages] no fixtures at ${src}\n` +
    `  regenerate them with:  cd backend && python -m blackbox.record_fixtures`,
  );
  process.exit(1);
}

mkdirSync(dest, { recursive: true });
cpSync(src, dest, { recursive: true });

// Pages serves the artifact as-is, but _next/ would be hidden if anything
// ever ran Jekyll over it.
mkdirSync(resolve(here, "../public"), { recursive: true });
writeFileSync(join(resolve(here, "../public"), ".nojekyll"), "");

console.log(`[prepare-pages] copied ${readdirSync(dest).join(", ")} -> public/fixtures`);
