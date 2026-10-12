# What differs from a Windows container / SaaS tier

The service tier is Microsoft's own binaries, patched at runtime (≈35 numbered patches in
upstream `src/StartupHook/StartupHook.cs`). Most AL behaves identically; these do not.
Upstream's full list: `$BCL_HOME/upstream/<sha>/KNOWN-LIMITATIONS.md`.

## Verified fine (in sbx, BC 28.5 and 29.0)
- ISV object ranges (tested: 6014400–6249170) publish and run under the CRONUS license.
- Big extensions: a 7,211-object ISV app (2,679 tables) publishes and its tests pass.
- Full-text search (`OptimizeForTextSearch`) — **only** with `bcl up --fts`.
- AL encryption / `IsolatedStorage` encrypted values — the tier creates a real tenant key on
  every boot (copied along with `bcl snapshot`).
- TestPage, `[HandlerFunctions]`, `TestPermissions` — with the `websocket` (default) and
  `bcdev` runners.

## Known gaps
| area | behaviour on Linux | workaround |
|---|---|---|
| Full-text search | default SQL image has no FTS → publish 422 *"Full-Text Search component is not installed"*, then AL1024 cascades in dependents | `bcl up --fts` (`mssql:2022-fts`, +550 MB) |
| RDLC reports | `Report.SaveAs(Pdf)` on RDLC returns false in the default image. Word/Excel layouts render | opt-in Mono renderer needs a custom image build (`BC_WITH_RDLC=1`) — not wired into bcl |
| .NET UI add-ins (Camera, Barcode…) | `NSClientCallback.CreateDotNetHandle` NullRef in tests that open such pages | none; skip those tests |
| Deleting users | tests doing `User.DeleteAll()` fail: the runner's own user is logged on | none (≈142 MS tests affected) |
| Outbound HTTP from AL | tenant is a *Sandbox* → BC asks the "allow HTTP requests" consent; tests need a handler | answer it with a `StrMenuHandler`, or mock HTTP |
| Time zones | DST zones are mapped to fixed offsets; server date math may be off by 1 h across DST | UTC personalization is forced at boot |
| `MemoryMappedFile` named maps | not supported on Linux .NET | — |
| Web client (experimental) | sign-in, role center, lists, cards work; record images/avatars 404, printing/upload untested, F5 launch-mode session binding unreliable (attach works) | use for poking at data; not for UI automation |
| BC 30 (preview) | boots upstream, but test-framework apps fail to publish | not supported until released and validated |
| BC 29 | verified in sbx incl. a large ISV app (compile, publish, tests, snapshot boot) on all runners. First boot of a NEW instance ~25 min (NST mount builds the .NET 10 assembly cache); later boots ~4 min | create once, then reuse / snapshot |
| BC 29 + `--runner altool --transport cli` | no public `al` (30.0.42-beta, 18.0.43) accepts BC29's dev endpoint: *"This AL extension version … cannot be used with the specified server"* | bcl probes and falls back to `--transport hub` |
| BC 27 and older | outside the supported window (SaaS lifecycle, BC28+) | may work; not validated |

## Test-runner fidelity (pick deliberately)
- **websocket** (default) and **bcdev** run each codeunit under Microsoft's Test Runner
  (isolation codeunit 130450): `TestPermissions`, UI handlers and unhandled-UI refusals behave
  like Windows. One client session per run, so `SingleInstance` state carries across codeunits
  (as on real BC).
- **altool** (`al runtests` → TestRunnerHub) has **no Test Runner codeunit**: everything runs as
  SUPER (`TestPermissions` ignored → permission bugs turn green), unhandled modal pages are not
  refused, per-test resets (WorkDate, application area) are skipped. Use it for fast inner
  loops, re-run with websocket before trusting a green result.
- `hybrid` routes codeunits with handlers / TestPermissions ≠ Disabled to websocket
  automatically (needs `--source-dir`).
- Per-method durations reported by BC are not wall clock — don't sum them.

## Environment facts that surprise people
- The database lives on a tmpfs: any container recreation = fresh CRONUS (use snapshots).
- Warm volumes (patched tier + assembly cache) do **not** make boots noticeably faster here;
  NST startup is ~2.5 min of JIT (tiered compilation is disabled on purpose for the patches).
- NST runs single-threaded-ish during a big publish (~1 core); a 7k-object app ≈ 11 min.
- CRONUS license: fine for development and tests; import your own with `--license`.
