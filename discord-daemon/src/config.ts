import { homedir } from 'os'
import { join } from 'path'
import { readFileSync, chmodSync } from 'fs'

export const STATE_DIR = process.env.DISCORD_STATE_DIR ?? join(homedir(), '.claude', 'channels', 'discord')
export const ACCESS_FILE = join(STATE_DIR, 'access.json')
export const APPROVED_DIR = join(STATE_DIR, 'approved')
export const INBOX_DIR = join(STATE_DIR, 'inbox')
export const ENV_FILE = join(STATE_DIR, '.env')

export const BIND_HOST = process.env.DAEMON_BIND_HOST ?? '127.0.0.1'
export const BIND_PORT = parseInt(process.env.DAEMON_BIND_PORT ?? '7777', 10)

// Shared secret between daemon and session-mcp clients. Required.
export const DAEMON_TOKEN = process.env.DAEMON_TOKEN ?? ''

// Discord text channel where session threads live. Required.
export const SESSIONS_CHANNEL_ID = process.env.DISCORD_SESSIONS_CHANNEL_ID ?? ''

export const HEARTBEAT_STALE_MS = parseInt(process.env.HEARTBEAT_STALE_MS ?? '90000', 10)
export const HEARTBEAT_SWEEP_MS = 15000

// Skip Discord gateway entirely. HTTP API still served. Stub thread IDs.
// Used by smoke tests + dev-mode runs without a real bot token.
export const MOCK_DISCORD = process.env.DAEMON_DISCORD_MOCK === '1'

// Load STATE_DIR/.env into process.env. Real env wins.
export function loadEnvFile(): void {
  try {
    chmodSync(ENV_FILE, 0o600)
    for (const line of readFileSync(ENV_FILE, 'utf8').split('\n')) {
      const m = line.match(/^(\w+)=(.*)$/)
      if (m && process.env[m[1]!] === undefined) process.env[m[1]!] = m[2]!
    }
  } catch {}
}

export function getDiscordToken(): string {
  const t = process.env.DISCORD_BOT_TOKEN
  if (!t) {
    throw new Error(`DISCORD_BOT_TOKEN required. Set in ${ENV_FILE} or env.`)
  }
  return t
}

export function assertRequired(): void {
  if (!DAEMON_TOKEN) throw new Error('DAEMON_TOKEN env var required (shared secret between daemon and sessions).')
  if (MOCK_DISCORD) return
  if (!SESSIONS_CHANNEL_ID) throw new Error('DISCORD_SESSIONS_CHANNEL_ID env var required (channel where session threads are created).')
}
