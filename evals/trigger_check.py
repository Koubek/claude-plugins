#!/usr/bin/env python3
"""Trigger checks for the skills in this marketplace (see evals/README.md).

isolated  skill-creator's run_eval for ONE skill description (temp command), each query in its
          own throw-away project dir under --base. Disable the installed plugins while this runs,
          or the model invokes the real skill instead of the temp command and recall reads 0 %.
combined  the real installed plugins, queries run from --cwd (e.g. the NpCore repo). Records which
          of our skills the model's FIRST assistant turn invokes (Skill tool, or Read of a
          SKILL.md). Any other first tool = no trigger; the process is killed before it runs.

Always run with stdin closed (</dev/null): claude -p otherwise reads it and the first wave of
runs misbehaves.

Usage:
  trigger_check.py isolated --eval-set F --skill-path DIR --base DIR [--runs 3] [--workers 10]
  trigger_check.py combined --eval-set F --cwd DIR [--runs 3] [--workers 10]
"""
import argparse
import json
import os
import select
import shutil
import subprocess
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed

def _skill_creator_dir():
    """skill-creator's scripts (the skill-creator plugin from claude-plugins-official)."""
    if os.environ.get("SKILL_CREATOR_DIR"):
        return os.environ["SKILL_CREATOR_DIR"]
    import glob
    c = glob.glob(os.path.expanduser("~/.claude/plugins/cache/claude-plugins-official/skill-creator/*/skills/skill-creator"))
    if not c:
        sys.exit("skill-creator not found: claude plugin install skill-creator@claude-plugins-official, or set SKILL_CREATOR_DIR")
    return max(c, key=os.path.getmtime)


SC = _skill_creator_dir()
sys.path.insert(0, SC)
import scripts.run_eval as run_eval_mod  # noqa: E402
from scripts.utils import parse_skill_md  # noqa: E402

_orig = run_eval_mod.run_single_query
SKILLS = ("bc-linux", "npcore-bc-linux")
MODEL = os.environ.get("TC_MODEL", "claude-opus-5-5")


def isolated_run_single_query(query, skill_name, skill_description, timeout, project_root, model=None):
    d = os.path.join(os.environ["TC_BASE"], uuid.uuid4().hex[:10])
    os.makedirs(os.path.join(d, ".claude", "commands"), exist_ok=True)
    try:
        return _orig(query, skill_name, skill_description, timeout, d, model)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def combined_single(query, cwd, timeout):
    """Return (sorted skills invoked in the first assistant turn, first tool name)."""
    cmd = ["claude", "-p", query, "--output-format", "stream-json", "--verbose",
           "--include-partial-messages", "--model", MODEL]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=cwd, env=env)
    found, first, cur, acc, buf = set(), None, None, "", ""
    start = time.time()
    try:
        while time.time() - start < timeout:
            if p.poll() is not None:
                break
            r, _, _ = select.select([p.stdout], [], [], 1.0)
            if not r:
                continue
            chunk = os.read(p.stdout.fileno(), 8192)
            if not chunk:
                break
            buf += chunk.decode("utf-8", errors="replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") != "stream_event":
                    continue
                se = ev.get("event", {})
                t = se.get("type", "")
                if t == "content_block_start" and se.get("content_block", {}).get("type") == "tool_use":
                    cur = se["content_block"].get("name", "")
                    acc = ""
                    first = first or cur
                    if cur not in ("Skill", "Read"):
                        return sorted(found), first
                elif t == "content_block_delta" and cur:
                    acc += se.get("delta", {}).get("partial_json", "")
                elif t == "content_block_stop" and cur:
                    try:
                        inp = json.loads(acc or "{}")
                    except json.JSONDecodeError:
                        inp = {}
                    name = str(inp.get("skill", "")).split(":")[-1]  # plugin skills: "<plugin>:<skill>"
                    path = str(inp.get("file_path", ""))
                    for s in SKILLS:
                        if name == s or f"/skills/{s}/" in path:
                            found.add(s)
                    cur = None
                elif t == "message_stop":
                    return sorted(found), first
        return sorted(found), first
    finally:
        try:
            p.kill()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["isolated", "combined"])
    ap.add_argument("--eval-set", required=True)
    ap.add_argument("--skill-path")
    ap.add_argument("--base")
    ap.add_argument("--cwd")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--timeout", type=int, default=60)
    a = ap.parse_args()
    evals = json.load(open(a.eval_set))

    if a.mode == "isolated":
        os.environ["TC_BASE"] = a.base
        os.makedirs(a.base, exist_ok=True)
        run_eval_mod.run_single_query = isolated_run_single_query
        name, desc, _ = parse_skill_md(__import__("pathlib").Path(a.skill_path))
        out = run_eval_mod.run_eval(eval_set=evals, skill_name=name, description=desc,
                                    num_workers=a.workers, timeout=a.timeout, project_root=a.base,
                                    runs_per_query=a.runs, model=MODEL)
        for r in sorted(out["results"], key=lambda r: (not r["should_trigger"], r["query"])):
            print(f"[{'PASS' if r['pass'] else 'FAIL'}] {r['triggers']}/{r['runs']} expect={r['should_trigger']}: {r['query'][:90]}")
        print("SUMMARY", json.dumps(out["summary"]))
        print(json.dumps(out), file=sys.stderr)
        return

    res = {}
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        fut = {ex.submit(combined_single, e["query"], a.cwd, a.timeout): e for e in evals for _ in range(a.runs)}
        for f in as_completed(fut):
            e = fut[f]
            try:
                res.setdefault(e["query"], (e, []))[1].append(f.result())
            except Exception as x:  # noqa: BLE001
                res.setdefault(e["query"], (e, []))[1].append(([], f"error {x}"))
    passed = 0
    for q, (e, runs) in sorted(res.items(), key=lambda kv: (not kv[1][0]["should_trigger"], kv[0])):
        hits = sum(1 for s, _ in runs if s)
        ok = (hits / len(runs) >= 0.5) == e["should_trigger"]
        passed += ok
        detail = "; ".join(f"{'+'.join(s) or '-'}({fst})" for s, fst in runs)
        print(f"[{'PASS' if ok else 'FAIL'}] {hits}/{len(runs)} expect={e['should_trigger']}: {q[:80]}\n        {detail}")
    print(f"SUMMARY passed {passed}/{len(res)}")


if __name__ == "__main__":
    main()
