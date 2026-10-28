---
name: review-change
description: Review a topic's staged changes as the repository's REVIEW.md asks, and write the review record that lets the commit through. Use before every commit in a repository with a REVIEW.md, and for "review this", "review before commit", "ready to commit?".
---

# Review a change before committing it

Read the repository's REVIEW.md first; without one, offer the review-setup skill and stop. Spend review effort where a
miss is costly and none where it is cheap: the tier decides, not the size of the diff or how long the session was.

## 1. Scope

One topic, staged. With nothing staged, stage the files changed for the current topic; ask when unsure which belong to
it, and never stage another topic's edits. Show `git diff --cached --stat`. Git runs no hook for cherry-pick or
most rebases: cherry-pick with `--no-commit` and review the result as a topic.

## 2. Tier

REVIEW.md's paths and words flag where a miss is costly (grep `git diff --cached -U0`); the tier is what the diff does
there, by REVIEW.md's tier list (so a flagged file can still be Low). Say the tier and why in one line, naming the
hunks that set it.

## 3. Evidence

REVIEW.md's checks for what changed (none for docs only); keep the last lines of their output. A failing check ends
the review: fix first. Medium and High: run the `simplify` skill first, and stage its edits, only when the diff adds a
file of code or changes more than about 200 lines of code.

## 4. Review

- Low: read the diff yourself, checking every claim in changed text against the code. No agents.
- Medium: `code-review medium`.
- High: start together `code-review high` and a fresh-context subagent on model fable (or the strongest model the
  Agent tool offers) with the diff, REVIEW.md, the project's rules (CLAUDE.md) and the hunks that set the tier. Add
  `security-review` when the change adds attack surface: a new entry point (route, command, hook), something run with
  the user's rights, input read from where untrusted code writes, or a new place secrets go. A second opinion from
  another model only when the user asks.

A skill named here that this Claude Code lacks: a fresh-context subagent with the same brief and effort instead.

Give every reviewer REVIEW.md and the topic's intent in a sentence, not your own conclusions. When other uncommitted
changes exist, name the topic's files as the target.

## 5. Findings

Check every finding against the code yourself. Each one ends fixed or answered with a reason: wrong, intentional, or
not worth it. A finding that repeats is a class of bug: fix every instance (grep), not the one line. Wrong findings go
into REVIEW.md "Not a problem here" by its rule.

After fixes, stage them and look only at what changed since the last round (`git diff <previous tree> <new tree>`).
Read it yourself when the fixes answer known findings or change only Low things; one reviewer (`code-review` at the
tier's level, given the findings already handled) only when they add new Medium or High behaviour. At most three
rounds; after the third, stop and ask the user to reconsider the approach.

## 6. Record

Write `.tmp/review/<tree>.md`, where `<tree>` is `git write-tree` of the final staged state: the tier and why, the
checks and their results, the findings with their outcomes, and what the checks would not catch (a few lines for Low).
When the folder is new, also write `.tmp/review/.gitignore` with the single line `*`, so records never get committed. A
commit of notes under `docs/` only (`docs/**/*.md`) needs no record. Anything staged later needs another look and a
new record.

## 7. Hand over

Show the user the record. Low: say what you read. Medium: the user reads the findings and the evidence. High: the user
reads the diff before the commit. Commit exactly what was reviewed: `git commit` with no `-a` and no paths. Draft the
commit message with these lines before the attribution:

    Testing: <what ran, what was looked at>
    Risk: <tier>: <why>
    Revert: <git revert of this commit is enough | what else to undo>
