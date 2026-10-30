#!/usr/bin/env python3
import argparse
import base64
import html
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

VAULT = Path.home() / "Recharge-Notes"
TEMPLATE = Path(__file__).resolve().parent.parent / "doc-template" / "template.html"
# licensed face: read from the recharge-auth checkout, never copied into this (public) repo
FONT = Path(os.environ.get(
    "ARTIFACT_DISPLAY_FONT",
    Path.home() / "dev/python/recharge-auth-wt/main/app/static/fonts/mackinac-book.woff2",
))
IMG_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\.png\)$", re.M)
NUM_RE = re.compile(r"^([0-9]+|[A-Z])\.\s+(.*)$", re.S)


def body_of(note: Path) -> str:
    text = note.read_text()
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    return re.split(r"\n## Artifact revisions\b", text)[0].strip() + "\n"


def slug(text: str) -> str:
    text = re.sub(r"^([0-9]+|[A-Z])\.\s+", "", html.unescape(re.sub(r"<[^>]+>", "", text)))
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def font_face() -> str:
    if not FONT.exists():
        print(f"warn: {FONT} missing, headings fall back to Georgia", file=sys.stderr)
        return ""
    data = base64.b64encode(FONT.read_bytes()).decode()
    return ('@font-face {\n  font-family: "Mackinac Pro";\n  font-weight: 350;\n  font-style: normal;\n'
            f'  font-display: swap;\n  src: url(data:font/woff2;base64,{data}) format("woff2");\n}}\n')


def build_html(note: Path, out: Path, args) -> None:
    body = body_of(note)
    h1 = re.search(r"^# (.+)$", body, re.M)
    if not h1:
        sys.exit(f"{note}: no H1")
    title = h1.group(1).strip()
    body = body.replace(h1.group(0) + "\n", "", 1)
    for old, new in args.replace:
        if old not in body:
            sys.exit(f"--replace text not in note: {old!r}")
        body = body.replace(old, new)

    diagrams = []

    def stash(m):
        mmd = note.parent / f"{m.group(2)}.mmd"
        if not mmd.exists():
            sys.exit(f"{mmd} missing: artifacts cannot load local images, give each diagram a sibling .mmd")
        diagrams.append((m.group(1), mmd.read_text()))
        return f"MERMAIDSLOT{len(diagrams) - 1}"

    body = IMG_RE.sub(stash, body)
    frag = subprocess.run(["pandoc", "-f", "gfm", "-t", "html5", "--wrap=none"], input=body, text=True,
                          capture_output=True, check=True).stdout
    for i, (alt, src) in enumerate(diagrams):
        frag = frag.replace(
            f"<p>MERMAIDSLOT{i}</p>",
            f'<figure class="diagram" aria-label="{html.escape(alt)}">'
            f'<pre class="mermaid">{html.escape(src.strip())}</pre></figure>',
        )

    toc = []

    def h2(m):
        inner = m.group(2)
        hid = slug(inner)
        num = NUM_RE.match(inner)
        toc.append((hid, num.group(1) if num else "", num.group(2) if num else inner))
        if num:
            inner = f'<span class="h2-num">{num.group(1)}</span><span>{num.group(2)}</span>'
        return f'<h2 id="{hid}">{inner}</h2>'

    frag = re.sub(r'<h2 id="([^"]*)">(.*?)</h2>', h2, frag, flags=re.S)
    frag = frag.replace("<p>This section is for", '<p class="audience">This section is for')
    frag = frag.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    if args.companion_url:
        frag = frag.replace(f"<strong>{args.companion_name}</strong>",
                            f'<a href="{args.companion_url}"><strong>{args.companion_name}</strong></a>')

    src_note = args.source_note or note
    try:
        source = str(src_note.resolve().relative_to(VAULT))
    except ValueError:
        source = src_note.name
    stamp = f"Rev {args.rev} · {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}"
    page = TEMPLATE.read_text()
    for key, val in {
        "{{DOCTITLE}}": args.doc_title or title, "{{TITLE}}": title, "{{EYEBROW}}": args.eyebrow,
        "{{STAMP}}": stamp, "{{SOURCE}}": source, "{{COMPANION_URL}}": args.companion_url or "",
        "{{COMPANION_NAME}}": args.companion_name or "", "{{FONT_FACE}}": font_face(),
        "{{TOC}}": "\n".join(f'<li><a href="#{h}"><span class="toc-num">{n}</span>{t}</a></li>' for h, n, t in toc),
        "{{BODY}}": frag,
    }.items():
        page = page.replace(key, val)
    if not args.companion_url:
        page = re.sub(r'\s*<a class="companion"[^>]*>[^<]*</a>', "", page)
    if not args.eyebrow:
        page = re.sub(r'\s*<p class="eyebrow"></p>', "", page)
    out.write_text(page)
    print(f"{out}  {stamp}  toc={len(toc)} diagrams={len(diagrams)}")


