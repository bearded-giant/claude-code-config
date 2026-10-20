const test = require('node:test');
const assert = require('node:assert');
const {
  visLen, clampAnsi, pie, fmtCountdown, fmtDuration,
  fitLine1, fitSolo, packLine2, charWidth, fmtPreflight, fmtMr,
  matchOrg, pinAccount, badgeFor, DEFAULT_BADGES, pickOrgs,
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

test('charWidth: columns, not code units', () => {
  assert.equal(charWidth(0x61), 1);           // a
  assert.equal(charWidth(0x6a5f), 2);         // CJK
  assert.equal(charWidth(0x1f680), 2);        // rocket
  assert.equal(charWidth(0x0301), 0);         // combining acute
  assert.equal(charWidth(0x200d), 0);         // ZWJ
  assert.equal(charWidth(0x2502), 1);         // ambiguous stays narrow
});

test('visLen counts display columns', () => {
  assert.equal(visLen('hello'), 5);
  assert.equal(visLen('\u6a5f\u80fd'), 4);       // 2 CJK = 4 columns
  assert.equal(visLen('e\u0301clair'), 6);       // combining mark is free
  assert.equal(visLen('a\u200db'), 2);           // ZWJ is free
  assert.equal(visLen(`${GREEN}\u{1F680}${RST}`), 2);
});

test('clampAnsi never splits a surrogate pair', () => {
  const s = 'ab\u{1F680}cd';
  for (let max = 1; max <= 6; max++) {
    const out = clampAnsi(s, max).replace(/\x1b\[[0-9;]*m/g, '');
    const lone = /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/;
    assert.ok(!lone.test(out), `lone surrogate at max=${max}`);
    assert.ok(visLen(out) <= max, `over budget at max=${max}`);
  }
});

test('clampAnsi budgets wide chars by column', () => {
  // a 2-column glyph is dropped rather than half-drawn
  assert.equal(visLen(clampAnsi('ab\u{1F680}cd', 3)), 2);
  assert.equal(visLen(clampAnsi('\u6a5f\u80fd\u6a5f', 4)), 4);
});

test('fit ladder holds with wide characters in the path', () => {
  const wide = seg({ displayPath: '.../dev/\u6a5f\u80fd\u30d6\u30e9\u30f3\u30c1', shortPath: '\u6a5f\u80fd' });
  for (const w of [200, 120, 100, 80, 60, 40, 20]) {
    assert.ok(visLen(fitLine1(w, wide).line1) <= w, `width ${w}`);
  }
});

test('fmtPreflight: silent when every check is ok or cache missing', () => {
  assert.equal(fmtPreflight(null), '');
  assert.equal(fmtPreflight({ gcloud: { ok: true }, glab: { ok: true } }), '');
});

test('fmtPreflight: expired is red x, unreachable is dim ~, ok is hidden', () => {
  const out = fmtPreflight({ gcloud: { ok: false }, glab: { ok: true }, vault: { ok: null } });
  assert.ok(out.includes('✗gcloud'));
  assert.ok(out.includes('~vault'));
  assert.ok(!out.includes('glab'));
  assert.equal(visLen(out), visLen('✗gcloud ~vault'));
});

test('fmtMr: renders iid + tag, empty when no MR', () => {
  assert.equal(fmtMr(null), '');
  assert.equal(fmtMr({}), '');
  const out = fmtMr({ iid: 1234, tag: 'GREEN', level: 'ok' });
  assert.ok(out.startsWith(GREEN));
  assert.ok(out.includes('!1234 GREEN'));
});

const ORGS = [
  { id: 'inc-uuid', label: 'rc-inc', spend_cap: { used_pct: 34, limit: 300000 } },
  {
    id: 'team-uuid',
    label: 'rc-team',
    five_hour: { used_pct: 98, resets_at: '2026-10-20T15:59:59.951319+00:00' },
    seven_day: { used_pct: 36, resets_at: '2026-10-25T17:59:59.951342+00:00' },
  },
];
const TEAM_LIMITS = {
  five_hour: { used_percentage: 98, resets_at: Date.parse('2026-10-20T16:00:00Z') / 1000 },
  seven_day: { used_percentage: 36, resets_at: Date.parse('2026-10-25T18:00:00Z') / 1000 },
};

test('matchOrg: session rate limits pick the org with matching reset times', () => {
  assert.equal(matchOrg(TEAM_LIMITS, ORGS).label, 'rc-team');
});

test('matchOrg: no windows, no match, or ambiguous match returns null', () => {
  assert.equal(matchOrg(undefined, ORGS), null);
  assert.equal(matchOrg({ spend_limit: { used_percentage: 3 } }, ORGS), null);
  const off = { five_hour: { resets_at: TEAM_LIMITS.five_hour.resets_at + 3600 } };
  assert.equal(matchOrg(off, ORGS), null);
  const twin = { ...ORGS[1], label: 'other' };
  assert.equal(matchOrg({ five_hour: TEAM_LIMITS.five_hour }, [...ORGS, twin]), null);
});

test('matchOrg: one disagreeing window rules the org out', () => {
  const mixed = { ...TEAM_LIMITS, seven_day: { resets_at: TEAM_LIMITS.seven_day.resets_at + 86400 } };
  assert.equal(matchOrg(mixed, ORGS), null);
});

const TEAM = { name: 'recharge, team', type: 'claude_team', uuid: 'team-uuid' };
const INC = { name: 'recharge, inc.', type: 'claude_enterprise', uuid: 'inc-uuid' };

test('pinAccount: first tick pins the global account', () => {
  const state = {};
  assert.equal(pinAccount(state, TEAM, 100, 1000), true);
  assert.deepEqual(state.acctPin.account, TEAM);
});

test('pinAccount: another session switching accounts does not move the pin', () => {
  const state = {};
  pinAccount(state, TEAM, 100, 1000);
  assert.equal(pinAccount(state, INC, 100, 2000), false);
  assert.deepEqual(state.acctPin.account, TEAM);
});

test('pinAccount: a new claude process re-pins', () => {
  const state = {};
  pinAccount(state, TEAM, 100, 1000);
  assert.equal(pinAccount(state, INC, 200, 2000), true);
  assert.deepEqual(state.acctPin.account, INC);
});

test('pinAccount: own /login follows the global account once it changes', () => {
  const state = {};
  pinAccount(state, TEAM, 100, Date.parse('2026-10-20T10:00:00Z'));
  state.loginAt = '2026-10-20T11:00:00Z';
  const t = Date.parse(state.loginAt);
  // login still in flight: global not written yet
  assert.equal(pinAccount(state, TEAM, 100, t + 5000), false);
  assert.equal(pinAccount(state, INC, 100, t + 30000), true);
  assert.deepEqual(state.acctPin.account, INC);
  // settled: a later switch elsewhere does not move it
  assert.equal(pinAccount(state, TEAM, 100, t + 60000), false);
  assert.deepEqual(state.acctPin.account, INC);
});

test('pinAccount: /login back into the same account settles after the follow window', () => {
  const state = {};
  pinAccount(state, TEAM, 100, Date.parse('2026-10-20T10:00:00Z'));
  state.loginAt = '2026-10-20T11:00:00Z';
  const t = Date.parse(state.loginAt);
  assert.equal(pinAccount(state, TEAM, 100, t + 11 * 60000), true);
  assert.equal(pinAccount(state, INC, 100, t + 12 * 60000), false);
  assert.deepEqual(state.acctPin.account, TEAM);
});

test('badgeFor: oauth accounts and usage labels map to the same badges', () => {
  const label = b => badgeFor(b, DEFAULT_BADGES).replace(/\x1b\[[0-9;]*m/g, '');
  assert.equal(label(TEAM), '[T]');
  assert.equal(label(INC), '[E]');
  assert.equal(label({ name: 'rc-team', type: '' }), '[T]');
  assert.equal(label({ name: 'rc-inc', type: '' }), '[E]');
  assert.equal(label({ name: 'skio', type: '' }), '[S]');
  assert.equal(label({ name: 'max', type: '' }), '');
  assert.equal(label(null), '');
});

test('pinAccount: legacy pin without uuid borrows it only from the same account', () => {
  const legacy = () => ({ acctPin: { ppid: 100, at: 1000, account: { name: INC.name, type: INC.type } } });
  const same = legacy();
  assert.equal(pinAccount(same, INC, 100, 2000), true);
  assert.equal(same.acctPin.account.uuid, 'inc-uuid');
  const other = legacy();
  assert.equal(pinAccount(other, TEAM, 100, 2000), false);
  assert.equal(other.acctPin.account.uuid, undefined);
});

test('pickOrgs: known session org shows only that org, ignoring the switch filter', () => {
  assert.deepEqual(pickOrgs(ORGS, 'inc-uuid', ['rc-team']).map(o => o.label), ['rc-inc']);
  assert.deepEqual(pickOrgs(ORGS, 'team-uuid', ['rc-inc']).map(o => o.label), ['rc-team']);
});

test('pickOrgs: known org missing from the cache shows nothing, not another account', () => {
  assert.deepEqual(pickOrgs(ORGS, 'skio-uuid', ['rc-team']), []);
});

test('pickOrgs: unknown session org falls back to the switch filter', () => {
  assert.deepEqual(pickOrgs(ORGS, '', ['rc-team']).map(o => o.label), ['rc-team']);
  assert.deepEqual(pickOrgs(ORGS, '', null).map(o => o.label), ['rc-inc', 'rc-team']);
});
