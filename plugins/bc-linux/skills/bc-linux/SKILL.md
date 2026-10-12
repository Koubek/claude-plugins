---
name: bc-linux
description: "Run a real Business Central server (NST + SQL Server) locally INSIDE this sbx sandbox with Docker (Stefan Maron's MsDyn365Bc.On.Linux) and drive it with the `bcl` CLI: start/stop/snapshot instances, make a sandbox-local work copy of an AL repo, compile against the server's exact build, publish .app files and run AL test codeunits (websocket, altool/hub or bcdev runners). Use this whenever the user wants to run, publish to or test against Business Central from the sandbox - 'run the tests', 'try my AL change on a real BC', 'spin up a BC', 'local / docker / Linux BC container' - even if they never say Linux. Prefer it over provisioning a remote or Windows BC container (~30+ min) unless the user explicitly asks for one or for a real SaaS environment."
---

# bc-linux — Business Central inside the sandbox

`bcl` runs Microsoft's unmodified BC service tier on Linux (patched at runtime by
[MsDyn365Bc.On.Linux](https://github.com/StefanMaron/MsDyn365Bc.On.Linux)) as a compose
stack **inside this sbx sandbox**: `sql` (SQL Server 2022) + `bc` (NST, dev endpoint,
OData, API, client services, optional web client) + `frontdoor` (nginx — one port that
looks like a Windows container). CRONUS demo DB, test toolkit pre-published, SUPER user.

Use it to compile → publish → run AL tests in minutes without a remote environment. Prefer it
over provisioning a remote or Windows BC container whenever a local tier is enough; validate on
real SaaS only for what `reference/LIMITATIONS.md` lists as different.

**Project companions:** a repo can ship a companion skill (conventionally `<project>-bc-linux`)
with its own recipe: which flags its apps need, snapshot names, test ranges. If one is listed
for the repo you are working in, load it too; it builds on the commands below.

```bash
command -v bcl >/dev/null || bash "${CLAUDE_SKILL_DIR}/bin/bcl" install   # only if bcl is not on PATH yet
bcl help                                                                  # every command; bcl up --help for options
```
Installed as the `bc-linux` plugin, `bcl` is already on PATH. A standalone copy of this skill
folder needs the `install` line once per sandbox; invoking through `bash` works even when the
folder came from Windows without exec bits.

## Ground rules for agents

- **Reuse before you create.** Booting takes 4–6 min and publishing a big ISV app
  10–15 min, while a sandbox often already has a running instance or a saved snapshot from
  earlier work. Always start with `bcl ls` and `bcl snapshot ls` (see *Start here*).
- **Long commands.** Give `bcl up` / big publishes the Bash tool `timeout: 1200000`, or run
  them with `run_in_background: true` and carry on when notified (`bcl up --no-wait` +
  `bcl wait` also works). The harness blocks plain `sleep` polling, so don't write wait loops.
- **The database is ephemeral** (SQL data lives on tmpfs): every container recreation starts
  from fresh CRONUS, *unless* the instance boots from a snapshot. Published apps survive only
  `bcl restart` (NST-only) and snapshots.
- **One instance ≈ 6–11 GB RAM** and sbx has no swap, so a second instance can get the whole
  sandbox OOM-killed. `bcl doctor` says how many fit; `bcl down` what you no longer need.
- **Build from a work copy, not from the repo.** AL repos usually sit on the user's host
  mount (Windows or macOS, via virtiofs): stamping `app.json` there breaks their VS Code (and must never be committed),
  and reading thousands of files over virtiofs is slow. `bcl workcopy` makes a sandbox-local
  copy of the *current working tree* (uncommitted and untracked edits included) with
  `app.json` stamped for the instance's BC version, in seconds.
- Exit codes are meaningful: `bcl compile` / `bcl publish` / `bcl test` fail loudly. Commands
  that produce something print only its path on stdout: `APP=$(bcl compile …)`. Every command
  answers `--help`; you should not need to read `bin/bcl` itself.

## Start here

```bash
bcl ls             # instances: BC version, state, and the DATABASE each one boots into
bcl snapshot ls    # saved databases (apps already installed), per BC build
```

- An instance with the BC version you need exists → `bcl up --name <it>` (no-op if healthy). If
  `bcl ls` shows `snapshot <label>` for it, that boot restores the snapshot's apps — nothing to republish.
- A snapshot holding the apps you need exists for that build → `bcl up --name <any> --snapshot <label>`
  (any instance on the same BC build can boot it; ~3–5 min instead of boot + publish).
- Neither → `bcl doctor`, then `bcl up --name <n> --version <major>` (add `--fts` if the app uses
  `OptimizeForTextSearch`; `bcl doctor --project <dir>` tells you).

## Supported BC versions

bcl follows Microsoft's SaaS lifecycle: the **current and the previous released major, never
below BC28** (today BC29 and BC28; `BCL_MIN_MAJOR` moves the floor). `bcl versions` labels them;
`bcl up --version latest|previous` resolves them from Microsoft's index, so scripts don't go stale. Without `--version`, a new instance gets
`previous` (BC28 today); an existing instance keeps its major. Older majors may still boot but are
not validated (bcl warns). Both supported majors are verified in sbx with every runner:

| | BC28 (28.5) | BC29 (29.0) |
|---|---|---|
| boot, compile (runtime 17.0 / 18.0), publish, snapshot | ✓ | ✓ |
| test runners websocket · altool hub · bcdev (optional) | ✓ | ✓ |
| altool `--transport cli` | ✓ | falls back to hub automatically — no public `al` accepts BC29's dev endpoint yet |
| large ISV app (7,211 objects, full-text search) compiles, publishes, tests pass, snapshot boot | ✓ | ✓ |

BC29's **first** boot of a new instance is slow (~25 min in sbx: the NST mounts the tenant for
~18 min while it builds the assembly cache for .NET 10). That is paid once per instance — later
boots take ~4 min and snapshot boots ~3 min — so create a BC29 instance once and keep reusing it.

