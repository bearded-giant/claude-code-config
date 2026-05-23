import {
  Client,
  GatewayIntentBits,
  Partials,
  ChannelType,
  type Message,
  type Attachment,
  type ThreadChannel,
  type TextChannel,
} from 'discord.js'
import { mkdirSync, writeFileSync, statSync, realpathSync } from 'fs'
import { join, sep } from 'path'
import { STATE_DIR, INBOX_DIR, SESSIONS_CHANNEL_ID, getDiscordToken } from './config.ts'
import { readAccess, saveAccess, pruneExpired, drainApprovals } from './access.ts'
import { registry } from './registry.ts'
import { handleControlDM } from './control.ts'
import { randomBytes } from 'crypto'

const MAX_CHUNK_LIMIT = 2000
const MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
const RECENT_SENT_CAP = 200

export class DiscordBot {
  client: Client
  // Track message IDs we recently sent → reply-to-bot in threads counts as us.
  private recentSentIds = new Set<string>()

  constructor() {
    this.client = new Client({
      intents: [
        GatewayIntentBits.DirectMessages,
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
      ],
      partials: [Partials.Channel],
    })

    this.client.on('error', err => {
      process.stderr.write(`daemon: client error: ${err}\n`)
    })

    this.client.on('messageCreate', msg => {
      if (msg.author.bot) return
      this.handleInbound(msg).catch(e => process.stderr.write(`daemon: handleInbound failed: ${e}\n`))
    })

    this.client.once('ready', c => {
      process.stderr.write(`daemon: gateway connected as ${c.user.tag}\n`)
    })
  }

  async start(): Promise<void> {
    await this.client.login(getDiscordToken())
    setInterval(() => this.drainApprovals(), 5000).unref()
  }

  async stop(): Promise<void> {
    await this.client.destroy()
  }

  // === Outbound ===

  async createSessionThread(label: string, cwd: string): Promise<{ threadId: string }> {
    const parent = await this.fetchSessionsChannel()
    const safe = label.replace(/[^a-zA-Z0-9._-]+/g, '-').slice(0, 80) || 'session'
    const name = `${safe}-${shortId()}`
    const thread = await parent.threads.create({
      name,
      autoArchiveDuration: 1440, // 24h idle archive
      reason: `claude session: ${cwd}`,
    })
    await thread.send(`session **${label}** online\ncwd: \`${cwd}\``)
    return { threadId: thread.id }
  }

  async archiveSessionThread(threadId: string, reason: string): Promise<void> {
    const ch = await this.client.channels.fetch(threadId).catch(() => null)
    if (!ch || !ch.isThread()) return
    try {
      await ch.send(`session ended — ${reason}`)
    } catch {}
    try {
      await ch.setArchived(true, 'session ended')
    } catch {}
  }

  async sendToThread(threadId: string, text: string, opts: { files?: string[]; replyTo?: string } = {}): Promise<{ ids: string[] }> {
    const ch = await this.fetchSessionThread(threadId)
    const files = opts.files ?? []
    for (const f of files) {
      assertSendable(f)
      const st = statSync(f)
      if (st.size > MAX_ATTACHMENT_BYTES) {
        throw new Error(`file too large: ${f} (${(st.size / 1024 / 1024).toFixed(1)}MB, max 25MB)`)
      }
    }
    if (files.length > 10) throw new Error('Discord allows max 10 attachments per message')

    const access = readAccess()
    const limit = Math.max(1, Math.min(access.textChunkLimit ?? MAX_CHUNK_LIMIT, MAX_CHUNK_LIMIT))
    const mode = access.chunkMode ?? 'length'
    const replyMode = access.replyToMode ?? 'first'
    const chunks = chunk(text, limit, mode)
    const ids: string[] = []
    for (let i = 0; i < chunks.length; i++) {
      const shouldReplyTo =
        opts.replyTo != null && replyMode !== 'off' && (replyMode === 'all' || i === 0)
      const sent = await ch.send({
        content: chunks[i],
        ...(i === 0 && files.length > 0 ? { files } : {}),
        ...(shouldReplyTo
          ? { reply: { messageReference: opts.replyTo!, failIfNotExists: false } }
          : {}),
      })
      this.noteSent(sent.id)
      ids.push(sent.id)
    }
    return { ids }
  }

