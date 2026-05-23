import {
  Client,
  GatewayIntentBits,
  Partials,
  ChannelType,
  ButtonBuilder,
  ButtonStyle,
  ActionRowBuilder,
  type Message,
  type Attachment,
  type ThreadChannel,
  type TextChannel,
  type Interaction,
} from 'discord.js'
import { mkdirSync, writeFileSync, statSync, realpathSync } from 'fs'
import { join, sep } from 'path'
import { STATE_DIR, INBOX_DIR, SESSIONS_CHANNEL_ID, getDiscordToken, MOCK_DISCORD } from './config.ts'
import { readAccess, saveAccess, pruneExpired, drainApprovals } from './access.ts'
import { registry } from './registry.ts'
import { handleControlDM } from './control.ts'
import { alert } from './alerts.ts'
import { metrics } from './metrics.ts'
import { randomBytes } from 'crypto'

const MAX_CHUNK_LIMIT = 2000
const MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
const RECENT_SENT_CAP = 200

type PendingPermission = {
  sessionId: string
  tool_name: string
  description: string
  input_preview: string
  createdAt: number
}

export class DiscordBot {
  client: Client
  // Track message IDs we recently sent → reply-to-bot in threads counts as us.
  private recentSentIds = new Set<string>()
  // Permission requests pending button click. Keyed by request_id.
  private pendingPermissions = new Map<string, PendingPermission>()

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
      metrics.incr('gateway_errors')
    })

    this.client.on('messageCreate', msg => {
      if (msg.author.bot) return
      metrics.incr('messages_received')
      this.handleInbound(msg).catch(e => {
        process.stderr.write(`daemon: handleInbound failed: ${e}\n`)
        metrics.incr('inbound_errors')
      })
    })

    this.client.once('ready', c => {
      process.stderr.write(`daemon: gateway connected as ${c.user.tag}\n`)
      metrics.setGauge('gateway_connected', 1)
      void alert('info', `gateway connected as ${c.user.tag}`)
    })

    this.client.on('interactionCreate', (interaction: Interaction) => {
      if (!interaction.isButton()) return
      void this.handlePermissionButton(interaction).catch(err =>
        process.stderr.write(`daemon: permission button error: ${err}\n`)
      )
    })

    // Gateway lifecycle alerts. shardDisconnect fires on any disconnect.
    this.client.on('shardDisconnect', (event, shardId) => {
      process.stderr.write(`daemon: shard ${shardId} disconnected (code ${event.code})\n`)
      metrics.setGauge('gateway_connected', 0)
      void alert('warn', `gateway disconnect shard=${shardId} code=${event.code}`)
    })
    this.client.on('shardReconnecting', shardId => {
      process.stderr.write(`daemon: shard ${shardId} reconnecting\n`)
    })
    this.client.on('shardResume', (shardId) => {
      process.stderr.write(`daemon: shard ${shardId} resumed\n`)
      metrics.setGauge('gateway_connected', 1)
      void alert('info', `gateway resumed shard=${shardId}`)
    })
  }

  async start(): Promise<void> {
    if (MOCK_DISCORD) {
      process.stderr.write('daemon: MOCK_DISCORD mode — gateway login skipped\n')
      return
    }
    await this.client.login(getDiscordToken())
    setInterval(() => this.drainApprovals(), 5000).unref()
  }

  async stop(): Promise<void> {
    if (MOCK_DISCORD) return
    await this.client.destroy()
  }

  // === Outbound ===

  async createSessionThread(label: string, cwd: string): Promise<{ threadId: string }> {
    if (MOCK_DISCORD) {
      const threadId = `mock-${label.replace(/[^a-zA-Z0-9]/g, '-')}-${shortId()}`
      process.stderr.write(`daemon[mock]: createSessionThread(${label}, ${cwd}) → ${threadId}\n`)
      return { threadId }
    }
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
    if (MOCK_DISCORD) {
      process.stderr.write(`daemon[mock]: archiveSessionThread(${threadId}, ${reason})\n`)
      return
    }
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
    if (MOCK_DISCORD) {
      const id = `mock-msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
      process.stderr.write(`daemon[mock]: send → ${threadId}: ${text.slice(0, 80)}\n`)
      return { ids: [id] }
    }
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
    if (MOCK_DISCORD) {
      process.stderr.write(`daemon[mock]: edit ${messageId} → ${text.slice(0, 80)}\n`)
      return { id: messageId }
    }
    const ch = await this.fetchSessionThread(threadId)
    const msg = await ch.messages.fetch(messageId)
    const edited = await msg.edit(text)
    return { id: edited.id }
  }

  async react(threadId: string, messageId: string, emoji: string): Promise<void> {
    if (MOCK_DISCORD) {
      process.stderr.write(`daemon[mock]: react ${messageId} ${emoji}\n`)
      return
    }
    const ch = await this.fetchSessionThread(threadId)
    const msg = await ch.messages.fetch(messageId)
    await msg.react(emoji)
  }

  async fetchMessages(threadId: string, limit: number): Promise<string> {
    if (MOCK_DISCORD) return '(mock — no history)'
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
    if (MOCK_DISCORD) return []
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
    if (MOCK_DISCORD) {
      process.stderr.write(`daemon[mock]: DM ${userId}: ${text}\n`)
      return
    }
    const user = await this.client.users.fetch(userId)
    await user.send(text)
  }

  // Permission relay: store pending + DM allowlisted users with Allow/Deny buttons.
  async dispatchPermissionRequest(args: {
    sessionId: string
    request_id: string
    tool_name: string
    description: string
    input_preview: string
  }): Promise<void> {
    this.pendingPermissions.set(args.request_id, {
      sessionId: args.sessionId,
      tool_name: args.tool_name,
      description: args.description,
      input_preview: args.input_preview,
      createdAt: Date.now(),
    })
    metrics.incr('permission_requests')
    const access = readAccess()
    const text = `🔐 Permission: \`${args.tool_name}\` (session \`${this.sessionLabel(args.sessionId)}\`)`
    if (MOCK_DISCORD) {
      process.stderr.write(`daemon[mock]: permission DM (would go to ${access.allowFrom.length} users): ${text}\n`)
      return
    }
    const row = new ActionRowBuilder<ButtonBuilder>().addComponents(
      new ButtonBuilder()
        .setCustomId(`perm:more:${args.request_id}`)
        .setLabel('See more')
        .setStyle(ButtonStyle.Secondary),
      new ButtonBuilder()
        .setCustomId(`perm:allow:${args.request_id}`)
        .setLabel('Allow')
        .setEmoji('✅')
        .setStyle(ButtonStyle.Success),
      new ButtonBuilder()
        .setCustomId(`perm:deny:${args.request_id}`)
        .setLabel('Deny')
        .setEmoji('❌')
        .setStyle(ButtonStyle.Danger),
    )
    for (const userId of access.allowFrom) {
      void (async () => {
        try {
          const user = await this.client.users.fetch(userId)
          await user.send({ content: text, components: [row] })
        } catch (err) {
          process.stderr.write(`daemon: permission DM to ${userId} failed: ${err}\n`)
        }
      })()
    }
  }

  private async handlePermissionButton(interaction: Interaction): Promise<void> {
    if (!interaction.isButton()) return
    const m = /^perm:(allow|deny|more):(.+)$/.exec(interaction.customId)
    if (!m) return
    const access = readAccess()
    if (!access.allowFrom.includes(interaction.user.id)) {
      await interaction.reply({ content: 'Not authorized.', ephemeral: true }).catch(() => {})
      return
    }
    const [, behavior, request_id] = m
    if (!request_id) return
    const pending = this.pendingPermissions.get(request_id)

    if (behavior === 'more') {
      if (!pending) {
        await interaction.reply({ content: 'Details no longer available.', ephemeral: true }).catch(() => {})
        return
      }
      let prettyInput: string
      try { prettyInput = JSON.stringify(JSON.parse(pending.input_preview), null, 2) }
      catch { prettyInput = pending.input_preview }
      const expanded = `🔐 Permission: \`${pending.tool_name}\` (session \`${this.sessionLabel(pending.sessionId)}\`)\n\ndescription: ${pending.description}\n\ninput_preview:\n\`\`\`json\n${prettyInput}\n\`\`\``
      const row = new ActionRowBuilder<ButtonBuilder>().addComponents(
        new ButtonBuilder().setCustomId(`perm:allow:${request_id}`).setLabel('Allow').setEmoji('✅').setStyle(ButtonStyle.Success),
        new ButtonBuilder().setCustomId(`perm:deny:${request_id}`).setLabel('Deny').setEmoji('❌').setStyle(ButtonStyle.Danger),
      )
      await interaction.update({ content: expanded.slice(0, 1900), components: [row] }).catch(() => {})
      return
    }

    // allow / deny
    if (!pending) {
      await interaction.reply({ content: 'Request expired or already answered.', ephemeral: true }).catch(() => {})
      return
    }
    registry.deliver(pending.sessionId, {
      kind: 'permission_decision',
      ts: new Date().toISOString(),
      request_id,
      behavior: behavior as 'allow' | 'deny',
    })
    this.pendingPermissions.delete(request_id)
    metrics.incr('permission_decisions')
    const label = behavior === 'allow' ? '✅ Allowed' : '❌ Denied'
    await interaction.update({
      content: `${interaction.message.content}\n\n${label} by ${interaction.user.username}`,
      components: [],
    }).catch(() => {})
  }

  private sessionLabel(sessionId: string): string {
    return registry.get(sessionId)?.label ?? sessionId.slice(0, 8)
  }

  // Mock-only helper for smoke tests: simulate an inbound thread message.
  injectMockMessage(threadId: string, content: string, user = 'tester', userId = '1'): void {
    if (!MOCK_DISCORD) throw new Error('injectMockMessage only allowed in MOCK_DISCORD mode')
    const sess = registry.getByThread(threadId)
    if (!sess) {
      process.stderr.write(`daemon[mock]: no session for thread ${threadId}\n`)
      return
    }
    registry.deliver(sess.sessionId, {
      kind: 'message',
      message_id: `mock-${Date.now()}`,
      chat_id: threadId,
      user,
      user_id: userId,
      ts: new Date().toISOString(),
      content,
    })
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
      const reply = await handleControlDM(msg.content.trim(), senderId, this)
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
