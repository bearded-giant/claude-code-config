#!/usr/bin/env node
// statusline with configurable style (compact/bar/minimal)
// config: ~/.claude/hooks/statusline-config.json

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

// ansi
const RST = '\x1b[0m';
const DIM = '\x1b[2m';
const GREEN = '\x1b[32m';
const YELLOW = '\x1b[33m';
const CYAN = '\x1b[36m';
const RED = '\x1b[31m';
const MAGENTA = '\x1b[35m';
const ORANGE = '\x1b[38;5;208m';
const BLINK_RED = '\x1b[5;31m';

const STATE_DIR = path.join(os.tmpdir(), 'claude-statusline');
const MAX_TOOLS = 50;


// --- config ---

function loadConfig() {
  const defaults = {
    style: 'compact',  // compact (pie) | bar | minimal
    line2: true,
    tools: 'last',     // last (1 active tool) | feed (last 3) | false
    agents: true,
    thinking: true,
    messages: true,
    lines: true,
    duration: true,
  };
  try {
    const cfgPath = path.join(__dirname, 'statusline-config.json');
    const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
    return { ...defaults, ...cfg };
  } catch (e) { return defaults; }
}

// --- helpers ---

function colorForPct(pct) {
  if (pct < 50) return GREEN;
  if (pct < 70) return YELLOW;
  if (pct < 85) return ORANGE;
  return BLINK_RED;
}

function fmtBar(pct, width) {
  const filled = Math.min(width, Math.round((pct / 100) * width));
  return '\u2588'.repeat(filled) + '\u2591'.repeat(width - filled);
}

function fmtDuration(ms) {
  const secs = Math.floor(ms / 1000);
  const m = Math.floor(secs / 60);
  const h = Math.floor(m / 60);
  if (h > 0) return `${h}h${(m % 60).toString().padStart(2, '0')}m`;
  if (m > 0) return `${m}m`;
  return `${secs}s`;
}

function fmtDurationShort(ms) {
  const secs = Math.floor(ms / 1000);
  const m = Math.floor(secs / 60);
  if (m > 0) return `${m}m`;
  return `${secs}s`;
}

function fmtCountdown(resets_at, now) {
  if (!resets_at) return '';
  const resetTime = typeof resets_at === 'string'
    ? new Date(resets_at).getTime() / 1000 : resets_at;
  const secs = Math.max(0, resetTime - now);
  if (secs <= 0) return '';
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  if (h >= 24) return ` ~${Math.floor(h / 24)}d${h % 24}h`;
  return ` ~${h}h${m.toString().padStart(2, '0')}m`;
}

// --- git info ---

function getGitInfo(dir) {
  const info = { branch: null, dirty: false, ahead: 0, behind: 0 };
  try {
    let gitDir = null;
    let current = dir;
    while (current !== '/') {
      const gitHead = path.join(current, '.git', 'HEAD');
      if (fs.existsSync(gitHead)) {
        const content = fs.readFileSync(gitHead, 'utf8').trim();
        info.branch = content.startsWith('ref: refs/heads/')
          ? content.slice(16)
          : content.slice(0, 7);
        gitDir = current;
        break;
      }
      current = path.dirname(current);
    }
    if (!gitDir) return info;

    try {
      const status = execSync(`git -C "${gitDir}" status --porcelain -b 2>/dev/null`, {
        timeout: 150, encoding: 'utf8',
      });
      const lines = status.split('\n');
      const header = lines[0] || '';
      const am = header.match(/ahead (\d+)/);
      const bm = header.match(/behind (\d+)/);
      if (am) info.ahead = parseInt(am[1]);
      if (bm) info.behind = parseInt(bm[1]);
      info.dirty = lines.slice(1).some(l => l.trim().length > 0);
    } catch (e) {}
  } catch (e) {}
  return info;
}

// --- context gauge ---

