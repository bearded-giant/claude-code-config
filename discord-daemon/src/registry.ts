import type { Session, InboxEvent } from './types.ts'
import { HEARTBEAT_STALE_MS } from './config.ts'

type Subscriber = (ev: InboxEvent) => void

type Entry = Session & {
  subscribers: Set<Subscriber>
  buffered: InboxEvent[]
}

const BUFFER_CAP = 200

class Registry {
  private bySession = new Map<string, Entry>()
  private byThread = new Map<string, string>() // threadId -> sessionId

  register(s: Omit<Session, 'registeredAt' | 'lastHeartbeat'>): Session {
    const now = Date.now()
    const existing = this.bySession.get(s.sessionId)
    if (existing) {
      // re-register (claude restarted same session_id) — keep buffer, refresh meta
      existing.label = s.label
      existing.cwd = s.cwd
      existing.pid = s.pid
      existing.threadId = s.threadId
      existing.lastHeartbeat = now
      this.byThread.set(s.threadId, s.sessionId)
      return entryToSession(existing)
    }
    const entry: Entry = {
      ...s,
      registeredAt: now,
      lastHeartbeat: now,
      subscribers: new Set(),
      buffered: [],
    }
    this.bySession.set(s.sessionId, entry)
    this.byThread.set(s.threadId, s.sessionId)
    return entryToSession(entry)
  }

  unregister(sessionId: string): Session | null {
    const e = this.bySession.get(sessionId)
    if (!e) return null
    this.bySession.delete(sessionId)
    this.byThread.delete(e.threadId)
    for (const sub of e.subscribers) {
      try { sub({ kind: 'message', message_id: '__closed__', chat_id: e.threadId, user: 'daemon', user_id: '0', ts: new Date().toISOString(), content: '__session_unregistered__' }) } catch {}
    }
    e.subscribers.clear()
    return entryToSession(e)
  }

  heartbeat(sessionId: string): boolean {
    const e = this.bySession.get(sessionId)
    if (!e) return false
    e.lastHeartbeat = Date.now()
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

  // Deliver event to all subscribers of session. Buffers if none connected.
  deliver(sessionId: string, ev: InboxEvent): boolean {
    const e = this.bySession.get(sessionId)
    if (!e) return false
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

  // Subscribe to inbox. Returns unsubscribe fn. Drains buffered events first.
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

  sweepStale(): Session[] {
    const cutoff = Date.now() - HEARTBEAT_STALE_MS
    const dead: Session[] = []
    for (const e of this.bySession.values()) {
      if (e.lastHeartbeat < cutoff) dead.push(entryToSession(e))
    }
    for (const d of dead) this.unregister(d.sessionId)
    return dead
  }
}

function entryToSession(e: Entry): Session {
  return {
    sessionId: e.sessionId,
    label: e.label,
    cwd: e.cwd,
    pid: e.pid,
    threadId: e.threadId,
    registeredAt: e.registeredAt,
    lastHeartbeat: e.lastHeartbeat,
  }
}

export const registry = new Registry()
