import { z } from 'zod'
import { DAEMON_TOKEN, BIND_HOST, BIND_PORT, MOCK_DISCORD } from './config.ts'
import { registry } from './registry.ts'
import { metrics } from './metrics.ts'
import type { DiscordBot } from './discord.ts'

const RegisterBody = z.object({
  session_id: z.string().min(1).max(128),
  label: z.string().min(1).max(120),
  cwd: z.string().min(1).max(1024),
  pid: z.number().int().nonnegative(),
})

const SendBody = z.object({
  chat_id: z.string().min(1),
  text: z.string(),
  reply_to: z.string().optional(),
  files: z.array(z.string()).optional(),
})

const EditBody = z.object({
  chat_id: z.string().min(1),
  message_id: z.string().min(1),
  text: z.string(),
})

const ReactBody = z.object({
  chat_id: z.string().min(1),
  message_id: z.string().min(1),
  emoji: z.string().min(1),
})

const FetchBody = z.object({
  chat_id: z.string().min(1),
  limit: z.number().int().positive().max(100).optional(),
})

const DownloadBody = z.object({
  chat_id: z.string().min(1),
  message_id: z.string().min(1),
})

const PermissionRequestBody = z.object({
  request_id: z.string().min(1),
  tool_name: z.string().min(1),
  description: z.string(),
  input_preview: z.string(),
})

export function startHTTP(bot: DiscordBot): { stop: () => void } {
  const server = Bun.serve({
    hostname: BIND_HOST,
    port: BIND_PORT,
    fetch: (req) => handle(req, bot),
  })
  process.stderr.write(`daemon: HTTP listening on ${BIND_HOST}:${BIND_PORT}\n`)
  return { stop: () => server.stop(true) }
}

async function handle(req: Request, bot: DiscordBot): Promise<Response> {
  const url = new URL(req.url)
  const path = url.pathname

  // /metrics is unauthenticated — Prometheus scrapers don't carry tokens.
  // Daemon binds to loopback + tailnet only, so unauthenticated is safe here.
  if (req.method === 'GET' && path === '/metrics') {
    const all = registry.list()
    const body = metrics.render({
      sessions_active: all.filter(s => s.state === 'active').length,
      sessions_dormant: all.filter(s => s.state === 'dormant').length,
    })
    return new Response(body, { headers: { 'Content-Type': 'text/plain; version=0.0.4' } })
  }

  // Auth gate
  if (!checkAuth(req)) return json({ error: 'unauthorized' }, 401)

  if (req.method === 'GET' && path === '/health') {
    return json({ ok: true, sessions: registry.list().length })
  }

  if (req.method === 'GET' && path === '/sessions') {
    return json({ sessions: registry.list() })
  }

  // Mock-only: inject an inbound thread message for smoke testing.
  if (MOCK_DISCORD && req.method === 'POST' && path === '/_mock/inject') {
    try {
      const body = (await req.json()) as { thread_id: string; content: string; user?: string; user_id?: string }
      bot.injectMockMessage(body.thread_id, body.content, body.user, body.user_id)
      return json({ ok: true })
    } catch (err) {
      return json({ error: (err as Error).message }, 400)
    }
  }

  if (req.method === 'POST' && path === '/sessions') {
    return await registerSession(req, bot)
  }

  const sessMatch = path.match(/^\/sessions\/([^/]+)(?:\/(.+))?$/)
  if (sessMatch) {
    const sessionId = sessMatch[1]!
    const tail = sessMatch[2]

    if (req.method === 'DELETE' && !tail) return await deleteSession(sessionId, bot)
    if (req.method === 'POST' && tail === 'heartbeat') return heartbeat(sessionId)
    if (req.method === 'POST' && tail === 'send') return await sendMessage(sessionId, req, bot)
    if (req.method === 'POST' && tail === 'edit') return await editMessage(sessionId, req, bot)
    if (req.method === 'POST' && tail === 'react') return await reactMessage(sessionId, req, bot)
    if (req.method === 'POST' && tail === 'fetch') return await fetchMessages(sessionId, req, bot)
    if (req.method === 'POST' && tail === 'download') return await downloadAttachments(sessionId, req, bot)
    if (req.method === 'POST' && tail === 'permission_request') return await permissionRequest(sessionId, req, bot)
    if (req.method === 'GET' && tail === 'inbox') return inboxStream(sessionId)
  }

  return json({ error: 'not found' }, 404)
}

function checkAuth(req: Request): boolean {
  const got = req.headers.get('x-daemon-token')
  if (!got) return false
  // constant-time-ish: lengths must match, byte comparison
  if (got.length !== DAEMON_TOKEN.length) return false
  let ok = 0
  for (let i = 0; i < got.length; i++) ok |= got.charCodeAt(i) ^ DAEMON_TOKEN.charCodeAt(i)
  return ok === 0
}

async function registerSession(req: Request, bot: DiscordBot): Promise<Response> {
  let body: z.infer<typeof RegisterBody>
  try {
    body = RegisterBody.parse(await req.json())
  } catch (err) {
    return json({ error: `bad body: ${(err as Error).message}` }, 400)
  }

  const existing = registry.get(body.session_id)
  let threadId: string
  if (existing) {
    threadId = existing.threadId
  } else {
    const created = await bot.createSessionThread(body.label, body.cwd)
    threadId = created.threadId
  }

  const sess = registry.register({
    sessionId: body.session_id,
    label: body.label,
    cwd: body.cwd,
    pid: body.pid,
    threadId,
  })
  return json({ session: sess })
}

