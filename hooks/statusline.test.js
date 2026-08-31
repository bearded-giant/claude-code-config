const test = require('node:test');
const assert = require('node:assert');
const {
  visLen, clampAnsi, pie, fmtCountdown, fmtDuration,
  fitLine1, fitSolo, packLine2,
} = require('./statusline.js');

const RST = '\x1b[0m';
const GREEN = '\x1b[32m';

const seg = (over = {}) => ({
  acctPart: '[T] ',
  modelPart: 'fable ',
  branchPart: ' | main',
  ctx: ' 72%',
  displayPath: '.../dev/claude-code-config',
  shortPath: 'claude-code-config',
  usage: ['5h 39% ~2h30m', '7d 5% ~6d17h'],
  usageCompact: ['5h 39%', '7d 5%'],
  ...over,
});

test('fitLine1 tier 1: everything fits, nothing spilled', () => {
  const fit = fitLine1(200, seg());
  assert.equal(fit.spilled.length, 0);
  assert.ok(fit.line1.includes('~2h30m'));
  assert.ok(fit.line1.includes('.../dev/'));
});

test('fitLine1 tier 2: drops countdowns before path', () => {
  const s = seg();
  const full = visLen(fitLine1(500, s).line1);
  const fit = fitLine1(full - 2, s);
  assert.ok(!fit.line1.includes('~2h30m'));
  assert.ok(fit.line1.includes('5h 39%'));
  assert.equal(fit.spilled.length, 0);
});

test('fitLine1 spills usage to line2 when path shortening is not enough', () => {
  const fit = fitLine1(38, seg());
  assert.equal(fit.spilled.length, 2);
  assert.ok(!fit.line1.includes('5h'));
  assert.ok(visLen(fit.line1) <= 38);
});

test('fitLine1 always returns a line within width', () => {
  for (const w of [10, 20, 40, 80, 200]) {
    assert.ok(visLen(fitLine1(w, seg()).line1) <= w, `width ${w}`);
  }
});

test('fitSolo keeps spilled usage on the single line', () => {
  const s = seg();
  const fit = fitLine1(38, s);
  const solo = fitSolo(60, s, fit);
  assert.ok(solo.includes('5h'));
  assert.ok(visLen(solo) <= 60);
});

test('packLine2 puts usage first and sheds oldest parts', () => {
  const sep = ' | ';
  const out = packLine2(30, ['5h 39%'], ['aaaaaaaaaa', 'bbbbbbbbbb', 'cccccccccc'], sep);
  assert.ok(out.startsWith('5h 39%'));
  assert.ok(!out.includes('aaaaaaaaaa'));
  assert.ok(visLen(out) <= 30);
});

test('packLine2 empty in, empty out', () => {
  assert.equal(packLine2(80, [], [], ' | '), '');
});

test('visLen ignores SGR escapes', () => {
  assert.equal(visLen(`${GREEN}abc${RST}`), 3);
  assert.equal(visLen('plain'), 5);
});

test('clampAnsi passes through when under width', () => {
  const s = `${GREEN}abc${RST}`;
  assert.equal(clampAnsi(s, 10), s);
  assert.equal(clampAnsi(s, 3), s);
});

test('clampAnsi truncates visible chars, keeps escapes free, appends reset', () => {
  const s = `${GREEN}abcdef${RST}ghij`;
  const out = clampAnsi(s, 4);
  assert.equal(visLen(out), 4);
  assert.ok(out.startsWith(GREEN));
  assert.ok(out.endsWith(RST));
  assert.equal(out, `${GREEN}abcd${RST}`);
});

test('clampAnsi handles escape at cut point', () => {
  const s = `ab${GREEN}cd${RST}`;
  assert.equal(visLen(clampAnsi(s, 2)), 2);
  assert.equal(visLen(clampAnsi(s, 3)), 3);
});

test('clampAnsi never wraps: long unstyled line', () => {
  assert.equal(visLen(clampAnsi('x'.repeat(500), 80)), 80);
});

test('fmtCountdown returns empty on unparseable resets_at', () => {
  assert.equal(fmtCountdown('not-a-date', 1000), '');
  assert.equal(fmtCountdown(undefined, 1000), '');
});

test('fmtCountdown formats hours and days', () => {
  assert.equal(fmtCountdown(1000 + 3600 * 2 + 60 * 5, 1000), ' ~2h05m');
  assert.equal(fmtCountdown(1000 + 3600 * 26, 1000), ' ~1d2h');
});

test('pie buckets', () => {
  assert.equal(pie(0), '○');
  assert.equal(pie(50), '◑');
  assert.equal(pie(100), '●');
});

test('fmtDuration', () => {
  assert.equal(fmtDuration(59 * 1000), '59s');
  assert.equal(fmtDuration(61 * 60 * 1000), '1h01m');
});
