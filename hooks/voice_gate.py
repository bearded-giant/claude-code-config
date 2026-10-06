#!/usr/bin/env python3
import json
import os
import re
import shlex
import sys
from pathlib import Path

VOICE = "~/.claude/config/voice.md"
BYPASS = "VOICE_GATE=off"
CAPS = {"reply": 80, "comment": 150, "slack": 80, "jira": 150}
MCP_BODY = {
    "mcp__plugin_slack_slack__slack_send_message": ("message", "slack"),
    "mcp__plugin_slack_slack__slack_send_message_draft": ("message", "slack"),
    "mcp__plugin_slack_slack__slack_schedule_message": ("message", "slack"),
    "mcp__plugin_kai_atlassian__addCommentToJiraIssue": ("commentBody", "jira"),
}

PREFILTER = re.compile(r"\b(glab|gh|curl)\b")
RAW_POST = re.compile(
    r"\b(glab\s+(mr|issue)\s+(note|comment)|gh\s+(pr|issue)\s+(comment|review)"
    r"|(glab|gh)\s+api\b.*?/(notes|discussions|comments|reviews|replies)\b.*?(body=|--input))",
    re.S,
)
POST_ENDPOINT = re.compile(r"/(notes|discussions|comments|reviews|replies)\b")
REPLY_ENDPOINT = re.compile(r"discussions/[^/\s]+/notes|/replies\b")
HEREDOC = re.compile(
    r"<<-?[ \t]*(['\"]?)(\w+)\1([^\n]*)\n(.*?)\n[ \t]*\2[ \t]*(?=\n|$)", re.S
)
SCRIPTS = {"python", "python3", "node", "ruby", "perl", "bash", "sh", "zsh", "jq"}
OPERATOR_CHARS = set(";&|\n()")

STARTERS = set(
    """a an the this that these those it its there here they we you he she and but so or
    if when then also now both one two three all any every each only just still not no yes
    nothing some most same fixed added removed updated changed moved switched kept keeping
    leaving left took taken done addressed confirmed deliberate intentional real good looks
    possibly probably maybe should could would can will is are was were does do did has have
    had after before since because with without for from in on at to by of as once until
    while plus otherwise however note see please thanks sure ok okay right yeah agreed makes
    my our your new old which what why how where who let overall finally first second last
    next other another even again instead backported fixing adding removing""".split()
)

FILLER = re.compile(
    r"\b(hope this helps|happy to help|feel free to|let me know if you have|great work"
    r"|nice work|great job|good catch|great catch|nice catch|thanks for the (review|catch|feedback)"
    r"|in summary|to summarize|overall,|delve|robust|seamless(ly)?|leverag(e|es|ing)"
    r"|tapestry|nuanced|it'?s important to note)\b",
    re.I,
)
FIRST_PERSON = re.compile(
    r"(?<![\w'’])(I|I['’](m|d|ll|ve)|[Mm]e|[Mm]y|[Mm]ine|[Mm]yself)(?![\w'’])"
)
LOWER_I = re.compile(r"(?<![\w'’.])i(['’](m|d|ll|ve))?(?![\w'’]|\.e\.)")
SENTENCE_START = re.compile(
    r"(?:^[ \t]*(?:[-*+][ \t]+|\d+[.)][ \t]+)?|[.!?][ \t]+)([A-Z][a-z'’]*)(?![A-Za-z])",
    re.M,
)
CODE_TOKENS = [
    re.compile(r"(?<![\w.@#/-])[a-z][a-z0-9]*(?:_[a-z0-9]+)+(?!\w|\.\w)"),
    re.compile(r"(?<!\w)[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+(?!\w|\.\w)"),
    re.compile(r"\b[A-Za-z_][\w.]*\(\)"),
    re.compile(
        r"(?<![\w/.-])(?:[\w-]+/)*[\w-]+\.(?:py|js|ts|tsx|jsx|md|json|ya?ml|sql|sh|go|rb|toml|lua|cfg|ini)(?::\d+)?(?!\w)"
    ),
    re.compile(r"(?<![\w-])--[a-z][\w-]+"),
    re.compile(r"(?<!\w)(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}(?!\w)"),
]
DASH = re.compile(r"[—–]")
EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿⭐⭕]")
ATTRIBUTION = re.compile(r"generated with \[?claude|co-authored-by:\s*claude", re.I)
MARKDOWN = re.compile(
    r"^[ \t]{0,3}#{1,6}[ \t]|^[ \t]*\|.+\|[ \t]*$|\*\*[^*\n]+\*\*", re.M
)


