export function decisionOf(job) {
  if (job?.decision && typeof job.decision === 'object') return job.decision
  try { return JSON.parse(job?.decision_json || '{}') } catch { return {} }
}

export function featuresOf(job) {
  if (job?.features && typeof job.features === 'object') return job.features
  try { return JSON.parse(job?.features_json || '{}') } catch { return {} }
}

export function statusMeta(s) {
  return ({
    awaiting_decision: { t: '待盖章', k: 'warn' },
    awaiting_manual: { t: '待回填', k: 'warn' },
    awaiting_approval: { t: '待确认花费', k: 'warn' },
    running: { t: '处理中', k: 'muted' },
    interrupted: { t: '已中断', k: 'muted' },
    rejected: { t: '已拒绝', k: 'bad' },
    done: { t: '已完成', k: 'ok' },
  })[s] || { t: s || '—', k: 'muted' }
}

export function budgetPct(job) {
  const b = Number(job?.budget_usd || decisionOf(job).budget_usd || 5) || 5
  const s = Number(job?.spent_usd || 0)
  return Math.max(0, Math.min(100, Math.round((s / b) * 100)))
}
