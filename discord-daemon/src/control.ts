import { registry } from './registry.ts'
import type { DiscordBot } from './discord.ts'
import type { InboxEvent } from './types.ts'

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
      if (!label) return 'usage: `kill <label>` — removes session from registry.'
      const s = resolveSession(label)
      if (!s) return `no session matching \`${label}\``
      registry.unregister(s.sessionId)
      try { await bot.archiveSessionThread(s.threadId, `killed via DM`) } catch {}
      return `unregistered \`${s.label}\` (${s.sessionId}) + archived thread`
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
    '`help` — this',
    '',
    'For interactive chat with a session, post in its thread (not here).',
  ].join('\n')
}

function formatList(): string {
  const sessions = registry.list()
  if (sessions.length === 0) return 'no active sessions'
  const rows = sessions.map(s => {
    const age = humanAge(Date.now() - s.registeredAt)
    const heartbeatAge = humanAge(Date.now() - s.lastHeartbeat)
    return `• \`${s.label}\` — ${s.cwd} — up ${age}, hb ${heartbeatAge} ago`
  })
  return `**${sessions.length} session(s):**\n${rows.join('\n')}`
}

function formatSession(s: ReturnType<typeof registry.list>[number]): string {
  return [
    `**${s.label}**`,
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
