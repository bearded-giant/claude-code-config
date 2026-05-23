import { readFileSync, writeFileSync, mkdirSync, renameSync, readdirSync, rmSync } from 'fs'
import type { Access } from './types.ts'
import { ACCESS_FILE, APPROVED_DIR, STATE_DIR } from './config.ts'

export function defaultAccess(): Access {
  return { dmPolicy: 'pairing', allowFrom: [], groups: {}, pending: {} }
}

export function readAccess(): Access {
  try {
    const raw = readFileSync(ACCESS_FILE, 'utf8')
    const parsed = JSON.parse(raw) as Partial<Access>
    return {
      dmPolicy: parsed.dmPolicy ?? 'pairing',
      allowFrom: parsed.allowFrom ?? [],
      groups: parsed.groups ?? {},
      pending: parsed.pending ?? {},
      mentionPatterns: parsed.mentionPatterns,
      ackReaction: parsed.ackReaction,
      replyToMode: parsed.replyToMode,
      textChunkLimit: parsed.textChunkLimit,
      chunkMode: parsed.chunkMode,
    }
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === 'ENOENT') return defaultAccess()
    try { renameSync(ACCESS_FILE, `${ACCESS_FILE}.corrupt-${Date.now()}`) } catch {}
    process.stderr.write('daemon: access.json corrupt, moved aside. Starting fresh.\n')
    return defaultAccess()
  }
}

export function saveAccess(a: Access): void {
  mkdirSync(STATE_DIR, { recursive: true, mode: 0o700 })
  const tmp = ACCESS_FILE + '.tmp'
  writeFileSync(tmp, JSON.stringify(a, null, 2) + '\n', { mode: 0o600 })
  renameSync(tmp, ACCESS_FILE)
}

export function pruneExpired(a: Access): boolean {
  const now = Date.now()
  let changed = false
  for (const [code, p] of Object.entries(a.pending)) {
    if (p.expiresAt < now) {
      delete a.pending[code]
      changed = true
    }
  }
  return changed
}

export type GateResult =
  | { action: 'deliver'; access: Access }
  | { action: 'drop' }
  | { action: 'pair'; code: string; isResend: boolean }

// Drain approval files written by the /discord:access skill. Returns
// { senderId, dmChannelId } per approval. Caller sends confirmation + may
// route any queued state.
export function drainApprovals(): Array<{ senderId: string; dmChannelId: string }> {
  let files: string[]
  try {
    files = readdirSync(APPROVED_DIR)
  } catch {
    return []
  }
  const out: Array<{ senderId: string; dmChannelId: string }> = []
  for (const senderId of files) {
    const file = `${APPROVED_DIR}/${senderId}`
    try {
      const dmChannelId = readFileSync(file, 'utf8').trim()
      if (dmChannelId) out.push({ senderId, dmChannelId })
    } catch {}
    rmSync(file, { force: true })
  }
  return out
}
