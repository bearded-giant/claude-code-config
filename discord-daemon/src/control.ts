import { spawnSync } from 'child_process'
import { existsSync, mkdirSync, readdirSync, statSync } from 'fs'
import { basename, dirname, join, resolve } from 'path'
import { HOME_ROOT } from './config.ts'
import { registry } from './registry.ts'
import type { DiscordBot } from './discord.ts'
import type { InboxEvent } from './types.ts'

const PROJECTS_ROOT = join(HOME_ROOT, 'dev')
const DEFAULT_SCRATCH = join(HOME_ROOT, 'scratch')
const PATH_OK = /^[A-Za-z0-9._/-]+$/
const PROJECTS_DEPTH = 3
const START_FLAGS: Record<string, readonly string[]> = {
  acct: ['team', 'ent'],
  effort: ['low', 'medium', 'high', 'xhigh', 'max'],
  model: ['opus', 'sonnet', 'fable'],
}

// DM commands from allowlisted users. Returns text to send back, or null to ignore.
// Sessions never receive DMs — DMs are control-only.
export async function handleControlDM(input: string, _userId: string, bot: DiscordBot): Promise<string | null> {
  const parts = input.split(/\s+/).filter(Boolean)
  const cmd = (parts[0] ?? '').toLowerCase()
  switch (cmd) {
    case '':
      return null
    case 'help':
    case '?':
      return helpText()
    case 'list':
    case 'ls':
    case 'sessions':
      return formatList()
    case 'status': {
      const label = parts[1]
      if (!label) return 'usage: `status <label>`'
      const s = resolveSession(label)
      if (!s) return `no session matching \`${label}\``
      return formatSession(s)
    }
    case 'kill': {
      const label = parts[1]
      if (!label) return 'usage: `kill <label>` — hard-removes session from registry (drops thread mapping; future register creates a new thread).'
      const s = resolveSession(label)
      if (!s) return `no session matching \`${label}\``
      registry.delete(s.sessionId)
      try { await bot.archiveSessionThread(s.threadId, `killed via DM`) } catch {}
      return `deleted \`${s.label}\` (${s.sessionId}) + archived thread`
    }
    case 'send': {
      const label = parts[1]
      const text = input.replace(/^\S+\s+\S+\s+/, '')
      if (!label || !text) return 'usage: `send <label> <message...>` — post into a session\'s thread without opening it'
      const s = resolveSession(label)
      if (!s) return `no session matching \`${label}\``
      try {
        await bot.sendToThread(s.threadId, text)
        return `→ \`${s.label}\``
      } catch (err) {
        return `send failed: ${(err as Error).message}`
      }
    }
    case 'tail': {
      const label = parts[1]
      const n = parts[2] ? parseInt(parts[2], 10) : 10
      if (!label || !Number.isFinite(n) || n <= 0) return 'usage: `tail <label> [n]` — show recent inbox events for a session'
      const s = resolveSession(label)
      if (!s) return `no session matching \`${label}\``
      const events = registry.recent(s.sessionId, n)
      if (events.length === 0) return `\`${s.label}\` has no recent inbox events`
      return `**${s.label} — last ${events.length}:**\n${events.map(formatEvent).join('\n')}`
    }
    case 'projects':
    case 'projs':
      return listProjects()
    case 'start':
    case 'spawn':
      return startSession(parts.slice(1))
    default:
      return `unknown command: \`${cmd}\`\n\n${helpText()}`
  }
}

function resolveSession(label: string): ReturnType<typeof registry.list>[number] | null {
  return registry.list().find(s => s.label === label || s.sessionId === label) ?? null
}

function helpText(): string {
  return [
    '**daemon commands:**',
    '`list` — show active sessions',
    '`status <label>` — details for one session',
    '`send <label> <text>` — post into a session\'s thread',
    '`tail <label> [n]` — last N inbox events',
    '`kill <label>` — unregister + archive thread',
    `\`projects\` — repos and worktrees under \`${relFromRoot(PROJECTS_ROOT)}\``,
    `\`start [relpath] [--acct team|ent] [--effort ${START_FLAGS.effort!.join('|')}] [--model ${START_FLAGS.model!.join('|')}]\` — spawn a dclaude session in \`${HOME_ROOT}/<relpath>\` (mkdir -p if missing; no relpath: \`${relFromRoot(DEFAULT_SCRATCH)}\`)`,
    '`help` — this',
    '',
    'For interactive chat with a session, post in its thread (not here).',
  ].join('\n')
}

export function parseStartArgs(tokens: string[]): { relpath: string; dclaudeArgs: string[] } | { error: string } {
  let relpath = ''
  const dclaudeArgs: string[] = []
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i]!
    if (t.startsWith('--')) {
      const eq = t.indexOf('=')
      const name = eq === -1 ? t.slice(2) : t.slice(2, eq)
      const allowed = START_FLAGS[name]
      if (!allowed) return { error: `unknown flag \`${t}\`` }
      const value = eq === -1 ? tokens[++i] : t.slice(eq + 1)
      if (!value || !allowed.includes(value)) return { error: `\`--${name}\` takes one of ${allowed.join('|')}` }
      dclaudeArgs.push(`--${name}`, value)
    } else if (!relpath) {
      relpath = t
    } else {
      return { error: `unexpected argument \`${t}\`` }
    }
  }
  return { relpath, dclaudeArgs }
}

