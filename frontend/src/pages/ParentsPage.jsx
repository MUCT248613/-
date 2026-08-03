import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api.js'
import { t } from '../i18n.js'

const STYLE_LABELS = {
  autonomy_support: '自主支持型',
  directive: '控制型',
  permissive: '放任型',
  uninvolved: '忽视型',
}

function fmt(v) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') return Number.isInteger(v) ? v : v.toFixed(2)
  return String(v)
}

export default function ParentsPage() {
  const { id } = useParams()
  const [parents, setParents] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const pageSize = 20

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api
      .listParents(id, page, pageSize)
      .then((r) => {
        if (cancelled) return
        setParents(r.parents)
        setTotal(r.total)
      })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [id, page])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div>
      <div className="page-header">
        <h2>家长档案</h2>
        <p>虚拟家长画像浏览（FR-F7）· 全部字段完整展示 · 参与方式与家庭支持维度</p>
      </div>

      {error && <div className="error-box">{error}</div>}

      {!selected && (
        <div className="card">
          <h3>家长列表（共 {total} 人）</h3>
          {loading && <div className="loading">加载中…</div>}
          {!loading && (
            <table>
              <thead>
                <tr>
                  <th>ID</th><th>学历</th><th>参与方式</th><th>职业类别</th><th>日互动(h)</th><th>情感温暖</th>
                </tr>
              </thead>
              <tbody>
                {parents.map((p) => (
                  <tr key={p.parent_id} className="clickable" onClick={() => setSelected(p)}>
                    <td>{p.parent_id}</td>
                    <td>{p.education_level || '—'}</td>
                    <td>{STYLE_LABELS[p.involvement_style] || p.involvement_style || '—'}</td>
                    <td>{p.occupation_category || '—'}</td>
                    <td>{fmt(p.daily_interaction_hours)}</td>
                    <td>{fmt(p.emotional_warmth)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
            <button className="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
            <span className="muted">第 {page} / {totalPages} 页</span>
            <button className="secondary" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一页</button>
          </div>
        </div>
      )}

      {selected && (
        <div className="card">
          <h3>
            家长档案 · {selected.parent_id}
            <button className="secondary" style={{ marginLeft: 12, fontSize: 12 }} onClick={() => setSelected(null)}>
              ← 返回列表
            </button>
          </h3>
          <table>
            <tbody>
              <tr><td className="muted" style={{ width: 160 }}>家长 ID</td><td>{selected.parent_id}</td></tr>
              <tr><td className="muted">学历</td><td>{selected.education_level || '—'}</td></tr>
              <tr><td className="muted">参与方式</td><td>{STYLE_LABELS[selected.involvement_style] || selected.involvement_style || '—'}</td></tr>
              <tr><td className="muted">职业类别</td><td>{selected.occupation_category || '—'}</td></tr>
              <tr><td className="muted">每日互动时长（小时）</td><td>{fmt(selected.daily_interaction_hours)}</td></tr>
              <tr><td className="muted">作业支持水平</td><td>{fmt(selected.homework_support_level)}</td></tr>
              <tr><td className="muted">情感温暖</td><td>{fmt(selected.emotional_warmth)}</td></tr>
              <tr><td className="muted">关联学生 ID</td><td>{selected.child_id || '—'}</td></tr>
            </tbody>
          </table>
          {selected.simulation_vector && (
            <>
              <h4 style={{ marginTop: 16 }}>仿真参数向量</h4>
              <table>
                <tbody>
                  <tr><td className="muted" style={{ width: 160 }}>支持质量</td><td>{fmt(selected.simulation_vector.support_quality)}</td></tr>
                  <tr><td className="muted">监督程度</td><td>{fmt(selected.simulation_vector.monitoring)}</td></tr>
                  <tr><td className="muted">期望水平</td><td>{fmt(selected.simulation_vector.expectation_level)}</td></tr>
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  )
}
