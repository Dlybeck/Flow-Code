import { useEffect, useRef, useState } from 'react'
import { cancelUrl, goStatusUrl, replyUrl } from './apiConfig'

type WorkPhase = 'investigating' | 'planning' | 'writing' | 'checking' | 'done' | 'error'

type CheckIn = {
  question: string
  options?: string[]
}

export type WorkStatus = {
  phase: WorkPhase
  activity_message: string
  check_in?: CheckIn | null
  plan_text?: string | null
  summary?: string
  note?: string
  changed_node_ids?: string[]
  error?: string
}

export type WorkResult = {
  summary: string
  note?: string
  changed_node_ids: string[]
  session_id: string
}

type WorkingPanelProps = {
  sessionId: string
  briefSummary: string
  nodeLabels: string[]
  onCancel: (prefilledBrief: string) => void
  onDone: (result: WorkResult) => void
  onPhaseChange?: (phase: WorkPhase) => void
}

const PHASE_FALLBACKS: Record<string, string> = {
  investigating: 'Investigating…',
  planning: 'Planning changes…',
  writing: 'Writing changes…',
  checking: 'Running checks…',
  done: 'Done.',
  error: 'Something went wrong.',
}

export function WorkingPanel({
  sessionId,
  briefSummary,
  nodeLabels,
  onCancel,
  onDone,
  onPhaseChange,
}: WorkingPanelProps) {
  const [status, setStatus] = useState<WorkStatus | null>(null)
  const [checkInAnswer, setCheckInAnswer] = useState('')
  const [replying, setReplying] = useState(false)
  const [skipCountdown, setSkipCountdown] = useState<number | null>(null)
  const [planConfirming, setPlanConfirming] = useState(false)
  const [planReviseOpen, setPlanReviseOpen] = useState(false)
  const [planReviseText, setPlanReviseText] = useState('')
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const checkInStartRef = useRef<number | null>(null)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone
  const onPhaseChangeRef = useRef(onPhaseChange)
  onPhaseChangeRef.current = onPhaseChange

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(goStatusUrl(sessionId), { cache: 'no-store' })
        if (!res.ok) return
        const s = (await res.json()) as WorkStatus
        setStatus(s)
        onPhaseChangeRef.current?.(s.phase)
        if (s.phase === 'done' && s.summary) {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
          onDoneRef.current({
            summary: s.summary,
            note: s.note,
            changed_node_ids: s.changed_node_ids ?? [],
            session_id: sessionId,
          })
        }
      } catch {
        // poll failure — wait for next tick
      }
    }

    void poll()
    pollIntervalRef.current = setInterval(() => void poll(), 2500)
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
    }
  }, [sessionId])

  // 30s auto-skip countdown when check-in appears
  useEffect(() => {
    if (!status?.check_in) {
      checkInStartRef.current = null
      setSkipCountdown(null)
      return
    }
    if (checkInStartRef.current === null) {
      checkInStartRef.current = Date.now()
    }
    const elapsed = (Date.now() - checkInStartRef.current) / 1000
    const remaining = Math.max(0, Math.round(30 - elapsed))
    setSkipCountdown(remaining)
    if (remaining <= 0) {
      void handleSkip()
      return
    }
    const t = setTimeout(() => setSkipCountdown((r) => (r !== null ? r - 1 : null)), 1000)
    return () => clearTimeout(t)
  })

  const handleReply = async (answer: string) => {
    setReplying(true)
    try {
      await fetch(replyUrl(sessionId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer }),
      })
      setCheckInAnswer('')
      checkInStartRef.current = null
      setSkipCountdown(null)
    } finally {
      setReplying(false)
    }
  }

  const handleSkip = async () => {
    await handleReply('__skip__')
  }

  const handlePlanConfirm = async () => {
    if (planConfirming) return
    setPlanConfirming(true)
    try {
      await fetch(replyUrl(sessionId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer: '__confirm__' }),
      })
      setPlanReviseOpen(false)
      setPlanReviseText('')
    } finally {
      setPlanConfirming(false)
    }
  }

  const handlePlanRevise = async () => {
    const trimmed = planReviseText.trim()
    if (!trimmed) return
    setPlanConfirming(true)
    try {
      await fetch(replyUrl(sessionId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer: trimmed }),
      })
      setPlanReviseOpen(false)
      setPlanReviseText('')
    } finally {
      setPlanConfirming(false)
    }
  }

  const handleCancel = async () => {
    try {
      await fetch(cancelUrl(sessionId), { method: 'POST' })
    } catch {
      // best-effort
    }
    onCancel(briefSummary)
  }

  const checkIn = status?.check_in
  const activityText =
    status
      ? (status.activity_message || PHASE_FALLBACKS[status.phase] || 'Working…')
      : 'Starting up…'

  return (
    <section className="working-panel">
      <h2>Working on it</h2>

      <div className="working-recap">
        <span className="working-recap-label">You asked:</span>{' '}
        <span className="working-recap-brief">
          {briefSummary.length > 120 ? briefSummary.slice(0, 120) + '…' : briefSummary}
        </span>
        {nodeLabels.length > 0 ? (
          <div className="working-recap-nodes">Around: {nodeLabels.join(', ')}</div>
        ) : null}
      </div>

      {status?.phase === 'planning' ? (
        <div className="plan-card">
          <p className="plan-card-label">Here's the plan — review before executing:</p>
          {status.plan_text ? (
            <pre className="plan-text">{status.plan_text}</pre>
          ) : null}
          <div className="plan-actions">
            <button
              type="button"
              className="plan-confirm-btn"
              onClick={() => void handlePlanConfirm()}
              disabled={planConfirming}
            >
              {planConfirming ? 'Starting…' : 'Looks good — execute →'}
            </button>
            {!planReviseOpen ? (
              <button
                type="button"
                className="plan-revise-btn"
                onClick={() => setPlanReviseOpen(true)}
              >
                Request revision
              </button>
            ) : (
              <div className="plan-revise-form">
                <textarea
                  className="plan-revise-textarea"
                  placeholder="What should change in the plan?"
                  rows={2}
                  value={planReviseText}
                  onChange={(e) => setPlanReviseText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void handlePlanRevise()
                  }}
                />
                <button
                  type="button"
                  className="plan-revise-submit"
                  onClick={() => void handlePlanRevise()}
                  disabled={!planReviseText.trim() || planConfirming}
                >
                  Send revision →
                </button>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="working-activity">
          <span className="working-spinner" aria-hidden />
          <span className="working-activity-text">{activityText}</span>
        </div>
      )}

      {checkIn ? (
        <div className="checkin-card">
          <p className="checkin-label">Quick question</p>
          <p className="checkin-question">{checkIn.question}</p>
          {checkIn.options && checkIn.options.length > 0 ? (
            <div className="checkin-options">
              {checkIn.options.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  className="checkin-option-btn"
                  onClick={() => void handleReply(opt)}
                  disabled={replying}
                >
                  {opt}
                </button>
              ))}
            </div>
          ) : (
            <div className="checkin-input-row">
              <input
                type="text"
                className="checkin-input"
                value={checkInAnswer}
                placeholder="Your reply…"
                onChange={(e) => setCheckInAnswer(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && checkInAnswer.trim()) void handleReply(checkInAnswer)
                }}
              />
              <button
                type="button"
                className="checkin-reply-btn"
                onClick={() => void handleReply(checkInAnswer)}
                disabled={!checkInAnswer.trim() || replying}
              >
                Reply →
              </button>
            </div>
          )}
          <button type="button" className="checkin-skip" onClick={() => void handleSkip()}>
            Skip — use your judgment
            {skipCountdown !== null && skipCountdown > 0 ? ` (auto in ${skipCountdown}s)` : null}
          </button>
        </div>
      ) : null}

      <button type="button" className="working-cancel" onClick={() => void handleCancel()}>
        Cancel
      </button>
    </section>
  )
}