  async editMessage(threadId: string, messageId: string, text: string): Promise<{ id: string }> {
    const ch = await this.fetchSessionThread(threadId)
    const msg = await ch.messages.fetch(messageId)
    const edited = await msg.edit(text)
    return { id: edited.id }
  }

  async react(threadId: string, messageId: string, emoji: string): Promise<void> {
    const ch = await this.fetchSessionThread(threadId)
    const msg = await ch.messages.fetch(messageId)
    await msg.react(emoji)
  }

  async fetchMessages(threadId: string, limit: number): Promise<string> {
    const ch = await this.fetchSessionThread(threadId)
    const msgs = await ch.messages.fetch({ limit: Math.min(limit, 100) })
    const me = this.client.user?.id
    const arr = [...msgs.values()].reverse()
    if (arr.length === 0) return '(no messages)'
    return arr
      .map(m => {
        const who = m.author.id === me ? 'me' : m.author.username
        const atts = m.attachments.size > 0 ? ` +${m.attachments.size}att` : ''
        const text = m.content.replace(/[\r\n]+/g, ' ⏎ ')
        return `[${m.createdAt.toISOString()}] ${who}: ${text}  (id: ${m.id}${atts})`
      })
      .join('\n')
  }

  async downloadAttachments(threadId: string, messageId: string): Promise<Array<{ path: string; name: string; contentType: string | null; size: number }>> {
    const ch = await this.fetchSessionThread(threadId)
    const msg = await ch.messages.fetch(messageId)
    const out: Array<{ path: string; name: string; contentType: string | null; size: number }> = []
    for (const att of msg.attachments.values()) {
      const path = await downloadAttachment(att)
      out.push({ path, name: safeAttName(att), contentType: att.contentType, size: att.size })
    }
    return out
  }

  // Control-side DM send — bypasses session/thread validation.
  async sendDM(userId: string, text: string): Promise<void> {
    const user = await this.client.users.fetch(userId)
    await user.send(text)
  }

  // === Inbound ===

  private async handleInbound(msg: Message): Promise<void> {
    const access = readAccess()
    if (pruneExpired(access)) saveAccess(access)
    if (access.dmPolicy === 'disabled') return

    const isDM = msg.channel.type === ChannelType.DM

    if (isDM) {
      await this.handleDM(msg)
      return
    }

    // Thread messages → route to session by thread_id
    if (msg.channel.isThread()) {
      const sess = registry.getByThread(msg.channelId)
      if (!sess) return // not one of ours, or session already gone
      // gate on user — must be allowlisted
      if (!access.allowFrom.includes(msg.author.id)) return

      const atts: string[] = []
      for (const att of msg.attachments.values()) {
        const kb = (att.size / 1024).toFixed(0)
        atts.push(`${safeAttName(att)} (${att.contentType ?? 'unknown'}, ${kb}KB)`)
      }
      const content = msg.content || (atts.length > 0 ? '(attachment)' : '')

      if (access.ackReaction) void msg.react(access.ackReaction).catch(() => {})

      registry.deliver(sess.sessionId, {
        kind: 'message',
        message_id: msg.id,
        chat_id: msg.channelId,
        user: msg.author.username,
        user_id: msg.author.id,
        ts: msg.createdAt.toISOString(),
        content,
        ...(atts.length > 0 ? { attachments: atts.join('; '), attachment_count: atts.length } : {}),
      })
    }
  }

  private async handleDM(msg: Message): Promise<void> {
    const access = readAccess()
    const senderId = msg.author.id

    if (access.allowFrom.includes(senderId)) {
      // Allowlisted user → control command
      const reply = await handleControlDM(msg.content.trim(), senderId)
      if (reply) {
        try { await msg.reply(reply) } catch (err) { process.stderr.write(`daemon: control reply failed: ${err}\n`) }
      }
      return
    }

    if (access.dmPolicy === 'allowlist') return

    // pairing flow (unchanged from original)
    for (const [code, p] of Object.entries(access.pending)) {
      if (p.senderId === senderId) {
        if ((p.replies ?? 1) >= 2) return
        p.replies = (p.replies ?? 1) + 1
        saveAccess(access)
        await this.sendPairingMessage(msg, code, true)
        return
      }
    }
    if (Object.keys(access.pending).length >= 3) return
    const code = randomBytes(3).toString('hex')
    const now = Date.now()
    access.pending[code] = {
      senderId,
      chatId: msg.channelId,
      createdAt: now,
      expiresAt: now + 60 * 60 * 1000,
      replies: 1,
    }
    saveAccess(access)
    await this.sendPairingMessage(msg, code, false)
  }

