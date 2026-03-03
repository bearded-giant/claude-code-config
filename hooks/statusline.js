#!/usr/bin/env node
// shows: model | directory | branch | context usage

const fs = require('fs');
const path = require('path');
const os = require('os');

function getGitBranch(dir) {
  try {
    let current = dir;
    while (current !== '/') {
      const gitHead = path.join(current, '.git', 'HEAD');
      if (fs.existsSync(gitHead)) {
        const content = fs.readFileSync(gitHead, 'utf8').trim();
        if (content.startsWith('ref: refs/heads/')) {
          return content.slice(16);
        }
        return content.slice(0, 7); // detached HEAD - show short sha
      }
      current = path.dirname(current);
    }
  } catch (e) {}
  return null;
}

// Read JSON from stdin
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  try {
    const data = JSON.parse(input);
    const model = data.model?.display_name || 'Claude';
    const dir = data.workspace?.current_dir || process.cwd();
    const branch = getGitBranch(dir);
    const remaining = data.context_window?.remaining_percentage;

    // detect recent compaction via signal file from PreCompact hook
    let recentCompact = false;
    try {
      const ts = fs.readFileSync('/tmp/claude-compact-ts', 'utf8').trim();
      const elapsed = Math.floor(Date.now() / 1000) - parseInt(ts, 10);
      if (elapsed >= 0 && elapsed < 30) recentCompact = true;
    } catch (e) {}

    // Context window display (shows % until compaction)
    let ctx = '';
    if (remaining != null) {
      const compactAt = 15;
      const pct = Math.round(remaining);
      const untilCompact = Math.max(0, pct - compactAt);

      // if compaction just happened and data looks stale, show reset state
      if (recentCompact && untilCompact < 25) {
        const bar = '░'.repeat(10);
        ctx = ` \x1b[32m${bar} compacted\x1b[0m`;
      } else {
        // bar fills from empty (fresh) to full (compaction imminent)
        const used = 100 - pct;
        const usable = 100 - compactAt;
        const filled = Math.min(10, Math.round((used / usable) * 10));
        const bar = '█'.repeat(filled) + '░'.repeat(10 - filled);

        // Color based on room until compact
        if (untilCompact > 50) {
          ctx = ` \x1b[32m${bar} ${untilCompact}%\x1b[0m`;
        } else if (untilCompact > 35) {
          ctx = ` \x1b[33m${bar} ${untilCompact}%\x1b[0m`;
        } else if (untilCompact > 20) {
          ctx = ` \x1b[38;5;208m${bar} ${untilCompact}%\x1b[0m`;
        } else {
          ctx = ` \x1b[5;31m${bar} ${untilCompact}%\x1b[0m`;
        }
      }
    }

    // usage display per org (5h and 7d from cache)
    let usagePart = '';
    try {
      const cacheFile = path.join(os.homedir(), '.cache', 'claude-usage', 'cache.json');
      if (fs.existsSync(cacheFile)) {
        const cache = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
        const now = Date.now() / 1000;

        if (!cache.expires_at || cache.expires_at < now) {
          const { spawn } = require('child_process');
          const child = spawn('python3', [path.join(__dirname, 'usage-fetch.py')], {
            detached: true,
            stdio: 'ignore',
          });
          child.unref();
        }

        function fmtCountdown(resets_at) {
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

        function colorFor(pct) {
          if (pct < 50) return '\x1b[32m';
          if (pct < 70) return '\x1b[33m';
          if (pct < 85) return '\x1b[38;5;208m';
          return '\x1b[5;31m';
        }

        function fmtBar(pct) {
          const filled = Math.min(5, Math.round(pct / 20));
          return '\u2588'.repeat(filled) + '\u2591'.repeat(5 - filled);
        }

        // read visibility config
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
            parts.push(`${colorFor(p)}5h ${fmtBar(p)} ${p}%${fmtCountdown(fh.resets_at)}\x1b[0m`);
          }
          if (show7d && sd && sd.used_pct != null) {
            const p = Math.min(100, Math.max(0, sd.used_pct));
            parts.push(`${colorFor(p)}7d ${fmtBar(p)} ${p}%${fmtCountdown(sd.resets_at)}\x1b[0m`);
          }
          if (parts.length) {
            usagePart += ` \u2502 \x1b[2m${org.label}\x1b[0m ${parts.join(' ')}`;
          }
        }
      }
    } catch (e) {}

    // Output
    const homeDir = os.homedir();
    const displayPath = dir.startsWith(homeDir) ? '~' + dir.slice(homeDir.length) : dir;
    const branchPart = branch ? ` │ \x1b[36m${branch}\x1b[0m` : '';
    process.stdout.write(`\x1b[2m${model}\x1b[0m │ \x1b[2m${displayPath}\x1b[0m${branchPart} │${ctx}${usagePart}`);
  } catch (e) {
    // Silent fail - don't break statusline on parse errors
  }
});
