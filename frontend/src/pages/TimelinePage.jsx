import React, { useEffect, useState, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api.js'
import { t, localName } from '../i18n.js'

const SCENE_COLORS = {
  school: '#4f8cff',
  social: '#38c7a4',
  shadow_edu: '#f5a623',
  self_study: '#a06bff',
  home: '#ef5b6b',
  parent: '#ef5b6b',
  fragment: '#8fa0bd',
}

const SCENE_KEYS = Object.keys(SCENE_COLORS)

function minToHHMM(min) {
  const h = Math.floor(min / 60)
  const m = Math.round(min % 60)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

export default function TimelinePage() {
  const { id } = useParams()
  const [students, setStudents] = useState([])
  const [sid, setSid] = useState('')
  const [timeline, setTimeline] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .listStudents(id, 1, 100)
      .then((r) => {
        setStudents(r.students)
        if (r.students.length) setSid(r.students[0].student_id)
      })
      .catch((e) => setError(e.message))
  }, [id])

  useEffect(() => {
    if (!sid) return
    let cancelled = false
    setLoading(true)
    api
      .getTimeline(id, sid)
      .then((t) => !cancelled && setTimeline(t))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [id, sid])

  // Build Gantt bars + cumulative fatigue curve
  const { bars, fatiguePath, fatiguePoints } = useMemo(() => {
    if (!timeline) return { bars: [], fatiguePath: '', fatiguePoints: [] }
    const events = timeline.events
    const W = 900
    const H = 220
    const x0 = 60
    const xScale = (min) => x0 + (min / 1440) * (W - x0 - 20)

    // Each event becomes a bar spanning [t, t+duration). Estimate duration as gap to next.
    const bars = events.map((e, i) => {
      const next = events[i + 1]
      const dur = next ? Math.max(5, next.timestamp_min - e.timestamp_min) : 30
      return { ...e, dur }
    })

    // Cumulative fatigue curve
    let fatigue = 50
    const pts = events.map((e) => {
      fatigue = Math.min(100, Math.max(0, fatigue + e.fatigue_change))
      return { min: e.timestamp_min, fatigue }
    })
    const yScale = (f) => H - 30 - (f / 100) * (H - 60)
    const path = pts
      .map((p, i) => `${i === 0 ? 'M' : 'L'}${xScale(p.min).toFixed(1)},${yScale(p.fatigue).toFixed(1)}`)
      .join(' ')

    return { bars, fatiguePath: path, fatiguePoints: pts, xScale, W, H }
  }, [timeline])

  const { xScale, W, H, x0 } = useMemo(() => {
    const W = 900
    const H = 220
    const x0 = 60
    return { xScale: (min) => x0 + (min / 1440) * (W - x0 - 20), W, H, x0 }
  }, [])

  return (
    <div>
      <div className="page-header">
        <h2>L-Model 时间轴</h2>
        <p>单学生 24h 事件流甘特图（五场景着色）· 疲劳曲线叠加</p>
      </div>

      <div className="card">
        <div className="field" style={{ maxWidth: 320 }}>
          <label>选择学生</label>
          <select value={sid} onChange={(e) => setSid(e.target.value)}>
            {students.map((s) => (
              <option key={s.student_id} value={s.student_id}>
                {s.student_id} · {localName(s.name)}
              </option>
            ))}
          </select>
        </div>

        {error && <div className="error-box">{error}</div>}
        {loading && <div className="loading">加载中…</div>}

        {timeline && !loading && (
          <>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
              {SCENE_KEYS.map((k) => (
                <span key={k} className="badge" style={{ borderColor: SCENE_COLORS[k], color: SCENE_COLORS[k] }}>
                  ■ {t('scene', k)}
                </span>
              ))}
            </div>

            <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ background: '#141b2b', borderRadius: 8 }}>
              {/* hour gridlines */}
              {[0, 4, 8, 12, 16, 20, 24].map((h) => (
                <g key={h}>
                  <line x1={xScale(h * 60)} y1={20} x2={xScale(h * 60)} y2={H - 30} stroke="#2c3a55" strokeWidth="1" />
                  <text x={xScale(h * 60)} y={H - 12} fill="#8fa0bd" fontSize="10" textAnchor="middle">
                    {String(h).padStart(2, '0')}:00
                  </text>
                </g>
              ))}

              {/* event bars (single lane) */}
              {bars.map((b, i) => (
                <rect
                  key={i}
                  x={xScale(b.timestamp_min)}
                  y={40}
                  width={Math.max(2, xScale(b.dur) - xScale(0))}
                  height={26}
                  rx={3}
                  fill={SCENE_COLORS[b.scene] || '#8fa0bd'}
                  opacity={0.85}
                >
                  <title>
                    {`${minToHHMM(b.timestamp_min)} · ${t('scene', b.scene)} · ${t('eventType', b.event_type)}\n学习增益 ${b.learning_gain.toFixed(3)} · 疲劳 Δ${b.fatigue_change}`}
                  </title>
                </rect>
              ))}

              {/* fatigue curve overlay */}
              <path d={fatiguePath} fill="none" stroke="#ef5b6b" strokeWidth="2" />
              <text x={x0} y={16} fill="#ef5b6b" fontSize="11">疲劳曲线（右轴 0-100）</text>
            </svg>

            <div className="row" style={{ marginTop: 16 }}>
              <div className="card stat"><span className="v">{timeline.total_learning_gain.toFixed(3)}</span><span className="l">当日总学习增益</span></div>
              <div className="card stat"><span className="v">{timeline.fatigue_end.toFixed(1)}</span><span className="l">日末疲劳</span></div>
              <div className="card stat"><span className="v">{timeline.stress_end.toFixed(1)}</span><span className="l">日末压力</span></div>
              <div className="card stat"><span className="v">{timeline.emotion_end.toFixed(1)}</span><span className="l">日末情绪</span></div>
            </div>

            <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              日期：{timeline.sim_date} · 事件数：{timeline.events.length} · 干预注入点以场景条带标注
            </div>
          </>
        )}
      </div>
    </div>
  )
}
