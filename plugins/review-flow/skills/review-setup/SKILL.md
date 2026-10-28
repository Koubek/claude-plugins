---
name: review-setup
description: Set up the review flow in a repository - draft its REVIEW.md (checks, risk tiers, what reviewers skip) from the code and its rules, which also turns on the commit gate. Use for "set up reviews here", "add a REVIEW.md", or when review-change finds no REVIEW.md.
---

# Set up the review flow in a repository

REVIEW.md is the project's knowledge: the review-change skill and every reviewer it starts read it, and the commit
gate is on in every repository that has one at its top. Draft it; the maintainer owns it.

## 1. Learn what matters here

Read the project's CLAUDE.md (and AGENTS.md, CONTRIBUTING, the CI workflows), how its tests and builds run, and
`git log` for fixes of past bugs (`git log --oneline -i --grep=fix -50`, then the interesting ones). Note:

- the commands that prove a change works, and how long they take;
- the rules that must hold: security boundaries, data that must not be lost, what runs with the user's rights,
  public APIs and formats others depend on;
- the paths and names where those rules live (a miss there is costly);
- generated, vendored and lock files.

## 2. Draft REVIEW.md

Start from template.md next to this skill and fill every section from what you found; drop the parts that do not
apply, and invent nothing the code does not show. High is short: only where a miss is costly. Show the draft, ask what
is missing or wrong, and write it at the repository's top.

## 3. Turn it on

- The gate: the plugin's SessionStart hook copies its commit-msg hook into git's hooks at every session start once
  REVIEW.md exists. Install it now from the repository's top: `sh <this skill's folder>/../../hooks/install-gate.sh`
  (when the permission system refuses, ask the user to run it with `!`). It skips a repository whose `core.hooksPath`
  is set or that has another commit-msg hook, and says so; tell the user, who can chain it by hand.
- Review records go to `.tmp/review/`, which keeps itself out of git (review-change writes its `.gitignore`).
- Colleagues: ask whether the plugin should be on for everyone who clones the repository. If yes, add to the
  repository's `.claude/settings.json` (merge, never replace; it applies once each person trusts the folder, and each
  installs the plugin once):

      "extraKnownMarketplaces": { "koubek-plugins": { "source": { "source": "github", "repo": "Koubek/claude-plugins" } } },
      "enabledPlugins": { "review-flow@koubek-plugins": true }

- Commit REVIEW.md (and the settings) as its own topic: say what you drafted it from, and let the maintainer read it
  before the commit.
