import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  LineChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import api from '../api.js'
import { t } from '../i18n.js'

// 内置兜底清单；运行时优先使用后端 /api/catalog 下发的 YAML 目录。
const FALLBACK_MODIFICATIONS = [
  { key: 'remove_shadow_edu', label: '移除课外班', effects: { shadow_hours_multiplier: 0 } },
  { key: 'increase_parental_support', label: '增加家长支持', effects: { parent_support_delta: 0.3 } },
  { key: 'forbid_romance', label: '禁止恋爱', effects: { romance_enabled: false } },
  { key: 'switch_class', label: '换班', effects: { class_switch: true } },
  { key: 'add_tutoring', label: '增加家教', effects: { tutoring_hours_delta: 3 } },
  { key: 'reduce_homework', label: '减少作业', effects: { homework_multiplier: 0.5 } },
  { key: 'boost_motivation', label: '提升学习动机', effects: { motivation_delta: 0.25 } },
  { key: 'improve_sleep', label: '改善睡眠与精力', effects: { fatigue_delta: -15, stress_delta: -8, emotion_delta: 8 } },
  { key: 'intensive_teacher_support', label: '加强教师支持', effects: { motivation_delta: 0.15, parent_support_delta: 0.15, achievement_rate_delta: 0.08 } },
  { key: 'reduce_stress', label: '减轻学业压力', effects: { stress_delta: -15, fatigue_delta: -8, motivation_delta: 0.1 } },
  { key: 'increase_study_time', label: '增加自主学习时间', effects: { shadow_hours_multiplier: 1.25, tutoring_hours_delta: 1.5, achievement_rate_delta: 0.05 } },
]

const CUSTOM_FIELDS = [
  { key: 'achievement_rate_delta', label: '每日成绩增益调整（分/天）', min: -0.2, max: 0.2, step: 0.01, defaultValue: 0 },
  { key: 'motivation_delta', label: '学习动机增量（-1 ~ +1）', min: -1, max: 1, step: 0.05, defaultValue: 0 },
  { key: 'parent_support_delta', label: '家长支持增量（-0.5 ~ +0.5）', min: -0.5, max: 0.5, step: 0.05, defaultValue: 0 },
  { key: 'shadow_hours_multiplier', label: '课外学习时间乘数（0 ~ 1.5）', min: 0, max: 1.5, step: 0.1, defaultValue: 1 },
  { key: 'tutoring_hours_delta', label: '家教时数增量（-3 ~ +4 小时/周）', min: -3, max: 4, step: 0.5, defaultValue: 0 },
  { key: 'homework_multiplier', label: '作业负担乘数（0.5 ~ 1.5）', min: 0.5, max: 1.5, step: 0.1, defaultValue: 1 },
  { key: 'fatigue_delta', label: '疲劳调整（-20 ~ +20 分）', min: -20, max: 20, step: 1, defaultValue: 0 },
  { key: 'stress_delta', label: '压力调整（-20 ~ +20 分）', min: -20, max: 20, step: 1, defaultValue: 0 },
  { key: 'emotion_delta', label: '情绪调整（-20 ~ +20 分）', min: -20, max: 20, step: 1, defaultValue: 0 },
]

const EFFECT_LABELS = {
  achievement_rate_delta: '每日成绩增益',
  achievement_delta: '每日成绩增益（兼容旧配置）',
  motivation_delta: '学习动机',
  parent_support_delta: '家长支持',
  shadow_hours_multiplier: '课外学习时间',
  tutoring_hours_delta: '家教时数',
  homework_multiplier: '作业负担',
  fatigue_delta: '疲劳',
  stress_delta: '压力',
  emotion_delta: '情绪',
  romance_enabled: '恋爱活动',
  class_switch: '班级关系',
}