  private async sendPairingMessage(msg: Message, code: string, isResend: boolean): Promise<void> {
    const lead = isResend ? 'Still pending' : 'Pairing required'
    try {
      await msg.reply(`${lead} — run in Claude Code:\n\n/discord:access pair ${code}`)
    } catch (err) {
      process.stderr.write(`daemon: pairing message failed: ${err}\n`)
    }
  }

  private async drainApprovals(): Promise<void> {
    for (const { dmChannelId } of drainApprovals()) {
      try {
        const ch = await this.client.channels.fetch(dmChannelId)
        if (ch && 'send' in ch) {
          await (ch as TextChannel).send('Paired! DM `help` for commands.')
        }
      } catch (err) {
        process.stderr.write(`daemon: approval confirm failed: ${err}\n`)
      }
    }
  }

  // === Helpers ===

  private async fetchSessionsChannel(): Promise<TextChannel> {
    const ch = await this.client.channels.fetch(SESSIONS_CHANNEL_ID)
    if (!ch || ch.type !== ChannelType.GuildText) {
      throw new Error(`DISCORD_SESSIONS_CHANNEL_ID must be a text channel (got ${ch?.type})`)
    }
    return ch as TextChannel
  }

  private async fetchSessionThread(threadId: string): Promise<ThreadChannel> {
    const ch = await this.client.channels.fetch(threadId)
    if (!ch || !ch.isThread()) throw new Error(`thread ${threadId} not found or not a thread`)
    if (ch.archived) {
      try { await ch.setArchived(false) } catch {}
    }
    return ch
  }

  private noteSent(id: string): void {
    this.recentSentIds.add(id)
    if (this.recentSentIds.size > RECENT_SENT_CAP) {
      const first = this.recentSentIds.values().next().value
      if (first) this.recentSentIds.delete(first)
    }
  }
}

// === Pure helpers (ported from plugin) ===

function shortId(): string {
  return randomBytes(2).toString('hex')
}

function chunk(text: string, limit: number, mode: 'length' | 'newline'): string[] {
  if (text.length <= limit) return [text]
  const out: string[] = []
  let rest = text
  while (rest.length > limit) {
    let cut = limit
    if (mode === 'newline') {
      const para = rest.lastIndexOf('\n\n', limit)
      const line = rest.lastIndexOf('\n', limit)
      const space = rest.lastIndexOf(' ', limit)
      cut = para > limit / 2 ? para : line > limit / 2 ? line : space > 0 ? space : limit
    }
    out.push(rest.slice(0, cut))
    rest = rest.slice(cut).replace(/^\n+/, '')
  }
  if (rest) out.push(rest)
  return out
}

function assertSendable(f: string): void {
  let real: string, stateReal: string
  try {
    real = realpathSync(f)
    stateReal = realpathSync(STATE_DIR)
  } catch { return }
  const inbox = join(stateReal, 'inbox')
  if (real.startsWith(stateReal + sep) && !real.startsWith(inbox + sep)) {
    throw new Error(`refusing to send daemon state: ${f}`)
  }
}

async function downloadAttachment(att: Attachment): Promise<string> {
  if (att.size > MAX_ATTACHMENT_BYTES) {
    throw new Error(`attachment too large: ${(att.size / 1024 / 1024).toFixed(1)}MB, max ${MAX_ATTACHMENT_BYTES / 1024 / 1024}MB`)
  }
  const res = await fetch(att.url)
  const buf = Buffer.from(await res.arrayBuffer())
  const name = att.name ?? `${att.id}`
  const rawExt = name.includes('.') ? name.slice(name.lastIndexOf('.') + 1) : 'bin'
  const ext = rawExt.replace(/[^a-zA-Z0-9]/g, '') || 'bin'
  const path = join(INBOX_DIR, `${Date.now()}-${att.id}.${ext}`)
  mkdirSync(INBOX_DIR, { recursive: true })
  writeFileSync(path, buf)
  return path
}

function safeAttName(att: Attachment): string {
  return (att.name ?? att.id).replace(/[\[\]\r\n;]/g, '_')
}
