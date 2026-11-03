import { spawnSync } from 'child_process'
import { existsSync, readFileSync, readdirSync, readlinkSync, statSync } from 'fs'
import { homedir } from 'os'
import { join } from 'path'
import { registry } from './registry.ts'

const SAFE = /^[A-Za-z0-9._:=/-]+$/
const KEEP_FLAGS = new Set(['--effort', '--model'])
const SHELLS = new Set(['bash', 'sh', 'dash', 'zsh'])
const RETRY_MS = 20_000
const QUEUE_TTL_MS = 4 * 3600_000
const PANE_FORMAT = ['#{pane_id}', '#{pane_pid}', '#{session_name}', '#{@claude_state}', '#{@claude_session_id}'].join('\t')

type Proc = { pid: number; ppid: number; comm: string; state: string; argv: string[]; env: Record<string, string>; cwd: string }
type Pane = { id: string; pid: number; session: string; state: string; transcriptId: string }
export type Target = { pane: Pane; label: string; cwd: string; cmd?: string; busy: string | null; skip?: string }

export function keptFlags(argv: string[]): string[] {
  const out: string[] = []
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]!
    const eq = a.indexOf('=')
    const name = eq === -1 ? a : a.slice(0, eq)
    if (!KEEP_FLAGS.has(name)) continue
    const value = eq === -1 ? argv[++i] : a.slice(eq + 1)
    if (value && SAFE.test(value)) out.push(name, value)
  }
  return out
}

export function acctOf(configDir: string | undefined): 'team' | 'ent' {
  return configDir?.endsWith('-ent') ? 'ent' : 'team'
}

export function projectSlug(cwd: string): string {
  return cwd.replace(/[^A-Za-z0-9]/g, '-')
}

export function relaunchCommand(o: { acct: string; flags: string[]; transcriptId: string; daemonId?: string; label?: string }): string {
  const env: string[] = []
  // the same CLAUDE_SESSION_ID makes session-mcp re-register into the session's existing Discord thread
  if (o.daemonId) env.push(`CLAUDE_SESSION_ID=${o.daemonId}`)
  if (o.label && SAFE.test(o.label)) env.push(`CLAUDE_SESSION_LABEL=${o.label}`)
  const words = [...env, 'dclaude', '--acct', o.acct, ...o.flags, '--resume', o.transcriptId]
  const bad = words.find(w => !SAFE.test(w))
  if (bad) throw new Error(`unsafe token \`${bad}\``)
  return `bash -lc "${words.join(' ')}"`
}

export function busyReason(state: string, children: { comm: string; state: string; pid: number }[]): string | null {
  if (state === 'busy') return 'mid-turn'
  if (state === 'ask') return 'waiting on a question'
  // a live shell child is a background task the restart would kill; zombies are finished ones
  const sh = children.find(c => SHELLS.has(c.comm) && c.state !== 'Z')
  return sh ? `background shell ${sh.pid} running` : null
}

function proc(pid: number): Proc | null {
  try {
    const stat = readFileSync(`/proc/${pid}/stat`, 'utf8')
    const close = stat.lastIndexOf(')')
    const rest = stat.slice(close + 2).split(' ')
    const env: Record<string, string> = {}
    try {
      for (const kv of readFileSync(`/proc/${pid}/environ`, 'utf8').split('\0')) {
        const i = kv.indexOf('=')
        if (i > 0) env[kv.slice(0, i)] = kv.slice(i + 1)
      }
    } catch {}
    let cwd = ''
    try { cwd = readlinkSync(`/proc/${pid}/cwd`) } catch {}
    return {
      pid,
      ppid: Number(rest[1]),
      comm: stat.slice(stat.indexOf('(') + 1, close),
      state: rest[0] ?? '',
      argv: readFileSync(`/proc/${pid}/cmdline`, 'utf8').split('\0').filter(Boolean),
      env,
      cwd,
    }
  } catch { return null }
}

function children(pid: number): Proc[] {
  const kids = new Set<number>()
  try {
    for (const tid of readdirSync(`/proc/${pid}/task`)) {
      try {
        for (const c of readFileSync(`/proc/${pid}/task/${tid}/children`, 'utf8').trim().split(/\s+/)) if (c) kids.add(Number(c))
      } catch {}
    }
  } catch {}
  return [...kids].map(proc).filter((p): p is Proc => p !== null)
}

function claudeIn(panePid: number): Proc | null {
  const p = proc(panePid)
  if (!p) return null
  if (p.comm === 'claude') return p
  return children(panePid).find(c => c.comm === 'claude') ?? null
}

function listPanes(): Pane[] {
  const r = spawnSync('tmux', ['list-panes', '-a', '-F', PANE_FORMAT], { encoding: 'utf8', timeout: 5_000 })
  if (r.status !== 0) return []
  return r.stdout.split('\n').filter(Boolean).map(line => {
    const [id = '', pid = '0', session = '', state = '', transcriptId = ''] = line.split('\t')
    return { id, pid: Number(pid), session, state, transcriptId }
  })
}