// Session-mcp shutting down → soft unregister. Keep thread mapping so a future
// register with same sessionId (same cwd hash, on resume) reattaches to the
// same Discord thread. Archive the thread; Discord auto-unarchives on next send.
async function deleteSession(sessionId: string, bot: DiscordBot): Promise<Response> {
  const dormant = registry.markDormant(sessionId)
  if (!dormant) return json({ error: 'no such session' }, 404)
  await bot.archiveSessionThread(dormant.threadId, 'session ended')
  return json({ ok: true })
}

function heartbeat(sessionId: string): Response {
  const ok = registry.heartbeat(sessionId)
  if (!ok) return json({ error: 'no such session' }, 404)
  return json({ ok: true })
}

function authorizeChatId(sessionId: string, chatId: string): string | null {
  const s = registry.get(sessionId)
  if (!s) return 'no such session'
  if (s.threadId !== chatId) return 'chat_id does not belong to this session'
  return null
}

async function sendMessage(sessionId: string, req: Request, bot: DiscordBot): Promise<Response> {
  let body: z.infer<typeof SendBody>
  try { body = SendBody.parse(await req.json()) } catch (err) { return json({ error: (err as Error).message }, 400) }
  const err = authorizeChatId(sessionId, body.chat_id)
  if (err) return json({ error: err }, 403)
  try {
    const { ids } = await bot.sendToThread(body.chat_id, body.text, { files: body.files, replyTo: body.reply_to })
    return json({ ids })
  } catch (e) {
    return json({ error: (e as Error).message }, 500)
  }
}

async function editMessage(sessionId: string, req: Request, bot: DiscordBot): Promise<Response> {
  let body: z.infer<typeof EditBody>
  try { body = EditBody.parse(await req.json()) } catch (err) { return json({ error: (err as Error).message }, 400) }
  const err = authorizeChatId(sessionId, body.chat_id)
  if (err) return json({ error: err }, 403)
  try {
    const { id } = await bot.editMessage(body.chat_id, body.message_id, body.text)
    return json({ id })
  } catch (e) {
    return json({ error: (e as Error).message }, 500)
  }
}

async function reactMessage(sessionId: string, req: Request, bot: DiscordBot): Promise<Response> {
  let body: z.infer<typeof ReactBody>
  try { body = ReactBody.parse(await req.json()) } catch (err) { return json({ error: (err as Error).message }, 400) }
  const err = authorizeChatId(sessionId, body.chat_id)
  if (err) return json({ error: err }, 403)
  try {
    await bot.react(body.chat_id, body.message_id, body.emoji)
    return json({ ok: true })
  } catch (e) {
    return json({ error: (e as Error).message }, 500)
  }
}

async function fetchMessages(sessionId: string, req: Request, bot: DiscordBot): Promise<Response> {
  let body: z.infer<typeof FetchBody>
  try { body = FetchBody.parse(await req.json()) } catch (err) { return json({ error: (err as Error).message }, 400) }
  const err = authorizeChatId(sessionId, body.chat_id)
  if (err) return json({ error: err }, 403)
  try {
    const text = await bot.fetchMessages(body.chat_id, body.limit ?? 20)
    return json({ text })
  } catch (e) {
    return json({ error: (e as Error).message }, 500)
  }
}

async function permissionRequest(sessionId: string, req: Request, bot: DiscordBot): Promise<Response> {
  let body: z.infer<typeof PermissionRequestBody>
  try { body = PermissionRequestBody.parse(await req.json()) } catch (err) { return json({ error: (err as Error).message }, 400) }
  if (!registry.get(sessionId)) return json({ error: 'no such session' }, 404)
  try {
    await bot.dispatchPermissionRequest({ sessionId, ...body })
    return json({ ok: true })
  } catch (e) {
    return json({ error: (e as Error).message }, 500)
  }
}

async function downloadAttachments(sessionId: string, req: Request, bot: DiscordBot): Promise<Response> {
  let body: z.infer<typeof DownloadBody>
  try { body = DownloadBody.parse(await req.json()) } catch (err) { return json({ error: (err as Error).message }, 400) }
  const err = authorizeChatId(sessionId, body.chat_id)
  if (err) return json({ error: err }, 403)
  try {
    const files = await bot.downloadAttachments(body.chat_id, body.message_id)
    return json({ files })
  } catch (e) {
    return json({ error: (e as Error).message }, 500)
  }
}

function inboxStream(sessionId: string): Response {
  const s = registry.get(sessionId)
  if (!s) return json({ error: 'no such session' }, 404)

  let unsub: (() => void) | null = null
  const stream = new ReadableStream({
    start(controller) {
      const enc = new TextEncoder()
      const send = (data: unknown) => {
        controller.enqueue(enc.encode(`data: ${JSON.stringify(data)}\n\n`))
      }
      send({ kind: 'hello', session_id: sessionId, label: s.label })
      unsub = registry.subscribe(sessionId, (ev) => send(ev))
      if (!unsub) {
        controller.close()
        return
      }
      // keep-alive every 25s
      const keep = setInterval(() => {
        try { controller.enqueue(enc.encode(`: ka\n\n`)) } catch { clearInterval(keep) }
      }, 25000)
    },
    cancel() {
      if (unsub) unsub()
    },
  })
  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    },
  })
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}