## Quick start (any AL app)

```bash
bcl up --name dev --version previous                # BC28 today; --version latest = BC29 (or reuse, see above)
W=$(bcl workcopy ~/src/myrepo app test --name dev)  # working tree → ~/.bc-linux/work/myrepo, stamped BC28
APP=$(bcl compile $W/app --name dev)                # symbols from the server's exact build (+ your own
                                                    # deps from the running server) + al compile
TST=$(bcl compile $W/test --name dev --extra "$APP")
bcl publish --name dev "$APP"                       # several apps: pass them in dependency order; same version = replace
bcl test --name dev --app "$TST" --junit-output /tmp/junit.xml   # publishes $TST itself first, then runs it
bcl snapshot save --name dev myapp                  # optional: next boots come back with the apps installed
```

After editing code, re-run `workcopy` → `compile` → `publish` (app) → `test` (which publishes the
test app); the work copy keeps its `.alpackages`, so the loop is seconds plus compile time. The stamped `app.json` targets the server:
`platform`/`application` = `<major>.0.0.0`, `runtime` = major−11, `BCxx` preprocessor symbols
replaced by `BC<major>`/`BC<major>00`. ISV object ranges (e.g. 6014400+) work with the CRONUS
license, and both `Cloud` and `OnPrem` targets publish.

## Test runners (`bcl test --runner …`)

| runner | how | speed | use when |
|---|---|---|---|
| `websocket` *(default)* | upstream `run-tests.sh`: OData suite setup + real client session under the Test Runner codeunit; republishes `--app` first | baseline | default; most faithful (TestPermissions, UI handlers, TestPage) |
| `altool` | `al runtests` → `/BC/dev/TestRunnerHub`; `--transport cli` (default, per-codeunit process) or `hub` (one SignalR session, ~5–10× faster) | fast | quick loops on BC 28+; **runs as SUPER, ignores TestPermissions**, unhandled-UI not refused |
| `hybrid` | per codeunit: altool where safe, websocket otherwise (needs `--source-dir <AL test src>`) | mixed | big suites |
| `bcdev` *(optional)* | `bcdev test` (the bcdev-cli Claude plugin, if installed) through the front door (`/BC/cs` via the web client) | ~websocket | your workflow already uses bcdev; `--codeunit ID [--method M]` or all |

Common flags: `--app T.app` (discovers `Subtype=Test` codeunits from its symbols),
`--codeunit-range "50100..50199"` / `--codeunit ID`, `--junit-output F`, `--company C`,
`--no-publish` (altool/bcdev: app already installed), `--timeout MIN`, `-- <raw runner args>`.

## VS Code and other launch.json-based tools

Every instance writes a launch.json that targets the **front door** (one port serving
`/BC/dev`, `/BC/cs`, OData, API and the web client, which is what the AL extension and
launch.json-based CLIs such as bcdev expect from a Windows container):

```bash
eval "$(bcl env)"     # BC_LAUNCH_JSON, BC_LAUNCH_NAME, BC_USERNAME, BC_PASSWORD, BC_DEV_URL, ...
bcl launch-json --merge path/to/.vscode/launch.json   # add the configs to a project (gitignored files only)
```

Any tool that takes a launch.json + name + NavUserPassword credentials works unchanged with
those variables. Point such tools at the **work copy** (`$W/app/app.json`), not the repo.

**From the host machine** (browser, VS Code F5/debugging): the user runs
`sbx ports <sandbox> --publish 7080:7080` (bcl prints the exact command), then uses
`http://localhost:7080/BC/` and a launch.json with `"server": "http://localhost", "port": 7080`.

## Big apps and multi-project repos

The pattern for a large ISV app plus its test app (verified with a 7,211-object app on BC28 and BC29):

```bash
bcl snapshot ls                                  # a snapshot with your apps for this build? → bcl up --name big --snapshot <label>, skip to the loop
bcl doctor --project ~/src/repo/app              # does the app need full-text search?
bcl up --name big --version previous --fts       # --fts when the app has OptimizeForTextSearch fields
W=$(bcl workcopy ~/src/repo app test --as myapp --name big)   # add --alias LINK=TARGET for case-only path mismatches
APP=$(bcl compile $W/app --name big)             # ~1 min for 7k objects
TST=$(bcl compile $W/test --name big --extra "$APP")
bcl publish --name big "$APP"                    # 10–15 min on first install of a big app → run in the background
bcl test --name big --app "$TST" --codeunit-range 50100..50199   # publishes the test app, then runs
bcl snapshot save --name big myapp               # ~10 s; later boots (any instance on this build) come back with both apps
```