function newestTranscript(cwd: string): string {
  const dir = join(homedir(), '.claude', 'projects', projectSlug(cwd))
  let best = ''
  let bestMtime = 0
  try {
    for (const f of readdirSync(dir)) {
      if (!f.endsWith('.jsonl')) continue
      const m = statSync(join(dir, f)).mtimeMs
      if (m > bestMtime) { bestMtime = m; best = f.slice(0, -'.jsonl'.length) }
    }
  } catch {}
  return best
}

export function planRestart(filter: string): Target[] {
  const found = listPanes()
    .map(pane => ({ pane, claude: claudeIn(pane.pid) }))
    .filter((x): x is { pane: Pane; claude: Proc } => x.claude !== null)
  const perCwd = new Map<string, number>()
  for (const { claude } of found) perCwd.set(claude.cwd, (perCwd.get(claude.cwd) ?? 0) + 1)
  const active = registry.list().filter(s => s.state === 'active')
  return found
    .map(({ pane, claude }): Target => {
      const reg = active.find(s => proc(s.pid)?.ppid === claude.pid)
      const label = reg?.label ?? claude.env.CLAUDE_SESSION_LABEL ?? pane.session
      const base = { pane, label, cwd: claude.cwd, busy: busyReason(pane.state, children(claude.pid)) }
      // remote-control holds no transcript of its own: rerun the pane's start command as is
      if (claude.argv[1] === 'remote-control') return base
      if (!claude.argv.includes('server:discord')) return { ...base, skip: 'not started by dclaude' }
      // sessions older than the SessionStart pane stamp: newest transcript in the cwd, only when no other claude shares it
      const transcriptId = pane.transcriptId || (perCwd.get(claude.cwd) === 1 ? newestTranscript(claude.cwd) : '')
      if (!transcriptId) return { ...base, skip: 'no transcript id on the pane and another claude shares its cwd' }
      try {
        const cmd = relaunchCommand({
          acct: acctOf(claude.env.CLAUDE_SECURESTORAGE_CONFIG_DIR),
          flags: keptFlags(claude.argv),
          transcriptId,
          daemonId: reg?.sessionId,
          label,
        })
        return { ...base, cmd }
      } catch (err) {
        return { ...base, skip: (err as Error).message }
      }
    })
    .filter(t => filter === 'all' || t.label === filter || t.pane.session === filter)
}

function respawn(t: Target): string {
  const args = ['respawn-pane', '-k', '-t', t.pane.id]
  if (t.cmd) args.push('-c', t.cwd, t.cmd)
  const r = spawnSync('tmux', args, { encoding: 'utf8', timeout: 10_000 })
  if (r.status === 0) return `\`${t.label}\` restarted`
  return `\`${t.label}\`: respawn failed: ${r.error?.message ?? (r.stderr.trim() || `exit ${r.status}`)}`
}

const queued = new Map<string, { label: string; since: number }>()
let timer: ReturnType<typeof setInterval> | null = null

function drainQueue(): void {
  const targets = new Map(planRestart('all').map(t => [t.pane.id, t]))
  for (const [paneId, q] of queued) {
    const t = targets.get(paneId)
    if (!t || t.skip || Date.now() - q.since > QUEUE_TTL_MS) {
      process.stderr.write(`daemon: restart of ${q.label} dropped (${t?.skip ?? (t ? 'waited too long' : 'pane gone')})\n`)
      queued.delete(paneId)
    } else if (!t.busy) {
      process.stderr.write(`daemon: ${respawn(t)} (was queued)\n`)
      queued.delete(paneId)
    }
  }
  if (queued.size === 0 && timer) { clearInterval(timer); timer = null }
}

function enqueue(t: Target): void {
  if (!queued.has(t.pane.id)) queued.set(t.pane.id, { label: t.label, since: Date.now() })
  timer ??= setInterval(drainQueue, RETRY_MS)
}

export const RESTART_USAGE = '`restart <label>|all [--force] [--dry-run]` — relaunch claude sessions in their tmux panes on the same transcript, flags and thread; busy ones wait until idle unless `--force`'

export function restartSessions(target: string, force = false, dryRun = false): string {
  if (!existsSync('/proc/self/stat')) return 'restart reads /proc: Linux hosts only'
  const targets = planRestart(target)
  if (targets.length === 0) return `no claude pane matching \`${target}\``
  const lines = targets.map(t => {
    if (t.skip) return `• \`${t.label}\`: skipped, ${t.skip}`
    if (dryRun) return `• \`${t.label}\`: ${t.busy && !force ? `${t.busy}, would wait` : 'would restart'} → ${t.cmd ?? 'its start command'}`
    if (t.busy && !force) {
      enqueue(t)
      return `• \`${t.label}\`: ${t.busy}, restarts once idle`
    }
    return `• ${respawn(t)}`
  })
  return `**restart ${target}${dryRun ? ' (dry run)' : ''}:**\n${lines.join('\n')}`
}
