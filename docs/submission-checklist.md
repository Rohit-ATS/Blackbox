# Submission checklist

Work top to bottom. Do not deviate.

## Verified during the build

- [x] `git clone` into a fresh directory → `cp .env.example .env` →
      `docker compose up` → working demo. Tested for real on a clean path:
      **1m15s cold build**, then both scenarios reproduced identical results
      (cold: PR #4471, 11 calls; warm: cites `PM-INC-3001-BB`, 8 calls).
- [x] `pytest -q` → **29 passed**
- [x] MCP server driven by a real client over stdio: 11 tools, correct root
      cause, tenant switching, `:AgentStep` trail read back out of the graph
- [x] Both scenarios run end to end from the browser with zero terminal
      interaction, zero console errors or warnings
- [x] Repo is MIT licensed, no secrets committed (`git log -p` scanned),
      `.env` untracked
- [x] README has setup, architecture, full schema link, the track-by-track
      table, MCP config block, tech stack, name and handle

## Still to do before submitting

- [ ] **Record the demo video** — script in [`demo-script.md`](./demo-script.md).
      2:45 max, 1920×1080, three dry runs then one take.
- [ ] Upload to YouTube, unlisted → public. Title:
      `BLACKBOX — an on-call agent that gets smarter every incident (FalkorDB Graph Hacks)`
- [ ] Add the video link at the top of the README (there is a `## Demo`
      placeholder waiting for it)
- [ ] Add a hero GIF to the README — a 6-second loop of the cold run's
      impact set filling red is the strongest few seconds you have
- [x] Push to a **public** GitHub repo —
      [Rohit-ATS/GraphHacks](https://github.com/Rohit-ATS/GraphHacks)
- [x] GitHub Pages deployment live at
      [rohit-ats.github.io/GraphHacks](https://rohit-ats.github.io/GraphHacks/console/),
      replaying the recorded runs (Pages is static, so there is no backend
      behind it — the page says so)
- [ ] Publish the blog post ([`blog-post.md`](./blog-post.md)) on dev.to and
      Hashnode, cross-link the repo, tag FalkorDB. Set `published: true` in
      the frontmatter and fill `canonical_url` on the second platform.
- [ ] Link the blog post in the README
- [ ] Select **all three tracks** on the submission form
- [ ] Withdraw the outstanding team invite so the roster is clean — **then**
      submit. The team locks at submission and cannot be changed after.
- [ ] Submit by **9:00 AM PDT**, not 11:20

## After submitting

Do not touch the code. Use the buffer to post on X/LinkedIn tagging
@FalkorDB and @WeMakeDevs, and drop the link in the FalkorDB Discord.

## Pre-flight for the recording

```bash
docker compose up -d
curl -s localhost:8000/api/health          # wait for 42 services
```

In the console: press **forget**, set playback **1×**, set the brain to
**planner** (or **auto** if you have a working API key), tenant `acme`.

## If something breaks on the day

- **Graph pane empty** → the backend is not up. `docker compose logs backend`;
  it prints the seed counts when ready.
- **Model errors in the stream** → expected without a valid API key. The run
  continues on the deterministic planner and the answer is unchanged. Either
  say so plainly, or switch the brain to **planner** before recording.
- **The warm run isn't warm** → the cold run must come first, and **forget**
  must not be pressed in between. `curl localhost:8000/api/stats` shows
  `self_authored_postmortems`; it should be ≥1 before you run warm.
- **A button does nothing** → the controls disable while a run is in flight.
  Wait for the timer to stop streaming.
