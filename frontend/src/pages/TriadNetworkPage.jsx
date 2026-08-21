import React, { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import api from '../api.js'

// 事件流由仿真状态变量（动机/疲劳/家长参与度/课堂收益等）派生，
// 用于按学生复盘教师与家长的影响路径；非字面行为记录。
const LANE_META = {
  teacher: { label: '教师线', color: '#38c7a4' },
  parent: { label: '家长线', color: '#f5a623' },
  peer: { label: '同伴线', color: '#4f8cff' },
  tutoring: { label: '补习线', color: '#b08cff' },
  student: { label: '学生状态', color: '#ef5b6b' },
}

function quantile(sortedArr, q) {
  if (!sortedArr.length) return 0
  const pos = (sortedArr.length - 1) * q
  const base = Math.floor(pos)
  const rest = pos - base
  return sortedArr[base] + (sortedArr[base + 1] !== undefined ? rest * (sortedArr[base + 1] - sortedArr[base]) : 0)
}

function buildEventFeed(timeline, parentTraj, teacherScore) {
  if (!timeline) return []
  const inv = parentTraj?.trajectory || []
  const meanInv = parentTraj?.mean_involvement ?? 0.5
  const days = timeline.map((d, i) => {
    let classN = 0, tutorN = 0, peerN = 0, homeN = 0
    let gainSchool = 0, gainTutor = 0, gainHome = 0
    let fatigue = 0, mot = 0
    for (const ev of d.events || []) {
      if (ev.event_type === 'classroom') { classN++; gainSchool += ev.learning_gain }
      else if (ev.event_type === 'tutoring') { tutorN++; gainTutor += ev.learning_gain }
      else if (ev.event_type === 'homework_or_recreation') { homeN++; gainHome += ev.learning_gain }
      else if (ev.event_type === 'peer_interaction') { peerN++ }
      fatigue += ev.fatigue_change
      mot += ev.motivation_change
    }
    return {
      date: d.sim_date, inv: inv[i] ?? meanInv, classN, tutorN, peerN, homeN,
      gainSchool, gainTutor, gainHome, fatigue, mot,
      motEnd: d.motivation_end ?? null, achEnd: d.achievement_end ?? null,
    }
  })
  const sorted = (arr) => [...arr].sort((a, b) => a - b)
  const p80gain = quantile(sorted(days.map((d) => d.gainSchool)), 0.8)
  const p80fat = quantile(sorted(days.map((d) => d.fatigue)), 0.8)
  const p80home = quantile(sorted(days.map((d) => d.gainHome)), 0.8)

  const feed = []
  // parent line: per-5-day bucket extremes (low / high involvement phases)
  for (let b = 0; b < days.length; b += 5) {
    const seg = days.slice(b, b + 5)
    if (!seg.length) continue
    const minD = seg.reduce((a, c) => (c.inv < a.inv ? c : a))
    const maxD = seg.reduce((a, c) => (c.inv > a.inv ? c : a))
    if (minD.inv <= meanInv - 0.04) {
      feed.push({ date: minD.date, lane: 'parent', text: `家长参与度降至阶段低点 ${minD.inv.toFixed(2)}（周期均值 ${meanInv.toFixed(2)}），家庭支持减弱` })
    }
    if (maxD.inv >= meanInv + 0.04 && maxD.date !== minD.date) {
      feed.push({ date: maxD.date, lane: 'parent', text: `家长参与度升至阶段高点 ${maxD.inv.toFixed(2)}（周期均值 ${meanInv.toFixed(2)}），家庭支持增强` })
    }
  }
  for (let i = 0; i < days.length; i++) {
    const d = days[i]
    if (d.classN > 0 && p80gain > 0 && d.gainSchool > p80gain) {
      feed.push({ date: d.date, lane: 'teacher', text: `课堂线高效：${d.classN} 节课累计增益 +${d.gainSchool.toFixed(2)}（教师影响力 ${teacherScore.toFixed(2)}）` })
    }
    if (p80fat > 0 && d.fatigue > p80fat) {
      feed.push({ date: d.date, lane: 'teacher', text: `学业疲劳累积 ${d.fatigue.toFixed(1)}，课堂线负荷偏高，需关注节奏` })
    }
    if (p80home > 0 && d.gainHome > p80home) {
      feed.push({ date: d.date, lane: 'parent', text: `家庭学习线活跃：作业/休闲 ${d.homeN} 段，增益 +${d.gainHome.toFixed(2)}` })
    }
    if (d.tutorN > 0) {
      feed.push({ date: d.date, lane: 'tutoring', text: `补习日：${d.tutorN} 场辅导，增益 +${d.gainTutor.toFixed(2)}` })
    }
    if (d.peerN >= 2) {
      feed.push({ date: d.date, lane: 'peer', text: `同伴互动活跃（${d.peerN} 次），当日动机变化 ${d.mot >= 0 ? '+' : ''}${d.mot.toFixed(2)}` })
    }
    const prev = i > 0 ? days[i - 1].motEnd : null
    if (d.motEnd !== null && prev !== null) {
      const delta = d.motEnd - prev
      if (delta <= -0.08) {
        feed.push({ date: d.date, lane: 'student', text: `动机由 ${prev.toFixed(2)} 降至 ${d.motEnd.toFixed(2)}，建议结合当日家庭 / 课堂线综合研判` })
      } else if (delta >= 0.08) {
        feed.push({ date: d.date, lane: 'student', text: `动机由 ${prev.toFixed(2)} 回升至 ${d.motEnd.toFixed(2)}` })
      }
    } else if (d.mot <= -0.2) {
      feed.push({ date: d.date, lane: 'student', text: `动机明显下滑（${d.mot.toFixed(2)}），建议结合当日家庭 / 课堂线综合研判` })
    } else if (d.mot >= 0.2) {
      feed.push({ date: d.date, lane: 'student', text: `动机明显回升（+${d.mot.toFixed(2)}）` })
    }
  }
  feed.sort((a, b) => (a.date < b.date ? -1 : 1))
  return feed
}

export default function TriadNetworkPage() {
  const { id } = useParams()
  const [triad, setTriad] = useState(null)
  const [error, setError] = useState(null)
  const [sid, setSid] = useState(null)
  const [search, setSearch] = useState('')
  const [timeline, setTimeline] = useState(null)
  const [lanes, setLanes] = useState({ teacher: true, parent: true, peer: true, tutoring: true, student: true })

  useEffect(() => {
    api.getTriadNetwork(id).then((t) => {
      setTriad(t)
      const first = (t.nodes || []).find((n) => n.type === 'student')
      if (first) setSid(first.id)
    }).catch((e) => setError(e.message))
  }, [id])

  useEffect(() => {
    if (!sid) return
    let cancelled = false
    setTimeline(null)
    api.getFullTimeline(id, sid)
      .then((r) => !cancelled && setTimeline(r.days))
      .catch((e) => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [id, sid])

  const students = useMemo(
    () => (triad ? triad.nodes.filter((n) => n.type === 'student') : []),
    [triad],
  )
  const nodeById = useMemo(() => {
    const m = {}
    if (triad) for (const n of triad.nodes) m[n.id] = n
    return m
  }, [triad])

  const filteredStudents = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return students
    return students.filter((s) => s.id.toLowerCase().includes(q) || (s.label || '').toLowerCase().includes(q))
  }, [students, search])

  const tInfo = triad && sid ? triad.teacher_influence?.[sid] : null
  const pInfo = triad && sid ? triad.parent_trajectory?.[sid] : null
  const teacherNode = tInfo ? nodeById[tInfo.teacher_id] : null
  const parentNode = pInfo ? nodeById[tInfo ? pInfo.parent_id : ''] : null
  const studentNode = sid ? nodeById[sid] : null

  const feed = useMemo(
    () => buildEventFeed(timeline, pInfo, tInfo?.score ?? 0.5),
    [timeline, pInfo, tInfo],
  )
  const visibleFeed = feed.filter((f) => lanes[f.lane]).slice(0, 150)

  const chartData = useMemo(() => {
    if (!timeline) return []
    const inv = pInfo?.trajectory || []
    const gains = timeline.map((d) => (d.events || []).reduce((s, e) => s + e.learning_gain, 0))
    const out = []
    let acc = 0
    for (let i = 0; i < timeline.length; i++) {
      acc += gains[i]
      if (i >= 7) acc -= gains[i - 7]
      out.push({
        day: i + 1,
        家长参与度: inv[i] ?? null,
        动机: timeline[i].motivation_end ?? null,
        '7日平均增益': Number((acc / Math.min(i + 1, 7)).toFixed(3)),
      })
    }
    return out
  }, [timeline, pInfo])

  const idx = students.findIndex((s) => s.id === sid)
  const step = (d) => {
    if (!students.length) return
    const ni = Math.min(students.length - 1, Math.max(0, idx + d))
    setSid(students[ni].id)
  }

  return (
    <div>
      <div className="page-header">
        <h2>三方关系网络 · 学生成长档案</h2>
        <p>按学生复盘仿真周期内教师 / 家长 / 同伴的影响路径 · 人生模拟器视角</p>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="card">
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            value={search}
            placeholder="搜索学生姓名 / ID"
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: 220 }}
          />
          <select value={sid || ''} onChange={(e) => setSid(e.target.value)} style={{ minWidth: 220 }}>
            {filteredStudents.map((s) => (
              <option key={s.id} value={s.id}>{s.label}（{s.id}）</option>
            ))}
          </select>
          <button className="secondary" disabled={idx <= 0} onClick={() => step(-1)}>← 上一位</button>
          <button className="secondary" disabled={idx < 0 || idx >= students.length - 1} onClick={() => step(1)}>下一位 →</button>
          <span className="muted" style={{ fontSize: 12 }}>
            {idx >= 0 ? `${idx + 1} / ${students.length}` : ''}
          </span>
        </div>
      </div>

      {studentNode && (
        <div className="card">
          <h3>三方概览 · {studentNode.label}</h3>
          <div className="row" style={{ gap: 16, alignItems: 'stretch' }}>
            <div style={{ flex: 1, background: '#1a2233', borderRadius: 8, padding: 12, border: '1px solid #2c3a55' }}>
              <div className="muted" style={{ fontSize: 12 }}>学生</div>
              <div style={{ fontWeight: 600 }}>{studentNode.label}</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                成就分 {studentNode.achievement_score?.toFixed(1)}
              </div>
            </div>
            <div style={{ flex: 1, background: '#1a2233', borderRadius: 8, padding: 12, border: '1px solid #38c7a4' }}>
              <div className="muted" style={{ fontSize: 12 }}>教师线 · {teacherNode?.label || tInfo?.teacher_id}</div>
              <div style={{ fontWeight: 600 }}>
                {teacherNode?.teaching_style || '—'} · 教龄 {teacherNode?.experience_years ?? '—'} 年
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                教师影响力 {tInfo?.score?.toFixed(2) ?? '—'}（经验×风格匹配）
              </div>
              <div style={{ background: '#2c3a55', borderRadius: 4, height: 6, marginTop: 6 }}>
                <div style={{ width: `${Math.round((tInfo?.score ?? 0) * 100)}%`, background: '#38c7a4', height: 6, borderRadius: 4 }} />
              </div>
            </div>
            <div style={{ flex: 1, background: '#1a2233', borderRadius: 8, padding: 12, border: '1px solid #f5a623' }}>
              <div className="muted" style={{ fontSize: 12 }}>家长线 · {parentNode?.label || pInfo?.parent_id}</div>
              <div style={{ fontWeight: 600 }}>
                平均参与度 {pInfo?.mean_involvement?.toFixed(2) ?? '—'}
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                当前参与 {parentNode?.involvement_level?.toFixed(2) ?? '—'}
              </div>
              <div style={{ background: '#2c3a55', borderRadius: 4, height: 6, marginTop: 6 }}>
                <div style={{ width: `${Math.round((pInfo?.mean_involvement ?? 0) * 100)}%`, background: '#f5a623', height: 6, borderRadius: 4 }} />
              </div>
            </div>
          </div>
        </div>
      )}

      {chartData.length > 0 && (
        <div className="card">
          <h3>90 天影响曲线</h3>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2c3a55" />
              <XAxis dataKey="day" stroke="#8fa0bd" />
              <YAxis yAxisId="inv" domain={[0, 1]} stroke="#f5a623" />
              <YAxis yAxisId="gain" orientation="right" stroke="#38c7a4" />
              <Tooltip contentStyle={{ background: '#1a2233', border: '1px solid #2c3a55', borderRadius: 8 }} />
              <Legend />
              <Line yAxisId="inv" type="monotone" dataKey="家长参与度" stroke="#f5a623" dot={false} />
              <Line yAxisId="inv" type="monotone" dataKey="动机" stroke="#ef5b6b" dot={false} />
              <Line yAxisId="gain" type="monotone" dataKey="7日平均增益" stroke="#38c7a4" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="card">
        <h3>影响事件流（{visibleFeed.length} 条）</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
          {Object.entries(LANE_META).map(([k, m]) => (
            <button
              key={k}
              className="secondary"
              style={{ borderColor: m.color, color: lanes[k] ? m.color : '#8fa0bd', opacity: lanes[k] ? 1 : 0.5 }}
              onClick={() => setLanes({ ...lanes, [k]: !lanes[k] })}
            >
              {m.label}
            </button>
          ))}
          <span className="muted" style={{ fontSize: 12, alignSelf: 'center' }}>
            事件流由仿真状态变量派生，展示教师 / 家长 / 同伴的影响通道
          </span>
        </div>
        {!timeline && <div className="loading">加载时间线…</div>}
        {timeline && visibleFeed.length === 0 && (
          <div className="muted">当前筛选下暂无显著事件。</div>
        )}
        <div style={{ maxHeight: 480, overflowY: 'auto' }}>
          {visibleFeed.map((f, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, padding: '6px 4px', borderBottom: '1px solid #22304a', alignItems: 'baseline' }}>
              <span className="muted" style={{ fontSize: 12, minWidth: 86 }}>{f.date}</span>
              <span style={{ fontSize: 11, color: LANE_META[f.lane].color, minWidth: 56 }}>
                {LANE_META[f.lane].label}
              </span>
              <span style={{ fontSize: 13 }}>{f.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
