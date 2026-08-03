import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api.js'

const VERDICT_LABELS = {
  pass: { text: '通过', color: '#38c7a4' },
  marginal: { text: '边缘', color: '#f5a623' },
  fail: { text: '未通过', color: '#e74c3c' },
}

function fmt(v) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') return v.toFixed(4)
  return String(v)
}

export default function CalibrationPage() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .getCalibration(id)
      .then((r) => !cancelled && setData(r))
      .catch((e) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [id])

  if (error) return <div className="error-box">{error}</div>
  if (!data) return <div className="loading">正在加载校准诊断…</div>

  const verdict = VERDICT_LABELS[data.verdict] || VERDICT_LABELS.marginal

  return (
    <div>
      <div className="page-header">
        <h2>校准诊断</h2>
        <p>
          虚拟-参考认知参数对比（FR-F2）· BKT 参数校准 · KS 检验 · 保真度判定
        </p>
      </div>

      <div className="card">
        <h3>总体判定</h3>
        <div className="row">
          <div className="stat">
            <span className="v" style={{ color: verdict.color }}>{verdict.text}</span>
            <span className="l">校准判定</span>
          </div>
          <div className="stat">
            <span className="v">{fmt(data.cognitive_distance)}</span>
            <span className="l">认知距离</span>
          </div>
          <div className="stat">
            <span className="v">{data.data_source === 'literature' ? '文献基线' : (data.data_source === 'real' ? '真实数据' : '合成数据')}</span>
            <span className="l">参照来源</span>
          </div>
        </div>
        <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          判定标准：认知距离 &lt; 0.10 通过，0.10–0.18 边缘，&gt; 0.18 未通过。
          参照基线为已发表 BKT/知识追踪文献的公开点估计（无需下载原始数据集）。
        </div>
      </div>

      {data.reference_basis && (
        <div className="card">
          <h3>文献参照基线（{data.reference_basis.n_studies} 项研究）</h3>
          <table>
            <thead>
              <tr><th>研究</th><th>数据集</th><th>p_know</th><th>p_learn</th><th>p_slip</th><th>p_guess</th></tr>
            </thead>
            <tbody>
              {(data.reference_basis.studies || []).map((s) => (
                <tr key={s.study_id}>
                  <td title={s.citation}><strong>{s.study_id}</strong></td>
                  <td className="muted">{s.dataset}</td>
                  <td>{fmt(s.params.p_know)}</td>
                  <td>{fmt(s.params.p_learn)}</td>
                  <td>{fmt(s.params.p_slip)}</td>
                  <td>{fmt(s.params.p_guess)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
            {data.reference_basis.note}
          </div>
        </div>
      )}

      <div className="card">
        <h3>BKT 参数对比（虚拟 vs 参考）</h3>
        <table>
          <thead>
            <tr><th>参数</th><th>虚拟值</th><th>参考值</th><th>绝对差</th><th>状态</th></tr>
          </thead>
          <tbody>
            {(data.diagnostics || []).map((d) => (
              <tr key={d.parameter}>
                <td><strong>{d.parameter}</strong></td>
                <td>{fmt(d.virtual_value)}</td>
                <td>{fmt(d.reference_value)}</td>
                <td>{fmt(d.absolute_diff)}</td>
                <td>
                  {d.status === 'ok'
                    ? <span className="badge green">正常</span>
                    : <span className="badge" style={{ color: '#f5a623', borderColor: '#f5a623' }}>偏离</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>KS 检验结果</h3>
        <table>
          <thead>
            <tr><th>参数</th><th>KS 统计量</th><th>p 值</th><th>结论</th></tr>
          </thead>
          <tbody>
            {Object.entries(data.ks_test_results || {}).map(([param, ks]) => (
              <tr key={param}>
                <td><strong>{param}</strong></td>
                <td>{fmt(ks.ks_statistic)}</td>
                <td>{fmt(ks.p_value)}</td>
                <td>
                  {ks.p_value > 0.05
                    ? <span className="badge green">不拒绝 H₀（分布一致）</span>
                    : <span className="badge" style={{ color: '#e74c3c', borderColor: '#e74c3c' }}>拒绝 H₀（分布偏离）</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          H₀：虚拟参数分布与参考分布无显著差异（α = 0.05）。
        </div>
      </div>

      <div className="card">
        <h3>人格分布参数</h3>
        <table>
          <tbody>
            {Object.entries(data.persona_distribution || {}).map(([key, val]) => (
              <tr key={key}>
                <td className="muted" style={{ width: 120 }}>{key}</td>
                <td>
                  {typeof val === 'object'
                    ? `μ = ${fmt(val.mu)}, σ = ${fmt(val.sigma)}`
                    : fmt(val)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
