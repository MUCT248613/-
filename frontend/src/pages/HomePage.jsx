import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api.js'

export default function HomePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    n_students: 100,
    n_teachers: 10,
    n_parents: 100,
    sim_days: 90,
    seed: '',
  })
  const [runIdInput, setRunIdInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [health, setHealth] = useState(null)
  const [runs, setRuns] = useState([])
  const [runsLoading, setRunsLoading] = useState(false)
  // Live progress of the run being created ({percent, stage, message}).
  const [progress, setProgress] = useState(null)
  const [startTime, setStartTime] = useState(null)
  const [elapsed, setElapsed] = useState(0)

  const loadRuns = async () => {
    setRunsLoading(true)
    try {
      const r = await api.listRuns()
      setRuns(r.runs || [])
    } catch {
      /* backend unreachable; the health card reports connectivity */
    } finally {
      setRunsLoading(false)
    }
  }

  useEffect(() => {
    loadRuns()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Tick a 1s timer while a run is being created so the elapsed / ETA display
  // stays live alongside the backend-reported percentage.
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
      setHealth(h.status === 'ok' ? '后端服务运行正常（v5.0 API）' : h.message)
    } catch (e) {
      setHealth(`后端不可达：${e.message}`)
    }
  }

  const resetProgress = () => {
    setBusy(false)
    setProgress(null)
    setStartTime(null)
    setElapsed(0)
  }

  // Poll the run status until it completes / fails, mirroring the backend's
  // live progress (percent + stage message) into the progress bar.
  const pollRun = (runId) => {
    const poll = async () => {
      try {
        const st = await api.getRun(runId)
        setProgress(st.progress || { percent: 0, stage: '', message: '…' })
        if (st.status === 'completed') {
          navigate(`/runs/${runId}/personas`)
          resetProgress()
          return
        }
        if (st.status === 'failed') {
          setError((st.progress && st.progress.message) || '运行失败')
          resetProgress()
          return
        }
        setTimeout(poll, 800)
      } catch (e) {
        setError(e.message)
        resetProgress()
      }
    }
    poll()
  }

  const createRun = async () => {
    setBusy(true)
    setError(null)
    setProgress({ percent: 0, stage: 'queued', message: '正在创建运行…' })
    setStartTime(Date.now())
    setElapsed(0)
    try {
      const payload = {
        n_students: Number(form.n_students),
        n_teachers: Number(form.n_teachers),
        n_parents: Number(form.n_parents),
        sim_days: Number(form.sim_days),
      }
      // 留空 = 真随机（后端每次随机取种子）；填入种子则可复现。
      if (form.seed !== '' && form.seed !== null && form.seed !== undefined) {
        payload.seed = Number(form.seed)
      }
      const run = await api.createRun(payload)
      // The backend now builds the run asynchronously and returns immediately
      // with status="running"; poll until it completes. (The synchronous test
      // path returns "completed" directly and navigates at once.)
      if (run.status === 'completed') {
        navigate(`/runs/${run.run_id}/personas`)
        resetProgress()
        return
      }
      pollRun(run.run_id)
    } catch (e) {
      setError(e.message)
      resetProgress()
    }
  }

  const openRun = () => {
    if (runIdInput.trim()) navigate(`/runs/${runIdInput.trim()}/personas`)
  }

  // Simple linear ETA from elapsed time and the backend-reported percentage.
  // Only shown once progress has advanced enough for a stable estimate.
  const pct = (progress && progress.percent) || 0
  const eta = pct >= 5 ? Math.max(0, Math.round((elapsed / pct) * (100 - pct))) : null

  return (
    <div className="main" style={{ maxWidth: 860, margin: '0 auto' }}>
      <div className="page-header">
        <h2>虚拟学生试验台 v5.0</h2>
        <p>教育 AI 多智能体仿真平台 · 后端端口 6668 · 前端端口 4000</p>
      </div>

      <div className="card">
        <h3>后端状态</h3>
        <button className="secondary" onClick={checkHealth}>
          检测后端 /api/health
        </button>
        <button className="secondary" style={{ marginLeft: 8 }} onClick={() => navigate('/settings')}>
          ⚙ 大模型配置
        </button>
        {health && <div style={{ marginTop: 10 }} className="muted">{health}</div>}
      </div>

      <div className="card">
        <h3>创建新的仿真运行</h3>
        {error && <div className="error-box">{error}</div>}
        <div className="row">
          <div className="field">
            <label>学生数 (1-5000)</label>
            <input
              type="number"
              value={form.n_students}
              min={1}
              max={5000}
              onChange={(e) => setForm({ ...form, n_students: e.target.value })}
            />
          </div>
          <div className="field">
            <label>教师数 (1-500)</label>
            <input
              type="number"
              value={form.n_teachers}
              min={1}
              max={500}
              onChange={(e) => setForm({ ...form, n_teachers: e.target.value })}
            />
          </div>
          <div className="field">
            <label>家长数 (1-5000)</label>
            <input
              type="number"
              value={form.n_parents}
              min={1}
              max={5000}
              onChange={(e) => setForm({ ...form, n_parents: e.target.value })}
            />
          </div>
        </div>
        <div className="row">
          <div className="field">
            <label>模拟天数 (1-1095)</label>
            <input
              type="number"
              value={form.sim_days}
              min={1}
              max={1095}
              onChange={(e) => setForm({ ...form, sim_days: e.target.value })}
            />
          </div>
          <div className="field">
            <label>随机种子（留空=每次随机）</label>
            <input
              type="number"
              value={form.seed}
              placeholder="留空 = 真随机"
              onChange={(e) => setForm({ ...form, seed: e.target.value })}
            />
          </div>
          <div className="field" style={{ alignSelf: 'flex-end' }}>
            <button onClick={createRun} disabled={busy}>
              {busy ? '创建中…' : '创建并进入'}
            </button>
          </div>
        </div>
      </div>

      {busy && progress && (
        <div className="card">
          <h3>正在生成仿真运行…</h3>
          <div style={{ background: '#e8e8e8', borderRadius: 6, height: 22, overflow: 'hidden', marginBottom: 10 }}>
            <div
              style={{
                width: `${Math.min(100, pct)}%`,
                background: '#4a90d9',
                height: '100%',
                transition: 'width 0.4s ease',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                paddingRight: 6,
                color: '#fff',
                fontSize: 12,
                boxSizing: 'border-box',
                minWidth: pct > 0 ? 36 : 0,
              }}
            >
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

      <div className="card">
        <h3>历史运行（{runs.length}）</h3>
        {runsLoading && <div className="loading">加载中…</div>}
        {!runsLoading && runs.length === 0 && (
          <div className="muted">暂无历史运行。创建一个新运行后会自动记录在这里，无需记住运行 ID。</div>
        )}
        {!runsLoading && runs.length > 0 && (
          <table>
            <thead>
              <tr><th>运行 ID</th><th>创建时间</th><th>学生数</th><th>模拟天数</th><th>状态</th></tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id} className="clickable" onClick={() => navigate(`/runs/${r.run_id}/personas`)}>
                  <td>{r.run_id}</td>
                  <td>{(r.created_at || '').replace('T', ' ').slice(0, 19)}</td>
                  <td>{r.n_students}</td>
                  <td>{r.sim_days}</td>
                  <td>{r.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div style={{ marginTop: 8 }}>
          <button className="secondary" onClick={loadRuns}>刷新列表</button>
          <span className="muted" style={{ fontSize: 12, marginLeft: 8 }}>点击任意一行进入该运行</span>
        </div>
      </div>

      <div className="card">
        <h3>打开已有运行</h3>
        <div className="row">
          <div className="field" style={{ flex: 2 }}>
            <label>运行 ID（如 RUN_XXXXXXXX）</label>
            <input
              value={runIdInput}
              placeholder="RUN_1A2B3C4D"
              onChange={(e) => setRunIdInput(e.target.value)}
            />
          </div>
          <div className="field" style={{ alignSelf: 'flex-end' }}>
            <button className="secondary" onClick={openRun}>
              打开
            </button>
          </div>
        </div>
        <div className="muted" style={{ fontSize: 12 }}>
          提示：运行已持久化到后端 data/runs/ 目录，重启后仍可在上方“历史运行”中打开。
        </div>
      </div>
    </div>
  )
}
