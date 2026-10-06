export const meta = {
  name: 'swarm-exec',
  description: 'Execution swarm: parse plan into work units, parallel implementers per dependency group, validator runs tests, bounded fix loop, optional artifacts',
  whenToUse: 'Invoked by /swarm-exec after the session created a work branch. Writes code; never commits.',
  phases: [
    { title: 'Parse', detail: 'plan -> work units + dependency groups' },
    { title: 'Implement', detail: 'parallel workers per group' },
    { title: 'Validate', detail: 'review diff; targeted tests after fixes, full suite once' },
    { title: 'Fix', detail: 'one agent per fix, sequential' },
  ],
}

// args: { plan, runDir, artifacts, timestamp, testCmd?, maxFixRounds? }
const ART = args.artifacts !== false
const RUN_DIR = args.runDir
const MAX_FIX = args.maxFixRounds || 2

const PLAN_SCHEMA = {
  type: 'object',
  required: ['goal', 'work_units', 'groups'],
  properties: {
    goal: { type: 'string' },
    test_cmd: { type: 'string' },
    work_units: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'title', 'files', 'instructions'],
        properties: {
          id: { type: 'string' },
          title: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } },
          instructions: { type: 'string' },
        },
      },
    },
    groups: {
      type: 'array',
      description: 'ordered dependency groups; each group is a list of work_unit ids that can run in parallel (no shared files)',
      items: { type: 'array', items: { type: 'string' } },
    },
  },
}

const WORKER_SCHEMA = {
  type: 'object',
  required: ['unit', 'status', 'files_changed', 'summary'],
  properties: {
    unit: { type: 'string' },
    status: { enum: ['complete', 'partial', 'blocked'] },
    files_changed: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string', description: 'max 2 sentences' },
    concerns: { type: 'array', items: { type: 'string' } },
  },
}

const VALIDATOR_SCHEMA = {
  type: 'object',
  required: ['verdict', 'tests_passed', 'summary', 'issues'],
  properties: {
    verdict: { enum: ['pass', 'partial', 'fail'] },
    tests_passed: { type: 'boolean' },
    test_output_summary: { type: 'string' },
    summary: { type: 'string' },
    issues: { type: 'array', items: { type: 'string' } },
    fix_units: {
      type: 'array',
      description: 'exactly one fix per unit',
      items: {
        type: 'object',
        required: ['id', 'title', 'files', 'instructions', 'tests'],
        properties: {
          id: { type: 'string' },
          title: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } },
          instructions: { type: 'string' },
          tests: { type: 'array', items: { type: 'string' }, description: 'test ids that prove this fix (path::name or -k expr)' },
        },
      },
    },
  },
}

function artifactSuffix(file) {
  if (!ART) return ''
  return `\n\nAFTER composing your JSON report, use the Write tool to save it verbatim to ${RUN_DIR}/${file} (pretty-printed). Then return the same JSON as your structured output.`
}

const GIT_RULES = 'HARD RULES: never git commit, never git push, never git merge, never amend, never touch files outside your assigned unit.'
const WORK_RULES = 'Files over ~500 lines: grep, then Read with offset/limit, never the whole file. Run only the tests you add or touch (path::name or -k), never the full file or suite.'

const brief = rs => rs.map(r =>
  `${r.unit} | ${r.status} | ${r.files_changed.join(', ')} | ${r.summary}${r.concerns?.length ? ` | concerns: ${r.concerns.join('; ')}` : ''}`
).join('\n')

phase('Parse')
const plan = await agent(
  `Parse this plan into independent work units and ordered dependency groups. If the plan is a file path, Read it (and sibling facts.md / spec.md if it lives in a .giantmem feature dir). Ground every file path against the real tree with Glob before emitting it. Units in the same group MUST NOT share files.\n\n## Plan\n${args.plan}` +
  artifactSuffix('plan.json'),
  { label: 'parse-plan', phase: 'Parse', schema: PLAN_SCHEMA, effort: 'low' }
)
if (!plan) return { verdict: 'fail', error: 'plan parsing failed' }
const unitById = Object.fromEntries(plan.work_units.map(u => [u.id, u]))
log(`${plan.work_units.length} units in ${plan.groups.length} groups`)

