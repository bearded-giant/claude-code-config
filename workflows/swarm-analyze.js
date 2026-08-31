export const meta = {
  name: 'swarm-analyze',
  description: 'Aspect-parallel analysis swarm: workers per aspect, validator synthesis, converge loop, optional on-disk artifacts',
  whenToUse: 'Invoked by /swarm. Multi-aspect analysis or review of code/architecture with reviewable per-agent artifacts.',
  phases: [
    { title: 'Derive', detail: 'derive aspects for custom tasks' },
    { title: 'Analyze', detail: 'one worker per aspect' },
    { title: 'Validate', detail: 'synthesize, check convergence' },
  ],
}

// args: { task, kind: 'review'|'analysis'|'custom', runDir, artifacts, timestamp,
//         aspects?, context?, maxIterations? }
const ART = args.artifacts !== false
const RUN_DIR = args.runDir
const MAX_ITER = args.maxIterations || 3

const ASPECT_SETS = {
  analysis: [
    { name: 'technical', focus: 'implementation quality, patterns, idioms, code structure' },
    { name: 'dependencies', focus: 'coupling, imports, external services, blast radius of change' },
    { name: 'dataflow', focus: 'how data moves: inputs, transformations, persistence, outputs' },
    { name: 'risks', focus: 'failure modes, edge cases, error handling, concurrency hazards' },
    { name: 'performance', focus: 'hot paths, N+1s, allocation, caching, scaling limits' },
    { name: 'maintainability', focus: 'readability, test coverage, docs drift, change cost' },
  ],
  review: [
    { name: 'requirements', focus: 'does the code satisfy the stated spec/acceptance criteria' },
    { name: 'technical_accuracy', focus: 'correctness of logic, types, boundaries, return values' },
    { name: 'security', focus: 'authz, input validation, injection, secrets, tenant isolation' },
    { name: 'consistency', focus: 'matches surrounding codebase conventions and patterns' },
    { name: 'completeness', focus: 'missing cases, missing tests, unfinished paths, TODOs' },
    { name: 'best_practices', focus: 'idiomatic usage, error handling, resource lifecycle' },
  ],
}

const WORKER_SCHEMA = {
  type: 'object',
  required: ['aspect', 'verdict', 'confidence', 'score', 'key_findings', 'evidence', 'issues'],
  properties: {
    aspect: { type: 'string' },
    verdict: { enum: ['good', 'acceptable', 'concerning', 'poor'] },
    confidence: { type: 'number' },
    score: { type: 'integer', minimum: 1, maximum: 10 },
    key_findings: { type: 'array', items: { type: 'string' } },
    evidence: { type: 'array', items: { type: 'string' }, description: 'file:line citations' },
    issues: {
      type: 'array',
      items: {
        type: 'object',
        required: ['severity', 'description'],
        properties: {
          severity: { enum: ['critical', 'major', 'minor'] },
          description: { type: 'string' },
          location: { type: 'string' },
        },
      },
    },
  },
}

const VALIDATOR_SCHEMA = {
  type: 'object',
  required: ['overall_verdict', 'confidence', 'summary', 'aspect_summaries', 'all_issues', 'converged', 'recommendations'],
  properties: {
    overall_verdict: { enum: ['pass', 'partial', 'fail'] },
    confidence: { type: 'number' },
    summary: { type: 'string' },
    aspect_summaries: { type: 'array', items: { type: 'string' } },
    all_issues: { type: 'array', items: { type: 'string' } },
    conflicts_resolved: { type: 'array', items: { type: 'string' } },
    converged: { type: 'boolean' },
    blocking: { type: 'array', items: { type: 'string' }, description: 'aspect names needing another pass' },
    recommendations: { type: 'array', items: { type: 'string' } },
  },
}

const ASPECTS_SCHEMA = {
  type: 'object',
  required: ['aspects'],
  properties: {
    aspects: {
      type: 'array',
      minItems: 3,
      maxItems: 8,
      items: {
        type: 'object',
        required: ['name', 'focus'],
        properties: { name: { type: 'string' }, focus: { type: 'string' } },
      },
    },
  },
}

function artifactSuffix(file) {
  if (!ART) return ''
  return `\n\nAFTER composing your JSON report, use the Write tool to save it verbatim to ${RUN_DIR}/${file} (pretty-printed). Then return the same JSON as your structured output. The file is the durable record; do not skip it.`
}

let aspects = args.aspects || ASPECT_SETS[args.kind]
if (!aspects) {
  phase('Derive')
  const derived = await agent(
    `Task: ${args.task}\n\nDerive 3-6 orthogonal analysis aspects for this task (for a comparison, make each aspect a comparison dimension). Each aspect gets a short snake_case name and a one-line focus statement.`,
    { label: 'derive-aspects', schema: ASPECTS_SCHEMA, effort: 'low' }
  )
  aspects = derived ? derived.aspects : ASPECT_SETS.analysis
}

let feedback = ''
let synthesis = null
let iteration = 0
let workers = []

while (iteration < MAX_ITER) {
  iteration++
  const round = iteration === 1 ? aspects : aspects.filter(a => (synthesis.blocking || []).includes(a.name))
  if (!round.length) break

  phase('Analyze')
  const results = (await parallel(round.map(a => () => agent(
    `You are a swarm worker analyzing ONE aspect: ${a.name}\n\n` +
    `## Focus\n${a.focus}\n\n## Task\n${args.task}\n` +
    (args.context ? `\n## Context\n${args.context}\n` : '') +
    (feedback ? `\n## Validator feedback from prior round\n${feedback}\n` : '') +
    `\n## Instructions\nUse Read/Glob/Grep to examine the actual code. Every finding needs file:line evidence. No time/effort estimates, no complexity ratings — findings, evidence, issues, recommendations only.` +
    artifactSuffix(`worker-${a.name}${iteration > 1 ? `-r${iteration}` : ''}.json`),
    { label: `worker:${a.name}`, phase: 'Analyze', schema: WORKER_SCHEMA }
  )))).filter(Boolean)
  workers = workers.filter(w => !results.some(r => r.aspect === w.aspect)).concat(results)

  phase('Validate')
  synthesis = await agent(
    `You are the swarm validator. Synthesize these worker reports (iteration ${iteration} of max ${MAX_ITER}).\n\n` +
    `## Worker reports\n${JSON.stringify(workers, null, 2)}\n\n` +
    `## Tasks\n1. Aggregate findings by aspect. 2. Resolve conflicts between workers. 3. Decide converged: true unless a specific aspect has contradictory or clearly incomplete coverage that another focused pass would fix — if so, converged: false and list those aspect names in blocking.` +
    artifactSuffix(`validator-${iteration}.json`),
    { label: `validator-${iteration}`, phase: 'Validate', schema: VALIDATOR_SCHEMA, effort: 'high' }
  )
  if (!synthesis || synthesis.converged) break
  feedback = `Blocking: ${(synthesis.blocking || []).join(', ')}. Issues so far: ${(synthesis.all_issues || []).join('; ')}`
  log(`not converged after iteration ${iteration}; re-running: ${(synthesis.blocking || []).join(', ')}`)
}

return { synthesis, workers, iterations: iteration, aspects: aspects.map(a => a.name), artifacts: ART ? RUN_DIR : null }
