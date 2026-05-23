// HTTP/SSE client wrapping the discord-daemon REST API.

export type DaemonConfig = {
  url: string
  token: string
}

export type SendArgs = {
  chat_id: string
  text: string
  reply_to?: string
  files?: string[]
}

export type RegisterArgs = {
  session_id: string
  label: string
  cwd: string
  pid: number
}

export type RegisterResult = {
  session: {
    sessionId: string
    label: string
    cwd: string
    pid: number
    threadId: string
    registeredAt: number
    lastHeartbeat: number
  }
}

export class DaemonClient {
  constructor(private cfg: DaemonConfig) {}

  private async req<T = unknown>(method: string, path: string, body?: unknown): Promise<T> {
    const res = await fetch(`${this.cfg.url}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'x-daemon-token': this.cfg.token,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
    if (!res.ok) {
      let detail: string
      try { detail = (await res.json() as { error?: string }).error ?? res.statusText } catch { detail = res.statusText }
      throw new Error(`daemon ${method} ${path}: ${res.status} ${detail}`)
    }
    return res.json() as Promise<T>
  }

  register(args: RegisterArgs): Promise<RegisterResult> {
    return this.req('POST', '/sessions', args)
  }

  unregister(sessionId: string): Promise<{ ok: true }> {
    return this.req('DELETE', `/sessions/${encodeURIComponent(sessionId)}`)
  }

  heartbeat(sessionId: string): Promise<{ ok: true }> {
    return this.req('POST', `/sessions/${encodeURIComponent(sessionId)}/heartbeat`)
  }

  send(sessionId: string, args: SendArgs): Promise<{ ids: string[] }> {
    return this.req('POST', `/sessions/${encodeURIComponent(sessionId)}/send`, args)
  }

  edit(sessionId: string, args: { chat_id: string; message_id: string; text: string }): Promise<{ id: string }> {
    return this.req('POST', `/sessions/${encodeURIComponent(sessionId)}/edit`, args)
  }

  react(sessionId: string, args: { chat_id: string; message_id: string; emoji: string }): Promise<{ ok: true }> {
    return this.req('POST', `/sessions/${encodeURIComponent(sessionId)}/react`, args)
  }

  fetchMessages(sessionId: string, args: { chat_id: string; limit?: number }): Promise<{ text: string }> {
    return this.req('POST', `/sessions/${encodeURIComponent(sessionId)}/fetch`, args)
  }

  downloadAttachments(sessionId: string, args: { chat_id: string; message_id: string }): Promise<{ files: Array<{ path: string; name: string; contentType: string | null; size: number }> }> {
    return this.req('POST', `/sessions/${encodeURIComponent(sessionId)}/download`, args)
  }

  // Open an SSE stream to /sessions/:id/inbox. Calls onEvent for each event.
  // Reconnects with backoff on failure. Returns a stop() function.
  openInbox(sessionId: string, onEvent: (ev: unknown) => void, onError?: (e: Error) => void): () => void {
    let stopped = false
    let abort: AbortController | null = null
    let backoff = 1000

    const loop = async () => {
      while (!stopped) {
        abort = new AbortController()
        try {
          const res = await fetch(`${this.cfg.url}/sessions/${encodeURIComponent(sessionId)}/inbox`, {
            headers: { 'x-daemon-token': this.cfg.token, Accept: 'text/event-stream' },
            signal: abort.signal,
          })
          if (!res.ok || !res.body) {
            throw new Error(`inbox ${res.status} ${res.statusText}`)
          }
          backoff = 1000
          const reader = res.body.getReader()
          const dec = new TextDecoder()
          let buf = ''
          while (!stopped) {
            const { done, value } = await reader.read()
            if (done) break
            buf += dec.decode(value, { stream: true })
            // SSE event framing: "data: ...\n\n" blocks
            let idx: number
            while ((idx = buf.indexOf('\n\n')) !== -1) {
              const block = buf.slice(0, idx)
              buf = buf.slice(idx + 2)
              for (const line of block.split('\n')) {
                if (!line.startsWith('data:')) continue
                const payload = line.slice(5).trim()
                if (!payload) continue
                try { onEvent(JSON.parse(payload)) } catch (err) { onError?.(err as Error) }
              }
            }
          }
        } catch (err) {
          if (stopped) return
          onError?.(err as Error)
          await new Promise(r => setTimeout(r, backoff))
          backoff = Math.min(backoff * 2, 30000)
        }
      }
    }

    void loop()
    return () => {
      stopped = true
      try { abort?.abort() } catch {}
    }
  }
}
