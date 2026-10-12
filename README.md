# claude-plugins

Jakub Vaňák's Claude Code plugin marketplace (`koubek-plugins`).

| plugin | what it does |
|---|---|
| [`bc-linux`](plugins/bc-linux) | Runs a real Business Central (NST + SQL Server) inside an sbx sandbox with Docker, using [StefanMaron/MsDyn365Bc.On.Linux](https://github.com/StefanMaron/MsDyn365Bc.On.Linux). The `bcl` CLI covers instances, DB snapshots, work copies, compile, publish and AL test runners. Supports BC28 and newer, following the SaaS lifecycle. Generic, nothing NP-specific. |
| [`npcore-bc-linux`](plugins/npcore-bc-linux) | NpCore / NP Retail companion to `bc-linux`: the verified recipe for NP Retail + NP Retail Tests. Depends on `bc-linux`. |

## Install

```bash
claude plugin marketplace add Koubek/claude-plugins        # private repo: uses your git credentials
claude plugin install bc-linux@koubek-plugins
claude plugin install npcore-bc-linux@koubek-plugins       # pulls in bc-linux as a dependency
```

Restart Claude Code, or run `/reload-plugins`. `bcl` is then on the Bash tool's PATH and the
skills load on their own when a task needs them (`/bc-linux:bc-linux` to force one).

**sbx sandboxes:** sbx does not carry host plugins into sandboxes. Install the plugins inside
the sandbox, or add the three commands above to your kit's provisioning commands, next to
the navipartner marketplace. Inside sbx, git authenticates through the sandbox proxy, so the
private repo works once a GitHub token is set (`sbx secret set github ...`).

## Develop

```
.claude-plugin/marketplace.json     the marketplace: lists the plugins
plugins/<plugin>/
  .claude-plugin/plugin.json        name, version, dependencies
  bin/                              on the Bash tool's PATH while the plugin is enabled
  skills/<skill>/SKILL.md           skills (+ their scripts and reference docs)
evals/                              trigger evals (not shipped)
```

- Validate: `claude plugin validate .` and `claude plugin validate plugins/<plugin>`.
- Release: bump `version` in the plugin's `plugin.json`. Installed copies only update when it
  changes. Then `claude plugin tag plugins/<plugin> --push`, which creates `<plugin>--v<version>`.
- Users update with `claude plugin marketplace update koubek-plugins` and
  `claude plugin update <plugin>@koubek-plugins`. Auto-update is off by default for
  non-official marketplaces; turn it on in `/plugin` → Marketplaces.
- Try local changes without pushing: `claude plugin marketplace add ./` (a local path), then
  install from it.

## Credits

`bc-linux` wraps Stefan Maron's [MsDyn365Bc.On.Linux](https://github.com/StefanMaron/MsDyn365Bc.On.Linux).
It clones and pulls upstream at runtime and vendors none of it. BC artifacts come from
Microsoft's CDN at runtime under Microsoft's terms. See
`plugins/bc-linux/skills/bc-linux/reference/INTERNALS.md`.
