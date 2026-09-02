#!/usr/bin/env python3
"""
Workspace Session End Hook for Claude Code
Hook: SessionEnd

Extracts session summary, discoveries, and plans from transcript.
Creates individual session files for grep-ability and git history.

If .giantmem/ doesn't exist, auto-initializes workspace structure first.
Falls back to scratch/ for legacy workspaces.

Input (JSON on stdin):
{
    "session_id": "...",
    "cwd": "/current/working/directory",
    "transcript_path": "~/.claude/projects/.../session.jsonl"
}

Output files:
- .giantmem/history/sessions/{timestamp}_{session_id}.md  (detailed session file)
- .giantmem/history/sessions.md  (index with one-liners)
- .giantmem/context/discoveries.md  (appended)
- .giantmem/plans/current.md  (updated if plans found)

Auto-init creates (if .giantmem/ missing):
- .giantmem/{context,plans,history,filebox,research,reviews}/
- .giantmem/history/sessions/
- .giantmem/WORKSPACE.md
- .giantmem/.gitkeep

NOTE: Uses only Python standard library (no external dependencies)
"""

import sys
import json
import os
import re
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Set, Optional
from collections import defaultdict

# a keyword anywhere in a sentence matched ordinary prose, so these anchor to the
# start of a line or list item and the line must read as a finished sentence
DISCOVERY_PATTERNS = [
    (r'(?:discovered|found|learned|realized|noticed)\b', 'finding'),
    (r'(?:pattern|architecture|structure)\b', 'architecture'),
    (r'(?:gotcha|caveat|watch out|careful|note that|important)\b', 'gotcha'),
    (r'(?:convention|standard|style|naming)\b', 'convention'),
    (r'(?:dependency|requires|depends on|imports?)\b', 'dependency'),
    (r'(?:config|configuration|setting|environment)\b', 'config'),
    (r'(?:entry\s*point|main|bootstrap|init)\b', 'entry'),
]

LIST_PREFIX_RE = re.compile(r'^\s*(?:[-*+]\s+|\d+[.)]\s+|#{1,6}\s+|>\s+)*')


def is_sentence(text: str) -> bool:
    """Reject mid-sentence captures: chat prose sliced at a keyword boundary."""
    if len(text) < 20 or text[0].islower():
        return False
    if '|' in text or '```' in text:
        return False
    if text.count('"') % 2 or text.count('`') % 2 or text.count('(') != text.count(')'):
        return False
    return text.rstrip().endswith(('.', '!', '?', ':'))

# topic extraction keywords
TOPIC_KEYWORDS = {
    'auth': ['auth', 'login', 'jwt', 'token', 'password', 'credential', 'oauth', 'permissions'],
    'api': ['api', 'endpoint', 'route', 'rest', 'graphql', 'request', 'response'],
    'database': ['database', 'sql', 'query', 'migration', 'model', 'schema', 'table'],
    'test': ['test', 'spec', 'pytest', 'jest', 'coverage', 'mock', 'fixture'],
    'bug': ['bug', 'fix', 'error', 'issue', 'debug', 'broken', 'failing'],
    'feature': ['feature', 'implement', 'add', 'create', 'new', 'build'],
    'refactor': ['refactor', 'cleanup', 'reorganize', 'restructure', 'rename'],
    'config': ['config', 'setting', 'env', 'environment', 'setup', 'install'],
    'docs': ['document', 'readme', 'comment', 'explain', 'describe'],
    'perf': ['performance', 'optimize', 'speed', 'slow', 'fast', 'cache'],
    'ui': ['ui', 'frontend', 'component', 'style', 'css', 'render', 'display'],
    'deploy': ['deploy', 'ci', 'cd', 'pipeline', 'docker', 'kubernetes'],
    'workspace': ['workspace', 'giantmem', 'hook', 'session', 'claude', 'mcp', 'plugin'],
}

# bonus weight given to workspace-defined topic
WORKSPACE_TOPIC_WEIGHT = 5


