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

    // Output
    const homeDir = os.homedir();
    const displayPath = dir.startsWith(homeDir) ? '~' + dir.slice(homeDir.length) : dir;
    const branchPart = branch ? ` │ \x1b[36m${branch}\x1b[0m` : '';
    process.stdout.write(`\x1b[2m${model}\x1b[0m │ \x1b[2m${displayPath}\x1b[0m${branchPart} │${ctx}`);
  } catch (e) {
    // Silent fail - don't break statusline on parse errors
  }
});
