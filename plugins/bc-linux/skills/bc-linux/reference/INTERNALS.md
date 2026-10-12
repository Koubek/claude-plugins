# bc-linux internals

## Layers
```
bcl (bash)                      this skill: lifecycle, ports, artifacts, snapshots, runners
 └─ docker compose  -p bcl-<name>
     ├─ <upstream>/docker-compose.yml      MsDyn365Bc.On.Linux @ pinned sha (sql + bc services)
     └─ <instance>/compose.bcl.yml         bcl override: snapshot mount on sql, web-client
                                           public URL, nginx front door
containers:  sql (mssql:2022[-fts], data on tmpfs)   bc (bc-runner:<sha>)   frontdoor (nginx)
```
Nothing BC-specific is reimplemented: boot, patching, DB restore, test toolkit publish and
the test runners are upstream's. bcl only adds what an sbx sandbox needs.

## Why each design choice
- **Host-side artifacts on `$BCL_HOME`** — upstream's container would download ~2.4 GB of zips
  into its own `/tmp`, i.e. onto sbx's small `/var/lib/docker` disk (~10 GB). bcl runs upstream's
  `download-artifacts.sh` on the sandbox host into `$BCL_HOME/artifacts/<type>-<version>-<country>`
  and bind-mounts it (`BC_ARTIFACTS_DIR`). The container finds upstream's
  `.bc-artifact-cache` stamp whose `request=` matches its own `BC_TYPE|BC_VERSION|BC_COUNTRY`
  and skips the download. The request string must match exactly — that is why the directory key
  is the requested version, not the resolved build. `bcl up` does not re-resolve a cached
  version (offline-friendly, stable); `--refresh` does. If the host-side download fails (sbx
  proxy trouble), bcl re-runs the same downloader inside a throwaway bc-runner container as the
  caller's uid — in sbx, containers egress directly instead of through the host proxy.
- **Pinned upstream + matching image** — every upstream master commit publishes
  `bc-runner:<full sha>`. bcl checks out `upstream/<sha>` (scripts: run-tests.sh,
  restart-service.sh, stage-symbols.py, ...) and runs exactly that image, so scripts and the
  baked TestRunner.dll never drift. `PINNED_REF` in `bin/bcl` is the commit validated in sbx;
  instances keep their ref until `--ref`.