// repos (.git) and worktree layouts (.bare + one dir per worktree) up to `depth` levels under root
export function listProjectPaths(root: string, depth = PROJECTS_DEPTH): string[] {
  const found: string[] = []
  const walk = (dir: string, level: number) => {
    for (const name of safeReadDirs(dir)) {
      const p = join(dir, name)
      if (existsSync(join(p, '.bare'))) {
        for (const wt of safeReadDirs(p)) found.push(join(p, wt))
      } else if (existsSync(join(p, '.git'))) {
        found.push(p)
      } else if (level < depth) {
        walk(p, level + 1)
      }
    }
  }
  walk(root, 1)
  return found.map(p => p.slice(root.length + 1)).sort()
}

function listProjects(): string {
  if (!existsSync(PROJECTS_ROOT)) return `no \`${PROJECTS_ROOT}\` on this host`
  const paths = listProjectPaths(PROJECTS_ROOT)
  if (paths.length === 0) return `no repos found under \`${PROJECTS_ROOT}\``
  const rel = relFromRoot(PROJECTS_ROOT)
  return `**projects:**\n${paths.map(p => `• \`${rel}/${p}\``).join('\n')}\n\nSpawn with: \`start ${rel}/<path> [--acct ent] [--effort high]\``
}

function startSession(tokens: string[]): string {
  const parsed = parseStartArgs(tokens)
  if ('error' in parsed) return `${parsed.error}\n\n${helpText()}`
  const { relpath, dclaudeArgs } = parsed
  let target: string
  if (!relpath) {
    target = DEFAULT_SCRATCH
  } else {
    if (relpath.startsWith('/') || relpath.includes('..') || !PATH_OK.test(relpath)) {
      return `invalid path: \`${relpath}\` — must be relative to \`${HOME_ROOT}\`, no \`..\`, chars [A-Za-z0-9._/-]`
    }
    target = resolve(HOME_ROOT, relpath)
    if (!target.startsWith(HOME_ROOT + '/')) {
      return `path escapes \`${HOME_ROOT}\`: \`${target}\``
    }
  }
  let createdMsg = ''
  if (!existsSync(target)) {
    try { mkdirSync(target, { recursive: true }); createdMsg = ' (created)' }
    catch (err) { return `mkdir failed: ${(err as Error).message}` }
  }
  return spawnDclaude(sessionNameFor(target), target, dclaudeArgs, createdMsg)
}

// worktree dirs all look like "master" or "main": name them <base>-wt-<branch>, same as the cvps alias
export function sessionNameFor(cwd: string): string {
  const parent = basename(dirname(cwd))
  const name = parent.endsWith('-wt') ? `${parent}-${basename(cwd)}` : basename(cwd)
  return name.replace(/[^A-Za-z0-9._-]+/g, '-').slice(0, 64) || 'session'
}

function spawnDclaude(sessionName: string, cwd: string, dclaudeArgs: string[], createdMsg: string): string {
  // detached tmux session; the login shell puts dclaude on PATH. args are allowlisted tokens, safe to join.
  const shell = `bash -lc "dclaude ${dclaudeArgs.join(' ')}"`
  const r = spawnSync('tmux', ['new-session', '-d', '-s', sessionName, '-c', cwd, shell], { encoding: 'utf8', timeout: 10_000 })
  if (r.error) return `tmux spawn failed: ${r.error.message}`
  if (r.status !== 0) return `tmux spawn failed: ${r.stderr.trim() || `exit ${r.status}`}`
  const flags = dclaudeArgs.length ? ` with \`${dclaudeArgs.join(' ')}\`` : ''
  return `spawning \`${sessionName}\` in \`${cwd}\`${createdMsg}${flags} — Discord thread should appear in a few seconds`
}

function safeReadDirs(p: string): string[] {
  try {
    return readdirSync(p).filter(name => {
      if (name.startsWith('.')) return false
      try { return statSync(join(p, name)).isDirectory() } catch { return false }
    })
  } catch { return [] }
}

function relFromRoot(p: string): string {
  const h = HOME_ROOT + '/'
  return p.startsWith(h) ? p.slice(h.length) : p
}

function formatList(): string {
  const sessions = registry.list()
  if (sessions.length === 0) return 'no sessions'
  const rows = sessions.map(s => {
    const age = humanAge(Date.now() - s.registeredAt)
    const heartbeatAge = humanAge(Date.now() - s.lastHeartbeat)
    const tag = s.state === 'dormant' ? ' _(dormant)_' : ''
    return `• \`${s.label}\`${tag} — \`${s.cwd}\` — up ${age}, hb ${heartbeatAge} ago`
  })
  return `**${sessions.length} session(s):**\n${rows.join('\n')}`
}

function formatSession(s: ReturnType<typeof registry.list>[number]): string {
  return [
    `**${s.label}** _(${s.state})_`,
    `session_id: \`${s.sessionId}\``,
    `cwd: \`${s.cwd}\``,
    `pid: ${s.pid}`,
    `thread: <#${s.threadId}>`,
    `up: ${humanAge(Date.now() - s.registeredAt)}`,
    `last heartbeat: ${humanAge(Date.now() - s.lastHeartbeat)} ago`,
  ].join('\n')
}

function formatEvent(ev: InboxEvent): string {
  if (ev.kind === 'message') {
    const snip = ev.content.length > 100 ? ev.content.slice(0, 100) + '…' : ev.content
    return `\`${ev.ts}\` ${ev.user}: ${snip}`
  }
  return `\`${(ev as { ts?: string }).ts ?? ''}\` [${(ev as { kind: string }).kind}]`
}

function humanAge(ms: number): string {
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h${m % 60}m`
  return `${Math.floor(h / 24)}d${h % 24}h`
}
