// Lightweight Prometheus exposition. No labels — counts are scalar.
// Daemon exposes /metrics over the same HTTP server.

class Metrics {
  private counters = new Map<string, number>([
    ['messages_received', 0],
    ['messages_sent', 0],
    ['tool_calls', 0],
    ['tool_errors', 0],
    ['inbound_errors', 0],
    ['gateway_errors', 0],
    ['sessions_registered_total', 0],
    ['sessions_unregistered_total', 0],
    ['permission_requests', 0],
    ['permission_decisions', 0],
  ])
  private gauges = new Map<string, number>([
    ['gateway_connected', 0],
  ])

  incr(name: string, by = 1): void {
    this.counters.set(name, (this.counters.get(name) ?? 0) + by)
  }

  setGauge(name: string, value: number): void {
    this.gauges.set(name, value)
  }

  // Returns Prometheus text format. Caller provides live values for
  // sessions_active (gauge derived from registry).
  render(extra: Record<string, number> = {}): string {
    const lines: string[] = []
    for (const [name, value] of this.counters) {
      lines.push(`# TYPE daemon_${name} counter`)
      lines.push(`daemon_${name} ${value}`)
    }
    for (const [name, value] of this.gauges) {
      lines.push(`# TYPE daemon_${name} gauge`)
      lines.push(`daemon_${name} ${value}`)
    }
    for (const [name, value] of Object.entries(extra)) {
      lines.push(`# TYPE daemon_${name} gauge`)
      lines.push(`daemon_${name} ${value}`)
    }
    lines.push(`# TYPE daemon_uptime_seconds gauge`)
    lines.push(`daemon_uptime_seconds ${Math.floor(process.uptime())}`)
    return lines.join('\n') + '\n'
  }
}

export const metrics = new Metrics()
