"""Record what the user's logged-in Chrome shows while one page action runs.

Attaches over CDP (no password, no browser download), logs fetch calls and SSE chunk arrival from
inside the page, polls the DOM, screencasts the tab to frames, assembles turn.mp4 + sheet.png, and
prints a verdict. Driven by a JSON profile (see ../profiles) plus CLI overrides.
"""
import argparse, base64, json, os, re, shutil, subprocess, sys, time
from playwright.sync_api import sync_playwright

INIT_TEMPLATE = r"""
(() => {
  const LOG_RE = new RegExp(%(log_re)s);
  const TEE_RE = new RegExp(%(tee_re)s);
  const orig = window.fetch;
  window.fetch = async function(input, init) {
    const url = typeof input === 'string' ? input : input.url;
    const res = await orig.apply(this, arguments);
    if (!LOG_RE.test(url)) return res;
    console.log('[net] ' + Date.now() + ' ' + res.status + ' ' + url);
    if (!TEE_RE.test(url) || !res.body) return res;
    const [a, b] = res.body.tee();
    (async () => {
      const r = b.getReader(); const dec = new TextDecoder(); let n = 0;
      for (;;) { const {value, done} = await r.read(); if (done) break; n++;
        const evs = (dec.decode(value, {stream: true}).match(/event: (\w+)/g) || []).join(',');
        console.log('[sse-chunk] ' + Date.now() + ' n=' + n + ' bytes=' + value.length + ' ' + evs); }
      console.log('[sse-end] ' + Date.now() + ' chunks=' + n);
    })();
    return new Response(a, {status: res.status, statusText: res.statusText, headers: res.headers});
  };
})();
"""

SNAPSHOT_JS = """(args) => {
  const body = document.body.innerText;
  const i = args.marker ? body.lastIndexOf(args.marker) : -1;
  const panel = i >= 0 ? body.slice(i, i + 3000) : '';
  const waiting = (args.waiting || []).filter(w => body.includes(w));
  const sent = args.sent || '';
  const j = sent ? body.lastIndexOf(sent) : -1;
  const k = args.composer ? body.indexOf(args.composer, j) : -1;
  const tail = j >= 0 ? body.slice(j + sent.length, k > 0 ? k : j + 1200).trim() : '';
  return {panel_rows: panel ? panel.split('\\n').filter(Boolean).length : 0, waiting, tail};
}"""


