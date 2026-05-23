#!/usr/bin/env bun
import { loadEnvFile, assertRequired, HEARTBEAT_SWEEP_MS } from './config.ts'
import { DiscordBot } from './discord.ts'
import { startHTTP } from './http.ts'
import { registry } from './registry.ts'

process.on('unhandledRejection', err => {
  process.stderr.write(`daemon: unhandled rejection: ${err}\n`)
})
process.on('uncaughtException', err => {
  process.stderr.write(`daemon: uncaught exception: ${err}\n`)
})

loadEnvFile()
assertRequired()

const bot = new DiscordBot()
await bot.start()
const http = startHTTP(bot)

const sweepTimer = setInterval(async () => {
  const dead = registry.sweepStale()
  for (const s of dead) {
    process.stderr.write(`daemon: evicting stale session ${s.label} (${s.sessionId})\n`)
    try { await bot.archiveSessionThread(s.threadId, 'heartbeat lost') } catch {}
  }
}, HEARTBEAT_SWEEP_MS)

let shuttingDown = false
async function shutdown(sig: string): Promise<void> {
  if (shuttingDown) return
  shuttingDown = true
  process.stderr.write(`daemon: ${sig} received, shutting down\n`)
  clearInterval(sweepTimer)
  http.stop()
  try { await bot.stop() } catch {}
  setTimeout(() => process.exit(0), 1000).unref()
}
process.on('SIGTERM', () => shutdown('SIGTERM'))
process.on('SIGINT', () => shutdown('SIGINT'))
