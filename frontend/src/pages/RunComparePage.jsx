import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import api from '../api.js'
import { t } from '../i18n.js'

export default function RunComparePage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [runs, setRuns] = useState([])
  const [selected, setSelected] = useState([])
  const [compareData, setCompareData] = useState(null)
  const [robustnessFilter, setRobustnessFilter] = useState('none')

  useEffect(() => {
    api.listRuns()
      .then((r) => {
        setRuns(r.runs || [])
        setLoading(false)
      })
      .catch((e) => {
        setError(e.message)
        setLoading(false)
      })
  }, [])

  const toggleRun = (runId) => {
    if (selected.includes(runId)) {
      setSelected(selected.filter((id) => id !== runId))
    } else if (selected.length < 3) {
      setSelected([...selected, runId])
    }
  }

  const loadComparison = async () => {
    if (selected.length < 2) {
      setError('\u8bf7\u81f3\u5c11\u9009\u62e9 2 \u4e2a\u8fd0\u884c')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const reports = await Promise.all(
        selected.map((id) => api.getReport(id))
      )
      const prescreenings = await Promise.all(
        selected.map((id) => api.getPrescreening(id))
      )
      setCompareData({ reports, prescreenings })
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // Build comparison chart data
  const buildChartData = () => {
    if (!compareData) return []
    const allInterventions = new Set()
    compareData.reports.forEach((r) => {
      (r.report_card?.effect_sizes || []).forEach((es) => {
        allInterventions.add(t('intervention', es.intervention_id))
      })
    })
    const data = []
    allInterventions.forEach((intvName) => {
      const row = { name: intvName }
      compareData.reports.forEach((r, idx) => {
        const es = (r.report_card?.effect_sizes || []).find(
          (e) => t('intervention', e.intervention_id) === intvName
        )
        row[`run${idx}`] = es ? es.hedges_g : null
      })
      data.push(row)
    })
    return data
  }

  const chartData = buildChartData()
  const COLORS = ['#4f8cff', '#38c7a4', '#f5a623']


  const getRunLabel = (runId) => {
    if (robustnessFilter === 'none') return runId
    const run = runs.find(r => r.run_id === runId)
    if (!run) return runId
    if (robustnessFilter === 'seed') {
      return `种子 ${run.config?.seed || '?'}`
    }
    if (robustnessFilter === 'sample') {
      return `n=${run.n_students || '?'}`
    }
    return runId
  }
  if (loading && !runs.length) return <div className="loading">{'\u52a0\u8f7d\u4e2d...'}</div>
  if (error && !runs.length) return <div className="error-box">{error}</div>

  return (
    <div>
      <div className="page-header">
        <h2>{'\u{1f4ca} \u8fd0\u884c\u5bf9\u6bd4'}</h2>
        <p>{'\u9009\u62e9 2-3 \u4e2a\u8fd0\u884c\uff0c\u5e76\u6392\u5c55\u793a\u6548\u5e94\u91cf\u3001\u51b3\u7b56\u7ed3\u679c\u3001\u6210\u672c\u6548\u7387'}</p>
      </div>

      {/* Run selection */}
      <div className="card">
        <h3>{'\u9009\u62e9\u8fd0\u884c\uff08\u6700\u591a 3 \u4e2a\uff09'}</h3>
        <div style={{ maxHeight: 300, overflowY: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>{'\u9009\u62e9'}</th>
                <th>{'\u8fd0\u884c ID'}</th>
                <th>{'\u521b\u5efa\u65f6\u95f4'}</th>
                <th>{'\u5b66\u751f\u6570'}</th>
                <th>{'\u6a21\u62df\u5929\u6570'}</th>
                <th>{'\u72b6\u6001'}</th>
              </tr>
            </thead>
            <tbody>
              {runs.slice(0, 20).map((r) => (
                <tr key={r.run_id} className="clickable" onClick={() => toggleRun(r.run_id)}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.includes(r.run_id)}
                      onChange={() => {}}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </td>
                  <td>{r.run_id}</td>
                  <td>{(r.created_at || '').replace('T', ' ').slice(0, 19)}</td>
                  <td>{r.n_students}</td>
                  <td>{r.sim_days}</td>
                  <td><span className="badge green">{r.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ marginTop: 12, display: 'flex', gap: 12 }}>
          <button onClick={loadComparison} disabled={selected.length < 2 || loading}>
            {'\u{1f50d} \u5f00\u59cb\u5bf9\u6bd4'}
          </button>
          <button className="secondary" onClick={() => navigate('/')}>
            {'\u{1f3e0} \u8fd4\u56de\u9996\u9875'}
          </button>
        </div>
        {error && <div className="error-box" style={{ marginTop: 12 }}>{error}</div>}
      </div>


      {/* Robustness filter */}
      {compareData && (
        <div className="card">
          <h3>{'\u{1f52c} \u7a33\u5065\u6027\u89c6\u89d2'}</h3>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <button
              className={robustnessFilter === 'none' ? '' : 'secondary'}
              onClick={() => setRobustnessFilter('none')}
            >
              {'\u9ed8\u8ba4\u89c6\u56fe'}
            </button>
            <button
              className={robustnessFilter === 'seed' ? '' : 'secondary'}
              onClick={() => setRobustnessFilter('seed')}
            >
              {'\u{1f3b2} \u6309\u79cd\u5b50\u5206\u7ec4'}
            </button>
            <button
              className={robustnessFilter === 'sample' ? '' : 'secondary'}
              onClick={() => setRobustnessFilter('sample')}
            >
              {'\u{1f4ca} \u6309\u6837\u672c\u91cf\u5206\u7ec4'}
            </button>
          </div>
          {robustnessFilter !== 'none' && (
            <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              {robustnessFilter === 'seed'
                ? '\u6309\u968f\u673a\u79cd\u5b50\u5206\u7ec4\u663e\u793a\uff0c\u68c0\u67e5\u7ed3\u8bba\u662f\u5426\u4f9d\u8d56\u4e8e\u7279\u5b9a\u7684\u968f\u673a\u6570\u5e8f\u5217'
                : '\u6309\u5b66\u751f\u6570\u5206\u7ec4\u663e\u793a\uff0c\u68c0\u67e5\u6548\u5e94\u91cf\u662f\u5426\u968f\u6837\u672c\u91cf\u53d8\u5316\u800c\u8d8b\u4e8e\u7a33\u5b9a'}
            </div>
          )}
        </div>
      )}
      {/* Comparison results */}
      {compareData && (
        <>
          {/* Effect sizes comparison chart */}
          <div className="card">
            <h3>{'\u6548\u5e94\u91cf\u5bf9\u6bd4\uff08Hedges\u2019 g\uff09'}</h3>
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2c3a55" />
                  <XAxis dataKey="name" stroke="#8fa0bd" />
                  <YAxis stroke="#8fa0bd" label={{ value: "Hedges' g", angle: -90, position: 'insideLeft', fill: '#8fa0bd' }} />
                  <Tooltip contentStyle={{ background: '#1a2233', border: '1px solid #2c3a55', borderRadius: 8 }} />
                  <Legend />
                  {selected.map((runId, idx) => (
                    <Bar key={runId} dataKey={`run${idx}`} fill={COLORS[idx]} name={getRunLabel(runId)} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="muted">{'\u6682\u65e0\u53ef\u5bf9\u6bd4\u7684\u6548\u5e94\u91cf\u6570\u636d'}</div>
            )}
          </div>

          {/* Decision summary table */}
          <div className="card">
            <h3>{'\u51b3\u7b56\u7ed3\u679c\u5bf9\u6bd4'}</h3>
            <table>
              <thead>
                <tr>
                  <th>{'\u8fd0\u884c ID'}</th>
                  <th style={{ color: '#38c7a4' }}>GO</th>
                  <th style={{ color: '#f5a623' }}>CONDITIONAL</th>
                  <th style={{ color: '#ef5b6b' }}>NO-GO</th>
                  <th>{'\u64cd\u4f5c'}</th>
                </tr>
              </thead>
              <tbody>
                {compareData.prescreenings.map((ps, idx) => (
                  <tr key={selected[idx]}>
                    <td>{selected[idx]}</td>
                    <td><strong>{ps.go_count || 0}</strong></td>
                    <td><strong>{ps.conditional_count || 0}</strong></td>
                    <td><strong>{ps.no_go_count || 0}</strong></td>
                    <td>
                      <button className="secondary" style={{ fontSize: 11 }}
                        onClick={() => navigate(`/runs/${selected[idx]}/dashboard`)}>
                        {'\u67e5\u770b\u8be6\u60c5'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Effect sizes detail table */}
          <div className="card">
            <h3>{'\u6548\u5e94\u91cf\u660e\u7ec6'}</h3>
            <table>
              <thead>
                <tr>
                  <th>{'\u5e72\u9884'}</th>
                  {selected.map((runId, idx) => (
                    <th key={runId} style={{ color: COLORS[idx] }}>{runId}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {chartData.map((row) => (
                  <tr key={row.name}>
                    <td>{row.name}</td>
                    {selected.map((runId, idx) => (
                      <td key={runId}>
                        {row[`run${idx}`] != null ? (
                          <strong>{row[`run${idx}`].toFixed(3)}</strong>
                        ) : (
                          <span className="muted">-</span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
