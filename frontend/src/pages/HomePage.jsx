import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api.js'
import { t } from '../i18n.js'
import { APP_VERSION_LABEL } from '../version.js'

const CHANNELS = ['teacher_mediated', 'parent_mediated', 'self_study_mediated', 'shadow_edu_mediated', 'direct']
const SCENES = ['school', 'home', 'self_study', 'shadow_edu']
const emptyCustom = () => ({
  label: '', default_channel: 'teacher_mediated', target_scene: 'school',
  effect_achievement: 4.0, evidence_hedges_g: 0.3, cost_yuan: 50,
  exposure_rate: 1.0, action: '',
})

export default function HomePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    n_students: 100, n_teachers: 10, n_parents: 100, sim_days: 90, seed: '',
  })
  const [runIdInput, setRunIdInput] = useState('')
  const [customOpen, setCustomOpen] = useState(false)
  const [customs, setCustoms] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [health, setHealth] = useState(null)
  const [runs, setRuns] = useState([])
  const [runsLoading, setRunsLoading] = useState(false)
  const [progress, setProgress] = useState(null)
  const [startTime, setStartTime] = useState(null)
  const [suggestDesc, setSuggestDesc] = useState('')
  const [suggestBusy, setSuggestBusy] = useState(false)
  const [suggestResult, setSuggestResult] = useState(null)
  const [suggestError, setSuggestError] = useState(null)
  const [elapsed, setElapsed] = useState(0)
  const [latestFindings, setLatestFindings] = useState(null)

  const loadRuns = async () => {
    setRunsLoading(true)
    try {
      const r = await api.listRuns()
      const runList = r.runs || []
      setRuns(runList)
      // Auto-load latest completed run's findings
      const latest = runList.find((r) => r.status === 'completed')
      if (latest && !latestFindings) {
        try {
          const [report, prescreening] = await Promise.all([
            api.getReport(latest.run_id),
            api.getPrescreening(latest.run_id),
          ])
          setLatestFindings({ run: latest, report, prescreening })
        } catch {
          // Silently fail - findings are optional
        }
      }
    } catch {
      /* backend unreachable */
    } finally {
      setRunsLoading(false)
    }
  }

  useEffect(() => { loadRuns() }, [])

  useEffect(() => {
    if (!busy || !startTime) return undefined
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000))
    }, 1000)
    return () => clearInterval(timer)
  }, [busy, startTime])

  const checkHealth = async () => {
    try {
      const h = await api.health()
      setHealth(h.status === 'ok' ? `后端服务运行正常（${APP_VERSION_LABEL} API）` : h.message)
    } catch (e) { setHealth(`后端不可达：${e.message}`) }
  }

  const resetProgress = () => {
    setBusy(false); setProgress(null); setStartTime(null); setElapsed(0)
  }

  const pollRun = (runId) => {
    const poll = async () => {
      try {
        const st = await api.getRun(runId)
        setProgress(st.progress || { percent: 0, stage: '', message: '…' })
        if (st.status === 'completed') {
          navigate(`/runs/${runId}/dashboard`)
          resetProgress()
          return
        }
        if (st.status === 'failed') {
          setError((st.progress && st.progress.message) || '运行失败')
          resetProgress()
          return
        }
        setTimeout(poll, 800)
      } catch (e) { setError(e.message); resetProgress() }
    }
    poll()
  }

  const handleSuggest = async () => {
    if (!suggestDesc.trim()) return
    setSuggestBusy(true); setSuggestError(null); setSuggestResult(null)
    try {
      const res = await api.suggestParams({ description: suggestDesc.trim() })
      setSuggestResult(res)
    } catch (e) { setSuggestError(e.message) }
    finally { setSuggestBusy(false) }
  }

  const applySuggestion = (idx) => {
    if (!suggestResult) return
    const s = suggestResult
    const updated = [...customs]
    if (idx >= updated.length) return
    updated[idx] = {
      ...updated[idx],
      effect_achievement: s.suggested_achievement_effect,
      exposure_rate: s.suggested_exposure_rate,
      evidence_hedges_g: s.suggested_evidence_g,
      cost_yuan: s.suggested_cost_yuan,
      action: s.suggested_action || updated[idx].action,
    }
    setCustoms(updated)
  }

  const createRun = async () => {
    setBusy(true); setError(null)
    setProgress({ percent: 0, stage: 'queued', message: '正在创建运行…' })
    setStartTime(Date.now()); setElapsed(0)
    try {
      const payload = {
        n_students: Number(form.n_students),
        n_teachers: Number(form.n_teachers),
        n_parents: Number(form.n_parents),
        sim_days: Number(form.sim_days),
      }
      if (form.seed !== '' && form.seed !== null && form.seed !== undefined) {
        payload.seed = Number(form.seed)
      }
      const validCustoms = customs
        .filter((c) => c.label && c.label.trim())
        .map((c) => ({
          label: c.label.trim(), default_channel: c.default_channel,
          target_scene: [c.target_scene], effect_achievement: Number(c.effect_achievement),
          exposure_rate: Number(c.exposure_rate), evidence_hedges_g: Number(c.evidence_hedges_g),
          cost_yuan: Number(c.cost_yuan), action: c.action || '',
        }))
      if (validCustoms.length) payload.interventions = validCustoms
      const run = await api.createRun(payload)
      pollRun(run.run_id)
    } catch (e) { setError(e.message); resetProgress() }
  }

  const openRun = () => {
    if (runIdInput.trim()) navigate(`/runs/${runIdInput.trim()}/dashboard`)
  }

  const addCustom = () => setCustoms([...customs, emptyCustom()])
  const removeCustom = (i) => setCustoms(customs.filter((_, idx) => idx !== i))
  const updateCustom = (i, patch) => {
    const updated = [...customs]
    updated[i] = { ...updated[i], ...patch }
    setCustoms(updated)
  }

  const pct = progress ? Math.round(progress.percent || 0) : 0
  const eta = pct >= 5 && elapsed > 0 ? Math.round((elapsed / pct) * (100 - pct)) : null

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px' }}>
      <div className="page-header">
        <h2>虚拟学生试验台 {APP_VERSION_LABEL}</h2>
        <p>多智能体教育仿真平台 · 虚拟预筛 → 真人试验决策支持</p>
      </div>

      {/* === LATEST FINDINGS CARD === */}
      {latestFindings && (
        <div className="card" style={{ background: 'linear-gradient(135deg, #1a2233 0%, #222d42 100%)', border: '1px solid #4f8cff', marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
            <div>
              <h3 style={{ margin: 0, color: '#4f8cff' }}>最新运行关键发现</h3>
              <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                运行 {latestFindings.run.run_id} · {latestFindings.run.n_students} 学生 · {latestFindings.run.sim_days} 天
              </div>
            </div>
            <button className="secondary" style={{ fontSize: 12 }} onClick={() => navigate(`/runs/${latestFindings.run.run_id}/dashboard`)}>
              查看完整摘要 →
            </button>
          </div>
          <div className="row" style={{ gap: 12 }}>
            <div className="stat">
              <span className="v" style={{ color: '#38c7a4' }}>{latestFindings.prescreening.go_count || 0}</span>
              <span className="l">GO</span>
            </div>
            <div className="stat">
              <span className="v" style={{ color: '#f5a623' }}>{latestFindings.prescreening.conditional_count || 0}</span>
              <span className="l">CONDITIONAL</span>
            </div>
            <div className="stat">
              <span className="v" style={{ color: '#ef5b6b' }}>{latestFindings.prescreening.no_go_count || 0}</span>
              <span className="l">NO-GO</span>
            </div>
          </div>
          {(() => {
            const topEs = (latestFindings.report.report_card?.effect_sizes || [])
              .sort((a, b) => Math.abs(b.hedges_g) - Math.abs(a.hedges_g))
              .slice(0, 2)
            if (topEs.length === 0) return null
            return (
              <div style={{ marginTop: 12, fontSize: 13 }}>
                <strong>Top 干预：</strong>
                {topEs.map((es, i) => (
                  <span key={i} style={{ marginRight: 16 }}>
                    {t('intervention', es.intervention_id)} @ {t('scene', es.scene)}: g={es.hedges_g.toFixed(2)}
                  </span>
                ))}
              </div>
            )
          })()}
        </div>
      )}

      {/* === QUICK ACTIONS === */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3>快速操作</h3>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <button onClick={() => document.getElementById('create-form')?.scrollIntoView({ behavior: 'smooth' })}>
            创建新运行
          </button>
          <button className="secondary" onClick={() => navigate('/compare')}>
            运行对比
          </button>
          {latestFindings && (
            <button className="secondary" onClick={() => navigate(`/runs/${latestFindings.run.run_id}/report`)}>
              查看最新报告
            </button>
          )}
          <button className="secondary" onClick={() => navigate('/settings')}>
            大模型配置
          </button>
        </div>
      </div>

      {/* === CREATE RUN FORM === */}
      <div className="card" id="create-form">
        <h3>创建新仿真运行</h3>
        {error && <div className="error-box">{error}</div>}
        <div className="row">
          <div className="field">
            <label>学生数</label>
            <input type="number" min={10} max={5000} value={form.n_students} onChange={(e) => setForm({ ...form, n_students: e.target.value })} />
          </div>
          <div className="field">
            <label>教师数</label>
            <input type="number" min={1} max={500} value={form.n_teachers} onChange={(e) => setForm({ ...form, n_teachers: e.target.value })} />
          </div>
          <div className="field">
            <label>家长数</label>
            <input type="number" min={10} max={5000} value={form.n_parents} onChange={(e) => setForm({ ...form, n_parents: e.target.value })} />
          </div>
          <div className="field">
            <label>模拟天数</label>
            <input type="number" min={1} max={1095} value={form.sim_days} onChange={(e) => setForm({ ...form, sim_days: e.target.value })} />
          </div>
          <div className="field">
            <label>随机种子（留空=真随机）</label>
            <input type="number" value={form.seed} onChange={(e) => setForm({ ...form, seed: e.target.value })} placeholder="42" />
          </div>
        </div>

        <div style={{ marginTop: 12 }}>
          <button className="secondary" onClick={() => setCustomOpen(!customOpen)}>
            {customOpen ? '收起' : '展开'}自定义候选干预
          </button>
        </div>

        {customOpen && (
          <>
            <div style={{ marginTop: 12, borderTop: '1px solid #2c3a55', paddingTop: 12 }}>
              {customs.map((c, i) => (
                <div key={i} className="row" style={{ marginBottom: 8, alignItems: 'flex-end' }}>
                  <div className="field" style={{ flex: 2 }}>
                    <label>干预名称</label>
                    <input value={c.label} placeholder="如：晨读计划" onChange={(e) => updateCustom(i, { label: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>通道</label>
                    <select value={c.default_channel} onChange={(e) => updateCustom(i, { default_channel: e.target.value })}>
                      {CHANNELS.map((ch) => <option key={ch} value={ch}>{ch}</option>)}
                    </select>
                  </div>
                  <div className="field">
                    <label>场景</label>
                    <select value={c.target_scene} onChange={(e) => updateCustom(i, { target_scene: e.target.value })}>
                      {SCENES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                  <div className="field">
                    <label>成绩效果</label>
                    <input type="number" min={-20} max={20} step={0.5} value={c.effect_achievement} onChange={(e) => updateCustom(i, { effect_achievement: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>暴露率</label>
                    <input type="number" min={0} max={1} step={0.05} value={c.exposure_rate} onChange={(e) => updateCustom(i, { exposure_rate: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>证据 g</label>
                    <input type="number" min={-1} max={2} step={0.05} value={c.evidence_hedges_g} onChange={(e) => updateCustom(i, { evidence_hedges_g: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>成本(元)</label>
                    <input type="number" min={0} step={10} value={c.cost_yuan} onChange={(e) => updateCustom(i, { cost_yuan: e.target.value })} />
                  </div>
                  <div className="field" style={{ flex: 2, minWidth: 160 }}>
                    <label>改进动作描述</label>
                    <input value={c.action} placeholder="具体可执行的教学改进动作" onChange={(e) => updateCustom(i, { action: e.target.value })} />
                  </div>
                  <button className="secondary" onClick={() => removeCustom(i)}>删除</button>
                </div>
              ))}
              <div style={{ marginTop: 12, borderTop: '1px solid #e0e0e0', paddingTop: 12 }}>
                <div style={{ fontWeight: 500, marginBottom: 6 }}>LLM 参数建议助手</div>
                <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                  描述你的干预想法，LLM 会建议剂量/暴露率/证据 g 等参数；离线时回退到文献参考。
                </div>
                <div className="row">
                  <div className="field" style={{ flex: 3 }}>
                    <input value={suggestDesc} placeholder="例如：每天增加 20 分钟正念呼吸练习" onChange={(e) => setSuggestDesc(e.target.value)} />
                  </div>
                  <div className="field" style={{ alignSelf: 'flex-end' }}>
                    <button className="secondary" onClick={handleSuggest} disabled={suggestBusy || !suggestDesc.trim()}>
                      {suggestBusy ? '分析中...' : '获取建议'}
                    </button>
                  </div>
                </div>
                {suggestError && <div className="error-box" style={{ marginTop: 6 }}>{suggestError}</div>}
                {suggestResult && (
                  <div style={{ marginTop: 8, background: 'var(--panel-2)', border: '1px solid var(--border)', borderRadius: 6, padding: 10, fontSize: 13 }}>
                    <div style={{ fontWeight: 500, marginBottom: 4 }}>
                      {suggestResult.source === 'llm' ? 'LLM 分析' : '文献参考'}
                      {' '}置信度: {suggestResult.confidence}
                    </div>
                    {suggestResult.fallback_reason && (
                      <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                        {suggestResult.fallback_reason}
                      </div>
                    )}
                    <div>成绩效果: {suggestResult.suggested_achievement_effect} | 动机: {suggestResult.suggested_motivation_effect}</div>
                    <div>暴露率: {suggestResult.suggested_exposure_rate} | 证据 g: {suggestResult.suggested_evidence_g} | 成本: {suggestResult.suggested_cost_yuan}元</div>
                    <div className="muted">来源: {suggestResult.source}{suggestResult.confidence ? ` · 置信度 ${suggestResult.confidence}` : ''}{suggestResult.fallback_reason ? ` · ${suggestResult.fallback_reason}` : ''}</div>
                    {suggestResult.suggested_action && <div>动作: {suggestResult.suggested_action}</div>}
                    {suggestResult.rationale && <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{suggestResult.rationale}</div>}
                    {customs.length > 0 && (
                      <div style={{ marginTop: 6 }}>
                        <span className="muted" style={{ fontSize: 12 }}>应用到: </span>
                        {customs.map((c, i) => c.label && (
                          <button key={i} className="secondary" style={{ fontSize: 11, marginRight: 4 }} onClick={() => applySuggestion(i)}>
                            {c.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
              <button className="secondary" onClick={addCustom}>+ 添加一个候选</button>
            </div>
          </>
        )}

        <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid #2c3a55', display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <button onClick={createRun} disabled={busy} style={{ padding: '10px 32px', fontSize: 15 }}>
            {busy ? '创建中…' : '创建并启动仿真运行'}
          </button>
          <span className="muted" style={{ fontSize: 12 }}>
            参数填好后点此创建；运行会自动出现在下方"历史运行"列表。
          </span>
        </div>
      </div>

      {busy && progress && (
        <div className="card">
          <h3>正在生成仿真运行…</h3>
          <div style={{ background: '#e8e8e8', borderRadius: 6, height: 22, overflow: 'hidden', marginBottom: 10 }}>
            <div style={{ width: `${Math.min(100, pct)}%`, background: '#4a90d9', height: '100%', transition: 'width 0.4s ease', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: 6, color: '#fff', fontSize: 12, boxSizing: 'border-box', minWidth: pct > 0 ? 36 : 0 }}>
              {pct}%
            </div>
          </div>
          <div style={{ fontSize: 13 }}>{progress.message}</div>
          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
            已用时 {elapsed} 秒
            {eta !== null ? ` · 预计还需约 ${eta} 秒` : ' · 进度达 5% 后显示预计剩余时间'}
          </div>
        </div>
      )}

      {/* === HISTORY LIST === */}
      <div className="card">
        <h3>历史运行（{runs.length}）</h3>
        {runsLoading && <div className="loading">加载中…</div>}
        {!runsLoading && runs.length === 0 && (
          <div className="muted">暂无历史运行。创建一个新运行后会自动记录在这里，无需记住运行 ID。</div>
        )}
        {!runsLoading && runs.length > 0 && (
          <table>
            <thead>
              <tr><th>运行 ID</th><th>创建时间</th><th>学生数</th><th>模拟天数</th><th>状态</th><th>操作</th></tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id}>
                  <td>{r.run_id}</td>
                  <td>{(r.created_at || '').replace('T', ' ').slice(0, 19)}</td>
                  <td>{r.n_students}</td>
                  <td>{r.sim_days}</td>
                  <td><span className="badge green">{r.status}</span></td>
                  <td>
                    <button className="secondary" style={{ fontSize: 11, marginRight: 4 }} onClick={() => navigate(`/runs/${r.run_id}/dashboard`)}>
                      摘要
                    </button>
                    <button className="secondary" style={{ fontSize: 11 }} onClick={() => navigate(`/runs/${r.run_id}/report`)}>
                      报告
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div style={{ marginTop: 8 }}>
          <button className="secondary" onClick={loadRuns}>刷新列表</button>
        </div>
      </div>

      {/* === OPEN EXISTING RUN === */}
      <div className="card">
        <h3>打开已有运行</h3>
        <div className="row">
          <div className="field" style={{ flex: 2 }}>
            <label>运行 ID（如 RUN_XXXXXXXX）</label>
            <input value={runIdInput} placeholder="RUN_1A2B3C4D" onChange={(e) => setRunIdInput(e.target.value)} />
          </div>
          <div className="field" style={{ alignSelf: 'flex-end' }}>
            <button className="secondary" onClick={openRun}>打开</button>
          </div>
        </div>
        <div className="muted" style={{ fontSize: 12 }}>
          提示：运行已持久化到后端 data/runs/ 目录，重启后仍可在上方"历史运行"中打开。
        </div>
      </div>
    </div>
  )
}
