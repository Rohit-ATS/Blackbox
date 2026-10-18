# Driving BLACKBOX from your own Claude

The same nine graph tools the agent uses, over MCP stdio. Nothing is
reimplemented here — `server.py` imports `backend/blackbox/tools.py`.

## Setup

FalkorDB must be running and seeded:

```bash
docker compose up -d falkordb
cd backend && python -m blackbox.seed --all
```

Then add this to your Claude Desktop config
(`%APPDATA%\Claude\claude_desktop_config.json` on Windows,
`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS),
replacing the path with where you cloned the repo:

```json
{
  "mcpServers": {
    "blackbox": {
      "command": "python",
      "args": ["/absolute/path/to/Blackbox/mcp/server.py"],
      "env": { "FALKOR_HOST": "localhost", "FALKOR_PORT": "6379" }
    }
  }
}
```

Restart Claude Desktop. Eleven tools appear.

## Things worth asking it

- *"What's in the graph?"* → `graph_overview`
- *"What breaks if checkout-api goes down?"* → 11 services, 3 customer-facing
- *"Something deployed in the last two hours broke checkout-api. What was it?"*
  → it should reach for `recent_changes` with `hops=2` and land on PR #4471
  on ledger-service, two hops upstream
- *"Prove that ledger-service can affect checkout-api."* → `causal_path`
- *"Who should I page about src/db/connection-pool.ts?"* → Priya Raghavan,
  not Marcus Webb, who is the rotation default
- *"Show me how BLACKBOX reasoned about INC-3001."* → `agent_trace` reads the
  :AgentStep chain back out of the graph
- *"Now look at tenant globex."* → every tool takes `tenant=`, and the two
  graphs cannot see each other

## Requirements

MCP Python SDK v2 (`mcp>=2`), installed with the backend requirements. The v2
SDK renamed FastMCP to `MCPServer` and derives tool schemas from type hints;
this server is written against that API.