def scrub(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"(?m)^>.*$", "", text)
    text = re.sub(r"`[^`\n]*`", "CODE", text)
    text = re.sub(r"<https?://[^>]*>", "URL", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", "URL", text)
    text = re.sub(r"<[@#!][^>]*>|@[\w.-]+", "NAME", text)
    return re.sub(r":[a-z0-9_+-]+:", "", text)


def dictionary():
    try:
        words = Path("/usr/share/dict/words").read_text(encoding="utf-8").split()
    except OSError:
        return set(), set()
    return {w for w in words if w.islower()}, {w for w in words if w[:1].isupper()}


def is_common(word, lower, proper):
    base = re.split(r"['’]", word)[0]
    if base in proper and base.lower() not in STARTERS:
        return False
    low = base.lower()
    stems = {low}
    for suffix, cuts in (("ing", (3,)), ("ed", (1, 2)), ("es", (2,)), ("s", (1,))):
        if low.endswith(suffix) and len(low) > len(suffix) + 2:
            stems.update(low[:-n] for n in cuts)
    return bool(stems & STARTERS) or bool(stems & lower)


def violations(body, surface):
    text = scrub(body)
    found = []
    if DASH.search(text):
        found.append("em/en dash: use a comma, semicolon, or new sentence")
    if surface != "slack":
        hits = sorted({m.group(0) for m in FIRST_PERSON.finditer(text)})
        if hits:
            found.append(
                f"first person ({', '.join(hits)}): drop it, `tightened the wording` not `I tightened the wording`"
            )
    if LOWER_I.search(text):
        found.append("lowercase pronoun `i`: write `I`")
    lower, proper = dictionary()
    starts = []
    for m in SENTENCE_START.finditer(text):
        word = m.group(1)
        if (
            word != "I"
            and not word.startswith(("I'", "I’"))
            and is_common(word, lower, proper)
        ):
            starts.append(word)
    if starts:
        found.append(
            f"capitalized sentence start ({', '.join(sorted(set(starts))[:5])}): lowercase it"
        )
    tokens = list(
        dict.fromkeys(m.group(0) for pat in CODE_TOKENS for m in pat.finditer(text))
    )
    if tokens:
        found.append(f"code not in backticks: {', '.join(tokens[:5])}")
    if MARKDOWN.search(text):
        found.append("markdown headers, tables, or bold: plain text only")
    if EMOJI.search(text):
        found.append("unicode emoji: drop it")
    filler = sorted({m.group(0).lower() for m in FILLER.finditer(text)})
    if filler:
        found.append(f"filler ({', '.join(filler)}): cut it")
    if ATTRIBUTION.search(body):
        found.append("Claude attribution: remove it")
    words = len(text.split())
    if words > CAPS[surface]:
        found.append(
            f"{words} words, cap is {CAPS[surface]} for a {surface}: cut to the point"
        )
    return found


def split_commands(cmd):
    lex = shlex.shlex(cmd, posix=True, punctuation_chars="();<>|&\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = ""
    cmds, cur = [], []
    for tok in lex:
        if tok and set(tok) <= OPERATOR_CHARS:
            if cur:
                cmds.append(cur)
            cur = []
        else:
            cur.append(tok)
    if cur:
        cmds.append(cur)
    return cmds


def post_kind(words):
    tool, sub = words[0], words[1:3]
    if len(sub) == 2:
        if (
            tool == "glab"
            and sub[0] in ("mr", "issue")
            and sub[1] in ("note", "comment")
        ):
            return "comment"
        if (
            tool == "gh"
            and sub[0] in ("pr", "issue")
            and sub[1] in ("comment", "review")
        ):
            return "comment"
    if tool == "curl" or (tool in ("glab", "gh") and sub[:1] == ["api"]):
        urls = [w for w in words if POST_ENDPOINT.search(w)]
        if urls:
            return "reply" if any(REPLY_ENDPOINT.search(u) for u in urls) else "comment"
    return None


def flag_pairs(words):
    for i, w in enumerate(words[1:], 1):
        if w.startswith("--") and "=" in w:
            yield tuple(w.split("=", 1))
        elif w.startswith("-") and i + 1 < len(words):
            yield w, words[i + 1]


class Bodies:
    def __init__(self, cwd):
        self.cwd, self.env, self.files, self.stdin = cwd, {}, {}, []

    def expand(self, path):
        path = re.sub(
            r"\$\{?(\w+)\}?",
            lambda m: self.env.get(m.group(1), m.group(0)),
            path.strip("'\""),
        )
        return os.path.normpath(os.path.join(self.cwd, os.path.expanduser(path)))

    def read_file(self, path):
        if path == "-":
            return self.stdin[-1] if self.stdin else None
        target = self.expand(path)
        text = next(
            (b for p, b in self.files.items() if self.expand(p) == target), None
        )
        if text is None:
            try:
                text = Path(target).read_text(encoding="utf-8")
            except OSError:
                return None
        if target.endswith(".json"):
            try:
                data = json.loads(text)
            except ValueError:
                return None
            text = next(
                (
                    data[k]
                    for k in ("body", "message", "note")
                    if isinstance(data.get(k), str)
                ),
                None,
            )
        return text

    def literal(self, value):
        m = re.fullmatch(r"\$\(\s*cat\s+(.+?)\s*\)", value.strip())
        if m:
            return self.read_file(m.group(1))
        if "$" in value:
            value = re.sub(
                r"\$\{?(\w+)\}?", lambda m: self.env.get(m.group(1), m.group(0)), value
            )
            return None if "$" in value else value
        return value

    def extract(self, words):
        is_gh_cli = words[0] == "gh" and words[1:2] != ["api"]
        found, missing = [], False
        for flag, val in flag_pairs(words):
            text, hit = None, True
            if flag in ("-m", "--message", "-b", "--body"):
                text = self.literal(val)
            elif flag in ("--body-file", "--input") or (is_gh_cli and flag == "-F"):
                text = self.read_file(val)
            elif flag in ("-f", "-F", "--field", "--raw-field") and val.startswith(
                "body="
            ):
                v = val[5:]
                text = self.read_file(v[1:]) if v.startswith("@") else self.literal(v)
            elif flag in ("-d", "--data", "--data-binary", "--data-raw"):
                if val.startswith("@"):
                    text = self.read_file(val[1:])
                else:
                    try:
                        text = json.loads(val).get("body")
                    except (ValueError, AttributeError):
                        text = None
            else:
                hit = False
            if hit and text is None:
                missing = True
            elif text is not None:
                found.append(text)
        if missing and not found:
            found = self.stdin + [
                b for p, b in self.files.items() if p.endswith((".md", ".txt"))
            ]
            missing = not found
        return found, missing


def bash_posts(cmd, cwd):
    raw = cmd.replace("\\\n", " ")
    bodies = Bodies(cwd)

    def cut(m):
        line_start = raw.rfind("\n", 0, m.start()) + 1
        head = raw[line_start : m.start()] + " " + m.group(3)
        segment = re.split(r"&&|\|\||;|\|", raw[line_start : m.start()])[-1].split()
        while segment and re.match(r"^\w+=", segment[0]):
            segment.pop(0)
        first = segment[0] if segment else ""
        if first not in SCRIPTS:
            target = re.search(r">\s*(\S+)", head)
            if first == "tee" and len(segment) > 1:
                bodies.files[segment[-1]] = m.group(4)
            elif target:
                bodies.files[target.group(1)] = m.group(4)
            elif first in ("glab", "gh", "curl", "cat"):
                bodies.stdin.append(m.group(4))
        return m.group(3)

    stripped = HEREDOC.sub(cut, raw)
    posts, unreadable = [], False
    for words in split_commands(stripped):
        while words and re.match(r"^\w+=", words[0]):
            key, _, val = words.pop(0).partition("=")
            bodies.env[key] = val
        if not words:
            continue
        if words[0] == "export":
            for w in words[1:]:
                key, _, val = w.partition("=")
                bodies.env[key] = val
            continue
        if words[0] == "cd" and len(words) > 1:
            bodies.cwd = bodies.expand(words[1])
            continue
        kind = post_kind(words)
        if not kind:
            continue
        found, missing = bodies.extract(words)
        unreadable = unreadable or missing
        posts += [(kind, b) for b in found]
    return posts, unreadable


def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}))


