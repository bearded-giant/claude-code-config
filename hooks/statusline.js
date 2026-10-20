#!/usr/bin/env node
// statusline with configurable style (compact/minimal)
// config: ~/.claude/hooks/statusline-config.json

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');

// ansi
const RST = '\x1b[0m';
const DIM = '\x1b[2m';
const GREEN = '\x1b[32m';
const YELLOW = '\x1b[33m';
const CYAN = '\x1b[36m';
const RED = '\x1b[31m';
const MAGENTA = '\x1b[35m';
const PURPLE = '\x1b[38;5;135m';
const ORANGE = '\x1b[38;5;208m';
const BLINK_RED = '\x1b[5;31m';

const STATE_DIR = path.join(os.tmpdir(), 'claude-statusline');
const MAX_TOOLS = 50;


// --- config ---

function loadConfig() {
  const defaults = {
    style: 'compact',  // compact (pie) | minimal
    line2: true,
    tools: 'last',     // last (1 active tool) | feed (last 3) | false
    agents: true,
    thinking: true,
    messages: true,
    lines: true,
    duration: true,
    gmdocs: false,
    models: true,
    preflight: true,
    mr: true,
  };
  try {
    const cfgPath = path.join(__dirname, 'statusline-config.json');
    const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
    return { ...defaults, ...cfg };
  } catch (e) { return defaults; }
}

// --- helpers ---

// UTF-16 code units are not display columns: CJK and emoji occupy two, marks
// and joiners occupy none, and a surrogate pair is one glyph across two units.
// East Asian Ambiguous (the pies and separators used here) stays narrow, which
// is what wezterm/iTerm2 draw by default; set STATUSLINE_AMBIGUOUS_WIDE=1 for
// terminals configured to draw it wide.
const AMBIGUOUS_WIDE = process.env.STATUSLINE_AMBIGUOUS_WIDE === '1';

const ZERO_RANGES = [
  [0x200b, 0x200f], [0x2060, 0x2064], [0x0300, 0x036f], [0x1ab0, 0x1aff],
  [0x1dc0, 0x1dff], [0x20d0, 0x20ff], [0xfe00, 0xfe0f], [0xfe20, 0xfe2f],
];
const WIDE_RANGES = [
  [0x1100, 0x115f], [0x2e80, 0x303e], [0x3041, 0x33ff], [0x3400, 0x4dbf],
  [0x4e00, 0x9fff], [0xa000, 0xa4cf], [0xa960, 0xa97f], [0xac00, 0xd7a3],
  [0xf900, 0xfaff], [0xfe10, 0xfe19], [0xfe30, 0xfe6f], [0xff00, 0xff60],
  [0xffe0, 0xffe6], [0x1f300, 0x1f64f], [0x1f680, 0x1f6ff], [0x1f900, 0x1f9ff],
  [0x20000, 0x2fffd], [0x30000, 0x3fffd],
];
const AMBIGUOUS_RANGES = [
  [0x2190, 0x21ff], [0x2500, 0x257f], [0x25a0, 0x25ff], [0x2660, 0x266f],
  [0x2776, 0x277f], [0xe000, 0xf8ff],
];

function inRanges(cp, ranges) {
  for (const [lo, hi] of ranges) if (cp >= lo && cp <= hi) return true;
  return false;
}

function charWidth(cp) {
  if (cp < 0x20 || (cp >= 0x7f && cp < 0xa0)) return 0;
  if (inRanges(cp, ZERO_RANGES)) return 0;
  if (inRanges(cp, WIDE_RANGES)) return 2;
  if (AMBIGUOUS_WIDE && inRanges(cp, AMBIGUOUS_RANGES)) return 2;
  return 1;
}

const NON_ASCII_RE = /[^\x20-\x7e]/;

