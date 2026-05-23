import { readFileSync, writeFileSync, mkdirSync, renameSync } from 'fs'
import { dirname } from 'path'
import type { Session, InboxEvent } from './types.ts'
import { HEARTBEAT_STALE_MS, SESSIONS_FILE } from './config.ts'

type Subscriber = (ev: InboxEvent) => void

type Entry = Session & {
  subscribers: Set<Subscriber>
  buffered: InboxEvent[]
  recentEvents: InboxEvent[]  // ring buffer for `tail`
}

const BUFFER_CAP = 200
const RECENT_CAP = 50
const PERSIST_DEBOUNCE_MS = 1000

type PersistedEntry = Pick<Session, 'sessionId' | 'label' | 'cwd' | 'pid' | 'threadId' | 'registeredAt' | 'lastHeartbeat' | 'state'>

class Registry {
  private bySession = new Map<string, Entry>()
  private byThread = new Map<string, string>() // threadId -> sessionId
  private persistTimer: ReturnType<typeof setTimeout> | null = null
  private persistDirty = false

  // Hydrate from disk. Returns loaded session count.
  loadFromDisk(): number {
    try {
      const raw = readFileSync(SESSIONS_FILE, 'utf8')
      const parsed = JSON.parse(raw) as { sessions: PersistedEntry[] }
      for (const s of parsed.sessions ?? []) {
        const entry: Entry = {
          ...s,
          state: s.state ?? 'active', // backward compat for pre-state persisted files
          subscribers: new Set(),
          buffered: [],
          recentEvents: [],
        }
        this.bySession.set(s.sessionId, entry)
        this.byThread.set(s.threadId, s.sessionId)
      }
      return this.bySession.size
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code !== 'ENOENT') {
        process.stderr.write(`daemon: failed to load sessions.json: ${err}\n`)
      }
      return 0
    }
  }

  // Debounced persist. Coalesces bursts (heartbeats every 30s, but multiple
  // sessions). Skip serializing subscribers/buffered — they're runtime-only.
  private schedulePersist(): void {
    this.persistDirty = true
    if (this.persistTimer) return
    this.persistTimer = setTimeout(() => {
      this.persistTimer = null
      if (!this.persistDirty) return
      this.persistDirty = false
      this.persistNow()
    }, PERSIST_DEBOUNCE_MS)
  }

  // Atomic write — tmp + rename. Called sync on shutdown.
  persistNow(): void {
    try {
      mkdirSync(dirname(SESSIONS_FILE), { recursive: true })
      const sessions: PersistedEntry[] = [...this.bySession.values()].map(entryToSession)
      const tmp = SESSIONS_FILE + '.tmp'
      writeFileSync(tmp, JSON.stringify({ sessions }, null, 2) + '\n', { mode: 0o600 })
      renameSync(tmp, SESSIONS_FILE)
    } catch (err) {
      process.stderr.write(`daemon: failed to persist sessions.json: ${err}\n`)
    }
  }

  register(s: Omit<Session, 'registeredAt' | 'lastHeartbeat' | 'state'>): Session {
    const now = Date.now()
    const existing = this.bySession.get(s.sessionId)
    if (existing) {
      existing.label = s.label
      existing.cwd = s.cwd
      existing.pid = s.pid
      existing.threadId = s.threadId
      existing.lastHeartbeat = now
      existing.state = 'active'
      this.byThread.set(s.threadId, s.sessionId)
      this.schedulePersist()
      return entryToSession(existing)
    }
    const entry: Entry = {
      ...s,
      state: 'active',
      registeredAt: now,
      lastHeartbeat: now,
      subscribers: new Set(),
      buffered: [],
      recentEvents: [],
    }
    this.bySession.set(s.sessionId, entry)
    this.byThread.set(s.threadId, s.sessionId)
    this.schedulePersist()
    return entryToSession(entry)
  }

  // Soft unregister: claude session-mcp shut down, but keep entry + thread mapping
  // so a future register with same sessionId reuses the thread.
  markDormant(sessionId: string): Session | null {
    const e = this.bySession.get(sessionId)
    if (!e) return null
    e.state = 'dormant'
    for (const sub of e.subscribers) {
      try { sub({ kind: 'message', message_id: '__closed__', chat_id: e.threadId, user: 'daemon', user_id: '0', ts: new Date().toISOString(), content: '__session_unregistered__' }) } catch {}
    }
    e.subscribers.clear()
    e.buffered.length = 0
    this.schedulePersist()
    return entryToSession(e)
  }

  // Hard delete: drop from registry entirely. Caller archives thread.
  delete(sessionId: string): Session | null {
    const e = this.bySession.get(sessionId)
    if (!e) return null
    this.bySession.delete(sessionId)
    this.byThread.delete(e.threadId)
    for (const sub of e.subscribers) {
      try { sub({ kind: 'message', message_id: '__closed__', chat_id: e.threadId, user: 'daemon', user_id: '0', ts: new Date().toISOString(), content: '__session_unregistered__' }) } catch {}
    }
    e.subscribers.clear()
    this.schedulePersist()
    return entryToSession(e)
  }

  heartbeat(sessionId: string): boolean {
    const e = this.bySession.get(sessionId)
    if (!e) return false
    e.lastHeartbeat = Date.now()
    this.schedulePersist()
    return true
  }

  get(sessionId: string): Session | null {
    const e = this.bySession.get(sessionId)
    return e ? entryToSession(e) : null
  }

  getByThread(threadId: string): Session | null {
    const sid = this.byThread.get(threadId)
    if (!sid) return null
    return this.get(sid)
  }

  list(): Session[] {
    return [...this.bySession.values()].map(entryToSession)
  }

  deliver(sessionId: string, ev: InboxEvent): boolean {
    const e = this.bySession.get(sessionId)
    if (!e) return false
    e.recentEvents.push(ev)
    if (e.recentEvents.length > RECENT_CAP) e.recentEvents.shift()
    if (e.subscribers.size === 0) {
      e.buffered.push(ev)
      if (e.buffered.length > BUFFER_CAP) e.buffered.shift()
      return true
    }
    for (const sub of e.subscribers) {
      try { sub(ev) } catch (err) { process.stderr.write(`daemon: subscriber error: ${err}\n`) }
    }
    return true
  }

  subscribe(sessionId: string, sub: Subscriber): (() => void) | null {
    const e = this.bySession.get(sessionId)
    if (!e) return null
    e.subscribers.add(sub)
    for (const ev of e.buffered) {
      try { sub(ev) } catch {}
    }
    e.buffered.length = 0
    return () => { e.subscribers.delete(sub) }
  }

  recent(sessionId: string, n: number): InboxEvent[] {
    const e = this.bySession.get(sessionId)
    if (!e) return []
    return e.recentEvents.slice(-n)
  }

  // Sweep active sessions whose heartbeats lapsed. Marks them dormant —
  // keeps thread mapping so resumes (claude --resume from same cwd) reattach.
  // Dormant sessions are not re-swept (they don't heartbeat by design).
  sweepStale(): Session[] {
    const cutoff = Date.now() - HEARTBEAT_STALE_MS
    const stale: Session[] = []
    for (const e of this.bySession.values()) {
      if (e.state === 'active' && e.lastHeartbeat < cutoff) stale.push(entryToSession(e))
    }
    for (const s of stale) this.markDormant(s.sessionId)
    return stale
  }
}

function entryToSession(e: Entry | PersistedEntry): Session {
  return {
    sessionId: e.sessionId,
    label: e.label,
    cwd: e.cwd,
    pid: e.pid,
    threadId: e.threadId,
    registeredAt: e.registeredAt,
    lastHeartbeat: e.lastHeartbeat,
    state: e.state ?? 'active',
  }
}

export const registry = new Registry()
