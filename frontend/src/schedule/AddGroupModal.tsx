import { useEffect, useMemo, useState } from 'react'
import { generateGrid } from '../scheduleApi'
import type { ScheduleDocument, ScheduleGroup } from './model'
import {
  TIME_OPTIONS_15,
  applyGeneratedGrid,
  emptyGrid,
  newId,
  pilotColorForIndex,
  validateGroupCounts,
} from './model'
import './schedule.css'

function parseLines(text: string): string[] {
  return text
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

// How often pilots rotate seats, in minutes. Each must be a multiple of the
// 15-min grid slot (the backend rejects others).
const SWAP_OPTIONS = [15, 30, 45, 60] as const

type Props = {
  doc: ScheduleDocument
  open: boolean
  onClose: () => void
  onCreate: (g: ScheduleGroup) => void
  editGroup?: ScheduleGroup | null
  onUpdate?: (g: ScheduleGroup) => void
}

export default function AddGroupModal({
  doc,
  open,
  onClose,
  onCreate,
  editGroup,
  onUpdate,
}: Props) {
  const isEdit = !!editGroup

  const [name, setName] = useState('New group')
  const [robots, setRobots] = useState('Robot A\nRobot B')
  const [tasks, setTasks] = useState('Break')
  const [pilots, setPilots] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const [useGenerate, setUseGenerate] = useState(false)
  const [tplStartTime, setTplStartTime] = useState(doc.day_start)
  const [swapMin, setSwapMin] = useState(45)
  const [totalHours, setTotalHours] = useState(9)

  useEffect(() => {
    setTplStartTime(doc.day_start)
  }, [doc.day_start])

  useEffect(() => {
    if (!editGroup) return
    setName(editGroup.name)
    setRobots(editGroup.robot_labels.join('\n'))
    setTasks(editGroup.task_labels.join('\n'))
    setPilots(editGroup.pilots.map((p) => p.name).join('\n'))
    setUseGenerate(false)
    setErr(null)
  }, [editGroup])

  const counts = useMemo(() => {
    const r = parseLines(robots).length
    const t = parseLines(tasks).length
    const p = parseLines(pilots).length
    return { robots: r, tasks: t, pilots: p }
  }, [robots, tasks, pilots])

  const countsValid = counts.pilots >= 2 && counts.robots >= 1 && counts.tasks >= 1 && counts.pilots === counts.robots + counts.tasks
  // Need at least 4 pilots per 3 robots so everyone gets enough off-seat rest.
  const ratioOk = counts.robots > 0 && counts.pilots / counts.robots >= 4 / 3
  // Display-only guess at which algorithm the backend will pick (it uses the
  // same pilots-divisible-by-robots test in generate_schedule_grid).
  const isBlockRotation = counts.robots > 0 && counts.pilots % counts.robots === 0

  function resetForm() {
    setName('New group')
    setRobots('Robot A\nRobot B')
    setTasks('Break')
    setPilots('')
    setErr(null)
    setUseGenerate(false)
    setTplStartTime(doc.day_start)
    setSwapMin(45)
    setTotalHours(9)
  }

  if (!open) return null

  async function submit() {
    setErr(null)
    const robot_labels = parseLines(robots)
    const task_labels = parseLines(tasks)
    const pilotNames = parseLines(pilots)
    const g: ScheduleGroup = {
      id: isEdit ? editGroup.id : newId(),
      name: name.trim() || 'Untitled group',
      robot_labels,
      task_labels,
      pilots: pilotNames.map((n, i) => ({
        id: isEdit && i < editGroup.pilots.length ? editGroup.pilots[i].id : newId(),
        name: n,
        color_hex: pilotColorForIndex(i),
      })),
      grid: [],
    }
    const v = validateGroupCounts(g)
    if (v) {
      setErr(v)
      return
    }

    if (useGenerate) {
      setSubmitting(true)
      try {
        const gen = await generateGrid({
          n_pilots: g.pilots.length,
          n_robots: robot_labels.length,
          n_tasks: task_labels.length,
          swap_min: swapMin,
          shift_min: 60,
          total_hours: totalHours,
        })
        g.grid = applyGeneratedGrid(gen, g.pilots, doc.day_start, doc.day_end, tplStartTime)
      } catch (e) {
        setErr(`Generation failed: ${e instanceof Error ? e.message : e}`)
        setSubmitting(false)
        return
      }
      setSubmitting(false)
    } else if (isEdit && !useGenerate) {
      g.grid = editGroup.grid
    } else {
      g.grid = emptyGrid(doc.day_start, doc.day_end, robot_labels.length + task_labels.length)
    }

    if (isEdit && onUpdate) {
      onUpdate(g)
    } else {
      onCreate(g)
    }
    onClose()
    resetForm()
  }

  return (
    <div className="sched-modal-overlay" role="dialog" aria-modal>
      <div className="sched-modal">
        <h3>{isEdit ? 'Edit group' : 'Add group'}</h3>
        <p className="sched-modal-hint">
          One entry per line (or comma-separated). Robots + tasks must equal
          number of pilots.
        </p>
        <label>
          Group name
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="sched-input"
          />
        </label>
        <label>
          Robot rows
          <textarea
            value={robots}
            onChange={(e) => setRobots(e.target.value)}
            rows={4}
            className="sched-textarea"
          />
        </label>
        <label>
          Task rows (Break, Monitor, …)
          <textarea
            value={tasks}
            onChange={(e) => setTasks(e.target.value)}
            rows={3}
            className="sched-textarea"
          />
        </label>
        <div className="sched-pilots-section">
          <div className="sched-pilots-toggle">
            <span className="sched-pilots-label">Pilots</span>
          </div>
          <label>
            Names (one per line or comma-separated)
            <textarea
              value={pilots}
              onChange={(e) => setPilots(e.target.value)}
              rows={4}
              className="sched-textarea"
              placeholder={'Ava Patel\nBen Carter\nChloe Kim'}
            />
          </label>
        </div>

        <div className="sched-generate-section">
          <label className="sched-checkbox-row">
            <input
              type="checkbox"
              checked={useGenerate}
              onChange={(e) => setUseGenerate(e.target.checked)}
            />
            Auto-generate rotation schedule
          </label>

          {useGenerate && (
            <div className="sched-generate-opts">
              {!countsValid ? (
                <p className="sched-muted">
                  Robots ({counts.robots}) + Tasks ({counts.tasks}) must equal
                  Pilots ({counts.pilots}) to generate.
                </p>
              ) : !ratioOk ? (
                <p className="sched-error">
                  Pilot/robot ratio ({(counts.pilots / counts.robots).toFixed(2)}) is
                  below 1.33 — operators would get insufficient rest.
                </p>
              ) : (
                <>
                  <p className="sched-muted" style={{ marginBottom: '0.5rem' }}>
                    Algorithm: <strong>{isBlockRotation ? 'Block Rotation' : 'Cascade'}</strong>
                    {' '}({counts.pilots}P-{counts.robots}R-{counts.tasks}T)
                  </p>
                  <label className="sched-time-label">
                    Swap duration
                    <select
                      className="sched-select"
                      value={swapMin}
                      onChange={(e) => setSwapMin(Number(e.target.value))}
                    >
                      {SWAP_OPTIONS.map((m) => (
                        <option key={m} value={m}>{m} min</option>
                      ))}
                    </select>
                  </label>
                  <label className="sched-time-label">
                    Schedule duration
                    <select
                      className="sched-select"
                      value={totalHours}
                      onChange={(e) => setTotalHours(Number(e.target.value))}
                    >
                      {[4, 5, 6, 7, 8, 9, 10, 11, 12].map((h) => (
                        <option key={h} value={h}>{h} hours</option>
                      ))}
                    </select>
                  </label>
                  <label className="sched-time-label">
                    Schedule starts at
                    <select
                      value={tplStartTime}
                      onChange={(e) => setTplStartTime(e.target.value)}
                      className="sched-time-input"
                    >
                      {TIME_OPTIONS_15.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </label>
                  <p className="sched-muted">
                    Slots outside the schedule window ({doc.day_start}–
                    {doc.day_end}) are clipped.
                  </p>
                </>
              )}
            </div>
          )}
        </div>

        {err ? <p className="sched-error">{err}</p> : null}
        <div className="sched-modal-actions">
          <button type="button" onClick={() => { onClose(); resetForm() }} disabled={submitting}>
            Cancel
          </button>
          <button
            type="button"
            className="sched-primary"
            onClick={submit}
            disabled={submitting}
          >
            {submitting ? 'Loading…' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  )
}
