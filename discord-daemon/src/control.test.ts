import { describe, expect, test } from 'bun:test'
import { mkdirSync, mkdtempSync, rmSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'

process.env.DISCORD_STATE_DIR = mkdtempSync(join(tmpdir(), 'control-test-state-'))
const { listProjectPaths, parseStartArgs, sessionNameFor } = await import('./control.ts')

describe('parseStartArgs', () => {
  test('relpath plus validated flags', () => {
    expect(parseStartArgs(['dev/python/cc-wt/master', '--acct', 'ent', '--effort', 'xhigh'])).toEqual({
      relpath: 'dev/python/cc-wt/master',
      dclaudeArgs: ['--acct', 'ent', '--effort', 'xhigh'],
    })
  })
  test('inline flag values and no relpath', () => {
    expect(parseStartArgs(['--model=opus'])).toEqual({ relpath: '', dclaudeArgs: ['--model', 'opus'] })
  })
  test('rejects bad values, unknown flags, extra positionals', () => {
    expect(parseStartArgs(['--acct', 'root'])).toEqual({ error: '`--acct` takes one of team|ent' })
    expect(parseStartArgs(['--effort'])).toEqual({ error: '`--effort` takes one of low|medium|high|xhigh|max' })
    expect(parseStartArgs(['--shell', 'zsh'])).toEqual({ error: 'unknown flag `--shell`' })
    expect(parseStartArgs(['a', 'b'])).toEqual({ error: 'unexpected argument `b`' })
  })
})

describe('listProjectPaths', () => {
  test('finds .git repos and .bare worktrees to depth 3', () => {
    const root = mkdtempSync(join(tmpdir(), 'projects-'))
    for (const d of ['a/.git', 'b-wt/.bare', 'b-wt/main', 'b-wt/feat', 'deep/x/y/.git', 'deep/x/y/z/.git', 'too/deep/x/y/.git', 'plain']) {
      mkdirSync(join(root, d), { recursive: true })
    }
    try {
      expect(listProjectPaths(root)).toEqual(['a', 'b-wt/feat', 'b-wt/main', 'deep/x/y'])
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })
})

describe('sessionNameFor', () => {
  test('worktree dirs carry the layout name', () => {
    expect(sessionNameFor('/Users/bryan/dev/python/cc-wt/master')).toBe('cc-wt-master')
    expect(sessionNameFor('/Users/bryan/dev/ai/kai')).toBe('kai')
    expect(sessionNameFor('/Users/bryan/scratch')).toBe('scratch')
  })
})