export default function CounterfactualPage() {
  const { id } = useParams()
  const [students, setStudents] = useState([])
  const [scope, setScope] = useState('cohort')
  const [studentId, setStudentId] = useState('')
  const [options, setOptions] = useState(FALLBACK_MODIFICATIONS)
  const [modKey, setModKey] = useState(FALLBACK_MODIFICATIONS[0].key)
  const [days, setDays] = useState(30)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [created, setCreated] = useState(null)
  const [comparison, setComparison] = useState(null)
  const [useCustom, setUseCustom] = useState(false)
  const [customEffects, setCustomEffects] = useState(
    Object.fromEntries(CUSTOM_FIELDS.map((f) => [f.key, f.defaultValue])),
  )

  useEffect(() => {
    api.listStudents(id, 1, 100)
      .then((res) => {
        const list = res.students || []
        setStudents(list)
        if (list.length) setStudentId((current) => current || list[0].student_id)
      })
      .catch(() => {})
  }, [id])

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
      if (scope === 'student' && studentId) payload.student_id = studentId
      if (useCustom) {
        payload.custom_effects = {}
        for (const field of CUSTOM_FIELDS) {
          const k = field.key
          const v = customEffects[k]
          const n = Number(v)
          if (!isNaN(n) && n !== field.defaultValue) {
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

  // The headline delta is the end-of-horizon change; the trajectory-average
  // delta is shown separately because averaging early, pre-effect days dilutes
  // the accumulated intervention impact.
  const delta = comparison
    ? (comparison.final_delta ?? (comparison.trajectory_modified.at(-1) - comparison.trajectory_baseline.at(-1)))
    : 0
  const averageDelta = comparison
    ? (comparison.average_delta ?? (comparison.modified_mean - comparison.baseline_mean))
    : 0
  const resultScope = comparison?.scope || created?.scope || scope
  const resultStudentId = comparison?.student_id || created?.student_id || studentId

  return (
    <div>
      <div className="page-header">
        <h2>假设推演（What-If）</h2>
        <p>同一起点 + 固定种子 · 单变量分流 · 基线 vs 假设条件下的轨迹对比</p>
      </div>

      <div className="card">
        <h3>创建假设分支</h3>
        {error && <div className="error-box">{error}</div>}
        <div className="tabs" style={{ marginBottom: 12 }}>
          <button className={scope === 'cohort' ? 'active' : ''} onClick={() => { setScope('cohort'); setComparison(null); setCreated(null) }}>
            群体平均
          </button>
          <button className={scope === 'student' ? 'active' : ''} onClick={() => { setScope('student'); setComparison(null); setCreated(null) }}>
            单个学生
          </button>
        </div>
        {scope === 'student' && (
          <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: 12 }}>
            <div className="field" style={{ minWidth: 280, marginBottom: 0 }}>
            <label>选择学生</label>
              <select value={studentId} onChange={(e) => { setStudentId(e.target.value); setComparison(null); setCreated(null) }} disabled={!students.length}>
                {students.map((student) => (
                  <option key={student.student_id} value={student.student_id}>
                    {student.student_id} · {student.name || '未命名'}
                  </option>
                ))}
              </select>
            </div>
            {(() => {
              const student = students.find((item) => item.student_id === studentId)
              if (!student) return null
              return (
                <div className="muted" style={{ fontSize: 12, lineHeight: 1.8 }}>
                  运行起点 {Number(student.baseline_achievement_score ?? student.achievement_score ?? 0).toFixed(1)}
                  {' · '}当前成绩 {Number(student.achievement_score || 0).toFixed(1)}
                  {' · '}动机 {Number(student.motivation_level || 0).toFixed(2)}
                  {student.grade ? ` · ${student.grade}` : ''}
                </div>
              )
            })()}
          </div>
        )}
        <div className="row">
          <div className="field">
            <label>干预变量（单变量分流）</label>
            <select value={modKey} onChange={(e) => setModKey(e.target.value)}>
              {options.map((m) => (
                <option key={m.key} value={m.key}>{m.label}</option>
              ))}
            </select>
          </div>
          {!useCustom && options.find((m) => m.key === modKey)?.effects && (
            <div className="field" style={{ minWidth: 280 }}>
              <label>本分支预期改变</label>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {Object.entries(options.find((m) => m.key === modKey).effects).map(([k, v]) => (
                  <span className="badge green" key={k}>{EFFECT_LABELS[k] || k}: {String(v)}</span>
                ))}
              </div>
            </div>
          )}
          <div className="field">
            <label>模拟天数 (1-365)</label>
            <input type="number" min={1} max={365} value={days} onChange={(e) => setDays(e.target.value)} />
          </div>
          <div className="field" style={{ alignSelf: 'flex-end' }}>
            <button onClick={createBranch} disabled={busy || (scope === 'student' && !studentId)}>
              {busy ? '分流中…' : '创建并对比'}
            </button>
          </div>
        </div>
        <div className="muted" style={{ fontSize: 12 }}>
          保证：起点深度克隆一致 · 两分支共用同一 RNG 种子 · 仅所选变量不同。成绩增益采用每日调整并带边际递减，不会瞬间跳到满分。
        </div>
      
        <div style={{ marginTop: 12, borderTop: '1px solid #2c3a55', paddingTop: 12 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input type="checkbox" checked={useCustom} onChange={(e) => setUseCustom(e.target.checked)} />
            <span>自定义反事实变量（研究者自由设定效果值）</span>
          </label>
          {useCustom && (
            <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 8 }}>
              {CUSTOM_FIELDS.map((field) => (
                <div className="field" key={field.key}>
                  <label>{field.label}</label>
                  <input type="number" min={field.min} max={field.max} step={field.step}
                    value={customEffects[field.key]}
                    onChange={(e) => {
                      const raw = e.target.value
                      if (raw === '') {
                        setCustomEffects({ ...customEffects, [field.key]: raw })
                        return
                      }
                      const number = Number(raw)
                      const value = Number.isFinite(number)
                        ? Math.min(field.max, Math.max(field.min, number))
                        : raw
                      setCustomEffects({ ...customEffects, [field.key]: value })
                    }} />
                </div>
              ))}
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
              <tr><td className="muted">分析范围</td><td>{created.scope === 'student' ? `单个学生 · ${created.student_id}` : '群体平均'}</td></tr>
              <tr><td className="muted">干预</td><td>{useCustom ? '自定义变量' : (options.find((m) => m.key === modKey)?.label || modKey)}</td></tr>
              <tr><td className="muted">状态</td><td><span className="badge green">{t('status', created.status)}</span></td></tr>
            </tbody>
          </table>
        </div>
      )}

      {comparison && (
        <>
          {scope === 'student' && comparison.scope !== 'student' && (
            <div className="error-box">
              后端返回的分析范围与当前选择不一致，已拒绝展示群体平均结果。请重启后端服务后重试。
            </div>
          )}
          <div className="row" style={{ marginBottom: 16 }}>
            <div className="card stat"><span className="v">{comparison.baseline_mean.toFixed(2)}</span><span className="l">{resultScope === 'student' ? `学生 ${resultStudentId} 基线平均成绩` : '基线平均成绩'}</span></div>
            <div className="card stat"><span className="v" style={{ color: '#38c7a4' }}>{comparison.modified_mean.toFixed(2)}</span><span className="l">{resultScope === 'student' ? '该学生假设平均成绩' : '假设条件平均成绩'}</span></div>
            <div className="card stat"><span className="v" style={{ color: delta >= 0 ? '#38c7a4' : '#ef5b6b' }}>{delta >= 0 ? '+' : ''}{delta.toFixed(2)}</span><span className="l">{resultScope === 'student' ? '该学生末日成绩变化 Δ' : '末日成绩变化 Δ'}</span></div>
            <div className="card stat"><span className="v" style={{ color: averageDelta >= 0 ? '#38c7a4' : '#ef5b6b' }}>{averageDelta >= 0 ? '+' : ''}{averageDelta.toFixed(2)}</span><span className="l">全程轨迹平均变化 Δ</span></div>
          </div>
          <div className="card">
          <h3>{resultScope === 'student' ? '个体轨迹对比（统一成绩轴）' : '叠加对比（统一成绩轴 + 差异阴影）'}</h3>
          <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
            两条曲线共用 0–100 成绩轴；灰色为基线，绿色为假设条件；阴影区表示逐日差异绝对值
          </div>
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={chartData} margin={{ top: 20, right: 60, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2c3a55" />
              <XAxis dataKey="day" stroke="#8fa0bd" label={{ value: '天数', position: 'insideBottomRight', offset: -5, fill: '#8fa0bd' }} />
              <YAxis domain={[0, 100]} stroke="#8fa0bd" label={{ value: '成绩（0-100）', angle: -90, position: 'insideLeft', fill: '#8fa0bd' }} />
              <Tooltip contentStyle={{ background: '#1a2233', border: '1px solid #2c3a55', borderRadius: 8 }} />
              <Legend />
              <Area type="monotone" dataKey="diff" fill="rgba(79, 140, 255, 0.16)" stroke="none" name="逐日差异绝对值" />
              <Line type="monotone" dataKey="baseline" name="基线" stroke="#8fa0bd" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="modified" name="假设条件" stroke="#38c7a4" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
          <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
            末日 Δ = 模拟结束日假设成绩 − 基线成绩；全程平均 Δ 对所有模拟日取平均。两条曲线同时向上只说明成绩随时间增长，不代表 Δ 为正。
            {resultScope === 'student' && ' 个体结果用于案例观察，不代表群体平均因果效应。'}
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
                <tr><td className="muted">全程平均成绩差 Δ</td><td>{averageDelta >= 0 ? '+' : ''}{averageDelta.toFixed(3)}</td></tr>
                <tr><td className="muted">末日基线成绩</td><td>{(comparison.baseline_final ?? comparison.trajectory_baseline.at(-1)).toFixed(3)}</td></tr>
                <tr><td className="muted">末日假设成绩</td><td>{(comparison.modified_final ?? comparison.trajectory_modified.at(-1)).toFixed(3)}</td></tr>
                <tr><td className="muted">末日成绩差 Δ</td><td>{delta >= 0 ? '+' : ''}{delta.toFixed(3)}</td></tr>
                {resultScope !== 'student' && <>
                  <tr><td className="muted">效应量 Hedges' g</td><td>{comparison.effect_size_g.toFixed(3)}</td></tr>
                  <tr><td className="muted">95% CI</td><td>[{comparison.ci_95[0].toFixed(3)}, {comparison.ci_95[1].toFixed(3)}]</td></tr>
                </>}
                {resultScope !== 'student' && comparison.ancova_g != null && (
                  <>
                    <tr><td className="muted">ANCOVA 调整 g</td><td>{comparison.ancova_g.toFixed(3)}</td></tr>
                    <tr><td className="muted">ANCOVA 95% CI</td><td>[{comparison.ancova_ci_95[0].toFixed(3)}, {comparison.ancova_ci_95[1].toFixed(3)}]</td></tr>
                    <tr><td className="muted">ANCOVA 调整均值差</td><td>{comparison.ancova_adjusted_diff.toFixed(3)}</td></tr>
                  </>
                )}
                <tr>
                  <td className="muted">显著性</td>
                  <td>
                    {resultScope === 'student' ? (
                      <span className="badge">个体案例，不进行显著性判断</span>
                    ) : comparison.ci_95[0] > 0 ? (
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
