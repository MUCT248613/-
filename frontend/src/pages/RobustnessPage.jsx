import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import api from '../api.js'
import { t } from '../i18n.js'

export default function RobustnessPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [runs, setRuns] = useState([])
  const [seedData, setSeedData] = useState([])
  const [sampleData, setSampleData] = useState([])

  useEffect(() => {
    api.getRobustness()
      .then((r) => {
        const completedRuns = r.runs || []
        setRuns(completedRuns)

        // Prepare seed sensitivity data
        const seedGroups = {}
        completedRuns.forEach((run) => {
          const effectSizes = run.effect_sizes || []
          if (!effectSizes.length) return
          
          const seed = run.seed ?? 'unknown'
          if (!seedGroups[seed]) seedGroups[seed] = []
          
          effectSizes.forEach(es => {
            seedGroups[seed].push({
              run_id: run.run_id,
              intervention_id: es.intervention_id,
              hedges_g: es.hedges_g,
              n_students: run.n_students,
            })
          })
        })
        
        // Convert to chart data: average effect size per intervention per seed
        const seedChartData = []
        const interventions = new Set()
        Object.values(seedGroups).forEach(runs => {
          runs.forEach(r => interventions.add(r.intervention_id))
        })
        
        interventions.forEach(intvId => {
          const row = { name: t('intervention', intvId) }
          Object.entries(seedGroups).forEach(([seed, runs]) => {
            const intvRuns = runs.filter(r => r.intervention_id === intvId)
            if (intvRuns.length > 0) {
              const avg = intvRuns.reduce((sum, r) => sum + r.hedges_g, 0) / intvRuns.length
              row[`seed_${seed}`] = avg
            }
          })
          seedChartData.push(row)
        })
        setSeedData(seedChartData)
        
        // Prepare sample size sensitivity data
        const sampleGroups = {}
        completedRuns.forEach((run) => {
          const effectSizes = run.effect_sizes || []
          if (!effectSizes.length) return
          
          const nStudents = run.n_students
          if (!sampleGroups[nStudents]) sampleGroups[nStudents] = []
          
          effectSizes.forEach(es => {
            sampleGroups[nStudents].push({
              run_id: run.run_id,
              intervention_id: es.intervention_id,
              hedges_g: es.hedges_g,
            })
          })
        })
        
        // Convert to chart data: effect size vs sample size per intervention
        const sampleChartData = []
        interventions.forEach(intvId => {
          const points = []
          Object.entries(sampleGroups).forEach(([nStudents, runs]) => {
            const intvRuns = runs.filter(r => r.intervention_id === intvId)
            if (intvRuns.length > 0) {
              const avg = intvRuns.reduce((sum, r) => sum + r.hedges_g, 0) / intvRuns.length
              points.push({
                sample_size: parseInt(nStudents),
                hedges_g: avg,
              })
            }
          })
          points.sort((a, b) => a.sample_size - b.sample_size)
          if (points.length > 0) {
            sampleChartData.push({
              intervention_id: intvId,
              name: t('intervention', intvId),
              data: points,
            })
          }
        })
        setSampleData(sampleChartData)
        
        setLoading(false)
      })
      .catch((e) => {
        setError(e.message)
        setLoading(false)
      })
  }, [])

  if (loading) return <div className="loading">加载中...</div>
  if (error) return <div className="error-box">{error}</div>

  const hasSeedData = seedData.length > 0 && Object.keys(seedData[0] || {}).length > 1
  const hasSampleData = sampleData.some(d => d.data.length > 1)

  return (
    <div>
      <div className="page-header">
        <h2>🔬 稳健性检验</h2>
        <p>稳健性检验展示结论是否依赖于特定随机种子或样本量</p>
      </div>

      <div className="card">
        <h3>说明</h3>
        <div className="muted" style={{ fontSize: 13, lineHeight: 1.8 }}>
          稳健性检验帮助判断研究结论的可靠性：
          <ul style={{ marginTop: 8, paddingLeft: 20 }}>
            <li><strong>种子敏感性</strong>：如果多次运行使用不同随机种子但得到相似的效应量，说明结论不依赖于特定的随机数序列</li>
            <li><strong>样本量敏感性</strong>：如果效应量随样本量增加而趋于稳定，说明样本量足够大，结论可靠</li>
          </ul>
        </div>
      </div>

      {/* Seed sensitivity */}
      <div className="card">
        <h3>种子敏感性分析</h3>
        {!hasSeedData ? (
          <div className="muted" style={{ padding: '20px 0', textAlign: 'center' }}>
            需要多次运行不同种子但相同配置才能生成种子敏感性分析
          </div>
        ) : (
          <>
            <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
              不同随机种子下各干预的平均效应量对比
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={seedData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2c3a55" />
                <XAxis dataKey="name" stroke="#8fa0bd" />
                <YAxis stroke="#8fa0bd" label={{ value: "Hedges' g", angle: -90, position: 'insideLeft', fill: '#8fa0bd' }} />
                <Tooltip contentStyle={{ background: '#1a2233', border: '1px solid #2c3a55', borderRadius: 8 }} />
                <Legend />
                {Object.keys(seedData[0] || {}).filter(k => k.startsWith('seed_')).map((key, idx) => {
                  const colors = ['#4f8cff', '#38c7a4', '#f5a623', '#a06bff', '#ef5b6b']
                  return (
                    <Line
                      key={key}
                      type="monotone"
                      dataKey={key}
                      stroke={colors[idx % colors.length]}
                      name={`种子 ${key.replace('seed_', '')}`}
                      strokeWidth={2}
                      dot={{ r: 4 }}
                    />
                  )
                })}
              </LineChart>
            </ResponsiveContainer>
          </>
        )}
      </div>

      {/* Sample size sensitivity */}
      <div className="card">
        <h3>样本量敏感性分析</h3>
        {!hasSampleData ? (
          <div className="muted" style={{ padding: '20px 0', textAlign: 'center' }}>
            需要多次运行不同样本量才能生成样本量敏感性分析
          </div>
        ) : (
          <>
            <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
              效应量随样本量的变化趋势
            </div>
            {sampleData.map((intv) => (
              <div key={intv.intervention_id} style={{ marginBottom: 24 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#e6ecf7' }}>
                  {intv.name}
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={intv.data} margin={{ top: 10, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2c3a55" />
                    <XAxis dataKey="sample_size" stroke="#8fa0bd" label={{ value: '样本量', position: 'insideBottom', offset: -5, fill: '#8fa0bd' }} />
                    <YAxis stroke="#8fa0bd" label={{ value: "Hedges' g", angle: -90, position: 'insideLeft', fill: '#8fa0bd' }} />
                    <Tooltip contentStyle={{ background: '#1a2233', border: '1px solid #2c3a55', borderRadius: 8 }} />
                    <Line type="monotone" dataKey="hedges_g" stroke="#4f8cff" strokeWidth={2} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ))}
          </>
        )}
      </div>

      <div className="card">
        <h3>快速操作</h3>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <button onClick={() => navigate('/compare')}>
            📊 对比其他运行
          </button>
          <button className="secondary" onClick={() => navigate('/')}>
            🏠 返回首页
          </button>
        </div>
      </div>
    </div>
  )
}
