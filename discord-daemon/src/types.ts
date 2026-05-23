export type GroupPolicy = {
  requireMention: boolean
  allowFrom: string[]
}

export type PendingEntry = {
  senderId: string
  chatId: string
  createdAt: number
  expiresAt: number
  replies: number
}

export type Access = {
  dmPolicy: 'pairing' | 'allowlist' | 'disabled'
  allowFrom: string[]
  groups: Record<string, GroupPolicy>
  pending: Record<string, PendingEntry>
  mentionPatterns?: string[]
  ackReaction?: string
  replyToMode?: 'off' | 'first' | 'all'
  textChunkLimit?: number
  chunkMode?: 'length' | 'newline'
}

export type Session = {
  sessionId: string
  label: string
  cwd: string
  pid: number
  threadId: string
  registeredAt: number
  lastHeartbeat: number
}

// Inbound event delivered to a session via SSE.
export type InboxEvent =
  | {
      kind: 'message'
      message_id: string
      chat_id: string
      user: string
      user_id: string
      ts: string
      content: string
      attachments?: string
      attachment_count?: number
    }
  | {
      kind: 'permission_decision'
      ts: string
      request_id: string
      behavior: 'allow' | 'deny'
    }

export type OutboundKind = 'reply' | 'react' | 'edit' | 'fetch_messages' | 'download_attachment'