function visLen(s) {
  const plain = s.replace(/\x1b\[[0-9;]*m/g, '');
  // most segments are plain ascii, where columns and length agree
  if (!NON_ASCII_RE.test(plain)) return plain.length;
  let w = 0;
  for (const ch of plain) w += charWidth(ch.codePointAt(0));
  return w;
}

// hard-truncate to max visible chars, ANSI-aware; last resort after the fit
// ladder so a miscount or unsheddable segment can never wrap the pane
function clampAnsi(s, max) {
  if (visLen(s) <= max) return s;
  let out = '';
  let vis = 0;
  let i = 0;
  while (i < s.length) {
    const m = /^\x1b\[[0-9;]*m/.exec(s.slice(i));
    if (m) {
      out += m[0];
      i += m[0].length;
      continue;
    }
    // step by code point so a surrogate pair is never cut in half
    const ch = String.fromCodePoint(s.codePointAt(i));
    const w = charWidth(ch.codePointAt(0));
    if (vis + w > max) break;
    out += ch;
    vis += w;
    i += ch.length;
  }
  return out + RST;
}

function termWidth() {
  // COLUMNS is inherited at claude launch and goes stale on resize; tmux knows live width
  const pane = process.env.TMUX_PANE;
  if (pane) {
    try {
      const w = parseInt(execFileSync('tmux', ['display-message', '-p', '-t', pane, '#{pane_width}'], {
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
  if (!isFinite(secs) || secs <= 0) return '';
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

// one letter for the tmux strip: h s o f, so an idle fable/opus pane is visible before its cache goes cold
function modelLetter(data) {
  const raw = ((data.model || {}).id || (data.model || {}).display_name || '').toLowerCase();
  const m = raw.match(/haiku|sonnet|opus|fable/);
  return m ? m[0][0] : '';
}

function readEffort(data) {
  return String(data?.effort?.level || process.env.CLAUDE_CODE_EFFORT_LEVEL || '');
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

// --- usage fetch spawn (once per tick, 15s backoff across ticks) ---

let usageFetchSpawned = false;

function spawnUsageFetch(backoffMs = 15000) {
  if (usageFetchSpawned) return;
  usageFetchSpawned = true;
  try {
    const marker = path.join(STATE_DIR, 'usage-fetch-spawned');
    try {
      if (Date.now() - fs.statSync(marker).mtimeMs < backoffMs) return;
    } catch (e) {}
    fs.mkdirSync(STATE_DIR, { recursive: true });
    fs.writeFileSync(marker, '');
    const { spawn } = require('child_process');
    const child = spawn('python3', [path.join(__dirname, 'usage-fetch.py')], {
      detached: true, stdio: 'ignore',
    });
    child.on('error', () => {});
    child.unref();
  } catch (e) {}
}

// --- account badge ---

const BADGE_COLORS = {
  green: GREEN, red: RED, blinkRed: BLINK_RED, yellow: YELLOW,
  purple: PURPLE, magenta: MAGENTA, cyan: CYAN, orange: ORANGE, dim: DIM,
};

// order matters: first match wins. override via statusline-config.json
// "badges": [{"match": "skio", "label": "S", "color": "purple"}, ...] —
// match is a regex tested against "name type" lowercased; name is the
// usage-fetch org label when the session was matched by its rate limits
const DEFAULT_BADGES = [
  { match: 'skio', label: 'S', color: 'purple' },
  { match: 'team', label: 'T', color: 'green' },
  { match: 'enterprise|\\binc\\b', label: 'E', color: 'blinkRed' },
];

// /login can finish well after its transcript line lands
const LOGIN_FOLLOW_MS = 600000;
const RESET_MATCH_SECS = 120;

// ~/.claude.json is the last /login anywhere, not this session's login
function globalAccount() {
  try {
    const src = path.join(os.homedir(), '.claude.json');
    // ~450KB of project history parsed per tick for one oauthAccount field;
    // key a cache on the file's identity
    const st = fs.statSync(src);
    const stamp = `${st.mtimeMs}:${st.size}`;
    const cacheFile = path.join(STATE_DIR, 'account-badge.json');
    try {
      const hit = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
      if (hit.stamp === stamp && hit.account && 'uuid' in hit.account) return hit.account;
    } catch (e) {}

    const oa = JSON.parse(fs.readFileSync(src, 'utf8')).oauthAccount || {};
    const account = {
      name: (oa.organizationName || '').toLowerCase(),
      type: (oa.organizationType || '').toLowerCase(),
      uuid: oa.organizationUuid || '',
    };
    try {
      fs.mkdirSync(STATE_DIR, { recursive: true });
      fs.writeFileSync(cacheFile, JSON.stringify({ stamp, account }));
    } catch (e) {}
    return account;
  } catch (e) { return null; }
}

// stdin rate_limits come from this process's own API headers, so their reset
// times identify the org it is billing against
function matchOrg(rateLimits, orgs) {
  if (!rateLimits) return null;
  const hits = orgs.filter(org => {
    let compared = 0;
    for (const w of ['five_hour', 'seven_day']) {
      const mine = rateLimits[w]?.resets_at;
      const theirs = org[w]?.resets_at;
      if (mine == null || theirs == null) continue;
      const t = typeof theirs === 'string' ? Date.parse(theirs) / 1000 : theirs;
      if (!(Math.abs(mine - t) <= RESET_MATCH_SECS)) return false;
      compared++;
    }
    return compared > 0;
  });
  return hits.length === 1 ? hits[0] : null;
}

// a running claude keeps the token it started with, so pin per process
// (ppid) and only follow the global account after this session's own /login
function pinAccount(state, global, ppid, now) {
  const pin = state.acctPin;
  const loginAt = Date.parse(state.loginAt || '') || 0;
  const changed = pin && (pin.account.name !== global.name || pin.account.type !== global.type);
  const relogged = pin && loginAt > pin.at && (changed || now - loginAt > LOGIN_FOLLOW_MS);
  if (pin && pin.ppid === ppid && !relogged) {
    // pins written before uuid was tracked: same account, so borrow it
    if (pin.account.uuid !== undefined || changed) return false;
    pin.account.uuid = global.uuid;
    return true;
  }
  state.acctPin = { ppid, at: now, account: global };
  return true;
}

function sessionAccount(data, state) {
  try {
    if (data.rate_limits) {
      let orgs = [];
      try {
        orgs = JSON.parse(fs.readFileSync(path.join(os.homedir(), '.cache', 'claude-usage', 'cache.json'), 'utf8')).orgs || [];
      } catch (e) {}
      const org = matchOrg(data.rate_limits, orgs);
      if (org) return { name: org.label || '', type: '', uuid: org.id || '' };
    }
    const global = globalAccount();
    if (!global || !data.session_id) return global;
    if (pinAccount(state, global, process.ppid, Date.now())) saveState(data.session_id, state);
    return state.acctPin.account;
  } catch (e) { return null; }
}

function badgeFor(account, badges) {
  if (!account) return '';
  const haystack = `${account.name} ${account.type}`;
  for (const b of badges) {
    try {
      if (new RegExp(b.match).test(haystack)) {
        return `${BADGE_COLORS[b.color] || YELLOW}[${b.label}]${RST}`;
      }
    } catch (e) {}
  }
  if (account.type) return `${YELLOW}[${account.type[0].toUpperCase()}]${RST}`;
  return '';
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
        info.root = gitDir;
        break;
      }
      headPath = null;
      current = path.dirname(current);
    }
    if (!gitDir) return info;

    try {
      const status = execFileSync('git', ['-C', gitDir, '--no-optional-locks', 'status', '--porcelain', '-b'], {
        timeout: 150, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'],
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

  // per-session marker (PreCompact hook in settings.json writes it); another
  // session's compact must not flash this session's badge
  let recentCompact = false;
  if (data.session_id) {
    try {
      const ts = fs.readFileSync(`/tmp/claude-compact-ts-${data.session_id}`, 'utf8').trim();
      const elapsed = Math.floor(Date.now() / 1000) - parseInt(ts, 10);
      if (elapsed >= 0 && elapsed < 30) recentCompact = true;
    } catch (e) {}
  }

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

const STALE_AFTER = 300;
const LINE2_CACHE_TTL_MS = 60000;
const TOOL_STALE_MS = 120000;
const STALE_CACHE_FACTOR = 20;

function isStale(tool) {
  if (!tool.startTime) return false;
  const started = new Date(tool.startTime).getTime();
  return Number.isFinite(started) && Date.now() - started > TOOL_STALE_MS;
}

// a session whose org is known shows only that org, never another account's
// numbers; the /usage-switch filter covers sessions that can't be placed
function pickOrgs(orgs, orgId, visible) {
  const withData = orgs.filter(o => o.five_hour || o.seven_day || o.spend_cap || o.models);
  if (orgId) return withData.filter(o => o.id === orgId);
  return withData.filter(o => !visible || visible.includes(o.label));
}

function usageGauges(compact, showModels = true, orgId = '') {
  const countdown = compact ? () => '' : fmtCountdown;
  try {
    const cacheFile = path.join(os.homedir(), '.cache', 'claude-usage', 'cache.json');
    if (!fs.existsSync(cacheFile)) {
      spawnUsageFetch();
      return [];
    }

    let cache;
    try {
      cache = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
    } catch (e) {
      // don't unlink: usage-fetch.py replaces the file atomically, and a
      // parse failure here can be a read racing that rename
      spawnUsageFetch();
      return [];
    }
    const now = Date.now() / 1000;

    // a fetch that cannot reach claude.ai leaves the previous numbers in place,
    // so mark them rather than rendering month-old percentages as if live
    const stale = cache.failed_at != null
      || (cache.fetched_at != null && now - cache.fetched_at > STALE_AFTER);

    if (!cache.expires_at || cache.expires_at < now) {
      spawnUsageFetch(cache.failed_at != null ? 120000 : 15000);
    }

    let visibleFilter = null;
    try {
      const cfgFile = path.join(os.homedir(), '.cache', 'claude-usage', 'config.json');
      const cfg = JSON.parse(fs.readFileSync(cfgFile, 'utf8'));
      if (Array.isArray(cfg.visible)) visibleFilter = cfg.visible;
    } catch (e) {}

    const orgs = pickOrgs(cache.orgs || [], orgId, visibleFilter);
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
      for (const [name, m] of Object.entries(showModels ? org.models || {} : {})) {
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
      out.push(`${label}${parts.join(' ')}${stale ? ` ${DIM}!${RST}` : ''}`);
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
    const file = path.join(STATE_DIR, `${sessionId}.json`);
    const tmp = `${file}.${process.pid}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(state));
    fs.renameSync(tmp, file);
  } catch (e) {}
}

// mirror ctx and api errors onto the tmux pane so the status strip can read them
function syncPaneState(data, state) {
  const pane = process.env.TMUX_PANE;
  if (!pane || !data.session_id) return;
  let remaining = data.context_window?.remaining_percentage;
  if (remaining == null && data.context_window?.used_percentage != null) {
    remaining = 100 - data.context_window.used_percentage;
  }
  const pct = remaining == null ? null : Math.round(remaining);
  const err = state.apiError || null;
  const model = modelLetter(data);
  const prevCtx = state.paneCtx ?? null;
  const prevErr = state.paneErr ?? null;
  const prevModel = state.paneModel ?? '';
  if (pct === prevCtx && err === prevErr && model === prevModel) return;
  const hook = path.join(__dirname, 'claude_tmux_state.sh');
  try {
    if (pct !== prevCtx && pct != null) {
      execFileSync('tmux', ['set-option', '-p', '-t', pane, '@claude_ctx', String(pct)], { timeout: 120 });
    }
    if (err !== prevErr) {
      execFileSync('bash', err ? [hook, 'err', err] : [hook, 'errclear'], { input: '', timeout: 500 });
    }
    if (model !== prevModel && model) {
      execFileSync('tmux', ['set-option', '-p', '-t', pane, '@claude_model', model], { timeout: 120 });
    }
    state.paneCtx = pct;
    state.paneErr = err;
    state.paneModel = model;
    if (state.offset == null) state.offset = 0;
    saveState(data.session_id, state);
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
  if (size < state.offset) {
    // transcript rewritten or truncated for this session id — reparse clean
    Object.assign(state, { offset: 0, tools: [], agents: [], thinkingCount: 0, messageCount: 0, skills: [] });
  }
  if (size <= state.offset) return state;

  let buf;
  try {
    const fd = fs.openSync(transcriptPath, 'r');
    buf = Buffer.alloc(size - state.offset);
    fs.readSync(fd, buf, 0, buf.length, state.offset);
    fs.closeSync(fd);
  } catch (e) { return state; }

  // only consume newline-terminated lines; a partially-flushed trailing line
  // stays unread so the next tick re-reads it complete
  const text = buf.toString('utf8');
  const lastNl = text.lastIndexOf('\n');
  if (lastNl === -1) return state;
  const complete = text.slice(0, lastNl);

  const toolIds = new Set(state.tools.map(t => t.id));
  const agentIds = new Set(state.agents.map(a => a.id));

  for (const line of complete.split('\n')) {
    if (!line.trim()) continue;
    let entry;
    try { entry = JSON.parse(line); } catch (e) { continue; }

    const msg = entry.message;
    if (!msg?.content) continue;

    if (entry.type === 'assistant') {
      if (entry.isApiErrorMessage) {
        const t = Array.isArray(msg.content)
          ? (msg.content.find(b => b.type === 'text')?.text || 'api error')
          : String(msg.content);
        state.apiError = t.replace(/\s+/g, ' ').slice(0, 60);
      } else if (state.apiError) {
        state.apiError = null;
      }
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
      // count human messages, not the user-role carriers of tool_results
      const isHuman = typeof msg.content === 'string' ||
        (Array.isArray(msg.content) && msg.content.some(b => b.type === 'text'));
      if (isHuman) state.messageCount++;
      if (typeof msg.content === 'string' && msg.content.includes('<command-name>/login</command-name>')) {
        state.loginAt = entry.timestamp;
      }
      if (!Array.isArray(msg.content)) continue;
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
  if (state.agents.length > MAX_TOOLS) {
    state.agents = state.agents.slice(-MAX_TOOLS);
  }
  if (state.skills.length > MAX_TOOLS) {
    state.skills = state.skills.slice(-MAX_TOOLS);
  }

  state.offset += Buffer.byteLength(text.slice(0, lastNl + 1), 'utf8');
  saveState(sessionId, state);
  return state;
}

// --- widget formatters ---

function fmtToolFeed(tools, mode) {
  if (!mode || !tools.length) return '';

  if (mode === 'last') {
    // just show the most recent non-completed tool, or last completed. a
    // tool_use whose result never arrived (interrupt, crash) would otherwise
    // read as running forever, so ignore ones that have gone cold.
    const fresh = tools.filter(t => !t.completed && !isStale(t));
    const lastDone = [...tools].reverse().find(x => x.completed);
    const t = fresh.length ? fresh[fresh.length - 1] : (lastDone || tools[tools.length - 1]);
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
  // per-dir cache: concurrent sessions in different repos must not clobber
  // each other's status or trigger cross-repo refresh loops
  const dirKey = require('crypto').createHash('md5').update(dir).digest('hex').slice(0, 8);
  const cachePath = path.join(STATE_DIR, `giantmem-status-${dirKey}.json`);
  const ttlMs = 30 * 1000;
  let cached = null;
  try {
    cached = JSON.parse(fs.readFileSync(cachePath, 'utf8'));
    if (Date.now() - fs.statSync(cachePath).mtimeMs < ttlMs) return cached;
  } catch (e) { /* miss */ }
  try {
    fs.mkdirSync(STATE_DIR, { recursive: true });
  } catch (e) {}
  // fire detached: child writes the cache file itself, parent exits immediately.
  // wrap in nohup + sh so the child survives parent exit on macos.
  // in-flight marker keeps ticks from stacking refreshes while one runs.
  try {
    const marker = `${cachePath}.refreshing`;
    let inFlight = false;
    try { inFlight = Date.now() - fs.statSync(marker).mtimeMs < 15000; } catch (e) {}
    if (!inFlight) {
      fs.writeFileSync(marker, '');
      const bin = path.join(os.homedir(), '.local/bin/giantmem');
      const escDir = dir.replace(/'/g, "'\\''");
      const escCache = cachePath.replace(/'/g, "'\\''");
      const cmd = `(${bin} status --root '${escDir}' --stale-days 30 --write-cache '${escCache}' </dev/null >/dev/null 2>&1 & disown) 2>/dev/null`;
      const child = require('child_process').spawn('/bin/bash', ['-c', cmd], {
        detached: true,
        stdio: 'ignore',
      });
      child.unref();
    }
  } catch (e) {}
  // stale same-dir data beats a blank segment while the refresh lands, but a
  // giantmem that never answers should not pin one answer on screen forever
  try {
    if (Date.now() - fs.statSync(cachePath).mtimeMs > ttlMs * STALE_CACHE_FACTOR) {
      return null;
    }
  } catch (e) {}
  return cached;
}

// --- preflight auth + branch MR (detached python fetchers, cached) ---

const PREFLIGHT_OK_TTL_MS = 5 * 60 * 1000;
// a red check re-polls fast so a fresh login clears it without a hook
const PREFLIGHT_RED_TTL_MS = 30 * 1000;
const PREFLIGHT_MAX_AGE_MS = 30 * 60 * 1000;
const MR_TTL_MS = 60 * 1000;
const MR_MAX_AGE_MS = 10 * 60 * 1000;
const BASE_BRANCHES = new Set(['main', 'master', 'stage']);
const MR_COLORS = { ok: GREEN, wait: YELLOW, bad: RED };

function readCache(cachePath) {
  try {
    const data = JSON.parse(fs.readFileSync(cachePath, 'utf8'));
    return { data, age: Date.now() - fs.statSync(cachePath).mtimeMs };
  } catch (e) { return { data: null, age: Infinity }; }
}

function spawnFetcher(cachePath, args) {
  try {
    const marker = `${cachePath}.refreshing`;
    try { if (Date.now() - fs.statSync(marker).mtimeMs < 30000) return; } catch (e) {}
    fs.mkdirSync(STATE_DIR, { recursive: true });
    fs.writeFileSync(marker, '');
    const child = require('child_process').spawn('python3', args, { detached: true, stdio: 'ignore' });
    child.on('error', () => {});
    child.unref();
  } catch (e) {}
}

function preflightStatus() {
  const cachePath = path.join(STATE_DIR, 'preflight.json');
  const { data, age } = readCache(cachePath);
  const healthy = data && Object.values(data).every(c => c.ok === true);
  if (age > (healthy ? PREFLIGHT_OK_TTL_MS : PREFLIGHT_RED_TTL_MS)) {
    spawnFetcher(cachePath, [path.join(__dirname, 'preflight_check.py'), cachePath]);
  }
  return age < PREFLIGHT_MAX_AGE_MS ? data : null;
}

function mrStatus(root, branch) {
  if (!root || !branch || BASE_BRANCHES.has(branch)) return null;
  const key = require('crypto').createHash('md5').update(`${root}\0${branch}`).digest('hex').slice(0, 8);
  const cachePath = path.join(STATE_DIR, `mr-${key}.json`);
  const { data, age } = readCache(cachePath);
  if (age > MR_TTL_MS) spawnFetcher(cachePath, [path.join(__dirname, 'mr_status.py'), root, branch, cachePath]);
  return age < MR_MAX_AGE_MS ? data : null;
}

function fmtPreflight(checks) {
  if (!checks) return '';
  return Object.entries(checks)
    .filter(([, c]) => c.ok !== true)
    .map(([id, c]) => (c.ok === false ? `${RED}✗${id}${RST}` : `${DIM}~${id}${RST}`))
    .join(' ');
}

function fmtMr(mr) {
  if (!mr || !mr.iid) return '';
  return `${MR_COLORS[mr.level] || DIM}!${mr.iid} ${mr.tag}${RST}`;
}

// --- line fitting (pure: width + prebuilt segments in, strings out) ---

function buildLine1(seg, p, u, bare) {
  return `${bare ? '' : seg.acctPart + seg.modelPart}${DIM}${p}${RST}${seg.branchPart}${seg.ctx ? ` │${seg.ctx}` : ''}` +
    u.map(s => ` │ ${s}`).join('');
}

// usage is the segment worth protecting, so it degrades last: full -> no
// countdowns -> basename-only path -> spilled onto line 2 -> bare
function fitLine1(width, seg) {
  let usage = seg.usage;
  let line1 = buildLine1(seg, seg.displayPath, usage);
  let spilled = [];
  if (visLen(line1) > width) {
    usage = seg.usageCompact;
    line1 = buildLine1(seg, seg.displayPath, usage);
  }
  if (visLen(line1) > width) {
    line1 = buildLine1(seg, seg.shortPath, usage);
  }
  if (visLen(line1) > width && usage.length) {
    spilled = usage;
    usage = [];
    line1 = buildLine1(seg, seg.shortPath, usage);
  }
  if (visLen(line1) > width) {
    line1 = buildLine1(seg, seg.shortPath, usage, true);
  }
  return { line1: clampAnsi(line1, width), usage, spilled };
}

// minimal / no-line2: one line only, usage stays on it
function fitSolo(width, seg, fit) {
  const only = fit.spilled.length ? fit.spilled : fit.usage;
  let solo = fit.spilled.length ? buildLine1(seg, seg.shortPath, only) : fit.line1;
  if (visLen(solo) > width) solo = buildLine1(seg, seg.shortPath, only, true);
  return clampAnsi(solo, width);
}

// spilled usage rides at the head of line 2; activity stats shed from the
// cheapest end to make room
function packLine2(width, spilled, parts, sep) {
  const usageStr = spilled.join(sep);
  const keep = parts.slice();
  const room = width - (usageStr ? visLen(usageStr) + visLen(sep) : 0);
  while (keep.length && visLen(keep.join(sep)) > room) keep.shift();
  const line2 = [usageStr, keep.join(sep)].filter(Boolean).join(sep);
  return line2 ? clampAnsi(line2, width) : '';
}

// --- main ---

let input = '';
const renderTick = () => {
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

    const transcript = parseTranscript(data.transcript_path, data.session_id);

    const account = sessionAccount(data, transcript);
    const acct = badgeFor(account, cfg.badges || DEFAULT_BADGES);
    const acctPart = acct ? `${acct} ${DIM}\u2502${RST} ` : '';
    const orgId = (account && account.uuid) || '';

    const width = termWidth() - 1;
    const seg = {
      acctPart, modelPart, branchPart, ctx,
      displayPath,
      shortPath: pathParts[pathParts.length - 1] || displayPath,
      usage: usageGauges(false, cfg.models, orgId),
      usageCompact: usageGauges(true, cfg.models, orgId),
    };
    const fit = fitLine1(width, seg);
    let line1 = fit.line1;
    const spilled = fit.spilled;

    syncPaneState(data, transcript);

    // minimal: one line only \u2014 keep usage on it, nothing else can carry it
    if (cfg.style === 'minimal' || !cfg.line2) {
      process.stdout.write(fitSolo(width, seg, fit));
      return;
    }

    // line 2
    const cost = data.cost || {};
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

    // last on line 2: packLine2 sheds from the front, so alerts survive narrow panes
    if (cfg.mr) {
      const mrStr = fmtMr(mrStatus(git.root, git.branch));
      if (mrStr) parts.push(mrStr);
    }
    if (cfg.preflight) {
      const authStr = fmtPreflight(preflightStatus());
      if (authStr) parts.push(authStr);
    }

    const sep = ` ${DIM}\u2502${RST} `;
    let line2 = parts.join(sep);

    // persist line 2 so it survives ticks with missing data; keyed by session
    // so concurrent sessions never render each other's stats
    if (data.session_id) {
      const line2Cache = path.join(STATE_DIR, `line2-cache-${data.session_id}.txt`);
      if (line2) {
        try { fs.mkdirSync(STATE_DIR, { recursive: true }); fs.writeFileSync(line2Cache, line2); } catch (e) {}
      } else {
        // bounded: an unbounded fallback re-rendered a dead line forever
        try {
          if (Date.now() - fs.statSync(line2Cache).mtimeMs < LINE2_CACHE_TTL_MS) {
            line2 = fs.readFileSync(line2Cache, 'utf8');
          }
        } catch (e) {}
      }
    }

    line2 = packLine2(width, spilled, line2 ? line2.split(sep) : [], sep);

    if (line2) {
      process.stdout.write(`${line1}\n${line2}`);
    } else {
      process.stdout.write(line1);
    }
  } catch (e) {
    // silent fail; STATUSLINE_DEBUG=1 leaves a breadcrumb
    if (process.env.STATUSLINE_DEBUG) {
      try {
        fs.mkdirSync(STATE_DIR, { recursive: true });
        fs.writeFileSync(path.join(STATE_DIR, 'error.txt'), String((e && e.stack) || e));
      } catch (e2) {}
    }
  }
};

if (require.main === module) {
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => input += chunk);
  process.stdin.on('end', renderTick);
}

module.exports = {
  visLen, clampAnsi, pie, fmtCountdown, fmtDuration, fmtDurationShort,
  buildLine1, fitLine1, fitSolo, packLine2, isStale, fmtToolFeed, charWidth,
  fmtPreflight, fmtMr, matchOrg, pinAccount, badgeFor, DEFAULT_BADGES, pickOrgs,
};
