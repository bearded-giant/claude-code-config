import { afterAll, describe, expect, test } from 'bun:test'
import { existsSync, mkdtempSync, rmSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'

const stateDir = mkdtempSync(join(tmpdir(), 'restart-test-state-'))
process.env.DISCORD_STATE_DIR = stateDir
const { acctOf, busyReason, keptFlags, relaunchCommand, restartSessions } = await import('./restart.ts')
afterAll(() => rmSync(stateDir, { recursive: true, force: true }))

describe('keptFlags', () => {
  test('keeps effort and model, drops channel, permission and prompt flags and the old resume', () => {
    const argv = [
      'claude', '--dangerously-load-development-channels', 'server:discord', '--dangerously-skip-permissions',
      '--append-system-prompt', 'Messages wrapped in <channel>', '--effort', 'xhigh', '--model=opus', '--resume', 'old-id',
    ]
    expect(keptFlags(argv)).toEqual(['--effort', 'xhigh', '--model', 'opus'])
  })
  test('drops a value that is not shell-safe', () => {
    expect(keptFlags(['claude', '--effort', 'x; rm -rf ~'])).toEqual([])
  })
})

describe('acctOf', () => {
  test('reads the slot from the credentials dir', () => {
    expect(acctOf('/home/u/.claude-ent')).toBe('ent')
    expect(acctOf('/home/u/.claude-team')).toBe('team')
    expect(acctOf(undefined)).toBe('team')
  })
})

describe('relaunchCommand', () => {
  test('resumes the transcript, keeps the daemon id so the thread reattaches', () => {
    expect(
      relaunchCommand({ acct: 'ent', flags: ['--effort', 'xhigh'], transcriptId: 'abc-123', daemonId: 'cwd-aba64f66-1f2e', label: 'cc-wt-master' }),
    ).toBe('bash -lc "CLAUDE_SESSION_ID=cwd-aba64f66-1f2e CLAUDE_SESSION_LABEL=cc-wt-master dclaude --acct ent --effort xhigh --resume abc-123 || exec bash -l"')
  })
  test('no daemon id: plain resume; unsafe label dropped', () => {
    expect(relaunchCommand({ acct: 'team', flags: [], transcriptId: 'abc', label: 'my label' })).toBe(
      'bash -lc "dclaude --acct team --resume abc || exec bash -l"',
    )
  })
  test('refuses an unsafe transcript id', () => {
    expect(() => relaunchCommand({ acct: 'team', flags: [], transcriptId: 'a"; rm -rf ~; "' })).toThrow('unsafe token')
  })
})

describe('busyReason', () => {
  test('turn state and live background shells block; zombies and mcp servers do not', () => {
    expect(busyReason('busy', [])).toBe('mid-turn')
    expect(busyReason('ask', [])).toBe('waiting on a question')
    expect(busyReason('ready', [{ comm: 'bash', state: 'S', pid: 9 }])).toBe('background shell 9 running')
    expect(busyReason('ready', [{ comm: 'bash', state: 'Z', pid: 9 }, { comm: 'bun', state: 'S', pid: 10 }])).toBeNull()
    expect(busyReason('', [])).toBeNull()
  })
})

describe('restartSessions', () => {
  test.if(!existsSync('/proc/self/stat'))('says so on hosts without /proc', () => {
    expect(restartSessions('all')).toBe('restart reads /proc: Linux hosts only')
  })
})
