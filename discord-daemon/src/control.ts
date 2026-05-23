import { spawn } from 'child_process'
import { existsSync, mkdirSync, readdirSync, statSync } from 'fs'
import { homedir } from 'os'
import { join, resolve } from 'path'
import { registry } from './registry.ts'
import type { DiscordBot } from './discord.ts'
import type { InboxEvent } from './types.ts'

const PROJECTS_ROOT = join(homedir(), 'dev')
const DEFAULT_SCRATCH = join(homedir(), 'scratch')
const PATH_OK = /^[A-Za-z0-9._/-]+$/

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
    case 'restart': {
      const label = parts[1]
      if (!label) return 'usage: `restart <label>` — signal session-mcp to exit so claude restarts cleanly'
      const s = resolveSession(label)
      if (!s) return `no session matching \`${label}\``
      registry.deliver(s.sessionId, {
        kind: 'message',
        message_id: `restart-${Date.now()}`,
        chat_id: s.threadId,
        user: 'daemon',
        user_id: '0',
        ts: new Date().toISOString(),
        content: '__daemon_restart_requested__',
      })
      return `restart signal sent to \`${s.label}\` (session-mcp may not exit on its own — manual claude restart still needed)`
    }
    case 'projects':
    case 'projs':
      return listProjects()
    case 'start':
    case 'spawn':
      return await startSession(parts.slice(1).join(' ').trim())
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
    '`restart <label>` — signal session restart',
    '`projects` — list discoverable repos under `~/dev`',
    '`start [relpath]` — spawn a new dclaude session. With no arg: `~/scratch`. With relpath: `$HOME/<relpath>` (mkdir -p if missing).',
    '`help` — this',
    '',
    'For interactive chat with a session, post in its thread (not here).',
  ].join('\n')
}

function listProjects(): string {
  if (!existsSync(PROJECTS_ROOT)) return `no \`${PROJECTS_ROOT}\` on this host`
  const groups: string[] = []
  const top = safeReadDirs(PROJECTS_ROOT)
  for (const entry of top) {
    const entryPath = join(PROJECTS_ROOT, entry)
    if (looksLikeRepo(entryPath)) {
      groups.push(`• \`${relFromHome(entryPath)}\``)
      continue
    }
    const subs = safeReadDirs(entryPath)
      .map(s => join(entryPath, s))
      .filter(looksLikeRepo)
    if (subs.length === 0) continue
    groups.push(`**${entry}/**`)
    for (const sub of subs) {
      groups.push(`• \`${relFromHome(sub)}\``)
    }
  }
  if (groups.length === 0) return `no repos found under \`${PROJECTS_ROOT}\``
  return `**projects:**\n${groups.join('\n')}\n\nSpawn with: \`start <relpath>\``
}

async function startSession(arg: string): Promise<string> {
  let target: string
  let createdMsg = ''
  if (!arg) {
    target = DEFAULT_SCRATCH
    if (!existsSync(target)) {
      try { mkdirSync(target, { recursive: true }); createdMsg = ` (created)` }
      catch (err) { return `mkdir failed: ${(err as Error).message}` }
    }
  } else {
    if (arg.startsWith('/') || arg.includes('..') || !PATH_OK.test(arg)) {
      return `invalid path: \`${arg}\` — must be relative to \$HOME, no \`..\`, chars [A-Za-z0-9._/-]`
    }
    target = resolve(homedir(), arg)
    if (!target.startsWith(homedir() + '/') && target !== homedir()) {
      return `path escapes \$HOME: \`${target}\``
    }
    if (!existsSync(target)) {
      try { mkdirSync(target, { recursive: true }); createdMsg = ` (created)` }
      catch (err) { return `mkdir failed: ${(err as Error).message}` }
    }
  }
  const sessionName = sanitizeTmuxName(arg ? arg.split('/').pop() ?? 'scratch' : 'scratch')
  return spawnDclaude(sessionName, target, createdMsg)
}

function spawnDclaude(sessionName: string, cwd: string, createdMsg: string): string {
  // Detached tmux session; inner shell sources bashrc so dclaude function exists.
  const cmd = 'tmux'
  const args = ['new-session', '-d', '-s', sessionName, '-c', cwd, 'bash -lc dclaude']
  try {
    const child = spawn(cmd, args, { stdio: 'ignore', detached: true })
    child.unref()
  } catch (err) {
    return `tmux spawn failed: ${(err as Error).message}`
  }
  return `spawning \`${sessionName}\` in \`${cwd}\`${createdMsg} — Discord thread should appear in a few seconds`
}

function safeReadDirs(p: string): string[] {
  try {
    return readdirSync(p).filter(name => {
      if (name.startsWith('.')) return false
      try { return statSync(join(p, name)).isDirectory() } catch { return false }
    })
  } catch { return [] }
}

function looksLikeRepo(p: string): boolean {
  return existsSync(join(p, '.git'))
}

function relFromHome(p: string): string {
  const h = homedir() + '/'
  return p.startsWith(h) ? p.slice(h.length) : p
}

function sanitizeTmuxName(s: string): string {
  return s.replace(/[^A-Za-z0-9._-]+/g, '-').slice(0, 64) || 'session'
}

function formatList(): string {
  const sessions = registry.list()
  if (sessions.length === 0) return 'no sessions'
  const rows = sessions.map(s => {
    const age = humanAge(Date.now() - s.registeredAt)
    const heartbeatAge = humanAge(Date.now() - s.lastHeartbeat)
    const tag = s.state === 'dormant' ? ' _(dormant)_' : ''
    return `• \`${s.label}\`${tag} — ${s.cwd} — up ${age}, hb ${heartbeatAge} ago`
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
