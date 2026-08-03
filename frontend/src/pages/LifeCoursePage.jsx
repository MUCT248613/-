import React, { useEffect, useState, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Legend, ReferenceLine,
} from 'recharts'
import api from '../api.js'
import { t } from '../i18n.js'

const METRICS = [
  { key: 'achievement', label: '成绩', color: '#4f8cff' },
  { key: 'motivation', label: '动机', color: '#38c7a4' },
  { key: 'fatigue', label: '疲劳', color: '#f5a623' },
  { key: 'stress', label: '压力', color: '#ef5b6b' },
  { key: 'emotion', label: '情绪', color: '#a06bff' },
]

const PALETTE = ['#4f8cff', '#38c7a4', '#f5a623', '#ef5b6b', '#a06bff', '#8fa0bd', '#ffd166', '#06d6a0']

export default function LifeCoursePage() {
  const { id } = useParams()
  const [students, setStudents] = useState([])
  const [selectedIds, setSelectedIds] = useState([])
  const [courses, setCourses] = useState({}) // sid -> life course
  const [metric, setMetric] = useState('achievement')
  const [eventDetail, setEventDetail] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .listStudents(id, 1, 100)
      .then((r) => {
        setStudents(r.students)
        if (r.students.length) setSelectedIds([r.students[0].student_id])
      })
      .catch((e) => setError(e.message))
  }, [id])

  // Fetch life course for each selected student
  useEffect(() => {
    let cancelled = false
    const missing = selectedIds.filter((sid) => !courses[sid])
    if (!missing.length) return
    Promise.all(missing.map((sid) => api.getLifeCourse(id, sid, 0, 90).then((c) => [sid, c]).catch(() => null)))
      .then((pairs) => {
        if (cancelled) return
        setCourses((prev) => {
          const next = { ...prev }
          pairs.forEach((p) => {
            if (p) next[p[0]] = p[1]
          })
          return next
        })
      })
    return () => {
      cancelled = true
    }
  }, [id, selectedIds])

  const toggleStudent = (sid) =>
    setSelectedIds((prev) =>
      prev.includes(sid) ? prev.filter((x) => x !== sid) : [...prev, sid],
    )

  const chartData = useMemo(() => {
    const primary = courses[selectedIds[0]]
    if (!primary) return []
    return primary.days.map((d, i) => {
      const row = { day: d }
      selectedIds.forEach((sid) => {
        const c = courses[sid]
        if (c && c[metric] && c[metric][i] !== undefined) row[sid] = c[metric][i]
      })
      return row
    })
  }, [courses, selectedIds, metric])

  const primaryCourse = courses[selectedIds[0]]
  const events = primaryCourse?.events || []

  return (
    <div>
      <div className="page-header">
        <h2>生命历程回放</h2>
        <p>单学生多曲线（成绩/动机/疲劳/压力/情绪）· 关键事件标注 · 多学生叠加对比</p>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="card">
        <h3>选择学生（可多选叠加对比，第一个为主学生）</h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
          {students.slice(0, 30).map((s) => (
            <button
              key={s.student_id}
              className={selectedIds.includes(s.student_id) ? '' : 'secondary'}
              style={{ fontSize: 12, padding: '5px 10px' }}
              onClick={() => toggleStudent(s.student_id)}
            >
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

        {chartData.length === 0 && <div className="loading">加载中…</div>}

        {chartData.length > 0 && (
          <ResponsiveContainer width="100%" height={380}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2c3a55" />
              <XAxis dataKey="day" stroke="#8fa0bd" label={{ value: '天', position: 'insideBottomRight', offset: -5, fill: '#8fa0bd' }} />
              <YAxis stroke="#8fa0bd" />
              <Tooltip contentStyle={{ background: '#1a2233', border: '1px solid #2c3a55', borderRadius: 8 }} />
              <Legend />
              {events.map((ev, i) => (
                <ReferenceLine
                  key={i}
                  x={ev.day}
                  stroke="#f5a623"
                  strokeDasharray="4 4"
                  label={{ value: t('eventType', ev.type), fill: '#f5a623', fontSize: 11, position: 'top' }}
                  onClick={() => setEventDetail(ev)}
                />
              ))}
              {selectedIds.map((sid, i) => (
                <Line
                  key={sid}
                  type="monotone"
                  dataKey={sid}
                  name={sid}
                  stroke={selectedIds.length === 1 ? (METRICS.find((m) => m.key === metric)?.color || PALETTE[i]) : PALETTE[i % PALETTE.length]}
                  dot={false}
                  strokeWidth={2}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}

        <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          点击黄色虚线（事件标注）查看详情。主学生：{selectedIds[0] || '—'}
        </div>
      </div>

      {eventDetail && (
        <div className="card">
          <h3>事件详情</h3>
          <table>
            <tbody>
              <tr><td className="muted">发生日</td><td>第 {eventDetail.day} 天</td></tr>
              <tr><td className="muted">类型</td><td>{t('eventType', eventDetail.type)}</td></tr>
              <tr><td className="muted">描述</td><td>{t('eventDescription', eventDetail.description)}</td></tr>
            </tbody>
          </table>
          <button className="secondary" style={{ marginTop: 8 }} onClick={() => setEventDetail(null)}>关闭</button>
        </div>
      )}

      {primaryCourse && (
        <div className="card">
          <h3>关键事件列表（主学生）</h3>
          <table>
            <thead>
              <tr><th>天</th><th>类型</th><th>描述</th></tr>
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
    </div>
  )
}
