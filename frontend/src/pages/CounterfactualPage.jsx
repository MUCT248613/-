import React, { useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import api from '../api.js'
import { t } from '../i18n.js'

const MODIFICATIONS = [
  { key: 'remove_shadow_edu', label: '移除课外班' },
  { key: 'increase_parental_support', label: '增加家长支持' },
  { key: 'forbid_romance', label: '禁止恋爱' },
  { key: 'switch_class', label: '换班' },
  { key: 'add_tutoring', label: '增加家教' },
  { key: 'reduce_homework', label: '减少作业' },
]

export default function CounterfactualPage() {
  const { id } = useParams()
  const [modKey, setModKey] = useState('remove_shadow_edu')
  const [days, setDays] = useState(30)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [created, setCreated] = useState(null)
  const [comparison, setComparison] = useState(null)

  const createBranch = async () => {
    setBusy(true)
    setError(null)
    setComparison(null)
    setCreated(null)
    try {
      const modification = { [modKey]: true }
      const res = await api.createCounterfactual(id, {
        modification,
        days: Number(days),
      })
      setCreated(res)
      const cmp = await api.getCounterfactualComparison(id, res.cf_id)
      setComparison(cmp)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const chartData = comparison
    ? comparison.trajectory_baseline.map((v, i) => ({
        day: i,
        baseline: Number(v.toFixed(2)),
        modified: Number(comparison.trajectory_modified[i]?.toFixed(2) ?? 0),
      }))
    : []

  const delta = comparison ? comparison.modified_mean - comparison.baseline_mean : 0

  return (
    <div>
      <div className="page-header">
        <h2>反事实对比</h2>
        <p>同一起点 + 固定种子 · 单变量分流 · 基线 vs 干预后轨迹对比</p>
      </div>

      <div className="card">
        <h3>创建反事实分支</h3>
        {error && <div className="error-box">{error}</div>}
        <div className="row">
          <div className="field">
            <label>干预变量（单变量分流）</label>
            <select value={modKey} onChange={(e) => setModKey(e.target.value)}>
              {MODIFICATIONS.map((m) => (
                <option key={m.key} value={m.key}>{m.label}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>模拟天数 (1-365)</label>
            <input type="number" min={1} max={365} value={days} onChange={(e) => setDays(e.target.value)} />
          </div>
          <div className="field" style={{ alignSelf: 'flex-end' }}>
            <button onClick={createBranch} disabled={busy}>
              {busy ? '分流中…' : '创建并对比'}
            </button>
          </div>
        </div>
        <div className="muted" style={{ fontSize: 12 }}>
          保证：起点深度克隆一致 · 两分支共用同一 RNG 种子 · 仅所选变量不同。
        </div>
      </div>

      {created && (
        <div className="card">
          <h3>分支信息</h3>
          <table>
            <tbody>
              <tr><td className="muted">反事实 ID</td><td>{created.cf_id}</td></tr>
              <tr><td className="muted">基础运行</td><td>{created.run_id}</td></tr>
              <tr><td className="muted">干预</td><td>{MODIFICATIONS.find((m) => m.key === modKey)?.label || modKey}</td></tr>
              <tr><td className="muted">状态</td><td><span className="badge green">{t('status', created.status)}</span></td></tr>
            </tbody>
          </table>
        </div>
      )}

      {comparison && (
        <>
          <div className="card">
            <h3>轨迹对比（分屏：基线 vs 干预后）</h3>
            <div className="grid-2">
              <div>
                <div className="muted" style={{ marginBottom: 6 }}>基线</div>
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2c3a55" />
                    <XAxis dataKey="day" stroke="#8fa0bd" />
                    <YAxis stroke="#8fa0bd" domain={['auto', 'auto']} />
                    <Tooltip contentStyle={{ background: '#1a2233', border: '1px solid #2c3a55', borderRadius: 8 }} />
                    <Line type="monotone" dataKey="baseline" name="基线" stroke="#8fa0bd" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div>
                <div className="muted" style={{ marginBottom: 6 }}>干预后</div>
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2c3a55" />
                    <XAxis dataKey="day" stroke="#8fa0bd" />
                    <YAxis stroke="#8fa0bd" domain={['auto', 'auto']} />
                    <Tooltip contentStyle={{ background: '#1a2233', border: '1px solid #2c3a55', borderRadius: 8 }} />
                    <Line type="monotone" dataKey="modified" name="干预后" stroke="#38c7a4" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div style={{ marginTop: 12 }}>
              <div className="muted" style={{ marginBottom: 6 }}>叠加视图</div>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2c3a55" />
                  <XAxis dataKey="day" stroke="#8fa0bd" />
                  <YAxis stroke="#8fa0bd" domain={['auto', 'auto']} />
                  <Tooltip contentStyle={{ background: '#1a2233', border: '1px solid #2c3a55', borderRadius: 8 }} />
                  <Legend />
                  <Line type="monotone" dataKey="baseline" name="基线" stroke="#8fa0bd" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="modified" name="干预后" stroke="#38c7a4" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card">
            <h3>差异指标汇总</h3>
            <table>
              <thead>
                <tr><th>指标</th><th>数值</th></tr>
              </thead>
              <tbody>
                <tr><td className="muted">基线均值</td><td>{comparison.baseline_mean.toFixed(3)}</td></tr>
                <tr><td className="muted">干预后均值</td><td>{comparison.modified_mean.toFixed(3)}</td></tr>
                <tr><td className="muted">均值差 Δ</td><td>{delta >= 0 ? '+' : ''}{delta.toFixed(3)}</td></tr>
                <tr><td className="muted">效应量 Hedges' g</td><td>{comparison.effect_size_g.toFixed(3)}</td></tr>
                <tr><td className="muted">95% CI</td><td>[{comparison.ci_95[0].toFixed(3)}, {comparison.ci_95[1].toFixed(3)}]</td></tr>
                <tr>
                  <td className="muted">显著性</td>
                  <td>
                    {comparison.ci_95[0] > 0 ? (
                      <span className="badge green">显著（CI 不含 0）</span>
                    ) : (
                      <span className="badge">不显著（CI 含 0）</span>
                    )}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
