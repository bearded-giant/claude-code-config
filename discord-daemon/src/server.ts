#!/usr/bin/env bun
import { loadEnvFile, assertRequired, HEARTBEAT_SWEEP_MS } from './config.ts'
import { DiscordBot } from './discord.ts'
import { startHTTP } from './http.ts'
import { registry } from './registry.ts'
import { alert } from './alerts.ts'

process.on('unhandledRejection', err => {
  process.stderr.write(`daemon: unhandled rejection: ${err}\n`)
})
process.on('uncaughtException', err => {
  process.stderr.write(`daemon: uncaught exception: ${err}\n`)
})

loadEnvFile()
assertRequired()

// Hydrate registry from disk first. Sessions persisted from prior boot show
// up here; their session-mcp heartbeats will land in the loaded entries.
const loaded = registry.loadFromDisk()
if (loaded > 0) {
  process.stderr.write(`daemon: hydrated ${loaded} session(s) from disk\n`)
}

const bot = new DiscordBot()

// HTTP first — health probes + smoke tests don't need Discord up. Login runs
// async; failures log but don't block boot. New sessions registering before
// login completes still get queued through the registry.
const http = startHTTP(bot)
bot.start()
  .then(() => alert('info', `daemon started, hydrated=${loaded}`))
  .catch(err => {
    process.stderr.write(`daemon: Discord start failed: ${err}\n`)
    process.stderr.write('daemon: HTTP still serving; fix credentials and restart\n')
    void alert('error', `daemon Discord start failed: ${err}`)
  })

const sweepTimer = setInterval(async () => {
  const stale = registry.sweepStale()
  for (const s of stale) {
    process.stderr.write(`daemon: marking dormant (heartbeat lost): ${s.label} (${s.sessionId})\n`)
    try { await bot.archiveSessionThread(s.threadId, 'heartbeat lost') } catch {}
  }
}, HEARTBEAT_SWEEP_MS)

let shuttingDown = false
async function shutdown(sig: string): Promise<void> {
  if (shuttingDown) return
  shuttingDown = true
  process.stderr.write(`daemon: ${sig} received, shutting down\n`)
  clearInterval(sweepTimer)
  // Persist registry synchronously so the next boot can hydrate.
  registry.persistNow()
  http.stop()
  // Threads are NOT archived here — systemd restarts daemon by default and
  // sessions reconnect via heartbeat. Stale entries get swept after restart
  // if their session-mcp never reconnects.
  // Override with DAEMON_ARCHIVE_ON_EXIT=1 for intentional teardown.
  if (process.env.DAEMON_ARCHIVE_ON_EXIT === '1') {
    process.stderr.write('daemon: archiving all session threads on exit\n')
    for (const s of registry.list()) {
      try { await bot.archiveSessionThread(s.threadId, `daemon ${sig}`) } catch {}
    }
  }
  await alert('warn', `daemon ${sig} shutdown`)
  try { await bot.stop() } catch {}
  setTimeout(() => process.exit(0), 1000).unref()
}
process.on('SIGTERM', () => shutdown('SIGTERM'))
process.on('SIGINT', () => shutdown('SIGINT'))
