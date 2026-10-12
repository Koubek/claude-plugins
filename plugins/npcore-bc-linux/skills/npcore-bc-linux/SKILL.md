---
name: npcore-bc-linux
description: "NpCore / NP Retail companion to the bc-linux skill (`bcl`, a real Business Central running locally inside this sbx sandbox): the verified recipe to compile, publish and test NP Retail + NP Retail Tests on a local BC28/BC29 (--fts, the shared `npretail` snapshot, test codeunit ids, bcdev against the local instance, timings) and when Crane (provision-bc-container) or a SaaS sandbox (publish-bc-saas) is still the right call. Use it together with bc-linux whenever NP Retail / NpCore code has to run on a real BC from the sandbox: running NP tests (e.g. codeunit 85006), trying an AL change in Application/ or Test/ on a server, getting NP Retail back from the npretail snapshot, publishing the NP Retail .app locally."
---

# NpCore on bc-linux

The **bc-linux** skill is the tool (`bcl help`, every command answers `--help`); this skill only
adds what is specific to the NpCore repo. The `bc-linux` plugin is a dependency of this one, so
`bcl` is on PATH. Everything below was verified end to end in sbx on BC 28.5 and 29.0 (compile
with 0 errors, publish, tests green, snapshot boot).

## Which tool for which job

| need | use |
|---|---|
| run NP tests, try a change on a real BC, publish NP Retail somewhere | **bcl** (this recipe), minutes, no remote round-trips |
| compile only, read AL errors, no server at all | `/bcdev` or **compile-al-project** (or `bcl compile` if an instance is already up) |
| a Windows/Crane container (shared with people, Crane-only setups, the real Windows web client) | **provision-bc-container** (~35 min) — only when asked |
| validate on real SaaS (S2S, real tenant) | **publish-bc-saas** — only when asked or when the bc-linux skill's `reference/LIMITATIONS.md` says Linux differs |

## Versions and app.json

NP follows the SaaS lifecycle: the latest and the previous major (BC29 and BC28 as of October
2026). Use `bcl up --version latest|previous` instead of hard-coding a number.

`bcl workcopy` copies the working tree (uncommitted edits included) to `~/.bc-linux/work/npcore`
and stamps **only the copy's** `app.json` files the way the repo's CLAUDE.md asks for local builds:
`platform`/`application` `<major>.0.0.0`, `runtime` major−11, and the `BCxx` preprocessor
symbols replaced by exactly `BC<major>` and `BC<major>00`. The repo's `app.json` is never touched,
so there is nothing to revert and nothing to accidentally commit. Point every other tool
(bcdev included) at the work copy, not at the repo.

## Recipe

```bash
ROOT=$(git rev-parse --show-toplevel)          # the NpCore repo (Application/ + Test/)
bcl ls; bcl snapshot ls                        # reuse first: see "Start here" in bc-linux
# fresh setup (skip whatever already exists):
bcl up --name np --version previous --fts      # or latest; BC29: a NEW instance's first boot takes ~25 min, once
W=$(bcl workcopy "$ROOT" Application Test --as npcore --name np)   # ~7 s
NP=$(bcl compile "$W/Application" --name np)               # ~1 min
NPT=$(bcl compile "$W/Test" --name np --extra "$NP")       # ~20 s
bcl publish --name np "$NP"                    # NP Retail ≈ 11 min (BC28) / ≈ 16 min (BC29) → run in the background
bcl test --name np --app "$NPT" --codeunit 85006   # publishes the Test app first, then runs it
bcl snapshot save --name np npretail           # 11 s, ~0.7 GB: later boots come back with both apps installed
```

If `bcl snapshot ls` already shows `npretail` for the build you need, skip the publish:
`bcl up --name np --snapshot npretail` (3–5 min; any instance on that build can boot it).
`bcl ls` shows which instances already boot into it. `npretail` is the shared label for
"NP Retail + NP Retail Tests at some recent commit": after the boot, `workcopy` → `compile` →
`publish` + `test` bring it to your working tree. Re-save it (`--force`) when the baseline should move.

## The inner loop after an edit

```bash
W=$(bcl workcopy "$ROOT" Application Test --as npcore --name np)
NPT=$(bcl compile "$W/Test" --name np)         # Test-only change: NP Retail symbols come from the running server
bcl test --name np --app "$NPT" --codeunit 85006   # (re)publishes the Test app, then runs; --method <name> needs --runner bcdev or altool
```

Changed `Application/`? Compile and `bcl publish` NP Retail first (≈ 1 min + the publish; a
same-version republish replaces the installed app), then compile and test as above.

