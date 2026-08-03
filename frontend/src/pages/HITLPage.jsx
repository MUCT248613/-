import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api.js'
import { t } from '../i18n.js'

const VERDICT_LABELS = {
  agree: { text: '同意', color: '#38c7a4' },
  disagree: { text: '不同意', color: '#e74c3c' },
  adjust: { text: '调整', color: '#f5a623' },
}

const TARGET_TYPE_LABELS = {
  intervention: '干预',
  hypothesis: '假设',
  profile: '画像',
  distortion: '失真',
}

const ROLE_LABELS = {
  teacher: '教师',
  researcher: '研究者',
  parent: '家长',
}

export default function HITLPage() {
  const { id } = useParams()
  const [feedbacks, setFeedbacks] = useState([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  // Form state
  const [targetType, setTargetType] = useState('intervention')
  const [targetId, setTargetId] = useState('')
  const [verdict, setVerdict] = useState('agree')
  const [comment, setComment] = useState('')
  const [adjustedValue, setAdjustedValue] = useState('')
  const [expertRole, setExpertRole] = useState('teacher')

  const loadFeedback = () => {
    api
      .getHITLFeedback(id)
      .then((r) => {
        setFeedbacks(r.feedbacks)
        setTotal(r.total)
      })
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    loadFeedback()
  }, [id])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!targetId.trim()) {
      setError('请填写目标 ID')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await api.submitHITLFeedback(id, {
        target_type: targetType,
        target_id: targetId.trim(),
        verdict,
        comment: comment.trim() || null,
        adjusted_value: adjustedValue ? parseFloat(adjustedValue) : null,
        expert_role: expertRole,
      })
      setTargetId('')
      setComment('')
      setAdjustedValue('')
      loadFeedback()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>人在回路（HITL）</h2>
        <p>
          专家审阅与反馈（FR-F5）· 对干预/假设/画像/失真进行人工判定 · 闭环改进
        </p>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="card">
        <h3>提交专家反馈</h3>
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label className="muted" style={{ display: 'block', marginBottom: 4 }}>目标类型</label>
              <select value={targetType} onChange={(e) => setTargetType(e.target.value)} style={{ width: '100%' }}>
                {Object.entries(TARGET_TYPE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="muted" style={{ display: 'block', marginBottom: 4 }}>目标 ID</label>
              <input
                value={targetId}
                onChange={(e) => setTargetId(e.target.value)}
                placeholder="如 cognitive_support / H1 / S00001"
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <label className="muted" style={{ display: 'block', marginBottom: 4 }}>判定</label>
              <select value={verdict} onChange={(e) => setVerdict(e.target.value)} style={{ width: '100%' }}>
                {Object.entries(VERDICT_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v.text}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="muted" style={{ display: 'block', marginBottom: 4 }}>专家角色</label>
              <select value={expertRole} onChange={(e) => setExpertRole(e.target.value)} style={{ width: '100%' }}>
                {Object.entries(ROLE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="muted" style={{ display: 'block', marginBottom: 4 }}>调整值（可选）</label>
              <input
                type="number"
                step="0.01"
                value={adjustedValue}
                onChange={(e) => setAdjustedValue(e.target.value)}
                placeholder="如 0.35"
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <label className="muted" style={{ display: 'block', marginBottom: 4 }}>评语（可选）</label>
              <input
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="补充说明…"
                style={{ width: '100%' }}
              />
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <button type="submit" disabled={submitting}>
              {submitting ? '提交中…' : '提交反馈'}
            </button>
          </div>
        </form>
      </div>

      <div className="card">
        <h3>历史反馈记录（共 {total} 条）</h3>
        {feedbacks.length === 0 ? (
          <div className="muted">暂无反馈记录。</div>
        ) : (
          <table>
            <thead>
              <tr><th>ID</th><th>类型</th><th>目标</th><th>判定</th><th>角色</th><th>调整值</th><th>评语</th><th>时间</th></tr>
            </thead>
            <tbody>
              {feedbacks.map((f) => {
                const vl = VERDICT_LABELS[f.verdict] || {}
                return (
                  <tr key={f.feedback_id}>
                    <td className="muted">{f.feedback_id}</td>
                    <td>{TARGET_TYPE_LABELS[f.target_type] || f.target_type}</td>
                    <td>{f.target_id}</td>
                    <td>
                      <span className="badge" style={{ color: vl.color, borderColor: vl.color }}>
                        {vl.text || f.verdict}
                      </span>
                    </td>
                    <td>{ROLE_LABELS[f.expert_role] || f.expert_role || '—'}</td>
                    <td>{f.adjusted_value != null ? f.adjusted_value.toFixed(3) : '—'}</td>
                    <td className="muted">{f.comment || '—'}</td>
                    <td className="muted">{f.created_at?.replace('T', ' ').slice(0, 19)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