# Spark roles for the Google Docs import; Mackinac isn't a Google font, so Georgia stands in for display
DOCX_RPR = {
    "Heading1": '<w:rFonts w:ascii="Georgia" w:hAnsi="Georgia" /><w:color w:val="0129F1" /><w:sz w:val="52" /><w:szCs w:val="52" />',
    "Heading2": '<w:rFonts w:ascii="Georgia" w:hAnsi="Georgia" /><w:color w:val="0129F1" /><w:sz w:val="34" /><w:szCs w:val="34" />',
    "Heading3": '<w:rFonts w:ascii="Inter" w:hAnsi="Inter" /><w:b /><w:color w:val="006D58" /><w:sz w:val="26" /><w:szCs w:val="26" />',
    "VerbatimChar": '<w:rFonts w:ascii="Inconsolata" w:hAnsi="Inconsolata" /><w:color w:val="006D58" /><w:shd w:val="clear" w:color="auto" w:fill="E3F1EE" /><w:sz w:val="22" />',
    "Hyperlink": '<w:color w:val="0129F1" /><w:u w:val="single" />',
}
TBL_BORDERS = "<w:tblBorders>" + "".join(
    f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="D8D4D1"/>'
    for side in ("top", "left", "bottom", "right", "insideH", "insideV")
) + "</w:tblBorders>"
LABEL_RUN = '<w:r><w:rPr><w:b /><w:color w:val="0000BB" /></w:rPr><w:t'


def house_reference(tmp: Path) -> Path:
    base, ref = tmp / "ref.docx", tmp / "ref-house.docx"
    subprocess.run(["pandoc", "-o", str(base), "--print-default-data-file", "reference.docx"], check=True)
    with zipfile.ZipFile(base) as src, zipfile.ZipFile(ref, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "word/styles.xml":
                s = data.decode()
                cut = s.index('<w:tblInd w:w="0" w:type="dxa" />', s.index('w:styleId="Table"'))
                s = s[:cut] + TBL_BORDERS + s[cut:]
                s = re.sub(r"(<w:rPrDefault>\s*<w:rPr>).*?(</w:rPr>)",
                           r'\1<w:rFonts w:ascii="Inter" w:hAnsi="Inter" w:eastAsia="Inter" w:cs="Inter" />'
                           r'<w:color w:val="262626" /><w:sz w:val="22" /><w:szCs w:val="22" />\2', s, count=1, flags=re.S)
                for sid, rpr in DOCX_RPR.items():
                    s, n = re.subn(rf'(<w:style [^>]*w:styleId="{sid}".*?<w:rPr>).*?(</w:rPr>)',
                                   lambda m: m.group(1) + rpr + m.group(2), s, count=1, flags=re.S)
                    assert n == 1, sid
                data = s.encode()
            dst.writestr(item, data)
    return ref


def style_tables(docx: Path) -> None:
    def row(m):
        tr = m.group(0)
        if "<w:tblHeader" in tr:
            tr = tr.replace("<w:tcPr />", '<w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="CFDCF9" /></w:tcPr>')
            return tr.replace("<w:r><w:t", LABEL_RUN)
        first, rest = tr.split("</w:tc>", 1)
        return first.replace("<w:r><w:t", LABEL_RUN) + "</w:tc>" + rest

    tmp = docx.with_suffix(".tmp.docx")
    with zipfile.ZipFile(docx) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "word/document.xml":
                xml = data.decode().replace("<w:tblLook", TBL_BORDERS + "<w:tblLook")
                data = re.sub(r"<w:tr>.*?</w:tr>", row, xml, flags=re.S).encode()
            dst.writestr(item, data)
    tmp.replace(docx)


def build_docx(note: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["pandoc", "-f", "gfm", "-o", str(out), "--reference-doc", str(house_reference(Path(tmp))),
             "--resource-path", str(note.parent)],
            input=body_of(note), text=True, check=True,
        )
    style_tables(out)
    print(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="Render a vault note into the TOC doc artifact template, and optionally a Google Docs-ready .docx.")
    ap.add_argument("note", type=Path)
    ap.add_argument("--out", type=Path, help="artifact HTML path")
    ap.add_argument("--rev", default="1")
    ap.add_argument("--source-note", type=Path,
                    help="vault note for the source-note meta when the input is a distilled copy")
    ap.add_argument("--doc-title", help="<title> name when the H1 carries a subtitle")
    ap.add_argument("--eyebrow", default="")
    ap.add_argument("--companion-url")
    ap.add_argument("--companion-name", help="bold text in the note to link, and the header link label")
    ap.add_argument("--replace", nargs=2, action="append", default=[], metavar=("OLD", "NEW"),
                    help="artifact-only text swap, e.g. a dated line the note keeps")
    ap.add_argument("--docx", type=Path, help="also write a .docx with diagrams embedded")
    args = ap.parse_args()
    if not args.out and not args.docx:
        ap.error("give --out, --docx, or both")
    if bool(args.companion_url) != bool(args.companion_name):
        ap.error("--companion-url and --companion-name go together")
    if args.out:
        build_html(args.note, args.out, args)
    if args.docx:
        build_docx(args.note, args.docx)


if __name__ == "__main__":
    main()