Test **only the codeunits that cover the change**: the Test app has ~300 test codeunits (ids
85000–86000) at roughly a minute each with the websocket runner, so the whole suite takes hours.
To find the ones that touch an object (paths contain spaces, hence `-Z`/`-0`):

```bash
grep -rlZE 'Subtype *= *Test' --include=*.al "$ROOT/Test" | xargs -0 grep -lZ '"NPR POS Post Entries"' \
  | xargs -0 grep -hoE '^[^ ]*codeunit [0-9]+ "[^"]+"'      # → codeunit 85101 "NPR POS Action Layaway Tests", ...
```

For a ~10 s turnaround use `--runner altool --transport hub --no-publish`, but re-run with the
default websocket runner before you report green: altool runs as SUPER and ignores
`TestPermissions`.

## Why the flags

- **`--fts`**: NP Retail declares `OptimizeForTextSearch` fields (e.g.
  `Application/src/SpeedGate/_EntryLog/SGEntryLog.Table.al`). Without the full-text-search SQL
  image the publish fails with HTTP 422 *"Full-Text Search component is not installed"* and the
  Test app then reports a misleading AL1024. `bcl doctor --project "$ROOT/Application"` confirms it.
- **No `--alias` needed** on current master (NP Retail compiles from the work copy with 0
  errors). If an older branch fails with `AL0327: Missing file 'src/_ControlAddins/...'` (a
  path whose case only matches on Windows), add
  `--alias Application/src/_ControlAddins=_ControlAddIns` to `bcl workcopy`.
- **`--as npcore`**: a stable work-copy name, so `.alpackages` and caches survive between loops.
- Warnings are suppressed by default (the repo's `-suppressWarnings` rule); `bcl compile --warnings`
  shows them.
- The Test app is `target: OnPrem` and depends on NP Retail, Tests-TestLibraries and Test Runner;
  bcl's instances carry the test toolkit, so it publishes as-is.

## bcdev against the local instance

The repo's CLAUDE.md routes symbols, compile, publish and tests to `/bcdev`. bcdev works against a
bcl instance unchanged, through its front door:

```bash
eval "$(bcl env --name np)"    # BC_LAUNCH_JSON, BC_LAUNCH_NAME, BC_USERNAME, BC_PASSWORD, ...
bcdev publish -launchJsonPath "$BC_LAUNCH_JSON" -launchJsonName "$BC_LAUNCH_NAME" -appPath "$NP" -Username "$BC_USERNAME" -Password "$BC_PASSWORD"
bcdev symbols -fromServer -appJsonPath "$W/Application/app.json" -launchJsonPath "$BC_LAUNCH_JSON" -launchJsonName "$BC_LAUNCH_NAME" -Username "$BC_USERNAME" -Password "$BC_PASSWORD"
bcl test --name np --runner bcdev --app "$NPT" --codeunit 85006    # bcdev test with a real exit code + JUnit
```

⚠ A bare `bcdev test` exits 0 even when tests fail (the result is only in its JSON `success`);
`bcl test --runner bcdev` parses it for you. bcdev needs the instance's web client (on by default)
because it runs tests through `/BC/cs`.

## Measured with NP Retail (sbx, 16 vCPU, 15.5 GB)

| step | time |
|---|---|
| `bcl up --snapshot npretail` (DB restore 7–17 s), BC28 or BC29 | 3–5 min |
| first boot of a NEW BC29 instance (one-time assembly cache) | ~25 min |
| `workcopy` / compile NP Retail / compile Tests (BC28) | 7 s / ~1 min / ~20 s |
| publish NP Retail (23 MB, 7,211 objects, 2,679 tables) | ~11 min BC28, ~16 min BC29 |
| `bcl snapshot save` (DB → 714 MB) | 11 s |
| 85004..85008 (4 codeunits, 114 tests), BC28: websocket · altool cli | 254 s · 187 s |
| codeunit 85006 alone, BC28: websocket · bcdev · altool hub | 55 s · 76 s · 11 s (green on every runner on BC29 too) |

## NP-relevant limitations

Read the bc-linux skill's `reference/LIMITATIONS.md` before trusting a red or green result. The ones NP code
runs into most:
- Outbound HTTP from AL (Shopify, Magento, payment and fiscal integrations) hits the sandbox
  tenant's "allow HTTP requests" consent. Mock HTTP or handle it with a `StrMenuHandler`.
- RDLC report PDFs don't render (Word and Excel layouts do).
- Tests that delete users fail, because the runner's own user is logged on.
- altool-runner greens skip `TestPermissions`, as noted above.
