export const meta = {
  name: 'swarm-exec',
  description: 'Execution swarm: parse plan into work units, parallel implementers per dependency group, validator runs tests, bounded fix loop, optional artifacts',
  whenToUse: 'Invoked by /swarm-exec after the session created a work branch. Writes code; never commits.',
  phases: [
    { title: 'Parse', detail: 'plan -> work units + dependency groups' },
    { title: 'Implement', detail: 'parallel workers per group' },
    { title: 'Validate', detail: 'review diff, run tests, fix loop' },
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
    summary: { type: 'string' },
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
  },
}

function artifactSuffix(file) {
  if (!ART) return ''
  return `\n\nAFTER composing your JSON report, use the Write tool to save it verbatim to ${RUN_DIR}/${file} (pretty-printed). Then return the same JSON as your structured output.`
}

const GIT_RULES = 'HARD RULES: never git commit, never git push, never git merge, never amend, never touch files outside your assigned unit.'

phase('Parse')
const plan = await agent(
  `Parse this plan into independent work units and ordered dependency groups. If the plan is a file path, Read it (and sibling facts.md / spec.md if it lives in a .giantmem feature dir). Ground every file path against the real tree with Glob before emitting it. Units in the same group MUST NOT share files.\n\n## Plan\n${args.plan}` +
  artifactSuffix('plan.json'),
  { label: 'parse-plan', phase: 'Parse', schema: PLAN_SCHEMA }
)
if (!plan) return { verdict: 'fail', error: 'plan parsing failed' }
const unitById = Object.fromEntries(plan.work_units.map(u => [u.id, u]))
log(`${plan.work_units.length} units in ${plan.groups.length} groups`)

async function implement(units, tag) {
  return (await parallel(units.map(u => () => agent(
    `You are a swarm implementation worker.\n\n## Goal\n${plan.goal}\n\n## Your unit: ${u.title}\nFiles: ${u.files.join(', ')}\n\n${u.instructions}\n\n${GIT_RULES}\nImplement fully. Match surrounding code style. Run relevant quick checks (lint/typecheck) if cheap.` +
    artifactSuffix(`worker-${tag}-${u.id}.json`),
    { label: `impl:${u.id}`, phase: 'Implement', schema: WORKER_SCHEMA }
  )))).filter(Boolean)
}

phase('Implement')
const reports = []
for (let g = 0; g < plan.groups.length; g++) {
  const units = plan.groups[g].map(id => unitById[id]).filter(Boolean)
  reports.push(...await implement(units, `g${g + 1}`))
}

phase('Validate')
let round = 0
let verdict = null
let fixReports = []
while (round <= MAX_FIX) {
  verdict = await agent(
    `You are the swarm validator.\n\n## Goal\n${plan.goal}\n\n## Worker reports\n${JSON.stringify(reports.concat(fixReports), null, 2)}\n\n## Tasks\n1. Review the actual diff (git diff) against the goal.\n2. Run tests: ${args.testCmd || plan.test_cmd || 'detect the project test command and run the relevant subset'}.\n3. verdict pass = tests green AND changes match goal. If fixable problems remain and this is round ${round} of ${MAX_FIX}, emit fix_units (non-overlapping files).\n${GIT_RULES}` +
    artifactSuffix(`validator-${round + 1}.json`),
    { label: `validator-${round + 1}`, phase: 'Validate', schema: VALIDATOR_SCHEMA, effort: 'high' }
  )
  if (!verdict || verdict.verdict === 'pass' || !verdict.fix_units || !verdict.fix_units.length || round === MAX_FIX) break
  round++
  log(`round ${round}: ${verdict.fix_units.length} fix units`)
  fixReports.push(...await implement(verdict.fix_units, `fix${round}`))
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