- **Front door** — the AL extension and launch.json-based CLIs (e.g. bcdev) derive every URL
  from one `server:port/BC`: publish goes to `/BC/dev/apps`, test sessions to
  `/BC/cs/?tenant=default` (the web client's client-services endpoint). On Linux those are different ports (7049 / 8080), so
  nginx maps `/BC/dev`→7049, `/BC/ODataV4`→7048, `/BC/api`→7052, `/BC/*`→8080 (web client with
  path base `/BC`). Websockets (debugger, SignalR) and unlimited uploads are enabled.
- **Web client on by default** — needed for `/BC/cs` (`--runner bcdev`, client-session tools) and the browser. It is
  upstream's experimental self-hosted `Prod.Client.WebCoreApp`; `--no-webclient` saves RAM.
- **Port slots** — compose project names isolate containers/volumes, but host ports are global;
  slot N shifts every published port by N×100 so instances never collide.
- **Clean environment for compose** — `in_instance_env` unsets any `BC_*`, `SQL_*`, … the
  caller's shell exports (e.g. a sourced `bc.dev.vars`) and sources `instance.env`, the single
  source of truth. `--env K=V` adds persisted pass-throughs (e.g. `BC_DISABLE_PATCHES`).

## Snapshots (DB-level, no CRIU)
Upstream's "snapshot mode" freezes the NST process with CRIU — it needs criu ≥ 4.2.1 built from
source, dockerd in experimental mode (restart), sysctls and host networking: not something to
do to an sbx VM. bcl implements the half that upstream measured as worth having on its own:
- `save`: `BACKUP DATABASE … COPY_ONLY, COMPRESSION, CHECKSUM` into
  `$BCL_HOME/snapshots/<artifact key>/<label>.bak` (bind-mounted into sql as `/bcl-snapshots`,
  dir mode 0777 because SQL Server runs as uid 10001), plus the tenant encryption key files
  from `/bc/service/Keys` and a JSON with the build and installed non-Microsoft apps.
- `up --snapshot L`: stop bc → start sql → `RESTORE … REPLACE` → start bc with
  `BC_CLEAR_ALL_APPS=none` + `BC_SKIP_APP_PUBLISH=true`. The entrypoint's own path then says
  *"CRONUS already exists"*, keeps every app and publishes nothing; NST boots on the restored
  tenant (real BC install state — no synthesized rows). Missing key files are copied in and
  the NST soft-restarted. The instance remembers `BCL_SNAPSHOT`, so a plain `bcl up` later
  (e.g. after a sandbox restart) lands in the same state. `--snapshot none` returns to CRONUS.
- Snapshots are tied to the exact BC build (checked against the JSON).

## State layout
```
$BCL_HOME (~/.bc-linux)
├── artifacts/<type>-<ver>-<country>/   app/ platform/ .bc-artifact-cache     (~3.2 GB each)
├── snapshots/<artifact key>/<label>.{bak,json,keys/}
├── upstream/<sha>/                    upstream checkout (scripts only are used)
├── instances/<name>/                  instance.env, compose.bcl.yml, frontdoor.conf,
│                                      launch.json, connection.env, license.bclicense, .lock
└── tmp/                               download scratch
docker volumes: bcl-<name>_bc-service, bcl-<name>_bc-assembly-cache (+ images)
```

## Upgrading upstream
1. `bcl update` lists new upstream commits since the pin.
2. Try one: `bcl up --name try --ref master` (or a sha), publish + test something real.
3. If good, set `PINNED_REF` in `bin/bcl` to that full sha and note it in SKILL.md.
Existing instances move only with `bcl up --name N --ref pinned`.

## Requirements of the sandbox
Docker daemon inside the sandbox (sbx default), compose v2, `git curl python3 unzip flock rsync`;
≈16 GB RAM for one instance plus compiles; outbound access to `github.com`, `ghcr.io`,
`bcartifacts-exdbf9fwegejdqak.b02.azurefd.net` (and `bcinsider-…azurefd.net` for previews).
Containers do not need internet when artifacts are host-side. Optional:
- `al` for `bcl compile` and the altool runner: the
  `Microsoft.Dynamics.BusinessCentral.Development.Tools` dotnet tool (cross-platform; a prerelease
  build for `al runtests`): `dotnet tool install -g Microsoft.Dynamics.BusinessCentral.Development.Tools --prerelease`.
- `bcdev` only for `--runner bcdev`: found on `PATH`, via `$BCL_BCDEV`, or in the bcdev-cli Claude
  plugin's cache.

Nothing requires sbx itself: on any Linux host with Docker the sbx-specific parts (proxy
fallback, `sbx ports` hints) simply stay idle.

## Installing and sharing
- **As a plugin (preferred):** the `bc-linux` plugin ships this skill plus a plugin-level
  `bin/bcl` that Claude Code puts on the Bash tool's PATH. sbx does not carry host plugins into
  sandboxes, so install it inside each sandbox: by hand, or in the sbx kit's provisioning
  commands (`claude plugin marketplace add <repo>` + `claude plugin install bc-linux@<marketplace>`).
  Updates arrive when the plugin's `version` is bumped.
- **As a plain skill:** this folder is self-contained (SKILL.md, `bin/`, `lib/`, `reference/`).
  Copy it into `~/.claude/skills/` or the host directory sbx shares read-only into every sandbox
  (`/run/sbx/skills-shared`), then run `bash <folder>/bin/bcl install` once per sandbox.

State is per sandbox (`$BCL_HOME`); nothing is written into the skill folder. Project-specific
recipes belong in a separate companion skill or plugin (`<project>-bc-linux`) that refers to this
one, so this folder stays generic and can be updated in one place.

## Credits and licensing
- The service-tier patching, images, entrypoint and test runners are
  [StefanMaron/MsDyn365Bc.On.Linux](https://github.com/StefanMaron/MsDyn365Bc.On.Linux). bcl does
  not vendor any of it: it clones the pinned commit and pulls the published images at runtime.
  Check upstream's license terms before redistributing this skill outside your organisation.
- Business Central artifacts are downloaded from Microsoft's public artifact CDN at runtime and
  are subject to Microsoft's terms. The CRONUS demo license that ships with them is for
  development and testing; nothing produced here is a supported production deployment.
