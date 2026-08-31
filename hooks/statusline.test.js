const test = require('node:test');
const assert = require('node:assert');
const { visLen, clampAnsi, pie, fmtCountdown, fmtDuration } = require('./statusline.js');

const RST = '\x1b[0m';
const GREEN = '\x1b[32m';

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