function contextGauge(data) {
  let remaining = data.context_window?.remaining_percentage;
  if (remaining == null && data.context_window?.used_percentage != null) {
    remaining = 100 - data.context_window.used_percentage;
  }
  if (remaining == null) return '';

  let recentCompact = false;
  try {
    const ts = fs.readFileSync('/tmp/claude-compact-ts', 'utf8').trim();
    const elapsed = Math.floor(Date.now() / 1000) - parseInt(ts, 10);
    if (elapsed >= 0 && elapsed < 30) recentCompact = true;
  } catch (e) {}

  const compactAt = 15;
  const pct = Math.round(remaining);
  const untilCompact = Math.max(0, pct - compactAt);

  if (recentCompact && untilCompact < 25) {
    return ` ${GREEN}${'\u2591'.repeat(10)} compacted${RST}`;
  }

  // used% relative to usable window (for bar fill)
  const usedPct = Math.round(((100 - pct) / (100 - compactAt)) * 100);

  let color;
  if (untilCompact > 50) color = GREEN;
  else if (untilCompact > 35) color = YELLOW;
  else if (untilCompact > 20) color = ORANGE;
  else color = BLINK_RED;

  const filled = Math.min(10, Math.round(usedPct / 10));
  const bar = '\u2588'.repeat(filled) + '\u2591'.repeat(10 - filled);
  return ` ${color}${bar} ${untilCompact}%${RST}`;
}

// --- rate limit usage ---

function usageGauges() {
  try {
    const cacheFile = path.join(os.homedir(), '.cache', 'claude-usage', 'cache.json');
    if (!fs.existsSync(cacheFile)) return '';

    const cache = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
    const now = Date.now() / 1000;

    if (!cache.expires_at || cache.expires_at < now) {
      const { spawn } = require('child_process');
      const child = spawn('python3', [path.join(__dirname, 'usage-fetch.py')], {
        detached: true, stdio: 'ignore',
      });
      child.unref();
    }

    let visibleFilter = null;
    let windowFilter = null;
    try {
      const cfgFile = path.join(os.homedir(), '.cache', 'claude-usage', 'config.json');
      const cfg = JSON.parse(fs.readFileSync(cfgFile, 'utf8'));
      if (Array.isArray(cfg.visible)) visibleFilter = cfg.visible;
      if (Array.isArray(cfg.windows)) windowFilter = cfg.windows;
    } catch (e) {}

    const show5h = !windowFilter || windowFilter.includes('5h');
    const show7d = !windowFilter || windowFilter.includes('7d');

    let result = '';
    const orgs = (cache.orgs || []).filter(
      o => !visibleFilter || visibleFilter.includes(o.label)
    );
    for (const org of orgs) {
      const fh = org.five_hour;
      const sd = org.seven_day;
      if (!fh && !sd) continue;

      let parts = [];
      if (show5h && fh && fh.used_pct != null) {
        const p = Math.min(100, Math.max(0, fh.used_pct));
        parts.push(`${colorForPct(p)}5h ${fmtBar(p, 5)} ${p}%${fmtCountdown(fh.resets_at, now)}${RST}`);
      }
      if (show7d && sd && sd.used_pct != null) {
        const p = Math.min(100, Math.max(0, sd.used_pct));
        parts.push(`${colorForPct(p)}7d ${fmtBar(p, 5)} ${p}%${fmtCountdown(sd.resets_at, now)}${RST}`);
      }
      if (parts.length) {
        result += ` \u2502 ${DIM}${org.label}${RST} ${parts.join(' ')}`;
      }
    }
    return result;
  } catch (e) { return ''; }
}

// --- transcript parsing (incremental) ---

function loadState(sessionId) {
  try {
    return JSON.parse(fs.readFileSync(path.join(STATE_DIR, `${sessionId}.json`), 'utf8'));
  } catch (e) {
    return { offset: 0, tools: [], agents: [], thinkingCount: 0, messageCount: 0, skills: [] };
  }
}

function saveState(sessionId, state) {
  try {
    fs.mkdirSync(STATE_DIR, { recursive: true });
    fs.writeFileSync(path.join(STATE_DIR, `${sessionId}.json`), JSON.stringify(state));
  } catch (e) {}
}

