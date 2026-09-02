# Bridge scripts

## Adobe host preflight

This read-only check confirms configured or standard-location Adobe executables
and adapter syntax. If `config.local.json` is absent, it auto-discovers the
installed Photoshop and Illustrator executables without launching Adobe or
modifying documents:

```powershell
cd .\adobe
.\scripts\adobe-host-check.ps1
```

Use `-NoAutoDiscover` to report only paths from `config.local.json`, or pass an
explicit file with `-ConfigPath`.

To include the intentionally pending After Effects adapter in the report:

```powershell
.\scripts\adobe-host-check.ps1 -IncludeAfterEffects
```

`hostRuntime` changes to `verified-result-envelope` when a completed result
envelope from that host is found under the job directories.

## Reverse SSH tunnel

Start the local bridge first with a strong token:

```powershell
$env:AGENT_TOOLKIT_TOKEN = "replace-with-a-long-random-token"
$env:AGENT_TOOLKIT_CORS_ORIGINS = "https://arena.ai"
npm run server
```

From a second PowerShell window, connect to a remote host that will run an
authenticated reverse proxy:

```powershell
.\scripts\bridge-tunnel.ps1 -Remote user@example-host -RemotePort 47921
```

The helper binds the remote end to `127.0.0.1` and uses
`ExitOnForwardFailure`. It does not publish the service to the public internet.
A remote HTTPS proxy must enforce the same bearer token and route only the
required endpoints.
