import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api.js'

function fmt(v) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') return Number.isInteger(v) ? v : v.toFixed(2)
  return String(v)
}

export default function TeachersPage() {
  const { id } = useParams()
  const [teachers, setTeachers] = useState([])
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
      .listTeachers(id, page, pageSize)
      .then((r) => {
        if (cancelled) return
        setTeachers(r.teachers)
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
        <h2>教师档案</h2>
        <p>虚拟教师画像浏览 · 任教学科 / 教学风格 / 课堂管理 · 仿真参数向量完整展示</p>
      </div>

      {error && <div className="error-box">{error}</div>}

      {!selected && (
        <div className="card">
          <h3>教师列表（共 {total} 人）</h3>
          {loading && <div className="loading">加载中…</div>}
          {!loading && (
            <table>
              <thead>
                <tr>
                  <th>ID</th><th>姓名</th><th>任教学科</th><th>教龄(年)</th><th>教学风格</th><th>课堂管理</th>
                </tr>
              </thead>
              <tbody>
                {teachers.map((t) => (
                  <tr key={t.teacher_id} className="clickable" onClick={() => setSelected(t)}>
                    <td>{t.teacher_id}</td>
                    <td>{t.name || '—'}</td>
                    <td>{t.subject || '—'}</td>
                    <td>{fmt(t.experience_years)}</td>
                    <td>{t.teaching_style || '—'}</td>
                    <td>{t.classroom_management || '—'}</td>
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
            教师档案 · {selected.teacher_id}
            <button className="secondary" style={{ marginLeft: 12, fontSize: 12 }} onClick={() => setSelected(null)}>
              ← 返回列表
            </button>
          </h3>
          <table>
            <tbody>
              <tr><td className="muted" style={{ width: 160 }}>教师 ID</td><td>{selected.teacher_id}</td></tr>
              <tr><td className="muted">姓名</td><td>{selected.name || '—'}</td></tr>
              <tr><td className="muted">任教学科</td><td>{selected.subject || '—'}</td></tr>
              <tr><td className="muted">教龄（年）</td><td>{fmt(selected.experience_years)}</td></tr>
              <tr><td className="muted">教学风格</td><td>{selected.teaching_style || '—'}</td></tr>
              <tr><td className="muted">课堂管理</td><td>{selected.classroom_management || '—'}</td></tr>
              <tr><td className="muted">教学理念</td><td>{selected.teaching_philosophy || '—'}</td></tr>
            </tbody>
          </table>
          {selected.simulation_vector && (
            <>
              <h4 style={{ marginTop: 16 }}>仿真参数向量</h4>
              <table>
                <tbody>
                  <tr><td className="muted" style={{ width: 160 }}>保真度</td><td>{fmt(selected.simulation_vector.fidelity)}</td></tr>
                  <tr><td className="muted">风格匹配基线</td><td>{fmt(selected.simulation_vector.style_match_base)}</td></tr>
                  <tr><td className="muted">经验水平</td><td>{fmt(selected.simulation_vector.experience_level)}</td></tr>
                  <tr><td className="muted">疲劳易感性</td><td>{fmt(selected.simulation_vector.fatigue_susceptibility)}</td></tr>
                  <tr><td className="muted">动机激励质量</td><td>{fmt(selected.simulation_vector.motivational_quality)}</td></tr>
                  <tr><td className="muted">错误觉察率</td><td>{fmt(selected.simulation_vector.error_detection_rate)}</td></tr>
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  )
}