function toolTarget(name, input) {
  if (!input) return '';
  switch (name) {
    case 'Read': case 'Write': case 'Edit':
      return path.basename(input.file_path || input.path || '');
    case 'Bash':
      return '';  // too noisy, skip bash targets
    case 'Grep':
      return input.pattern ? `/${input.pattern.slice(0, 12)}/` : '';
    case 'Glob':
      return (input.pattern || '').slice(0, 15);
    case 'Agent':
      return input.name || input.description || '';
    default:
      return '';
  }
}

function parseTranscript(transcriptPath, sessionId) {
  const empty = { tools: [], agents: [], thinkingCount: 0, messageCount: 0, skills: [] };
  if (!transcriptPath || !sessionId) return empty;

  try {
    if (!fs.existsSync(transcriptPath)) return empty;
  } catch (e) { return empty; }

  const state = loadState(sessionId);

  let size;
  try { size = fs.statSync(transcriptPath).size; } catch (e) { return state; }
  if (size <= state.offset) return state;

  let buf;
  try {
    const fd = fs.openSync(transcriptPath, 'r');
    buf = Buffer.alloc(size - state.offset);
    fs.readSync(fd, buf, 0, buf.length, state.offset);
    fs.closeSync(fd);
  } catch (e) { return state; }

  const toolIds = new Set(state.tools.map(t => t.id));
  const agentIds = new Set(state.agents.map(a => a.id));

  for (const line of buf.toString('utf8').split('\n')) {
    if (!line.trim()) continue;
    let entry;
    try { entry = JSON.parse(line); } catch (e) { continue; }

    const msg = entry.message;
    if (!msg?.content) continue;

    if (entry.type === 'assistant') {
      for (const block of msg.content) {
        if (block.type === 'tool_use' && !toolIds.has(block.id)) {
          toolIds.add(block.id);
          state.tools.push({
            id: block.id,
            name: block.name,
            completed: false,
            startTime: entry.timestamp,
            target: toolTarget(block.name, block.input),
          });

          if (block.name === 'Agent' && !agentIds.has(block.id)) {
            agentIds.add(block.id);
            state.agents.push({
              id: block.id,
              name: block.input?.name || block.input?.description?.slice(0, 20) || 'agent',
              status: 'running',
              startTime: entry.timestamp,
            });
          }

          if (block.name === 'Skill') {
            const s = block.input?.skill;
            if (s && !state.skills.includes(s)) state.skills.push(s);
          }
        } else if (block.type === 'thinking') {
          state.thinkingCount++;
        }
      }
    } else if (entry.type === 'user') {
      state.messageCount++;
      for (const block of msg.content) {
        if (block.type === 'tool_result' && block.tool_use_id) {
          const tool = state.tools.find(t => t.id === block.tool_use_id);
          if (tool && !tool.completed) {
            tool.completed = true;
            if (tool.startTime) {
              tool.durationMs = new Date(entry.timestamp) - new Date(tool.startTime);
            }
          }
          const agent = state.agents.find(a => a.id === block.tool_use_id);
          if (agent && agent.status === 'running') {
            agent.status = 'completed';
            if (agent.startTime) {
              agent.durationMs = new Date(entry.timestamp) - new Date(agent.startTime);
            }
          }
        }
      }
    }
  }

  if (state.tools.length > MAX_TOOLS) {
    state.tools = state.tools.slice(-MAX_TOOLS);
  }

  state.offset = size;
  saveState(sessionId, state);
  return state;
}

// --- widget formatters ---

