import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api.js'
import { t } from '../i18n.js'

const DECISION_STYLES = {
  go: { label: 'GO（推荐进入实证）', color: '#38c7a4', bg: 'rgba(56,199,164,0.1)' },
  conditional: { label: 'CONDITIONAL（有条件推荐）', color: '#f5a623', bg: 'rgba(245,166,35,0.1)' },
  no_go: { label: 'NO-GO（暂不推荐）', color: '#e74c3c', bg: 'rgba(231,76,60,0.1)' },
}

const CHECK_LABELS = {
  effect_threshold: '效应量 ≥ 0.20',
  ci_significance: '95% CI 不跨零',
  fidelity: '非高失真区',
  feasibility: '优先级 ≥ 0.40',
}

export default function PrescreeningPage() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .getPrescreening(id)
      .then((r) => !cancelled && setData(r))
      .catch((e) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [id])

  if (error) return <div className="error-box">{error}</div>
  if (!data) return <div className="loading">正在生成预筛报告…</div>

  return (
    <div>
      <div className="page-header">
        <h2>预筛报告</h2>
        <p>
          虚拟预筛 → 真人试验决策支持（FR-F4）· Go / No-Go 判定 · 不替代实证
        </p>
      </div>

      <div className="card">
        <h3>决策概览</h3>
        <div className="row">
          <div className="stat">
            <span className="v" style={{ color: '#38c7a4' }}>{data.go_count}</span>
            <span className="l">GO</span>
          </div>
          <div className="stat">
            <span className="v" style={{ color: '#f5a623' }}>{data.conditional_count}</span>
            <span className="l">CONDITIONAL</span>
          </div>
          <div className="stat">
            <span className="v" style={{ color: '#e74c3c' }}>{data.no_go_count}</span>
            <span className="l">NO-GO</span>
          </div>
        </div>
      </div>

      <div className="card">
        <h3>判定标准</h3>
        <ul style={{ lineHeight: 2, paddingLeft: 20 }}>
          {(data.criteria || []).map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      </div>

      <div className="card">
        <h3>候选干预预筛明细</h3>
        <table>
          <thead>
            <tr>
              <th>排名</th><th>干预</th><th>场景</th><th>Hedges' g</th><th>95% CI</th>
              <th>优先级</th><th>失真区</th><th>判定</th>
            </tr>
          </thead>
          <tbody>
            {(data.candidates || []).map((c) => {
              const ds = DECISION_STYLES[c.decision] || DECISION_STYLES.no_go
              return (
                <tr key={c.intervention_id}>
                  <td><strong>{c.rank}</strong></td>
                  <td>{t('intervention', c.intervention_id)}</td>
                  <td>{t('scene', c.scene)}</td>
                  <td><strong>{c.hedges_g?.toFixed(3)}</strong></td>
                  <td className="muted">[{c.ci_95?.[0]?.toFixed(3)}, {c.ci_95?.[1]?.toFixed(3)}]</td>
                  <td className="muted">{c.priority_score?.toFixed(3)}</td>
                  <td>
                    {c.in_distorted_region
                      ? <span className="badge" style={{ color: '#f5a623', borderColor: '#f5a623' }}>失真</span>
                      : <span className="badge green">正常</span>}
                  </td>
                  <td>
                    <span className="badge" style={{ color: ds.color, borderColor: ds.color }}>
                      {c.decision.toUpperCase()}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {(data.candidates || []).map((c) => (
        <div className="card" key={`detail-${c.intervention_id}`}>
          <h3>
            {c.rank}. {t('intervention', c.intervention_id)}
            <span
              className="badge"
              style={{
                marginLeft: 8,
                color: (DECISION_STYLES[c.decision] || {}).color,
                borderColor: (DECISION_STYLES[c.decision] || {}).color,
              }}
            >
              {(DECISION_STYLES[c.decision] || {}).label}
            </span>
          </h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {Object.entries(c.checks || {}).map(([key, pass]) => (
              <span
                key={key}
                className="badge"
                style={{
                  color: pass ? '#38c7a4' : '#e74c3c',
                  borderColor: pass ? '#38c7a4' : '#e74c3c',
                }}
              >
                {pass ? '✓' : '✗'} {CHECK_LABELS[key] || key}
              </span>
            ))}
          </div>
        </div>
      ))}

      <div className="privacy-note">{data.disclaimer}</div>
    </div>
  )
}