def read_transcript(transcript_path: str) -> List[dict]:
    """Read and parse the JSONL transcript file."""
    messages = []
    full_path = os.path.expanduser(transcript_path)

    if not os.path.exists(full_path):
        return messages

    try:
        with open(full_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        msg = json.loads(line)
                        messages.append(msg)
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass

    return messages


def extract_user_prompts(messages: List[dict]) -> List[str]:
    """Extract user prompts from transcript."""
    prompts = []
    for msg in messages:
        if msg.get('type') == 'user':
            message = msg.get('message', {})
            content = message.get('content', '')
            if isinstance(content, str) and content.strip():
                # truncate long prompts
                text = content.strip()
                if len(text) > 200:
                    text = text[:200] + '...'
                prompts.append(text)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        text = block.get('text', '').strip()
                        if text:
                            if len(text) > 200:
                                text = text[:200] + '...'
                            prompts.append(text)
    return prompts


def extract_assistant_content(messages: List[dict]) -> str:
    """Extract text content from assistant messages."""
    content_parts = []

    for msg in messages:
        if msg.get('type') == 'assistant':
            message = msg.get('message', {})
            content = message.get('content', [])

            for block in content:
                if isinstance(block, dict) and block.get('type') == 'text':
                    content_parts.append(block.get('text', ''))
                elif isinstance(block, str):
                    content_parts.append(block)

    return '\n'.join(content_parts)


def extract_tool_usage(messages: List[dict]) -> Dict[str, List[str]]:
    """
    Extract tool usage with file paths from transcript.
    Returns dict: tool_name -> list of file paths touched.
    """
    tool_files: Dict[str, Set[str]] = defaultdict(set)

    for msg in messages:
        if msg.get('type') == 'assistant':
            message = msg.get('message', {})
            content = message.get('content', [])

            for block in content:
                if isinstance(block, dict) and block.get('type') == 'tool_use':
                    tool_name = block.get('name', 'unknown')
                    tool_input = block.get('input', {})

                    # extract file paths based on tool type
                    file_path = None
                    if tool_name in ('Read', 'Write', 'Edit', 'MultiEdit'):
                        file_path = tool_input.get('file_path')
                    elif tool_name == 'Glob':
                        file_path = tool_input.get('pattern')
                    elif tool_name == 'Grep':
                        file_path = tool_input.get('path') or tool_input.get('pattern')
                    elif tool_name == 'Bash':
                        cmd = tool_input.get('command', '')
                        if cmd:
                            # truncate long commands
                            file_path = cmd[:100] + ('...' if len(cmd) > 100 else '')
                    elif tool_name == 'Task':
                        desc = tool_input.get('description', '')
                        if desc:
                            file_path = f"[{desc}]"

                    if file_path:
                        tool_files[tool_name].add(file_path)
                    else:
                        # still count the tool use
                        tool_files[tool_name].add('')

    # convert sets to sorted lists, filter empty strings
    return {
        tool: sorted([f for f in files if f])
        for tool, files in tool_files.items()
    }


def extract_workspace_topic(workspace_dir: Path) -> Optional[str]:
    """
    Extract topic hint from WORKSPACE.md Purpose section.
    Returns matching topic keyword if found, None otherwise.
    """
    workspace_file = workspace_dir / "WORKSPACE.md"
    if not workspace_file.exists():
        return None

    try:
        content = workspace_file.read_text().lower()

        # look for purpose section content
        purpose_match = re.search(r'## purpose\s*\n(.+?)(?=\n##|\Z)', content, re.DOTALL)
        if not purpose_match:
            return None

        purpose_text = purpose_match.group(1).strip()

        # skip if just placeholder comment
        if purpose_text.startswith('<!--') or not purpose_text:
            return None

        # check for topic keywords in purpose
        for topic, keywords in TOPIC_KEYWORDS.items():
            for keyword in keywords:
                if re.search(r'\b' + keyword + r'\w*\b', purpose_text):
                    return topic

    except Exception:
        pass

    return None


def extract_session_topic(
    user_prompts: List[str],
    assistant_content: str,
    workspace_topic: Optional[str] = None
) -> str:
    """
    Extract a topic/theme from the session by analyzing content.
    If workspace has a topic defined, it gets bonus weight.
    Returns a short topic tag like 'auth', 'api', 'refactor'.
    """
    # combine all text for analysis
    all_text = ' '.join(user_prompts).lower() + ' ' + assistant_content.lower()

    # count keyword matches per topic
    topic_scores: Dict[str, int] = defaultdict(int)
    for topic, keywords in TOPIC_KEYWORDS.items():
        for keyword in keywords:
            count = len(re.findall(r'\b' + keyword + r'\w*\b', all_text))
            topic_scores[topic] += count

    # apply workspace topic bonus if defined
    if workspace_topic and workspace_topic in topic_scores:
        topic_scores[workspace_topic] += WORKSPACE_TOPIC_WEIGHT

    # get top topic
    if topic_scores:
        top_topic = max(topic_scores.items(), key=lambda x: x[1])
        if top_topic[1] > 2:  # minimum threshold
            return top_topic[0]

    # fallback to workspace topic if available
    if workspace_topic:
        return workspace_topic

    return 'general'


def extract_session_brief(user_prompts: List[str], topic: str) -> str:
    """
    Generate a brief summary from user prompts.
    Tries to capture the main intent of the session.
    """
    if not user_prompts:
        return f"{topic} session"

    # use first substantive prompt as base
    first_prompt = user_prompts[0]

    # clean it up for a brief
    brief = first_prompt.replace('\n', ' ').strip()

    # if it's a question, keep it short
    if '?' in brief:
        brief = brief.split('?')[0] + '?'

    # truncate
    if len(brief) > 80:
        brief = brief[:77] + '...'

    return brief


def extract_timestamps(messages: List[dict]) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Extract session start and end timestamps from messages."""
    start_time = None
    end_time = None

    for msg in messages:
        ts = msg.get('timestamp')
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                if start_time is None or dt < start_time:
                    start_time = dt
                if end_time is None or dt > end_time:
                    end_time = dt
            except (ValueError, AttributeError):
                pass

    return start_time, end_time


def extract_discoveries(content: str) -> List[Tuple[str, str]]:
    """Extract potential discoveries from assistant content."""
    discoveries = []
    seen = set()

    for raw in content.splitlines():
        line = LIST_PREFIX_RE.sub('', raw.strip(), count=1).strip()
        if not is_sentence(line) or line in seen:
            continue

        for pattern, category in DISCOVERY_PATTERNS:
            if not re.match(pattern, line, re.IGNORECASE):
                continue
            finding = line if len(line) <= 200 else line[:200] + '...'
            seen.add(line)
            discoveries.append((category, finding))
            break

    return discoveries[:10]


def extract_plans(content: str) -> List[str]:
    """Extract implementation plans/steps from content."""
    plans = []
    seen = set()

    list_pattern = r'(?:^|\n)\s*(\d+[\.\)]\s+.+?)(?=\n\s*\d+[\.\)]|\n\n|$)'
    matches = re.findall(list_pattern, content, re.MULTILINE | re.DOTALL)

    for match in matches:
        step = ' '.join(match.split())
        if len(step) > 15 and step not in seen and is_sentence(step):
            seen.add(step)
            plans.append(step)

    # case-sensitive: lowercase "next" and "step" are ordinary words, and with
    # IGNORECASE they captured the rest of any sentence containing them
    todo_pattern = r'^\s*(?:TODO|NEXT|STEP)\s*[:\-]\s*(.+?)\s*$'
    matches = re.findall(todo_pattern, content, re.MULTILINE)

    for match in matches:
        step = match.strip()
        if len(step) > 10 and step not in seen:
            seen.add(step)
            plans.append(f"TODO: {step}")

    return plans[:15]


def create_session_file(
    workspace_dir: Path,
    session_id: str,
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    topic: str,
    brief: str,
    user_prompts: List[str],
    tool_usage: Dict[str, List[str]],
    discoveries: List[Tuple[str, str]],
) -> Optional[Path]:
    """Create individual session summary file."""
    sessions_dir = workspace_dir / "history" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    # filename: YYYYMMDD_HHMMSS_sessionid.md
    now = datetime.now()
    timestamp_str = now.strftime('%Y%m%d_%H%M%S')
    session_short = session_id[:8] if session_id else 'unknown'
    filename = f"{timestamp_str}_{session_short}.md"
    session_file = sessions_dir / filename

    # format times
    start_str = start_time.strftime('%Y-%m-%d %H:%M') if start_time else now.strftime('%Y-%m-%d %H:%M')
    end_str = end_time.strftime('%H:%M') if end_time else now.strftime('%H:%M')

    # build content
    lines = [
        f"# Session: {start_str} - {end_str}",
        "",
        "## Summary",
        f"Topic: {topic}",
        f"Brief: {brief}",
        "",
    ]

    # user prompts
    if user_prompts:
        lines.append("## User Prompts")
        for prompt in user_prompts[:10]:  # limit to 10
            # escape for markdown
            prompt_clean = prompt.replace('\n', ' ').strip()
            lines.append(f"- {prompt_clean}")
        lines.append("")

    # files modified (group by action)
    if tool_usage:
        lines.append("## Files Touched")

        # group by modification type
        modified = tool_usage.get('Edit', []) + tool_usage.get('MultiEdit', [])
        created = tool_usage.get('Write', [])
        read_files = tool_usage.get('Read', [])

        if modified:
            lines.append("### Modified")
            for f in sorted(set(modified))[:20]:
                lines.append(f"- {f}")

        if created:
            lines.append("### Created")
            for f in sorted(set(created))[:10]:
                lines.append(f"- {f}")

        if read_files:
            lines.append("### Read")
            for f in sorted(set(read_files))[:15]:
                lines.append(f"- {f}")

        lines.append("")

    # tool usage stats
    if tool_usage:
        lines.append("## Tool Usage")
        for tool, files in sorted(tool_usage.items()):
            count = len(files) if files else 1
            lines.append(f"- {tool}: {count}")
        lines.append("")

    # bash commands
    bash_cmds = tool_usage.get('Bash', [])
    if bash_cmds:
        lines.append("## Commands Run")
        for cmd in bash_cmds[:10]:
            lines.append(f"- `{cmd}`")
        lines.append("")

    # discoveries
    if discoveries:
        lines.append("## Discoveries Extracted")
        for category, finding in discoveries:
            finding_clean = finding.replace('\n', ' ').strip()
            lines.append(f"- [{category}] {finding_clean}")
        lines.append("")

    # session metadata
    lines.extend([
        "## Metadata",
        f"- Session ID: {session_id}",
        f"- Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}",
    ])

    try:
        session_file.write_text('\n'.join(lines))
        return session_file
    except Exception:
        return None


def update_session_index(
    workspace_dir: Path,
    session_id: str,
    topic: str,
    brief: str,
    tool_usage: Dict[str, List[str]],
    discoveries_count: int,
    session_filename: str,
):
    """Add one-liner to sessions.md index."""
    index_file = workspace_dir / "history" / "sessions.md"
    index_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    session_short = session_id[:8] if session_id else 'unknown'

    # count edits
    edit_count = len(tool_usage.get('Edit', [])) + len(tool_usage.get('Write', []))

    # build summary parts
    parts = []
    if edit_count > 0:
        parts.append(f"{edit_count} edits")
    if discoveries_count > 0:
        parts.append(f"{discoveries_count} discoveries")

    summary = ', '.join(parts) if parts else 'read-only'

    # truncate brief for index
    brief_short = brief[:50] + '...' if len(brief) > 50 else brief

    line = f"- {timestamp}: [{topic}] {session_short} - {brief_short} ({summary})"

    try:
        with open(index_file, 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass


def append_discoveries(workspace_dir: Path, discoveries: List[Tuple[str, str]]) -> int:
    """Append discoveries to discoveries.md."""
    if not discoveries:
        return 0

    discoveries_file = workspace_dir / "context" / "discoveries.md"
    discoveries_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    # a re-run over the same transcript must not re-append what is already there
    recorded = set()
    if discoveries_file.exists():
        try:
            for line in discoveries_file.read_text(errors='replace').splitlines():
                hit = re.match(r'- \d{4}-\d\d-\d\d \d\d:\d\d: \[[^\]]+\] (.*)', line)
                if hit:
                    recorded.add(hit.group(1).strip())
        except OSError:
            pass

    lines = []
    for category, finding in discoveries:
        finding = finding.replace('\n', ' ').strip()
        if finding in recorded:
            continue
        recorded.add(finding)
        lines.append(f"- {timestamp}: [{category}] {finding}")

    if not lines:
        return 0

    try:
        with open(discoveries_file, 'a') as f:
            f.write('\n'.join(lines) + '\n')
        return len(lines)
    except Exception:
        return 0


def save_plans(workspace_dir: Path, plans: List[str]) -> bool:
    """Save plans to plans/current.md."""
    if not plans:
        return False

    plans_file = workspace_dir / "plans" / "current.md"
    plans_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    content = f"# Current Plan\nUpdated: {timestamp}\n\n"
    content += "## Steps\n"
    for i, plan in enumerate(plans, 1):
        plan = plan.replace('\n', ' ').strip()
        if not plan.startswith(('TODO', 'FIXME', 'NEXT')):
            content += f"{i}. {plan}\n"
        else:
            content += f"- {plan}\n"

    try:
        if plans_file.exists():
            steps = content.split('## Steps', 1)[-1].strip()
            if steps and steps in plans_file.read_text(errors='replace'):
                return True
            mtime = plans_file.stat().st_mtime
            age_hours = (datetime.now().timestamp() - mtime) / 3600
            if age_hours < 1:
                with open(plans_file, 'a') as f:
                    f.write(f"\n---\n{content}")
                return True

        with open(plans_file, 'w') as f:
            f.write(content)
        return True
    except Exception:
        return False


TIMELINE_LIMIT = 50
# TIMELINE_LIMIT = None  # uncomment for no limit


def build_features_table(workspace_dir: Path) -> str:
    """Build markdown features table from meta.json files."""
    features_dir = workspace_dir / "features"
    if not features_dir.exists():
        return ""

    rows = []
    for meta_file in sorted(features_dir.glob("*/meta.json")):
        try:
            data = json.loads(meta_file.read_text())
            name = data.get("name", meta_file.parent.name)
            status = data.get("status", "unknown")
            branch = data.get("branch", "-") or "-"
            rows.append((name, status, branch))
        except (json.JSONDecodeError, OSError):
            continue

    if not rows:
        return ""

    lines = [
        "| Feature | Status | Branch |",
        "|---------|--------|--------|",
    ]
    for name, status, branch in rows:
        lines.append(f"| {name} | {status} | {branch} |")

    return '\n'.join(lines)


def build_timeline(workspace_dir: Path, limit: Optional[int] = TIMELINE_LIMIT) -> str:
    """Build timeline of md file changes, excluding session files and WORKSPACE.md."""
    exclude_dirs = {'history'}
    exclude_files = {'WORKSPACE.md', '_index.md'}

    entries = []
    for md_file in workspace_dir.rglob("*.md"):
        rel = md_file.relative_to(workspace_dir)
        # skip excluded dirs and files
        if rel.parts[0] in exclude_dirs:
            continue
        if rel.name in exclude_files:
            continue

        try:
            stat = md_file.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)
            entries.append((mtime, str(rel)))
        except OSError:
            continue

    if not entries:
        return ""

    entries.sort(key=lambda x: x[0], reverse=True)
    if limit:
        entries = entries[:limit]

    lines = [
        "| Modified | File |",
        "|----------|------|",
    ]
    for mtime, rel_path in entries:
        date_str = mtime.strftime('%Y-%m-%d %H:%M')
        lines.append(f"| {date_str} | {rel_path} |")

    return '\n'.join(lines)


def update_workspace_md(workspace_dir: Path):
    """Regenerate Features and Timeline sections in WORKSPACE.md."""
    workspace_file = workspace_dir / "WORKSPACE.md"
    if not workspace_file.exists():
        return

    content = workspace_file.read_text()

    features_table = build_features_table(workspace_dir)
    timeline = build_timeline(workspace_dir)

    # parse into sections: list of (heading, body) tuples
    # header block (before first ##) is stored with heading=""
    sections = []
    current_heading = ""
    current_lines = []

    for line in content.split('\n'):
        if line.startswith('## '):
            sections.append((current_heading, '\n'.join(current_lines)))
            current_heading = line
            current_lines = []
        else:
            current_lines.append(line)
    sections.append((current_heading, '\n'.join(current_lines)))

    # rebuild: replace Features/Timeline, preserve everything else
    has_features = any(h == '## Features' for h, _ in sections)
    has_timeline = any(h == '## Timeline' for h, _ in sections)

    new_sections = []
    for heading, body in sections:
        if heading == '## Features':
            new_sections.append(('## Features', '\n' + features_table + '\n' if features_table else '\nNo features tracked.\n'))
        elif heading == '## Timeline':
            new_sections.append(('## Timeline', '\n' + timeline + '\n' if timeline else '\nNo files tracked yet.\n'))
        else:
            new_sections.append((heading, body))

    # insert Features and Timeline if they didn't exist
    # insert after Purpose section, or after header if no Purpose
    if not has_features or not has_timeline:
        insert_idx = 1  # after header block
        for i, (heading, _) in enumerate(new_sections):
            if heading == '## Purpose':
                insert_idx = i + 1
                break

        if not has_timeline:
            timeline_body = '\n' + timeline + '\n' if timeline else '\nNo files tracked yet.\n'
            new_sections.insert(insert_idx, ('## Timeline', timeline_body))
        if not has_features:
            features_body = '\n' + features_table + '\n' if features_table else '\nNo features tracked.\n'
            new_sections.insert(insert_idx, ('## Features', features_body))

    # reassemble
    result_lines = []
    for heading, body in new_sections:
        if heading:
            result_lines.append(heading)
        result_lines.append(body)

    new_content = '\n'.join(result_lines)
    # clean up excessive blank lines
    while '\n\n\n' in new_content:
        new_content = new_content.replace('\n\n\n', '\n\n')

    workspace_file.write_text(new_content)


def workspace_init(cwd: Path) -> Path:
    workspace_dir = cwd / ".giantmem"
    name = cwd.name

    subdirs = ['context', 'plans', 'history', 'filebox', 'research', 'reviews']
    for subdir in subdirs:
        (workspace_dir / subdir).mkdir(parents=True, exist_ok=True)

    (workspace_dir / "history" / "sessions").mkdir(parents=True, exist_ok=True)

    workspace_file = workspace_dir / "WORKSPACE.md"
    if not workspace_file.exists():
        today = datetime.now().strftime('%Y-%m-%d')

        # try to get git branch
        branch = "main"
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
        except Exception:
            pass

        content = f"""# Workspace: {name}
Started: {today}
Branch: {branch}
Status: [ ] In Progress  [ ] Complete

## Purpose
<!-- describe what this branch/project is for -->

## Features
No features tracked.

## Timeline
No files tracked yet.

## Notes
<!-- session notes, decisions, context -->
"""
        workspace_file.write_text(content)

    gitkeep = workspace_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()

    return workspace_dir


def main():
    """Main hook entry point."""
    try:
        input_data = json.load(sys.stdin)

        session_id = input_data.get("session_id", "unknown")
        cwd = input_data.get("cwd", os.getcwd())
        transcript_path = input_data.get("transcript_path", "")

        cwd_path = Path(cwd)
        workspace_dir = cwd_path / ".giantmem"
        if not workspace_dir.exists():
            workspace_dir = cwd_path / "scratch"

        # auto-init workspace if neither exists
        if not workspace_dir.exists():
            workspace_dir = workspace_init(cwd_path)
            print(f"Workspace: initialized .giantmem/ in {cwd_path.name}", file=sys.stderr)

        if not transcript_path:
            return

        messages = read_transcript(transcript_path)
        if not messages:
            return

        # extract all content
        user_prompts = extract_user_prompts(messages)
        assistant_content = extract_assistant_content(messages)
        tool_usage = extract_tool_usage(messages)
        start_time, end_time = extract_timestamps(messages)

        if not assistant_content and not user_prompts:
            return

        # derive topic and brief (with workspace hint if available)
        workspace_topic = extract_workspace_topic(workspace_dir)
        topic = extract_session_topic(user_prompts, assistant_content, workspace_topic)
        brief = extract_session_brief(user_prompts, topic)

        # extract discoveries and plans
        discoveries = extract_discoveries(assistant_content)
        plans = extract_plans(assistant_content)

        # create individual session file
        session_file = create_session_file(
            workspace_dir=workspace_dir,
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            topic=topic,
            brief=brief,
            user_prompts=user_prompts,
            tool_usage=tool_usage,
            discoveries=discoveries,
        )

        # update index
        session_filename = session_file.name if session_file else ''
        update_session_index(
            workspace_dir=workspace_dir,
            session_id=session_id,
            topic=topic,
            brief=brief,
            tool_usage=tool_usage,
            discoveries_count=len(discoveries),
            session_filename=session_filename,
        )

        # persist discoveries and plans (existing behavior)
        discoveries_count = append_discoveries(workspace_dir, discoveries)
        has_plans = save_plans(workspace_dir, plans)

        # regenerate features table and timeline in WORKSPACE.md
        update_workspace_md(workspace_dir)

        # output summary
        parts = []
        if session_file:
            parts.append(f"session:{session_file.name}")
        if discoveries_count > 0:
            parts.append(f"{discoveries_count} discoveries")
        if has_plans:
            parts.append("plans")

        if parts:
            print(f"Workspace: {', '.join(parts)}", file=sys.stderr)

        # index this session into the search db (incremental, ~1s)
        search_script = Path(os.environ.get(
            'GIANT_TOOLING_DIR', str(Path.home() / "dev/giant-tooling")
        )) / "giantmem-archive/giantmem-search.py"
        if search_script.exists():
            try:
                subprocess.Popen(
                    ["python3", str(search_script), "ingest", "--sessions-only"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    except Exception:
        pass


if __name__ == "__main__":
    main()