def load_profile(path):
    with open(path) as fh:
        prof = json.load(fh)
    prof['_dir'] = os.path.dirname(os.path.abspath(path))
    return prof


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--profile', required=True, help='JSON profile (see profiles/)')
    ap.add_argument('--out', required=True, help='output dir (created)')
    ap.add_argument('--url', help='override profile url')
    ap.add_argument('--message', help='override action.message')
    ap.add_argument('--cdp', help='override cdp endpoint')
    ap.add_argument('--max-seconds', type=int)
    ap.add_argument('--no-video', action='store_true', help='skip the screencast: verdict + logs only')
    ap.add_argument('--no-maximize', action='store_true')
    a = ap.parse_args()

    p = load_profile(a.profile)
    cdp = a.cdp or p.get('cdp', 'http://localhost:9222')
    action = p.get('action', {})
    message = a.message or action.get('message', '')
    max_seconds = a.max_seconds or p.get('max_seconds', 90)
    tail_seconds = p.get('tail_seconds', 8)
    done_event = p.get('done_event', 'message')
    watch = p.get('watch', {})
    os.makedirs(f'{a.out}/frames', exist_ok=True)
    ffmpeg = shutil.which('ffmpeg')

    init_js = INIT_TEMPLATE % {
        'log_re': json.dumps(p.get('log_url_regex', '/stream|/token|event-stream')),
        'tee_re': json.dumps(p.get('tee_url_regex', '/stream')),
    }

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        page.add_init_script(init_js)
        logs = []
        page.on('console', lambda m: logs.append((time.time(), m.type, m.text)))
        page.on('pageerror', lambda e: logs.append((time.time(), 'pageerror', str(e))))
        cdp_session = ctx.new_cdp_session(page)
        if p.get('maximize', True) and not a.no_maximize:
            win = cdp_session.send('Browser.getWindowForTarget')
            cdp_session.send('Browser.setWindowBounds', {'windowId': win['windowId'], 'bounds': {'windowState': 'maximized'}})
        page.bring_to_front()

        url = a.url or p['url']
        pre = p.get('pre')
        if pre:
            page.goto(pre.get('url', url).format(**{}), wait_until='networkidle')
            js = open(os.path.join(p['_dir'], pre['js'])).read()
            result = page.evaluate(js)
            if not isinstance(result, dict) or result.get('error'):
                raise SystemExit(f'pre step failed: {result}')
            url = url.format(**result)
        page.goto(url, wait_until='networkidle')

        composer = action.get('fill_placeholder')
        box = page.get_by_placeholder(composer) if composer else None
        if box is not None:
            box.wait_for(timeout=20000)
        if p.get('scroll_top', True):
            page.evaluate('window.scrollTo(0,0)')

        frames = []; pending = []
        if not a.no_video:
            cdp_session.on('Page.screencastFrame', lambda prm: (frames.append((time.time(), prm['data'])), pending.append(prm['sessionId'])))
            cdp_session.send('Page.startScreencast', {'format': 'jpeg', 'quality': 75, 'maxWidth': 2000, 'maxHeight': 1300, 'everyNthFrame': 1})
            time.sleep(0.8)

        if box is not None and message:
            box.fill(message)
        t0 = time.time()
        submit = action.get('submit', 'enter')
        if box is not None and submit == 'enter':
            box.press('Enter')
        elif submit.startswith('click:'):
            page.click(submit[6:])

        snap_args = {'marker': watch.get('panel_marker'), 'waiting': watch.get('waiting_phrases', []), 'sent': message, 'composer': composer}
        timeline = []; last = None; done_at = None
        while time.time() - t0 < max_seconds:
            while pending:
                cdp_session.send('Page.screencastFrameAck', {'sessionId': pending.pop(0)})
            if p.get('scroll_top', True):
                page.evaluate('window.scrollTo(0,0)')
            snap = page.evaluate(SNAPSHOT_JS, snap_args)
            key = (snap['panel_rows'], tuple(snap['waiting']), snap['tail'][:120])
            if key != last:
                timeline.append((round(time.time() - t0, 2), snap)); last = key
            if done_at is None and any(t.startswith('[sse-chunk]') and done_event in t for _, _, t in logs):
                done_at = time.time()
            if done_at and time.time() - done_at > tail_seconds:
                break
            time.sleep(0.15)
        if not a.no_video:
            cdp_session.send('Page.stopScreencast')
            time.sleep(0.3)
            while pending:
                cdp_session.send('Page.screencastFrameAck', {'sessionId': pending.pop(0)})

        with open(f'{a.out}/console.log', 'w') as fh:
            for ts, typ, text in logs:
                fh.write(f'{ts - t0:8.2f} {typ} {text[:400]}\n')
        json.dump({'url': url, 'message': message, 'timeline': timeline}, open(f'{a.out}/timeline.json', 'w'), indent=1)

        video = None
        if frames:
            for i, (ts, data) in enumerate(frames):
                open(f'{a.out}/frames/f{i:05d}.jpg', 'wb').write(base64.b64decode(data))
            with open(f'{a.out}/list.txt', 'w') as fh:
                for i, (ts, _) in enumerate(frames):
                    nxt = frames[i + 1][0] if i + 1 < len(frames) else ts + 1.0
                    fh.write(f"file 'frames/f{i:05d}.jpg'\nduration {max(nxt - ts, 0.02):.3f}\n")
                fh.write(f"file 'frames/f{len(frames) - 1:05d}.jpg'\n")
            if ffmpeg:
                mp4 = f'{a.out}/turn.mp4'
                r = subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', f'{a.out}/list.txt',
                                    '-fps_mode', 'vfr', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-pix_fmt', 'yuv420p', mp4],
                                   capture_output=True, text=True)
                video = mp4 if r.returncode == 0 else None
                if video:
                    subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-i', mp4, '-vf', 'fps=1,scale=480:-1,tile=4x3', '-frames:v', '1', f'{a.out}/sheet.png'])

        def first(pred):
            return next((round(ts - t0, 1) for ts, _, t in logs if pred(t)), None)
        fa = first(lambda t: t.startswith('[sse-chunk]') and 'activity' in t)
        fd = first(lambda t: t.startswith('[sse-chunk]') and 'delta' in t)
        fm = first(lambda t: t.startswith('[sse-chunk]') and done_event in t)
        end = fm if fm is not None else 1e9
        base_rows = timeline[0][1]['panel_rows'] if timeline else None
        fp = next((t for t, s in timeline[1:] if s['panel_rows'] != base_rows), None)
        phrases = watch.get('waiting_phrases', [])
        def is_text(tail):
            tail = tail.strip()
            return bool(tail) and not any(tail.startswith(w) or tail.endswith(w) for w in phrases)
        ft = next((t for t, s in timeline[1:] if is_text(s['tail']) and t < end + 0.5), None)
        panel_live = fa is not None and fp is not None and fp < end
        text_live = fd is not None and ft is not None
        errs = [t for _, typ, t in logs if typ in ('error', 'pageerror') and 'React error' not in t]
        lines = [
            f'url: {url}',
            f'frames in browser: activity {fa}s, delta {fd}s, {done_event} {fm}s',
            f'render: panel first changed at {fp}s, provisional text at {ft}s',
            f'live activity panel: {"yes" if panel_live else "no"}; live provisional text: {"yes" if text_live else "no"}',
            f'STREAMING LIVE: {"yes" if (panel_live or text_live) else "NO"}',
            'panel rows over time (s:rows): ' + ' '.join(f'{t}:{s["panel_rows"]}' for t, s in timeline),
            f'video: {video or "none (" + ("no ffmpeg on PATH" if not ffmpeg else "no frames" if not frames else "ffmpeg failed") + ")"}',
            f'frames: {len(frames)}  console errors: {" | ".join(e[:80] for e in errs) if errs else "none"}',
            f'out: {a.out}',
        ]
        open(f'{a.out}/summary.txt', 'w').write('\n'.join(lines) + '\n')
        print('\n'.join(lines))
        # tab stays open so the user can look at the end state


if __name__ == '__main__':
    main()
