import React, { useEffect, useState, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Legend, ReferenceLine,
} from 'recharts'
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

const METRICS = [
  { key: 'achievement', label: '\u6210\u7ee9', color: '#4f8cff' },
  { key: 'motivation', label: '\u52a8\u673a', color: '#38c7a4' },
  { key: 'fatigue', label: '\u75b2\u52b3', color: '#f5a623' },
  { key: 'stress', label: '\u538b\u529b', color: '#ef5b6b' },
  { key: 'emotion', label: '\u60c5\u7eea', color: '#a06bff' },
]

const PALETTE = ['#4f8cff', '#38c7a4', '#f5a623', '#ef5b6b', '#a06bff', '#8fa0bd', '#ffd166', '#06d6a0']

const TABS = [
  { key: 'timeline', label: '\u5b66\u4e60\u8f68\u8ff9\u56de\u653e' },
  { key: 'life_course', label: '\u751f\u547d\u5386\u7a0b' },
]

export default function TimelinePage() {
  const { id } = useParams()
  const [tab, setTab] = useState('timeline')

  // ---- Timeline tab state ----
  const [students, setStudents] = useState([])
  const [sid, setSid] = useState('')
  const [timeline, setTimeline] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // ---- Life course tab state ----
  const [selectedIds, setSelectedIds] = useState([])
  const [courses, setCourses] = useState({})
  const [metric, setMetric] = useState('achievement')
  const [eventDetail, setEventDetail] = useState(null)
  const [lcError, setLcError] = useState(null)

  // Load students (shared by both tabs)
  useEffect(() => {
    api
      .listStudents(id, 1, 100)
      .then((r) => {
        setStudents(r.students)
        if (r.students.length) {
          setSid(r.students[0].student_id)
          setSelectedIds([r.students[0].student_id])
        }
      })
      .catch((e) => setError(e.message))
  }, [id])

  // Timeline: load timeline for selected student
  useEffect(() => {
    if (!sid || tab !== 'timeline') return
    let cancelled = false
    setLoading(true)
    api
      .getTimeline(id, sid)
      .then((t) => !cancelled && setTimeline(t))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [id, sid, tab])

  // Life course: load courses for selected students
  useEffect(() => {
    if (tab !== 'life_course') return
    let cancelled = false
    const missing = selectedIds.filter((s) => !courses[s])
    if (!missing.length) return
    Promise.all(missing.map((s) => api.getLifeCourse(id, s, 0, 90).then((c) => [s, c]).catch(() => null)))
      .then((pairs) => {
        if (cancelled) return
        setCourses((prev) => {
          const next = { ...prev }
          pairs.forEach((p) => { if (p) next[p[0]] = p[1] })
          return next
        })
      })
    return () => { cancelled = true }
  }, [id, selectedIds, tab])

  // Timeline Gantt + fatigue
  const { bars, fatiguePath, fatiguePoints, xScale, W, H, x0 } = useMemo(() => {
    const W = 900, H = 220, x0 = 60
    const xScale = (min) => x0 + (min / 1440) * (W - x0 - 20)
    if (!timeline) return { bars: [], fatiguePath: '', fatiguePoints: [], xScale, W, H, x0 }

    const events = timeline.events
    const bars = events.map((e, i) => {
      const next = events[i + 1]
      const dur = next ? Math.max(5, next.timestamp_min - e.timestamp_min) : 30
      return { ...e, dur }
    })

    let fatigue = 50
    const pts = events.map((e) => {
      fatigue = Math.min(100, Math.max(0, fatigue + e.fatigue_change))
      return { min: e.timestamp_min, fatigue }
    })
    const yScale = (f) => H - 30 - (f / 100) * (H - 60)
    const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${xScale(p.min).toFixed(1)},${yScale(p.fatigue).toFixed(1)}`).join(' ')

    return { bars, fatiguePath: path, fatiguePoints: pts, xScale, W, H, x0 }
  }, [timeline])

  // Life course chart data
  const chartData = useMemo(() => {
    const primary = courses[selectedIds[0]]
    if (!primary) return []
    return primary.days.map((d, i) => {
      const row = { day: d }
      selectedIds.forEach((s) => {
        const c = courses[s]
        if (c && c[metric] && c[metric][i] !== undefined) row[s] = c[metric][i]
      })
      return row
    })
  }, [courses, selectedIds, metric])

  const primaryCourse = courses[selectedIds[0]]
  const events = primaryCourse?.events || []

  const toggleStudent = (s) =>
    setSelectedIds((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s])

  return (
    <div>
      <div className="page-header">
        <h2>{'\u{1f4c8} \u5b66\u4e60\u8f68\u8ff9'}</h2>
        <p>{'\u5355\u5b66\u751f 24h \u4e8b\u4ef6\u6d41 \u00b7 \u591a\u6307\u6807\u751f\u547d\u5386\u7a0b\u56de\u653e \u00b7 \u5173\u952e\u4e8b\u4ef6\u6807\u6ce8'}</p>
      </div>

      <div className="tabs">
        {TABS.map((tb) => (
          <button key={tb.key} className={tab === tb.key ? 'active' : ''} onClick={() => setTab(tb.key)}>
            {tb.label}
          </button>
        ))}
      </div>

      {/* ============ Timeline Tab ============ */}
      {tab === 'timeline' && (
        <div className="card">
          <div className="field" style={{ maxWidth: 320 }}>
            <label>{'\u9009\u62e9\u5b66\u751f'}</label>
            <select value={sid} onChange={(e) => setSid(e.target.value)}>
              {students.map((s) => (
                <option key={s.student_id} value={s.student_id}>
                  {s.student_id} {'\u00b7'} {localName(s.name)}
                </option>
              ))}
            </select>
          </div>

          {error && <div className="error-box">{error}</div>}
          {loading && <div className="loading">{'\u52a0\u8f7d\u4e2d\u2026'}</div>}

          {timeline && !loading && (
            <>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
                {SCENE_KEYS.map((k) => (
                  <span key={k} className="badge" style={{ borderColor: SCENE_COLORS[k], color: SCENE_COLORS[k] }}>
                    {'\u25a0'} {t('scene', k)}
                  </span>
                ))}
              </div>

              <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ background: '#141b2b', borderRadius: 8 }}>
                {[0, 4, 8, 12, 16, 20, 24].map((h) => (
                  <g key={h}>
                    <line x1={xScale(h * 60)} y1={20} x2={xScale(h * 60)} y2={H - 30} stroke="#2c3a55" strokeWidth="1" />
                    <text x={xScale(h * 60)} y={H - 12} fill="#8fa0bd" fontSize="10" textAnchor="middle">
                      {String(h).padStart(2, '0')}:00
                    </text>
                  </g>
                ))}
                {bars.map((b, i) => (
                  <rect key={i} x={xScale(b.timestamp_min)} y={40}
                    width={Math.max(2, xScale(b.dur) - xScale(0))} height={26} rx={3}
                    fill={SCENE_COLORS[b.scene] || '#8fa0bd'} opacity={0.85}>
                    <title>{`${minToHHMM(b.timestamp_min)} \u00b7 ${t('scene', b.scene)} \u00b7 ${t('eventType', b.event_type)}\n\u5b66\u4e60\u589e\u76ca ${b.learning_gain.toFixed(3)} \u00b7 \u75b2\u52b3 \u0394${b.fatigue_change}`}</title>
                  </rect>
                ))}
                <path d={fatiguePath} fill="none" stroke="#ef5b6b" strokeWidth="2" />
                <text x={x0} y={16} fill="#ef5b6b" fontSize="11">{'\u75b2\u52b3\u66f2\u7ebf\uff08\u53f3\u8f74 0-100\uff09'}</text>
              </svg>

              <div className="row" style={{ marginTop: 16 }}>
                <div className="card stat"><span className="v">{timeline.total_learning_gain.toFixed(3)}</span><span className="l">{'\u5f53\u65e5\u603b\u5b66\u4e60\u589e\u76ca'}</span></div>
                <div className="card stat"><span className="v">{timeline.fatigue_end.toFixed(1)}</span><span className="l">{'\u65e5\u672b\u75b2\u52b3'}</span></div>
                <div className="card stat"><span className="v">{timeline.stress_end.toFixed(1)}</span><span className="l">{'\u65e5\u672b\u538b\u529b'}</span></div>
                <div className="card stat"><span className="v">{timeline.emotion_end.toFixed(1)}</span><span className="l">{'\u65e5\u672b\u60c5\u7eea'}</span></div>
              </div>

              <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                {'\u65e5\u671f'}: {timeline.sim_date} {'\u00b7'} {'\u4e8b\u4ef6\u6570'}: {timeline.events.length} {'\u00b7'} {'\u5e72\u9884\u6ce8\u5165\u70b9\u4ee5\u573a\u666f\u6761\u5e26\u6807\u6ce8'}
              </div>
            </>
          )}
        </div>
      )}

      {/* ============ Life Course Tab ============ */}
      {tab === 'life_course' && (
        <>
          {lcError && <div className="error-box">{lcError}</div>}

          <div className="card">
            <h3>{'\u9009\u62e9\u5b66\u751f\uff08\u53ef\u591a\u9009\u53e0\u52a0\u5bf9\u6bd4\uff0c\u7b2c\u4e00\u4e2a\u4e3a\u4e3b\u5b66\u751f\uff09'}</h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
              {students.slice(0, 30).map((s) => (
                <button key={s.student_id}
                  className={selectedIds.includes(s.student_id) ? '' : 'secondary'}
                  style={{ fontSize: 12, padding: '5px 10px' }}
                  onClick={() => toggleStudent(s.student_id)}>
                  {s.student_id}
                </button>
              ))}
            </div>

            <div className="tabs">
              {METRICS.map((m) => (
                <button key={m.key} className={metric === m.key ? 'active' : ''} onClick={() => setMetric(m.key)}>
                  {m.label}
                </button>
              ))}
            </div>

            {chartData.length === 0 && <div className="loading">{'\u52a0\u8f7d\u4e2d\u2026'}</div>}

            {chartData.length > 0 && (
              <ResponsiveContainer width="100%" height={380}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2c3a55" />
                  <XAxis dataKey="day" stroke="#8fa0bd" label={{ value: '\u5929', position: 'insideBottomRight', offset: -5, fill: '#8fa0bd' }} />
                  <YAxis stroke="#8fa0bd" />
                  <Tooltip contentStyle={{ background: '#1a2233', border: '1px solid #2c3a55', borderRadius: 8 }} />
                  <Legend />
                  {events.map((ev, i) => (
                    <ReferenceLine key={i} x={ev.day} stroke="#f5a623" strokeDasharray="4 4"
                      label={{ value: t('eventType', ev.type), fill: '#f5a623', fontSize: 11, position: 'top' }}
                      onClick={() => setEventDetail(ev)} />
                  ))}
                  {selectedIds.map((s, i) => (
                    <Line key={s} type="monotone" dataKey={s} name={s}
                      stroke={selectedIds.length === 1 ? (METRICS.find((m) => m.key === metric)?.color || PALETTE[i]) : PALETTE[i % PALETTE.length]}
                      dot={false} strokeWidth={2} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            )}

            <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              {'\u70b9\u51fb\u9ec4\u8272\u865a\u7ebf\uff08\u4e8b\u4ef6\u6807\u6ce8\uff09\u67e5\u770b\u8be6\u60c5\u3002\u4e3b\u5b66\u751f\uff1a'}{selectedIds[0] || '\u2014'}
            </div>
          </div>

          {eventDetail && (
            <div className="card">
              <h3>{'\u4e8b\u4ef6\u8be6\u60c5'}</h3>
              <table>
                <tbody>
                  <tr><td className="muted">{'\u53d1\u751f\u65e5'}</td><td>{'\u7b2c'} {eventDetail.day} {'\u5929'}</td></tr>
                  <tr><td className="muted">{'\u7c7b\u578b'}</td><td>{t('eventType', eventDetail.type)}</td></tr>
                  <tr><td className="muted">{'\u63cf\u8ff0'}</td><td>{t('eventDescription', eventDetail.description)}</td></tr>
                </tbody>
              </table>
              <button className="secondary" style={{ marginTop: 8 }} onClick={() => setEventDetail(null)}>{'\u5173\u95ed'}</button>
            </div>
          )}

          {primaryCourse && (
            <div className="card">
              <h3>{'\u5173\u952e\u4e8b\u4ef6\u5217\u8868\uff08\u4e3b\u5b66\u751f\uff09'}</h3>
              <table>
                <thead>
                  <tr><th>{'\u5929'}</th><th>{'\u7c7b\u578b'}</th><th>{'\u63cf\u8ff0'}</th></tr>
                </thead>
                <tbody>
                  {events.map((ev, i) => (
                    <tr key={i} className="clickable" onClick={() => setEventDetail(ev)}>
                      <td>{ev.day}</td>
                      <td>{t('eventType', ev.type)}</td>
                      <td>{t('eventDescription', ev.description)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}