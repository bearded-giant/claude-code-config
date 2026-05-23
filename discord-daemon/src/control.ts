import { registry } from './registry.ts'

// DM commands from allowlisted users. Returns text to send back, or null to ignore.
// Sessions never receive DMs — DMs are control-only.
export async function handleControlDM(input: string, _userId: string): Promise<string | null> {
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
      const s = registry.list().find(s => s.label === label || s.sessionId === label)
      if (!s) return `no session matching \`${label}\``
      return formatSession(s)
    }
    case 'kill': {
      const label = parts[1]
      if (!label) return 'usage: `kill <label>` — removes session from registry. Process not actually killed; claude will re-register on next heartbeat unless dead.'
      const s = registry.list().find(s => s.label === label || s.sessionId === label)
      if (!s) return `no session matching \`${label}\``
      registry.unregister(s.sessionId)
      return `unregistered \`${s.label}\` (${s.sessionId})`
    }
    default:
      return `unknown command: \`${cmd}\`\n\n${helpText()}`
  }
}

function helpText(): string {
  return [
    '**daemon commands:**',
    '`list` — show active sessions',
    '`status <label>` — details for one session',
    '`kill <label>` — unregister a session',
    '`help` — this',
    '',
    'To chat with a session, post in its thread (not here).',
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

function humanAge(ms: number): string {
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h${m % 60}m`
  return `${Math.floor(h / 24)}d${h % 24}h`
}
