import { ALERT_WEBHOOK } from './config.ts'

// Fire-and-forget alert post. Compatible with ntfy.sh, Discord webhooks, etc.
// Body is plain text; consumer decides how to format.
export async function alert(level: 'info' | 'warn' | 'error', text: string): Promise<void> {
  if (!ALERT_WEBHOOK) return
  try {
    await fetch(ALERT_WEBHOOK, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain', Title: `daemon ${level}`, Priority: level === 'error' ? 'high' : 'default' },
      body: text,
    })
  } catch (err) {
    process.stderr.write(`daemon: alert webhook failed: ${err}\n`)
  }
}
