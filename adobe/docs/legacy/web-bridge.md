# Web-agent bridge

## Local mode

Start the server from PowerShell:

```powershell
cd C:\IA\LUCIDA\adobe
$env:AGENT_TOOLKIT_TOKEN = "use-a-long-random-local-token"
npm run server
```

The server binds to `127.0.0.1:47921` by default.

For a browser-based client, add only the exact origins that should be allowed:

```powershell
$env:AGENT_TOOLKIT_CORS_ORIGINS = "https://arena.ai"
```

CORS is disabled when this variable is empty. The bearer token remains
required; CORS is not an authentication mechanism.
Requests are limited to 2,000,000 bytes.

Health check:

```powershell
curl.exe http://127.0.0.1:47921/health
```

Discovery endpoints:

```text
GET /agent-card       Agent-readable manifest and safety policy
GET /capabilities     Full registry of tools and workflows
GET /openapi.json     Minimal API description
GET /jobs/<id>        Job status; synchronizes Adobe result envelopes when pending
POST /adobe/enqueue   Enqueue one allowlisted Adobe operation
GET /jobs/<id>/adobe  Read Adobe result envelopes for a job
```

The discovery endpoints still require the bearer token when one is configured.

Run the first workflow:

```powershell
$body = @{ tool = "workflow.image-to-svg-preview"; params = @{ image = "C:\\IA\\svg\\d3\\docs\\public\\logo.png"; animation = "float"; vectorize = $true } } | ConvertTo-Json -Depth 5
Invoke-RestMethod http://127.0.0.1:47921/run -Method Post -ContentType "application/json" -Body $body
```

## Remote/web session

A hosted web session cannot automatically see `C:\IA\svg`. It needs a
deliberate bridge or tunnel to the local server. Keep the server localhost-only
unless all of the following are true:

- a strong bearer token is configured;
- only the required port is exposed;
- the bridge authenticates every request;
- input roots and output paths remain allowlisted;
- destructive operations require confirmation.

Adding `https://arena.ai` to the CORS allowlist only permits browser JavaScript
running in that origin to call the local API. It does not make the API reachable
by Arena's server-side model. For that case, use an authenticated tunnel or a
small relay with the same allowlists and audit logging.

The repository includes `scripts/bridge-tunnel.ps1` for a reverse SSH tunnel.
It binds both ends to loopback by default and requires
`AGENT_TOOLKIT_TOKEN`; it still needs a remote host and an authenticated HTTPS
proxy before a hosted agent can reach it.

The bridge exposes the registry's explicit web allowlist through `POST /run`.
The request shape is:

```json
{
  "tool": "svg.particles",
  "params": { "count": 40 }
}
```

The server dispatches only registered, allowlisted tools and never exposes an
arbitrary shell endpoint. File-producing web runs receive an isolated job and
write outputs only below that job's `output/` directory.

Adobe commands reject `options.overwrite=true` unless the request also carries
`options.confirmOverwrite=true`; the ordinary SVG/Blender CLI uses `--force` as
its explicit confirmation.