def main():
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    args = data.get("tool_input") or {}
    if tool == "Bash":
        cmd = args.get("command", "")
        if not PREFILTER.search(cmd) or BYPASS in cmd:
            return
        try:
            posts, unreadable = bash_posts(cmd, data.get("cwd") or os.getcwd())
        except ValueError:
            posts, unreadable = [], bool(RAW_POST.search(cmd))
    elif tool in MCP_BODY:
        key, surface = MCP_BODY[tool]
        posts, unreadable = [(surface, args.get(key) or "")], False
    else:
        return
    if unreadable:
        block(
            "voice gate can't read this post's body (shell variable, script-built JSON, or a file "
            "that doesn't exist). write the body with the Write tool or `cat > FILE <<'EOF'`, then "
            'post with -m "$(cat FILE)", --body-file FILE, --input FILE.json, or -F body=@FILE.'
        )
        return
    problems = [p for surface, body in posts for p in violations(body, surface)]
    if problems:
        block(
            "voice gate: this post doesn't read like Bryan.\n- "
            + "\n- ".join(dict.fromkeys(problems))
            + f"\nrewrite per {VOICE} (read it if not loaded this session) and retry. "
            f"Bryan's own verbatim words only: prefix the Bash command with {BYPASS}. "
            "MCP posts have no bypass: show Bryan the draft and these violations instead."
        )


if __name__ == "__main__":
    main()
