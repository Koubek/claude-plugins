# Troubleshooting — symptom → cause → fix

Start with `bcl status` (probes) and `bcl logs --tail 200` (the entrypoint prints
`[entrypoint] [<s>] Step …` lines). `bcl doctor` re-checks the environment.

| symptom | cause | fix |
|---|---|---|
| `bcl up` dies with *only N MB RAM available* | another instance / big compile running; sbx has no swap | `bcl ls`, `bcl down --name <other>`; `--force` only if you accept OOM risk |
| *only N MB free on the Docker disk* | `/var/lib/docker` is a small (~10 GB) dedicated disk: images ≈3–3.5 GB + ≈2.5 GB per instance | `bcl down --purge --name <old>`; `docker image prune`; drop the FTS image if unused |
| artifact download: many `WARN range … http=exit7/28/56` then ERROR | sbx proxy outage/degradation (seen after the host resumed from sleep: every large transfer through the proxy failed while containers still had direct egress) | bcl automatically retries from a throwaway bc-runner container (direct egress). If both fail: check `curl -sI https://example.com`, wait, re-run `bcl up`. Persistent 403 → network policy (sandbox CLAUDE.md) |
| `[artifacts]` timings print absurd ms values | Ubuntu 26.04's `date` lacks `%3N` — cosmetic | ignore |
| `bc container exited during boot` | read the logs bcl printed; common: SQL not ready (`bcl logs sql`), corrupted service volume | `bcl down --purge` then `bcl up` (artifacts are kept) |
| boot sits at `NST startup` 2–3 min | normal: JIT with tiered compilation off | wait; `bcl up` timeout is 30 min |
| `bcl up` re-downloads although artifacts exist | the request changed (`--version 28` vs `28.5` are different keys) or `--refresh` | reuse the same version string; `bcl artifacts ls` |
| publish: HTTP 422 *Full-Text Search component is not installed* (then AL1024 in dependents) | app uses `OptimizeForTextSearch` | `bcl up --fts` (recreates SQL) |
| publish: HTTP 422 *already deployed / installed* | identical package already installed | bcl treats it as success; change the version to republish changed code |
| publish: 422 *Publishing failed … original extensions have been restored* | install/upgrade trigger error or object-ID clash (*defined in multiple apps*) | read the body bcl prints; fix the app |
| publish: HTTP 000 after a long time | publish exceeded `--timeout` (default 1800 s) or NST died | `bcl status`; raise `--timeout`; run publishes of big apps in the background |
| publish: 401 | wrong credentials (set at instance creation) | `bcl status` shows the login; `bcl env` |
| `bcdev test` → `404 … EndOpenSession` | launch.json points at the dev port; bcdev needs `/BC/cs` on the SAME port | use the instance launch.json (front door): `eval "$(bcl env)"`; instance must have the web client (default) |
| `bcdev test` exits 0 although tests failed | bcdev reports failure only in its JSON | `bcl test --runner bcdev` (proper exit code + JUnit) |
| altool runner: *no test results returned for a Subtype=Test codeunit* although `al` said "passed" | `al` 30.x prints JSON; upstream parses `--raw` text | bcl auto-uses `lib/al-raw`; if you call upstream directly pass `--altool-cmd <skill>/lib/al-raw` |
| altool: *This AL extension version … cannot be used with the specified server* | the installed `al` predates the server (BC29 today) | bcl falls back to `--transport hub` automatically; or use the websocket/bcdev runners |
| altool passes from one directory and fails from another | `al` caches server info + keys next to its cwd; a stale cache can mask an incompatibility | bcl runs `al` from a fresh empty dir on every `bcl test` |
| `run-tests.sh` can't find the API / companies on a non-zero slot | upstream falls back to a hard-coded `:7052` | bcl passes the front door as `--base-url`; keep the front door enabled |
| tests: *0 total* / codeunits not found | test app not installed, or range doesn't intersect its codeunits | `bcl apps`; check `--codeunit-range`; websocket runner republishes `--app` itself |
| web client 502 via front door | web client still starting (20–40 s after healthy) or crashed (auto-restarted) | `bcl logs webclient`; wait |
| *tenant records encryption key … missing* in logs | DB restored into an instance whose volume lacks the key | bcl copies snapshot keys + restarts NST automatically; otherwise `bcl snapshot save` again from the source |
| `snapshot … was taken on BC X but artifacts are now Y` | `--refresh` moved the build under the same key | re-create the snapshot on the new build (or `--force`, risky) |
| ports busy for slot N | another stack (or a non-bcl compose) holds them | `--slot M`, or stop the other stack |
| everything slow after the laptop slept | sbx VM was suspended; containers survive, network may need a minute | `bcl status`; re-run the failed step |

## Useful one-liners
```bash
bcl sql "SELECT [Name],[Version Major] FROM [Published Application] WHERE [Publisher]<>'Microsoft'"
bcl exec -- tail -n 100 /tmp/webclient.log
bcl logs --tail 400 | grep -E '\[entrypoint\]|ERROR|Exception' | tail -40
docker stats --no-stream $(docker ps -q --filter label=com.docker.compose.project=bcl-default)
```
