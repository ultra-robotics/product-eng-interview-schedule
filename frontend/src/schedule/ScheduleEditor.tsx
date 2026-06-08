import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getSchedule, putSchedule } from '../scheduleApi'
import { useEditMode } from '../EditModeContext'
import type { ScheduleDocument, ScheduleGroup } from './model'
import {
  DEFAULT_DAY_END,
  DEFAULT_DAY_START,
  SCHEDULE_VERSION,
  TIME_OPTIONS_15,
  resizeGrid,
  timeSlotCount,
} from './model'
import AddGroupModal from './AddGroupModal'
import GroupBlock from './GroupBlock'
import PilotViewPanel from './PilotViewPanel'
import './schedule.css'

type Brush = { pilotId: string | null; eraser: boolean }
type TabId = 'robot' | 'pilots' | `pilot:${string}`

export default function ScheduleEditor() {
  const { shift: shiftStr, day: dayStr } = useParams<{
    shift: string
    day: string
  }>()
  const shift = Number(shiftStr)
  const day = dayStr === 'tomorrow' ? 'tomorrow' : 'today'
  const navigate = useNavigate()
  const { isEditMode } = useEditMode()

  const [doc, setDoc] = useState<ScheduleDocument | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [saveState, setSaveState] = useState<
    'idle' | 'saving' | 'saved' | 'error'
  >('idle')
  const [modalOpen, setModalOpen] = useState(false)
  const [editingGroup, setEditingGroup] = useState<ScheduleGroup | null>(null)
  const [brushes, setBrushes] = useState<Record<string, Brush>>({})
  const [activeTab, setActiveTab] = useState<TabId>('robot')

  useEffect(() => {
    if (shiftStr !== '1' && shiftStr !== '2' && shiftStr !== '3') {
      setErr('Invalid shift')
      return
    }
    if (day !== 'today' && day !== 'tomorrow') {
      setErr('Invalid day')
      return
    }
    setErr(null)
    getSchedule(shift, day)
      .then((d) => {
        setErr(null)
        setDoc({
          ...d,
          version: d.version ?? SCHEDULE_VERSION,
        })
      })
      .catch((e: Error) => setErr(e.message))
  }, [shift, day, shiftStr, dayStr])

  const persist = useCallback(
    (snapshot: ScheduleDocument) => {
      setSaveState('saving')
      putSchedule(shift, day, snapshot)
        .then(() => {
          setSaveState('saved')
          window.setTimeout(() => setSaveState('idle'), 2000)
        })
        .catch(() => setSaveState('error'))
    },
    [shift, day],
  )

  const updateGroup = useCallback(
    (id: string, g: ScheduleGroup) => {
      if (!doc) return
      const next = {
        ...doc,
        groups: doc.groups.map((x) => (x.id === id ? g : x)),
      }
      setDoc(next)
      if (isEditMode) window.setTimeout(() => persist(next), 1000)
    },
    [isEditMode, persist],
  )

  const removeGroup = useCallback(
    (id: string) => {
      if (!doc) return
      const next = { ...doc, groups: doc.groups.filter((x) => x.id !== id) }
      setDoc(next)
      setBrushes((b) => {
        const nb = { ...b }
        delete nb[id]
        return nb
      })
      setActiveTab((prev) => {
        if (prev === 'robot' || prev === 'pilots') return prev
        if (prev.startsWith('pilot:') && prev.includes(id)) return 'robot'
        return prev
      })
      if (isEditMode) window.setTimeout(() => persist(next), 1000)
    },
    [isEditMode, persist],
  )

  const addGroup = useCallback(
    (g: ScheduleGroup) => {
      if (!doc) return
      const next = { ...doc, groups: [...doc.groups, g] }
      setDoc(next)
      if (isEditMode) window.setTimeout(() => persist(next), 1000)
    },
    [isEditMode, persist],
  )

  const handleTimeChange = useCallback(
    (field: 'day_start' | 'day_end', value: string) => {
      if (!doc) return
      const newStart = field === 'day_start' ? value : doc.day_start
      const newEnd = field === 'day_end' ? value : doc.day_end
      try {
        timeSlotCount(newStart, newEnd)
      } catch {
        return
      }
      const groups = doc.groups.map((g) => {
        const nRows = g.robot_labels.length + g.task_labels.length
        if (nRows === 0) return g
        return {
          ...g,
          grid: resizeGrid(
            g.grid,
            doc.day_start,
            doc.day_end,
            newStart,
            newEnd,
            nRows,
          ),
        }
      })
      const next = { ...doc, day_start: newStart, day_end: newEnd, groups }
      setDoc(next)
      if (isEditMode) window.setTimeout(() => persist(next), 1000)
    },
    [isEditMode, persist],
  )

  const copyToTomorrow = useCallback(async () => {
    if (!doc) return
    if (!confirm(`Copy today's Shift ${shift} schedule to tomorrow?`)) return
    try {
      await putSchedule(shift, 'tomorrow', { ...doc, slot_key: `s${shift}-tomorrow` })
      navigate(`/schedule/shift/${shift}/tomorrow`)
    } catch (e) {
      alert(`Failed to copy: ${e instanceof Error ? e.message : e}`)
    }
  }, [shift, navigate])

  const promoteTomorrow = useCallback(async () => {
    if (!doc) return
    if (
      !confirm(
        'Copy this schedule to Today and clear Tomorrow for Shift ' +
          shift +
          '?',
      )
    )
      return
    try {
      await putSchedule(shift, 'today', { ...doc, slot_key: `s${shift}-today` })
      const emptyDoc: ScheduleDocument = {
        version: SCHEDULE_VERSION,
        slot_key: '',
        day_start: DEFAULT_DAY_START,
        day_end: DEFAULT_DAY_END,
        groups: [],
      }
      await putSchedule(shift, 'tomorrow', emptyDoc)
      navigate(`/schedule/shift/${shift}/today`)
    } catch (e) {
      alert(`Failed to promote: ${e instanceof Error ? e.message : e}`)
    }
  }, [shift, navigate])

  const pilotTabs = useMemo(() => {
    if (!doc) return []
    const tabs: { key: string; label: string }[] = []
    for (const g of doc.groups) {
      for (const p of g.pilots) {
        tabs.push({
          key: `${g.id}:${p.id}`,
          label: doc.groups.length > 1 ? `${p.name} (${g.name})` : p.name,
        })
      }
    }
    return tabs
  }, [])

  if (err && !doc) {
    return (
      <div className="sched-page">
        <Link to="/schedule">← Home</Link>
        <p className="sched-error">{err}</p>
      </div>
    )
  }

  if (!doc) {
    return (
      <div className="sched-page">
        <Link to="/schedule">← Home</Link>
        <p>Loading…</p>
      </div>
    )
  }

  return (
    <div className="sched-page sched-editor">
      <header className="sched-editor-head">
        <Link to="/schedule" className="sched-home-link">
          ← Home
        </Link>
        <h1>
          Shift {shift} — {day === 'today' ? 'Today' : 'Tomorrow'}
        </h1>
        <div className="sched-time-controls">
          <label className="sched-time-label">
            Start
            <select
              value={doc.day_start}
              onChange={(e) => handleTimeChange('day_start', e.target.value)}
              className="sched-time-input"
              disabled={!isEditMode}
            >
              {TIME_OPTIONS_15.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
          <label className="sched-time-label">
            End
            <select
              value={doc.day_end}
              onChange={(e) => handleTimeChange('day_end', e.target.value)}
              className="sched-time-input"
              disabled={!isEditMode}
            >
              {TIME_OPTIONS_15.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
        </div>
        <span className="sched-save">
          {saveState === 'saving' && 'Saving…'}
          {saveState === 'saved' && 'Saved'}
          {saveState === 'error' && 'Save failed'}
        </span>
        {day === 'today' && isEditMode && (
          <button
            type="button"
            className="sched-promote-btn"
            onClick={copyToTomorrow}
          >
            Copy to Tomorrow →
          </button>
        )}
        {day === 'tomorrow' && isEditMode && (
          <button
            type="button"
            className="sched-promote-btn"
            onClick={promoteTomorrow}
          >
            Make this Today →
          </button>
        )}
      </header>

      <nav className="sched-tabs">
        <button
          type="button"
          className={activeTab === 'robot' ? 'sched-tab active' : 'sched-tab'}
          onClick={() => setActiveTab('robot')}
        >
          Robot View
        </button>
        <button
          type="button"
          className={
            activeTab === 'pilots' ? 'sched-tab active' : 'sched-tab'
          }
          onClick={() => setActiveTab('pilots')}
        >
          All Pilots
        </button>
        {pilotTabs.map((pt) => (
          <button
            key={pt.key}
            type="button"
            className={
              activeTab === `pilot:${pt.key}`
                ? 'sched-tab active'
                : 'sched-tab'
            }
            onClick={() => setActiveTab(`pilot:${pt.key}`)}
          >
            {pt.label}
          </button>
        ))}
      </nav>

      <div className="sched-tab-body">
        {activeTab === 'robot' && (
          <section className="sched-section sched-robot-section">
            {isEditMode && (
              <button
                type="button"
                className="sched-primary"
                onClick={() => setModalOpen(true)}
              >
                Add group
              </button>
            )}
            {doc.groups.map((g) => (
              <GroupBlock
                key={g.id}
                dayStart={doc.day_start}
                dayEnd={doc.day_end}
                group={g}
                activePilotId={brushes[g.id]?.pilotId ?? null}
                eraser={brushes[g.id]?.eraser ?? false}
                editable={isEditMode}
                onChange={(ng) => updateGroup(g.id, ng)}
                onDelete={() => removeGroup(g.id)}
                onCopy={addGroup}
                onEdit={() => { setEditingGroup(g); setModalOpen(true) }}
                onPickPilot={(id) =>
                  setBrushes((s) => ({
                    ...s,
                    [g.id]: { pilotId: id, eraser: false },
                  }))
                }
                onPickEraser={() =>
                  setBrushes((s) => ({
                    ...s,
                    [g.id]: { pilotId: null, eraser: true },
                  }))
                }
              />
            ))}
          </section>
        )}

        {activeTab === 'pilots' && (
          <section className="sched-section">
            <PilotViewPanel doc={doc} />
          </section>
        )}

        {activeTab.startsWith('pilot:') && (
          <section className="sched-section">
            <PilotViewPanel doc={doc} filterKey={activeTab.slice(6)} />
          </section>
        )}
      </div>

      <AddGroupModal
        doc={doc}
        open={modalOpen}
        onClose={() => { setModalOpen(false); setEditingGroup(null) }}
        onCreate={addGroup}
        editGroup={editingGroup}
        onUpdate={(g) => { updateGroup(g.id, g); setEditingGroup(null) }}
      />
    </div>
  )
}
