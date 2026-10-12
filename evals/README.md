# Trigger evals

These check whether Claude picks the right skill for a prompt. They are not shipped with the
plugins (`evals/` sits outside `plugins/`).

| set | what it checks |
|---|---|
| `bc-linux/trigger_eval.json` | generic prompts (no NP context): 10 should trigger, 10 near misses |
| `npcore-bc-linux/trigger_eval.json` | NpCore prompts, run from the NpCore repo with both plugins installed |

Requires the skill-creator plugin (`claude plugin install skill-creator@claude-plugins-official`).

```bash
# 1. One description in isolation, from a neutral directory. Disable the installed plugin first,
#    or the model invokes the real skill instead of the temporary command.
claude plugin disable bc-linux@koubek-plugins
python3 evals/trigger_check.py isolated --eval-set evals/bc-linux/trigger_eval.json \
  --skill-path plugins/bc-linux/skills/bc-linux --base /tmp/trig </dev/null
claude plugin enable bc-linux@koubek-plugins

# 2. Both plugins installed for real, from inside the NpCore repo
python3 evals/trigger_check.py combined --eval-set evals/npcore-bc-linux/trigger_eval.json \
  --cwd <NpCore repo> </dev/null
```

Gotchas learned the hard way:
- Keep stdin closed (`</dev/null`). Otherwise the first wave of `claude -p` runs misbehaves and
  scores 0.
- Each isolated query needs its own project dir (the script does this). skill-creator's stock
  `run_eval` shares one `.claude/commands` dir between parallel workers.
- Project memory that mentions a skill steers the model to `cat` its SKILL.md instead of
  invoking it. Run from a directory without such memory.

Last results (2026-10-12): generic 20/20, NpCore combined 20/20. The only stray near miss is
the GitHub Actions prompt (1 of 3 runs).