The loop after an edit: `workcopy` → `compile` only what changed → `publish` the app if it
changed → `bcl test --app "$TST" --codeunit <id>` (or `--runner altool --transport hub
--no-publish` for a ~10 s turnaround; mind the runner caveats above). When only the test app changed, compiling it alone is
enough: dependencies that are not in the BC artifacts are downloaded from the running server.
`--alias` creates a symlink in the work copy for paths that only resolve on case-insensitive
Windows file systems. Without `--fts`, publishing an app with `OptimizeForTextSearch` fields
fails with *"Full-Text Search component is not installed"*, and every dependent app then reports a
misleading AL1024. Re-save the snapshot when the baseline should move (`--force` overwrites).

## Measured in sbx (16 vCPU, 15.5 GB, no swap)

| step | time |
|---|---|
| artifact download (once per BC build, 3.2 GB on `$BCL_HOME`) | ~2 min |
| `bcl up`, fresh CRONUS — BC28 cold or warm, BC29 warm | 4–6 min |
| `bcl up` of a brand-new BC29 instance (one-time assembly-cache build) | ~25 min |
| `bcl up` of a 2nd instance (slot 1), artifacts + images cached — works offline | ~4 min |
| `bcl up --snapshot` with a large app installed (DB restore 7–17 s), BC28 or BC29 | 3–5 min |
| `bcl restart` (NST only, DB kept) | ~2 min |
| publish small app / large app (23 MB .app, 7,211 objects, 2,679 tables) | 2–6 s / ~11 min (BC28), ~16 min (BC29) |
| `bcl snapshot save` (large-app DB → 714 MB) | 11 s |
| large app's tests, 4 codeunits / 114 tests: websocket · altool cli | 254 s · 187 s (first run JIT-warms) |
| one codeunit: websocket · bcdev · altool hub | 55 s · 76 s · 11 s |

## Instances, ports, state

`--name N` on every command (default `default`, or `$BCL_INSTANCE`). Each instance gets a
port **slot** (first free 0–9); every port is `base + slot*100`:

| | slot 0 | slot 1 |
|---|---|---|
| front door (launch.json, VS Code, browser) | 7080 | 7180 |
| dev / OData / API | 7049 / 7048 / 7052 | 7149 / 7148 / 7152 |
| client services / mgmt / web client direct / SQL | 7085 / 7045 / 8080 / 11433 | 7185 / 7145 / 8180 / 11533 |

Login `BCRUNNER` / `Admin123!` (change with `--user/--password` at create time).
State under `$BCL_HOME` (default `~/.bc-linux`): `artifacts/` (per BC build),
`snapshots/<build>/`, `instances/<name>/` (instance.env, launch.json, connection.env),
`upstream/<sha>/` (pinned scripts). Docker volumes `bcl-<name>_bc-service` and
`_bc-assembly-cache` hold the patched tier (removed by `bcl down --purge`).

## Command reference

```
bcl doctor [--project DIR]            preflight (+ FTS need of an AL project)
bcl up [--name N] [--version V] [--country C] [--fts] [--snapshot L|none] [--no-webclient]
       [--license F] [--env K=V] [--slot N] [--ref R] [--refresh] [--no-wait] [--timeout MIN]
bcl wait | status [--json] | ls | logs [bc|sql|frontdoor|webclient] [--tail N] [-f]
bcl restart [--hard]                  soft = NST only (keeps DB); --hard = recreate
bcl down [--purge] [--all]            stop; --purge also drops volumes + instance dir
bcl workcopy REPO [DIR ...] [--as LABEL] [--alias LINK=TARGET] [--version N | --no-stamp]   → work dir
bcl compile PROJECT_DIR [--extra dep.app ...] [--out F] [--warnings]                        → .app path
bcl symbols --app-json P [--out D] [--extra dep.app]
bcl publish [--sync-mode ForceSync|Synchronize|Recreate] [--timeout S] A.app [B.app ...]
bcl apps [--all]                      installed extensions (from SQL)
bcl test --app T.app [--runner websocket|altool|hybrid|bcdev] [--codeunit-range R | --codeunit ID [--method M]]
         [--junit-output F] [--transport cli|hub] [--source-dir D] [--no-publish] [-- runner args]
bcl snapshot save <label> [--force] | ls | rm <label> | restore <label>
bcl env | launch-json [--merge F] | sql "<T-SQL>" | exec [-- cmd]
bcl versions [--major 28] [-c dk] | artifacts [ls|rm KEY] | update | install
```

## More

- `reference/LIMITATIONS.md` — what differs from a Windows/SaaS tier (read before trusting a red/green test).
- `reference/TROUBLESHOOTING.md` — symptom → fix table.
- `reference/INTERNALS.md` — architecture, why each design choice, upgrading the upstream pin,
  requirements, sharing the skill, credits and licensing.
