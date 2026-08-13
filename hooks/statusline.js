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
    gmdocs: false,
  };
  try {
    const cfgPath = path.join(__dirname, 'statusline-config.json');
    const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
    return { ...defaults, ...cfg };
  } catch (e) { return defaults; }
}

// --- helpers ---

function visLen(s) {
  return s.replace(/\x1b\[[0-9;]*m/g, '').length;
}

function termWidth() {
  // COLUMNS is inherited at claude launch and goes stale on resize; tmux knows live width
  const pane = process.env.TMUX_PANE;
  if (pane) {
    try {
      const w = parseInt(execSync(`tmux display-message -p -t '${pane}' '#{pane_width}'`, {
        timeout: 120, encoding: 'utf8',
      }).trim(), 10);
      if (w > 0) return w;
    } catch (e) {}
  }
  const env = parseInt(process.env.COLUMNS, 10);
  return env > 0 ? env : 120;
}

function colorForPct(pct) {
  if (pct < 50) return GREEN;
  if (pct < 70) return YELLOW;
  if (pct < 85) return ORANGE;
  return BLINK_RED;
}

// pie/circle gauge: ○ ◔ ◑ ◕ ●
const PIES = ['\u25CB', '\u25D4', '\u25D1', '\u25D5', '\u25CF'];

function pie(pct) {
  if (pct <= 0) return PIES[0];
  if (pct <= 25) return PIES[1];
  if (pct <= 50) return PIES[2];
  if (pct <= 75) return PIES[3];
  return PIES[4];
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

// --- model + effort ---

function modelLabel(data) {
  const m = data.model || {};
  const raw = m.display_name || m.id || '';
  if (!raw) return '';
  // shorten: "Claude Opus 4.7 (1M context)" -> "opus-4.7"
  const s = raw.toLowerCase()
    .replace(/claude[\s-]*/g, '')
    .replace(/\s*\(.*?\)\s*/g, '')
    .replace(/\s+/g, '-')
    .trim();
  return s;
}

function readEffort(data) {
  // priority: stdin data > settings.json > env var
  const fromData = data?.effort_level || data?.effortLevel || data?.model?.effort_level;
  if (fromData) return String(fromData);
  try {
    const s = JSON.parse(fs.readFileSync(path.join(os.homedir(), '.claude', 'settings.json'), 'utf8'));
    if (s.effortLevel) return String(s.effortLevel);
  } catch (e) {}
  return process.env.CLAUDE_CODE_EFFORT_LEVEL || '';
}

function effortLabel(data) {
  const e = readEffort(data).toLowerCase();
  if (!e) return '';
  let color = DIM;
  if (e === 'xhigh' || e === 'ultra') color = RED;
  else if (e === 'high') color = ORANGE;
  else if (e === 'medium') color = YELLOW;
  else if (e === 'low' || e === 'minimal') color = GREEN;
  return `${color}${e}${RST}`;
}

// --- account badge ---

function accountBadge() {
  try {
    const raw = fs.readFileSync(path.join(os.homedir(), '.claude.json'), 'utf8');
    const j = JSON.parse(raw);
    const oa = j.oauthAccount || {};
    const type = (oa.organizationType || '').toLowerCase();
    const name = (oa.organizationName || '').toLowerCase();
    // team_tier / claude_team / name contains "team" -> T
    // enterprise / contains "inc" -> E
    const isTeam = type.includes('team') || name.includes('team');
    const isEnt = type.includes('enterprise') || name.includes('inc');
    if (isTeam) return `${GREEN}[T]${RST}`;
    if (isEnt) return `${BLINK_RED}[E]${RST}`;
    if (type) return `${YELLOW}[${type[0].toUpperCase()}]${RST}`;
    return '';
  } catch (e) { return ''; }
}

// --- git info ---

function getGitInfo(dir) {
  const info = { branch: null, dirty: false, untracked: false, ahead: 0, behind: 0 };
  try {
    let gitDir = null;
    let headPath = null;
    let current = dir;
    while (current !== '/') {
      const dotGit = path.join(current, '.git');
      try {
        const st = fs.statSync(dotGit);
        if (st.isDirectory()) {
          headPath = path.join(dotGit, 'HEAD');
        } else if (st.isFile()) {
          // worktree/submodule: ".git" is a file containing "gitdir: <path>"
          const ref = fs.readFileSync(dotGit, 'utf8').trim();
          const m = ref.match(/^gitdir:\s*(.+)$/);
          if (m) {
            const resolved = path.isAbsolute(m[1]) ? m[1] : path.resolve(current, m[1]);
            headPath = path.join(resolved, 'HEAD');
          }
        }
      } catch (e) { /* not here, keep walking */ }
      if (headPath && fs.existsSync(headPath)) {
        const content = fs.readFileSync(headPath, 'utf8').trim();
        info.branch = content.startsWith('ref: refs/heads/')
          ? content.slice(16)
          : content.slice(0, 7);
        gitDir = current;
        break;
      }
      headPath = null;
      current = path.dirname(current);
    }
    if (!gitDir) return info;

    try {
      const status = execSync(`git -C "${gitDir}" --no-optional-locks status --porcelain -b 2>/dev/null`, {
        timeout: 150, encoding: 'utf8',
      });
      const lines = status.split('\n');
      const header = lines[0] || '';
      const am = header.match(/ahead (\d+)/);
      const bm = header.match(/behind (\d+)/);
      if (am) info.ahead = parseInt(am[1]);
      if (bm) info.behind = parseInt(bm[1]);
      const fileLines = lines.slice(1).filter(l => l.trim().length > 0);
      info.dirty = fileLines.some(l => !l.startsWith('??'));
      info.untracked = fileLines.some(l => l.startsWith('??'));
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
    return ` ${GREEN}${pie(0)} compacted${RST}`;
  }

  const usedPct = Math.round(((100 - pct) / (100 - compactAt)) * 100);

  let color;
  if (untilCompact > 50) color = GREEN;
  else if (untilCompact > 35) color = YELLOW;
  else if (untilCompact > 20) color = ORANGE;
  else color = BLINK_RED;

  return ` ${color}${pie(usedPct)} ${untilCompact}%${RST}`;
}

// --- spend cap gauge ---

function nextMonthResetEpoch() {
  // first of next month at 00:00 UTC (Enterprise spend cap resets calendar-monthly)
  const now = new Date();
  const next = Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1, 0, 0, 0);
  return next / 1000;
}

function usageGauges(compact) {
  const countdown = compact ? () => '' : fmtCountdown;
  try {
    const cacheFile = path.join(os.homedir(), '.cache', 'claude-usage', 'cache.json');
    if (!fs.existsSync(cacheFile)) return [];

    let cache;
    try {
      cache = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
    } catch (e) {
      // corrupt cache — drop it so next tick refetches clean
      try { fs.unlinkSync(cacheFile); } catch (e2) {}
      return [];
    }
    const now = Date.now() / 1000;

    if (!cache.expires_at || cache.expires_at < now) {
      const { spawn } = require('child_process');
      const child = spawn('python3', [path.join(__dirname, 'usage-fetch.py')], {
        detached: true, stdio: 'ignore',
      });
      child.unref();
    }

    let visibleFilter = null;
    try {
      const cfgFile = path.join(os.homedir(), '.cache', 'claude-usage', 'config.json');
      const cfg = JSON.parse(fs.readFileSync(cfgFile, 'utf8'));
      if (Array.isArray(cfg.visible)) visibleFilter = cfg.visible;
    } catch (e) {}

    const orgs = (cache.orgs || [])
      .filter(o => o.five_hour || o.seven_day || o.spend_cap || o.models)
      .filter(o => !visibleFilter || visibleFilter.includes(o.label));
    if (!orgs.length) return [];

    const out = [];
    for (const org of orgs) {
      const parts = [];

      const fh = org.five_hour;
      if (fh && fh.used_pct != null) {
        const p = Math.min(100, Math.max(0, fh.used_pct));
        parts.push(`${colorForPct(p)}5h ${pie(p)} ${p}%${countdown(fh.resets_at, now)}${RST}`);
      }
      const sd = org.seven_day;
      if (sd && sd.used_pct != null) {
        const p = Math.min(100, Math.max(0, sd.used_pct));
        parts.push(`${colorForPct(p)}7d ${pie(p)} ${p}%${countdown(sd.resets_at, now)}${RST}`);
      }
      for (const [name, m] of Object.entries(org.models || {})) {
        if (m.used_pct == null) continue;
        const p = Math.min(100, Math.max(0, m.used_pct));
        parts.push(`${colorForPct(p)}${name.toLowerCase()} ${pie(p)} ${p}%${countdown(m.resets_at, now)}${RST}`);
      }
      const sc = org.spend_cap;
      if (sc && sc.limit) {
        const p = Math.min(100, Math.max(0, sc.used_pct || 0));
        const pctStr = p < 10 ? p.toFixed(1) : String(Math.round(p));
        const resetAt = sc.resets_at || nextMonthResetEpoch();
        parts.push(`${colorForPct(p)}cap ${pie(p)} ${pctStr}%${countdown(resetAt, now)}${RST}`);
      }

      if (!parts.length) continue;
      const label = orgs.length > 1 ? `${DIM}${org.label}${RST} ` : '';
      out.push(`${label}${parts.join(' ')}`);
    }
    return out;
  } catch (e) { return []; }
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
    const target = t.target ? ` ${t.target.slice(0, 60)}` : '';
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

// --- giantmem status (cached) ---

function giantmemStatus(dir) {
  const cachePath = path.join(STATE_DIR, 'giantmem-status.json');
  const ttlMs = 30 * 1000;
  try {
    const st = fs.statSync(cachePath);
    if (Date.now() - st.mtimeMs < ttlMs) {
      const cached = JSON.parse(fs.readFileSync(cachePath, 'utf8'));
      if (cached.__dir === dir) return cached;
    }
  } catch (e) { /* miss */ }
  try {
    fs.mkdirSync(STATE_DIR, { recursive: true });
  } catch (e) {}
  // fire detached: child writes the cache file itself, parent exits immediately.
  // wrap in nohup + sh so the child survives parent exit on macos.
  try {
    const bin = path.join(os.homedir(), '.local/bin/giantmem');
    const escDir = dir.replace(/'/g, "'\\''");
    const escCache = cachePath.replace(/'/g, "'\\''");
    const cmd = `(${bin} status --root '${escDir}' --stale-days 30 --write-cache '${escCache}' </dev/null >/dev/null 2>&1 & disown) 2>/dev/null`;
    const child = require('child_process').spawn('/bin/bash', ['-c', cmd], {
      detached: true,
      stdio: 'ignore',
    });
    child.unref();
  } catch (e) {}
  // return last cached (may be from a different dir; statusline tolerates that)
  try {
    return JSON.parse(fs.readFileSync(cachePath, 'utf8'));
  } catch (e) {
    return null;
  }
}

// --- main ---

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  try {
    const data = JSON.parse(input);
    const cfg = loadConfig();

    const dir = data.cwd || data.workspace?.current_dir || process.cwd();
    const homeDir = os.homedir();
    const fullPath = dir.startsWith(homeDir) ? '~' + dir.slice(homeDir.length) : dir;
    // show last 2 path components for readability on narrow panes
    const pathParts = fullPath.split('/');
    const displayPath = pathParts.length > 2 ? '.../' + pathParts.slice(-2).join('/') : fullPath;

    // git
    const git = getGitInfo(dir);
    let branchPart = '';
    if (git.branch) {
      let b = `${CYAN}${git.branch}${RST}`;
      if (git.dirty) b += `${YELLOW}*${RST}`;
      if (git.untracked) b += `${GREEN}?${RST}`;
      if (git.ahead) b += `${GREEN}+${git.ahead}${RST}`;
      if (git.behind) b += `${RED}-${git.behind}${RST}`;
      branchPart = ` \u2502 ${b}`;
    }

    const ctx = contextGauge(data);

    const model = modelLabel(data);
    const effort = effortLabel(data);
    let modelPart = '';
    if (model || effort) {
      const inner = [model && `${MAGENTA}${model}${RST}`, effort].filter(Boolean).join(`${DIM}\u00B7${RST}`);
      modelPart = `${inner} ${DIM}\u2502${RST} `;
    }

    const acct = accountBadge();
    const acctPart = acct ? `${acct} ${DIM}\u2502${RST} ` : '';

    // usage is the segment worth protecting, so it degrades last: full -> no
    // countdowns -> basename-only path -> spilled onto line 2
    const width = termWidth() - 1;
    const build = (p, u, bare) => `${bare ? '' : acctPart + modelPart}${DIM}${p}${RST}${branchPart} \u2502${ctx}` +
      u.map(s => ` \u2502 ${s}`).join('');
    const shortPath = pathParts[pathParts.length - 1] || displayPath;

    let usage = usageGauges(false);
    let line1 = build(displayPath, usage);
    let spilled = [];
    if (visLen(line1) > width) {
      usage = usageGauges(true);
      line1 = build(displayPath, usage);
    }
    if (visLen(line1) > width) {
      line1 = build(shortPath, usage);
    }
    if (visLen(line1) > width && usage.length) {
      spilled = usage;
      usage = [];
      line1 = build(shortPath, usage);
    }
    if (visLen(line1) > width) {
      line1 = build(shortPath, usage, true);
    }

    // minimal: one line only \u2014 keep usage on it, nothing else can carry it
    if (cfg.style === 'minimal' || !cfg.line2) {
      const only = spilled.length ? spilled : usage;
      let solo = spilled.length ? build(shortPath, only) : line1;
      if (visLen(solo) > width) solo = build(shortPath, only, true);
      process.stdout.write(solo);
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
        let lp = `${DIM}w:${RST}`;
        if (added) lp += `${DIM}${GREEN}+${added}${RST}`;
        if (removed) lp += `${DIM}${RED}-${removed}${RST}`;
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

    // giantmem status (cached 30s, never blocks)
    const gm = giantmemStatus(dir);
    if (gm) {
      const segs = [];
      if (gm.active_feature) segs.push(`${ORANGE}feat:${gm.active_feature}${RST}`);
      if (cfg.gmdocs && gm.live_docs_today) segs.push(`${DIM}gm:${RST}${GREEN}${gm.live_docs_today}${RST}${DIM}/d${RST}`);
      if (segs.length) parts.push(segs.join(`${DIM} ${RST}`));
    }

    const sep = ` ${DIM}\u2502${RST} `;
    let line2 = parts.join(sep);

    // persist line 2 so it survives ticks with missing data
    const line2Cache = path.join(STATE_DIR, 'line2-cache.txt');
    if (line2) {
      try { fs.mkdirSync(STATE_DIR, { recursive: true }); fs.writeFileSync(line2Cache, line2); } catch (e) {}
    } else {
      try { line2 = fs.readFileSync(line2Cache, 'utf8'); } catch (e) {}
    }

    // usage rides at the head of line 2 when line 1 couldn't hold it; the
    // activity stats are shed from the cheapest end to make room
    const usageStr = spilled.join(sep);
    let keep = line2 ? line2.split(sep) : [];
    const room = width - (usageStr ? visLen(usageStr) + visLen(sep) : 0);
    while (keep.length && visLen(keep.join(sep)) > room) keep.shift();
    line2 = [usageStr, keep.join(sep)].filter(Boolean).join(sep);

    if (line2) {
      process.stdout.write(`${line1}\n${line2}`);
    } else {
      process.stdout.write(line1);
    }
  } catch (e) {
    // silent fail
  }
});
