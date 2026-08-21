import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  LineChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import api from '../api.js'
import { t } from '../i18n.js'

// 内置兜底清单；运行时优先使用后端 /api/catalog 下发的 YAML 目录。
const FALLBACK_MODIFICATIONS = [
  { key: 'remove_shadow_edu', label: '移除课外班' },
  { key: 'increase_parental_support', label: '增加家长支持' },
  { key: 'forbid_romance', label: '禁止恋爱' },
  { key: 'switch_class', label: '换班' },
  { key: 'add_tutoring', label: '增加家教' },
  { key: 'reduce_homework', label: '减少作业' },
]

export default function CounterfactualPage() {
  const { id } = useParams()
  const [options, setOptions] = useState(FALLBACK_MODIFICATIONS)
  const [modKey, setModKey] = useState(FALLBACK_MODIFICATIONS[0].key)
  const [days, setDays] = useState(30)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [created, setCreated] = useState(null)
  const [comparison, setComparison] = useState(null)
  const [useCustom, setUseCustom] = useState(false)
  const [customEffects, setCustomEffects] = useState({
    shadow_hours_multiplier: 1.0,
    parent_support_delta: 0.0,
    tutoring_hours_delta: 0.0,
    homework_multiplier: 1.0,
  })

  useEffect(() => {
    // 反事实变量清单由 YAML 目录（单一事实来源）下发；失败时保留内置兜底。
    api
      .getCatalog()
      .then((cat) => {
        const list = (cat.counterfactuals || []).filter((m) => m && m.key)
        if (list.length) {
          setOptions(list)
          setModKey((cur) =>
            list.some((m) => m.key === cur) ? cur : list[0].key,
          )
        }
      })
      .catch(() => {})
  }, [])

  const createBranch = async () => {
    setBusy(true)
    setError(null)
    setComparison(null)
    setCreated(null)
    try {
      const payload = { days: Number(days) }
      if (useCustom) {
        payload.custom_effects = {}
        for (const [k, v] of Object.entries(customEffects)) {
          const n = Number(v)
          if (!isNaN(n) && n !== 0 && n !== 1) {
            payload.custom_effects[k] = n
          }
        }
        if (Object.keys(payload.custom_effects).length === 0) {
          setError('请至少修改一个假设变量（值不能为默认值）')
          setBusy(false)
          return
        }
        payload.modification = {}
      } else {
        payload.modification = { [modKey]: true }
      }
      const res = await api.createCounterfactual(id, payload)
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
    ? comparison.trajectory_baseline.map((v, i) => {
        const baseline = Number(v.toFixed(2))
        const modified = Number(comparison.trajectory_modified[i]?.toFixed(2) ?? 0)
        return {
          day: i,
          baseline,
          modified,
          diff: Math.abs(modified - baseline),
        }
      })
    : []

  const delta = comparison ? comparison.modified_mean - comparison.baseline_mean : 0

  return (
    <div>
      <div className="page-header">
        <h2>假设推演（What-If）</h2>
        <p>同一起点 + 固定种子 · 单变量分流 · 基线 vs 假设条件下的轨迹对比</p>
      </div>

      <div className="card">
        <h3>创建假设分支</h3>
        {error && <div className="error-box">{error}</div>}
        <div className="row">
          <div className="field">
            <label>干预变量（单变量分流）</label>
            <select value={modKey} onChange={(e) => setModKey(e.target.value)}>
              {options.map((m) => (
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
      
        <div style={{ marginTop: 12, borderTop: '1px solid #2c3a55', paddingTop: 12 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input type="checkbox" checked={useCustom} onChange={(e) => setUseCustom(e.target.checked)} />
            <span>自定义反事实变量（研究者自由设定效果值）</span>
          </label>
          {useCustom && (
            <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div className="field">
                <label>课外学习时间乘数 (0=完全移除)</label>
                <input type="number" min={0} max={2} step={0.1}
                  value={customEffects.shadow_hours_multiplier}
                  onChange={(e) => setCustomEffects({...customEffects, shadow_hours_multiplier: e.target.value})} />
              </div>
              <div className="field">
                <label>家长支持增量 (-1 ~ +1)</label>
                <input type="number" min={-1} max={1} step={0.05}
                  value={customEffects.parent_support_delta}
                  onChange={(e) => setCustomEffects({...customEffects, parent_support_delta: e.target.value})} />
              </div>
              <div className="field">
                <label>家教时数增量 (小时/周)</label>
                <input type="number" min={-6} max={10} step={0.5}
                  value={customEffects.tutoring_hours_delta}
                  onChange={(e) => setCustomEffects({...customEffects, tutoring_hours_delta: e.target.value})} />
              </div>
              <div className="field">
                <label>作业负担乘数 (0.5=减半)</label>
                <input type="number" min={0} max={2} step={0.1}
                  value={customEffects.homework_multiplier}
                  onChange={(e) => setCustomEffects({...customEffects, homework_multiplier: e.target.value})} />
              </div>
            </div>
          )}
        </div></div>

      {created && (
        <div className="card">
          <h3>分支信息</h3>
          <table>
            <tbody>
              <tr><td className="muted">假设分支 ID</td><td>{created.cf_id}</td></tr>
              <tr><td className="muted">基础运行</td><td>{created.run_id}</td></tr>
              <tr><td className="muted">干预</td><td>{useCustom ? '自定义变量' : (options.find((m) => m.key === modKey)?.label || modKey)}</td></tr>
              <tr><td className="muted">状态</td><td><span className="badge green">{t('status', created.status)}</span></td></tr>
            </tbody>
          </table>
        </div>
      )}

      {comparison && (
        <>
          <div className="card">
          <h3>叠加对比（双轴 + 差异阴影）</h3>
          <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
            左轴：基线轨迹（灰色）；右轴：干预后轨迹（绿色）；阴影区：差异大小
          </div>
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={chartData} margin={{ top: 20, right: 60, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2c3a55" />
              <XAxis dataKey="day" stroke="#8fa0bd" label={{ value: '天数', position: 'insideBottomRight', offset: -5, fill: '#8fa0bd' }} />
              <YAxis yAxisId="left" stroke="#8fa0bd" label={{ value: '基线成绩', angle: -90, position: 'insideLeft', fill: '#8fa0bd' }} />
              <YAxis yAxisId="right" orientation="right" stroke="#38c7a4" label={{ value: '干预后成绩', angle: 90, position: 'insideRight', fill: '#38c7a4' }} />
              <Tooltip contentStyle={{ background: '#1a2233', border: '1px solid #2c3a55', borderRadius: 8 }} />
              <Legend />
              <Area yAxisId="left" type="monotone" dataKey="diff" fill="rgba(79, 140, 255, 0.2)" stroke="none" name="差异" />
              <Line yAxisId="left" type="monotone" dataKey="baseline" name="基线" stroke="#8fa0bd" dot={false} strokeWidth={2} />
              <Line yAxisId="right" type="monotone" dataKey="modified" name="干预后" stroke="#38c7a4" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
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
                {comparison.ancova_g != null && (
                  <>
                    <tr><td className="muted">ANCOVA 调整 g</td><td>{comparison.ancova_g.toFixed(3)}</td></tr>
                    <tr><td className="muted">ANCOVA 95% CI</td><td>[{comparison.ancova_ci_95[0].toFixed(3)}, {comparison.ancova_ci_95[1].toFixed(3)}]</td></tr>
                    <tr><td className="muted">ANCOVA 调整均值差</td><td>{comparison.ancova_adjusted_diff.toFixed(3)}</td></tr>
                  </>
                )}
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
