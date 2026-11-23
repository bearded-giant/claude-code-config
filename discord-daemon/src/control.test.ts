import { afterAll, describe, expect, test } from 'bun:test'
import { mkdirSync, mkdtempSync, rmSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'

const stateDir = mkdtempSync(join(tmpdir(), 'control-test-state-'))
process.env.DISCORD_STATE_DIR = stateDir
const { handleControlDM, listProjectPaths, parseStartArgs, sessionNameFor } = await import('./control.ts')
const { registry } = await import('./registry.ts')
afterAll(() => rmSync(stateDir, { recursive: true, force: true }))

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
    expect(sessionNameFor('/Users/bryan/sandbox')).toBe('sandbox')
  })
})

describe('list', () => {
  test('cwd sits in a code span so underscores never pair into italics', async () => {
    registry.register({ sessionId: 's1', label: 'bryan_grimes_x', cwd: '/home/bryan_grimes_x', pid: 1, threadId: 't1' })
    registry.markDormant('s1')
    const out = await handleControlDM('list', 'u', null as never)
    expect(out).toContain('• `bryan_grimes_x` _(dormant)_ — `/home/bryan_grimes_x` — up ')
    registry.delete('s1')
  })
})

describe('send', () => {
  test('posts into the thread and hands the text to the session', async () => {
    registry.register({ sessionId: 's2', label: 'kai', cwd: '/x/kai', pid: 1, threadId: 't2' })
    const posted: string[] = []
    const bot = { sendToThread: async (_t: string, text: string) => { posted.push(text); return { ids: ['m1'] } } }
    expect(await handleControlDM('send kai run the\ntests', 'u1', bot as never, 'bryan')).toBe('→ `kai`')
    expect(posted).toEqual(['run the\ntests'])
    expect(registry.recent('s2', 5)).toEqual([
      expect.objectContaining({ kind: 'message', message_id: 'm1', chat_id: 't2', user: 'bryan', user_id: 'u1', content: 'run the\ntests' }),
    ])
    registry.markDormant('s2')
    expect(await handleControlDM('send kai hello', 'u1', bot as never, 'bryan')).toContain('dormant')
    registry.delete('s2')
  })
  test('no text is a usage error, nothing posted', async () => {
    registry.register({ sessionId: 's3', label: 'kai', cwd: '/x/kai', pid: 1, threadId: 't3' })
    const posted: string[] = []
    const bot = { sendToThread: async (_t: string, text: string) => { posted.push(text); return { ids: ['m1'] } } }
    expect(await handleControlDM('send kai', 'u1', bot as never)).toContain('usage:')
    expect(posted).toEqual([])
    registry.delete('s3')
  })
})