function worker(u, tag, phaseName) {
  const tests = u.tests?.length ? `\nTests for this unit: ${u.tests.join(' ')}` : ''
  return agent(
    `You are a swarm implementation worker.\n\n## Goal\n${plan.goal}\n\n## Your unit: ${u.title}\nFiles: ${u.files.join(', ')}${tests}\n\n${u.instructions}\n\n${GIT_RULES}\n${WORK_RULES}\nImplement fully. Match surrounding code style. Run relevant quick checks (lint/typecheck) if cheap.` +
    artifactSuffix(`worker-${tag}-${u.id}.json`),
    { label: `${phaseName === 'Fix' ? 'fix' : 'impl'}:${u.id}`, phase: phaseName, schema: WORKER_SCHEMA }
  )
}

async function implement(units, tag) {
  return (await parallel(units.map(u => () => worker(u, tag, 'Implement')))).filter(Boolean)
}

// fixes usually share files, so always sequential; parallelize disjoint fixes if fix loops get slow
async function fixSequential(units, tag) {
  const out = []
  for (const u of units) {
    const r = await worker(u, tag, 'Fix')
    if (r) out.push(r)
  }
  return out
}

phase('Implement')
const reports = []
for (let g = 0; g < plan.groups.length; g++) {
  const units = plan.groups[g].map(id => unitById[id]).filter(Boolean)
  reports.push(...await implement(units, `g${g + 1}`))
}

const FULL_TESTS = args.testCmd || plan.test_cmd || 'the project test command (detect it)'

phase('Validate')
let round = 0
let runs = 0
let verdict = null
let fixReports = []
let targeted = null
while (true) {
  runs++
  const testStep = targeted
    ? `Run ONLY these tests, not the full file or suite: ${targeted.join(' ')}`
    : `Run the full tests once: ${FULL_TESTS}`
  verdict = await agent(
    `You are the swarm validator.\n\n## Goal\n${plan.goal}\n\n## Worker reports (unit | status | files | summary)\n${brief(reports.concat(fixReports))}\n\n## Tasks\n1. Review the actual diff (git diff) against the goal.\n2. ${testStep}\n3. verdict pass = those tests green AND changes match goal. If fixable problems remain and this is fix round ${round} of ${MAX_FIX}, emit fix_units: one fix per unit, each naming the tests that prove it.\n${GIT_RULES}\n${WORK_RULES}` +
    artifactSuffix(`validator-${runs}.json`),
    { label: `validator-${runs}${targeted ? '-targeted' : ''}`, phase: 'Validate', schema: VALIDATOR_SCHEMA }
  )
  if (!verdict) break
  if (verdict.verdict === 'pass') {
    if (!targeted) break
    targeted = null
    continue
  }
  if (!verdict.fix_units?.length || round === MAX_FIX) break
  round++
  log(`round ${round}: ${verdict.fix_units.length} fixes, sequential`)
  fixReports.push(...await fixSequential(verdict.fix_units, `fix${round}`))
  targeted = verdict.fix_units.flatMap(u => u.tests || [])
  if (!targeted.length) targeted = null
}

return {
  verdict: verdict ? verdict.verdict : 'fail',
  tests_passed: verdict ? verdict.tests_passed : false,
  summary: verdict ? verdict.summary : 'validator failed',
  issues: verdict ? verdict.issues : [],
  units: plan.work_units.length,
  fix_rounds: round,
  files_changed: [...new Set(reports.concat(fixReports).flatMap(r => r.files_changed))],
  artifacts: ART ? RUN_DIR : null,
}