function fmtToolFeed(tools, mode) {
  if (!mode || !tools.length) return '';

  if (mode === 'last') {
    // just show the most recent non-completed tool, or last completed
    const running = tools.filter(t => !t.completed);
    const t = running.length ? running[running.length - 1] : tools[tools.length - 1];
    const target = t.target ? ` ${t.target.slice(0, 30)}` : '';
    if (!t.completed) return `${CYAN}${t.name}${target}...${RST}`;
    return `${DIM}${t.name}${target}${RST}`;
  }

  // feed mode: last 3
  return tools.slice(-3).map(t => {
    const target = t.target ? `:${t.target.slice(0, 10)}` : '';
    if (!t.completed) return `${CYAN}${t.name}${target}...${RST}`;
    const dur = t.durationMs ? `(${fmtDurationShort(t.durationMs)})` : '';
    return `${DIM}${t.name}${target}${dur}${RST}`;
  }).join(' ');
}

function fmtAgents(agents) {
  const running = agents.filter(a => a.status === 'running');
  const completed = agents.filter(a => a.status === 'completed');
  if (!running.length && !completed.length) return '';

  const parts = [];
  for (const a of running) {
    const elapsed = a.startTime ? fmtDurationShort(Date.now() - new Date(a.startTime).getTime()) : '';
    parts.push(`${MAGENTA}${a.name}(${elapsed})${RST}`);
  }
  if (completed.length && !running.length) {
    parts.push(`${DIM}agents:${completed.length}${RST}`);
  } else if (completed.length && running.length) {
    parts.push(`${DIM}+${completed.length}done${RST}`);
  }
  return parts.join(' ');
}

// --- main ---

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  try {
    const data = JSON.parse(input);
    const cfg = loadConfig();

    const model = data.model?.display_name || 'Claude';
    const dir = data.cwd || data.workspace?.current_dir || process.cwd();
    const homeDir = os.homedir();
    const displayPath = dir.startsWith(homeDir) ? '~' + dir.slice(homeDir.length) : dir;

    // git
    const git = getGitInfo(dir);
    let branchPart = '';
    if (git.branch) {
      let b = `${CYAN}${git.branch}${RST}`;
      if (git.dirty) b += `${YELLOW}*${RST}`;
      if (git.ahead) b += `${GREEN}+${git.ahead}${RST}`;
      if (git.behind) b += `${RED}-${git.behind}${RST}`;
      branchPart = ` \u2502 ${b}`;
    }

    const ctx = contextGauge(data);
    const usage = usageGauges();
    const line1 = `${DIM}${model}${RST} \u2502 ${DIM}${displayPath}${RST}${branchPart} \u2502${ctx}${usage}`;

    // minimal: one line only
    if (cfg.style === 'minimal' || !cfg.line2) {
      process.stdout.write(line1);
      return;
    }

    // line 2
    const cost = data.cost || {};
    const transcript = parseTranscript(data.transcript_path, data.session_id);
    const parts = [];

    if (cfg.duration && cost.total_duration_ms) {
      parts.push(`${DIM}${fmtDuration(cost.total_duration_ms)}${RST}`);
    }

    if (cfg.lines) {
      const added = cost.total_lines_added || 0;
      const removed = cost.total_lines_removed || 0;
      if (added || removed) {
        let lp = '';
        if (added) lp += `${GREEN}+${added}${RST}`;
        if (removed) lp += `${RED}-${removed}${RST}`;
        parts.push(lp);
      }
    }

    if (cfg.messages && transcript.messageCount) {
      parts.push(`${DIM}msgs:${transcript.messageCount}${RST}`);
    }

    if (cfg.thinking && transcript.thinkingCount) {
      parts.push(`${DIM}think:${transcript.thinkingCount}${RST}`);
    }

    if (cfg.tools) {
      const toolStr = fmtToolFeed(transcript.tools, cfg.tools);
      if (toolStr) parts.push(toolStr);
    }

    if (cfg.agents) {
      const agentStr = fmtAgents(transcript.agents);
      if (agentStr) parts.push(agentStr);
    }

    const sep = ` ${DIM}\u2502${RST} `;
    const line2 = parts.join(sep);

    if (line2) {
      process.stdout.write(`${line1}\n${line2}`);
    } else {
      process.stdout.write(line1);
    }
  } catch (e) {
    // silent fail
  }
});
