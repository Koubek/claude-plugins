// The review-flow gate and its installer, with real commits in temporary repositories: node --test "tests/*.test.mjs"
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { after, test } from 'node:test';

const repo = await mkdtemp(join(tmpdir(), 'review-flow-'));
const other = await mkdtemp(join(tmpdir(), 'review-flow-'));
after(() => Promise.all([rm(repo, { recursive: true, force: true }), rm(other, { recursive: true, force: true })]));
// Neither git's own variables (set when the tests run from a git hook) nor the user's git configuration take part.
const env = {
  ...Object.fromEntries(Object.entries(process.env).filter(([k]) => !k.startsWith('GIT_') && k !== 'CLAUDECODE')),
  GIT_CONFIG_GLOBAL: join(other, 'no-global-config'),
  GIT_CONFIG_NOSYSTEM: '1',
};
const id = ['-c', 'user.name=t', '-c', 'user.email=t@t'];
const git = (...args) => execFileSync('git', [...id, ...args], { cwd: repo, env, encoding: 'utf8' }).trim();
/** Whether a commit or merge made from Claude Code goes through. */
const fromClaude = (...args) => spawnSync('git', [...id, ...args], { cwd: repo, env: { ...env, CLAUDECODE: '1' } }).status === 0;
const review = () => writeFile(join(repo, '.tmp', 'review', `${git('write-tree')}.md`), 'reviewed');
/** Runs the install as the SessionStart hook does; what it says (nothing when it installed or had nothing to do). */
const install = (dir) =>
  execFileSync('sh', [join(import.meta.dirname, '..', 'plugins', 'review-flow', 'hooks', 'install-gate.sh')], {
    env: { ...env, CLAUDE_PROJECT_DIR: dir },
    encoding: 'utf8',
  });
const commitFile = async (name) => {
  await writeFile(join(repo, name), name);
  git('add', name);
  git('commit', '-q', '-m', `${name}, by hand`);
};

test("Claude's commits go through only with a review of exactly the tree they commit", async () => {
  git('init', '-q', '-b', 'main');
  await writeFile(join(repo, 'REVIEW.md'), 'what matters here');
  assert.match(install(repo), /Review gate on/);
  await mkdir(join(repo, '.tmp', 'review'), { recursive: true });
  await writeFile(join(repo, '.tmp', 'review', '.gitignore'), '*\n');
  assert.equal(git('status', '--porcelain', '--', '.tmp'), '', 'records keep themselves out of git');
  git('add', 'REVIEW.md');

  assert.equal(fromClaude('commit', '-m', 'x', '-m', 'mentions Not reviewed: in passing'), false);
  assert.equal(fromClaude('commit', '-m', 'Not reviewed: setting up'), true);

  await writeFile(join(repo, 'a.txt'), 'one');
  git('add', 'a.txt');
  await review();
  await writeFile(join(repo, 'a.txt'), 'two');
  assert.equal(fromClaude('commit', '-a', '-m', 'x'), false, '-a commits a tree the review did not see');
  assert.equal(fromClaude('commit', '-m', 'x'), true);

  git('add', 'a.txt');
  await review();
  git('reset', '-q');
  assert.equal(fromClaude('commit', '-a', '-m', 'x'), true, 'git hands the hook the index that -a commits');

  git('checkout', '-q', '-b', 'side');
  await commitFile('b.txt');
  git('checkout', '-q', 'main');
  await commitFile('c.txt');
  assert.equal(fromClaude('commit', '-q', '--amend', '-m', 'c.txt, reworded'), true, 'a message-only amend changes no tree');
  assert.equal(fromClaude('merge', '-q', '--no-edit', 'side'), true, 'a merge brings in commits reviewed where they were made');

  git('checkout', '-q', 'side');
  await commitFile('d.txt');
  git('checkout', '-q', 'main');
  await commitFile('e.txt');
  git('merge', '-q', '--no-commit', '--no-ff', 'side');
  assert.equal(fromClaude('commit', '-m', 'merge'), true, 'a merge finished with git commit');

  await mkdir(join(repo, 'docs'));
  await writeFile(join(repo, 'docs', 'notes.md'), 'notes');
  await writeFile(join(repo, 'docs', 'poznámky.md'), 'a name git quotes by default');
  git('add', 'docs');
  assert.equal(fromClaude('commit', '-m', 'x'), true, 'notes under docs/ need no review');
  await writeFile(join(repo, 'CLAUDE.md'), 'rules');
  git('add', 'CLAUDE.md');
  assert.equal(fromClaude('commit', '-m', 'x'), false, 'other markdown tells agents what to do');
  git('rm', '-q', '--cached', 'CLAUDE.md');
  git('mv', 'a.txt', 'docs/a.md');
  assert.equal(fromClaude('commit', '-m', 'x'), false, 'a renamed file counts by both names');

  git('rm', '-q', 'REVIEW.md');
  assert.equal(fromClaude('commit', '-m', 'x'), true, 'a project without a REVIEW.md has no gate');
});

test('the install needs a REVIEW.md, keeps another commit-msg hook, refreshes its own, and skips when hooks live elsewhere', async () => {
  execFileSync('git', ['init', '-q'], { cwd: other, env });
  const hook = join(other, '.git', 'hooks', 'commit-msg');
  assert.equal(install(other), '');
  assert.equal(existsSync(hook), false, 'no REVIEW.md, no gate');

  await writeFile(join(other, 'REVIEW.md'), 'what matters here');
  for (const foreign of ['#!/bin/sh\nexit 0\n', '#!/bin/sh\n# our own review gate checks\nexit 0\n']) {
    await writeFile(hook, foreign);
    assert.match(install(other), /another hook/);
    assert.equal(await readFile(hook, 'utf8'), foreign);
  }

  await writeFile(hook, '#!/bin/sh\n# sbx-manager review gate (written by .claude/hooks/review-gate.ts, see REVIEW.md)\n');
  assert.match(install(other), /Review gate on/);
  assert.match(await readFile(hook, 'utf8'), /review-flow plugin/);
  assert.match(install(other), /Review gate on/, 'its own hook, installed already');

  execFileSync('git', ['config', 'core.hooksPath', 'elsewhere'], { cwd: other, env });
  assert.match(install(other), /core\.hooksPath is set/);
});
