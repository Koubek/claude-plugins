#!/bin/sh
# SessionStart: copies the review gate (commit-msg next to this file) into git's hooks of a project that has a REVIEW.md
# at its top, and tells Claude the gate is on. Never writes over another hook; says why when it does not install.
# Always exits 0.
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
top=$(git rev-parse --show-toplevel 2>/dev/null) && [ -f "$top/REVIEW.md" ] || exit 0
if [ -n "$(git config --get core.hooksPath)" ]; then
  echo 'Review gate not installed: core.hooksPath is set, so git does not read .git/hooks.'
  exit 0
fi
src="$(dirname "$0")/commit-msg"
hook=$(git rev-parse --git-path hooks/commit-msg) || exit 0
# Ours: the second line of this plugin's gate, or of the copy it started from in sbx-manager. A link is never ours.
if [ -L "$hook" ] || { [ -e "$hook" ] && ! sed -n 2p "$hook" | grep -qE '^# (review gate \(review-flow plugin|sbx-manager review gate)'; }; then
  echo "Review gate not installed: $hook is another hook."
  exit 0
fi
if { mkdir -p "$(dirname "$hook")" && { cmp -s "$src" "$hook" || cp "$src" "$hook"; } && chmod +x "$hook"; }; then
  echo 'Review gate on (review-flow): review each topic with the review-change skill before committing it; REVIEW.md says what matters here.'
else
  echo "Review gate not installed: could not write $hook."
fi
exit 0
