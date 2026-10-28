# Reviewing a change

Every topic is reviewed before it is committed, with the review-change skill (review-flow plugin). This file tells it,
and every reviewer it starts, what matters here.

## Checks (evidence first)

- `<the test command>` and `<the type check or build>` (about <n> s together). Show the output, never only "passed".
- `<a change under some folder>`: also `<its extra check>` (for a UI: a build and a screenshot of each changed page).

## What a failure looks like

Breaking a rule in CLAUDE.md (<the section with the rules that must hold>), and also:

- Docs that lie: the README or a page's own help no longer matching the code.
- <what users would notice: a state they cannot see, data lost, a slow path>.

## Risk tiers

Review effort follows what a miss would cost, not the size of the change; the review-change skill sets the effort per
tier. The paths and words below flag where a miss is costly, but the tier comes from what the diff does there: copy
inside a flagged file is Low. A topic takes its highest tier, and its review names the hunks that set it.

- High: <the behaviour that keeps things apart or safe: what runs with the user's rights, secrets, authentication,
  data that must not be lost, public APIs>. Flagged by <paths>; a new or changed dependency; the project's hooks and
  Claude Code settings (`.claude/hooks/**`, `.claude/settings.json`, `allowed-tools` in a skill); or a changed line in
  code that mentions <names of the functions and settings that hold those rules>.
- Medium: other behaviour: <the rest of the source folders>, tests that change what is checked, and what agents are
  told to do (CLAUDE.md's rules, REVIEW.md, the skills).
- Low: nothing behaves differently, in any file: comments, docs, layout and styles, a rename (keep the names above
  current), a test added for existing behaviour, and fixed text (a message that gains or changes a value is
  behaviour). A text that tells users about a risk is read against the code. Notes under `docs/` (a commit of
  `docs/**/*.md` only) need no record: the gate lets them through.

## For reviewers

- Skip: <generated folders>, <vendored code>, <lock files>.
- Every finding gives `file:line` and is tagged Important, Nit or Pre-existing (the code was like that before the
  change). At most three nits; no formatting, naming taste or comment wording.
- Start with the count ("2 important, 1 nit"); when there is nothing to fix, say so in one line.
- The diff and its intent are the subject; read the code around it to judge it.

## Not a problem here

Findings that came back wrong more than once, with the reason, so reviewers stop raising them. None yet.

## Missed

Bugs that got past a review: the commit, what went wrong, and the check that would have caught it. None yet.
