import type { ScheduleDocument, GeneratedGrid } from './schedule/model'

export const API_BASE = import.meta.env.VITE_API_BASE ?? ''

async function readErrorBody(r: Response): Promise<string> {
  const t = await r.text()
  try {
    const j = JSON.parse(t) as { detail?: unknown }
    if (typeof j.detail === 'string') return j.detail
    if (Array.isArray(j.detail)) {
      return j.detail
        .map((x) =>
          typeof x === 'object' && x && 'msg' in x
            ? String((x as { msg: string }).msg)
            : String(x),
        )
        .join('; ')
    }
  } catch {
    /* plain text */
  }
  return t || r.statusText
}

export async function getSchedule(
  shift: number,
  day: 'today' | 'tomorrow',
): Promise<ScheduleDocument> {
  const r = await fetch(`${API_BASE}/api/schedule/${shift}/${day}`)
  if (!r.ok) throw new Error(await readErrorBody(r))
  return r.json() as Promise<ScheduleDocument>
}


export async function putSchedule(
  shift: number,
  day: 'today' | 'tomorrow',
  doc: ScheduleDocument,
): Promise<void> {
  const r = await fetch(`${API_BASE}/api/schedule/${shift}/${day}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(doc),
  })
  if (!r.ok) throw new Error(await readErrorBody(r))
}

export async function generateGrid(params: {
  n_pilots: number
  n_robots: number
  n_tasks: number
  swap_min?: number
  shift_min?: number
  total_hours?: number
}): Promise<GeneratedGrid> {
  const r = await fetch(`${API_BASE}/api/schedule/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!r.ok) throw new Error(await readErrorBody(r))
  return r.json() as Promise<GeneratedGrid>
}
