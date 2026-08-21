import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend,
} from 'recharts'
import api from '../api.js'
import { t } from '../i18n.js'

const DECISION_COLORS = {
  go: '#38c7a4',
  conditional: '#f5a623',
  no_go: '#ef5b6b',
}

export default function DashboardPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null)
  const [showEffectSizes, setShowEffectSizes] = useState(false)
  const [showPriorityRanking, setShowPriorityRanking] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([
      api.getRun(id),
      api.getReport(id),
      api.getPrescreening(id),
      api.getCalibration(id).catch(() => null),
    ])
      .then(([run, report, prescreening, calibration]) => {
        if (cancelled) return
        setData({ run, report, prescreening, calibration })
        setLoading(false)
      })
      .catch((e) => {
        if (cancelled) return
        setError(e.message)
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [id])

  if (loading) return <div className="loading">加载中...</div>
  if (error) return <div className="error-box">{error}</div>
  if (!data) return null

  const { run, report, prescreening, calibration } = data
  const rc = report.report_card || {}
  const ov = rc.overview || {}

  const effectSizes = (rc.effect_sizes || [])
    .sort((a, b) => Math.abs(b.hedges_g) - Math.abs(a.hedges_g))
    .slice(0, 3)

  const decisionData = [
    { name: 'GO', value: prescreening.go_count || 0 },
    { name: 'CONDITIONAL', value: prescreening.conditional_count || 0 },
    { name: 'NO-GO', value: prescreening.no_go_count || 0 },
  ].filter((d) => d.value > 0)

  const bestIntv = effectSizes[0]
  const bestScene = bestIntv ? (rc.effect_sizes || []).find(
    (es) => t('intervention', es.intervention_id) === bestIntv.name
  )?.scene : null

  let conclusion = ''
  let bestLabel = ''
  if (bestIntv && prescreening.go_count > 0) {
    conclusion = '本次运行发现 ' + bestIntv.name + ' 在 ' + t('scene', bestScene) + ' 场景效果最佳（g=' + bestIntv.g.toFixed(2) + '），建议优先实证。'
    bestLabel = bestIntv.name + ' (g=' + bestIntv.g.toFixed(2) + ')'
  } else if (prescreening.conditional_count > 0) {
    conclusion = '本次运行发现 ' + prescreening.conditional_count + ' 个干预有条件性推荐，需补充条件后可考虑实证。'
  } else {
    conclusion = '本次运行未发现显著有效的干预方案，建议调整假设后重新测试。'
  }

  return (
    <div>
      <div className="page-header">
        <h2>执行摘要</h2>
        <p>本次运行的关键发现与决策建议</p>
      </div>

      {/* Compact conclusion card */}
      <div className="card" style={{ background: 'linear-gradient(135deg, #1a2233 0%, #222d42 100%)', border: '1px solid #4f8cff', padding: '12px 16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div style={{ fontSize: 15, lineHeight: 1.5, flex: 1, minWidth: 300 }}>
            <span style={{ color: '#4f8cff', fontWeight: 600 }}>核心发现：</span>{conclusion}
          </div>
          {bestLabel && (
            <div style={{ background: 'rgba(79,140,255,0.15)', borderRadius: 8, padding: '8px 16px', border: '1px solid rgba(79,140,255,0.3)' }}>
              <div style={{ fontSize: 11, color: '#8fa0bd' }}>最优干预</div>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#4f8cff' }}>{bestLabel}</div>
            </div>
          )}
        </div>
      </div>

      {/* Compact overview stats */}
      <div className="row" style={{ marginBottom: 12 }}>
        <div className="card">
          <div className="stat">
            <span className="v">{ov.n_students || run.n_students}</span>
            <span className="l">虚拟学生</span>
          </div>
        </div>
        <div className="card">
          <div className="stat">
            <span className="v">{effectSizes.length}</span>
            <span className="l">干预方案</span>
          </div>
        </div>
      </div>

      {/* Virtual vs Literature comparison card */}
      {calibration && (
        <div className="card" style={{ background: 'linear-gradient(135deg, #1a2233 0%, #1e2a3d 100%)', border: '1px solid #2c3a55' }}>
          <h3>虚拟 vs 文献</h3>
          <div style={{ display: 'flex', gap: 24, alignItems: 'stretch', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={{ fontSize: 13, color: '#8fa0bd', marginBottom: 8 }}>虚拟学生 BKT 参数</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {Object.entries(calibration.bkt_params_virtual || {}).map(([k, v]) => (
                  <div key={k} style={{ background: '#141b2b', borderRadius: 6, padding: '8px 12px' }}>
                    <div style={{ fontSize: 11, color: '#8fa0bd' }}>{k}</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: '#4f8cff' }}>{typeof v === 'number' ? v.toFixed(4) : v}</div>
                  </div>
                ))}
              </div>
            </div>
            <div style={{ flex: 0.8, minWidth: 160, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', borderLeft: '1px solid #2c3a55', borderRight: '1px solid #2c3a55', padding: '0 16px' }}>
              <div style={{ fontSize: 13, color: '#8fa0bd', marginBottom: 4 }}>认知距离</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: (calibration.cognitive_distance || 0) < 0.10 ? '#38c7a4' : (calibration.cognitive_distance || 0) < 0.18 ? '#f5a623' : '#ef5b6b' }}>
                {typeof calibration.cognitive_distance === 'number' ? calibration.cognitive_distance.toFixed(4) : '—'}
              </div>
              <div style={{ marginTop: 4 }}>
                <span className="badge" style={{ color: (calibration.cognitive_distance || 0) < 0.10 ? '#38c7a4' : (calibration.cognitive_distance || 0) < 0.18 ? '#f5a623' : '#ef5b6b', borderColor: (calibration.cognitive_distance || 0) < 0.10 ? '#38c7a4' : (calibration.cognitive_distance || 0) < 0.18 ? '#f5a623' : '#ef5b6b' }}>
                  {calibration.verdict === 'pass' ? '通过' : calibration.verdict === 'marginal' ? '边缘' : '未通过'}
                </span>
              </div>
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={{ fontSize: 13, color: '#8fa0bd', marginBottom: 8 }}>文献基线参数（5篇研究聚合）</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {[['p_know', 0.38], ['p_learn', 0.25], ['p_slip', 0.10], ['p_guess', 0.20]].map(([k, v]) => (
                  <div key={k} style={{ background: '#141b2b', borderRadius: 6, padding: '8px 12px' }}>
                    <div style={{ fontSize: 11, color: '#8fa0bd' }}>{k}</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: '#38c7a4' }}>{v.toFixed(4)}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div style={{ marginTop: 16, padding: '10px 14px', background: 'rgba(245,166,35,0.1)', borderRadius: 6, border: '1px solid rgba(245,166,35,0.3)', fontSize: 13, color: '#f5a623' }}>
            以上为虚拟仿真结果，需真人试验验证，不可直接外推
          </div>
        </div>
      )}

      {/* Decision pie chart with counts */}
      <div className="card">
        <h3>预筛决策分布</h3>
        <div style={{ display: 'flex', gap: 24, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 280, height: 220 }}>
            {decisionData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={decisionData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, value }) => name + ': ' + value}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {decisionData.map((entry, index) => (
                      <Cell key={'cell-' + index} fill={DECISION_COLORS[entry.name.toLowerCase()]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#1a2233', border: '1px solid #2c3a55', borderRadius: 8 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="muted">暂无决策数据</div>
            )}
          </div>
          <div style={{ flex: 0.6, minWidth: 180 }}>
            {decisionData.map((d) => (
              <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <div style={{ width: 12, height: 12, borderRadius: 3, background: DECISION_COLORS[d.name.toLowerCase()] }}></div>
                <span style={{ fontSize: 14, fontWeight: 600, color: DECISION_COLORS[d.name.toLowerCase()] }}>{d.value}</span>
                <span style={{ fontSize: 13, color: '#8fa0bd' }}>{d.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* NO-GO narrative section */}
      <div className="card">
        <h3>排除的不靠谱假设</h3>
        {(() => {
          const noGoCandidates = (prescreening.candidates || []).filter(c => c.decision === 'no_go')
          if (noGoCandidates.length === 0) {
            return <div className="muted">本次运行所有候选干预均通过预筛</div>
          }
          return (
            <>
              <div style={{ marginBottom: 12, fontSize: 14 }}>
                本次运行排除了 <strong style={{ color: '#ef5b6b' }}>{noGoCandidates.length}</strong> 个不靠谱假设，节省了真人试验成本
              </div>
              <table>
                <thead>
                  <tr>
                    <th>干预</th>
                    <th>Hedges g</th>
                    <th>排除原因</th>
                  </tr>
                </thead>
                <tbody>
                  {noGoCandidates.map((c) => {
                    const reasons = []
                    if (!c.checks?.effect_threshold) reasons.push('效应量不足 (|g|=' + Math.abs(c.hedges_g || 0).toFixed(2) + ' &lt; 0.20)')
                    if (!c.checks?.ci_significance) reasons.push('CI 跨零')
                    if (!c.checks?.fidelity) reasons.push('高失真区')
                    if (!c.checks?.feasibility) reasons.push('优先级不足 (' + (c.priority_score || 0).toFixed(2) + ' &lt; 0.40)')
                    return (
                      <tr key={c.intervention_id}>
                        <td>{t('intervention', c.intervention_id)}</td>
                        <td><strong>{c.hedges_g?.toFixed(3)}</strong></td>
                        <td style={{ color: '#ef5b6b', fontSize: 12 }}>
                          {reasons.join('；') || '未通过某些标准'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </>
          )
        })()}
      </div>

      {/* Quick actions */}
      <div className="card">
        <h3>快速操作</h3>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <button onClick={() => navigate('/runs/' + id + '/report')}>查看详细报告</button>
          <button onClick={() => navigate('/runs/' + id + '/prescreening')}>查看预筛决策</button>
          <button onClick={() => navigate('/runs/' + id + '/counterfactual')}>反事实推演</button>
          <button className="secondary" onClick={() => navigate('/runs/' + id + '/export')}>比赛材料</button>
          <button className="secondary" onClick={() => navigate('/compare')}>对比其他运行</button>
          <button className="secondary" onClick={() => navigate('/runs/' + id + '/demo')}>演示模式</button>
          <button className="secondary" onClick={() => navigate('/')}>返回首页</button>
        </div>
      </div>

      {/* Collapsible: Effect Sizes Detail */}
      <div className="card">
        <div
          style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
          onClick={() => setShowEffectSizes(!showEffectSizes)}
        >
          <h3 style={{ margin: 0 }}>效应量详情</h3>
          <span style={{ fontSize: 18, color: '#4f8cff' }}>{showEffectSizes ? '▲' : '▼'}</span>
        </div>
        {showEffectSizes && (
          <div style={{ marginTop: 16 }}>
            <table>
              <thead>
                <tr>
                  <th>干预</th>
                  <th>场景</th>
                  <th>Hedges g</th>
                  <th>95% CI</th>
                  <th>样本量</th>
                </tr>
              </thead>
              <tbody>
                {(rc.effect_sizes || []).map((es) => (
                  <tr key={'es-' + es.intervention_id + '-' + es.scene}>
                    <td>{t('intervention', es.intervention_id)}</td>
                    <td>{t('scene', es.scene)}</td>
                    <td><strong>{es.hedges_g?.toFixed(3)}</strong></td>
                    <td className="muted">[{es.ci_lower?.toFixed(3)}, {es.ci_upper?.toFixed(3)}]</td>
                    <td className="muted">{es.sample_size}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Collapsible: Priority Ranking Detail */}
      <div className="card">
        <div
          style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
          onClick={() => setShowPriorityRanking(!showPriorityRanking)}
        >
          <h3 style={{ margin: 0 }}>优先级排序详情</h3>
          <span style={{ fontSize: 18, color: '#4f8cff' }}>{showPriorityRanking ? '▲' : '▼'}</span>
        </div>
        {showPriorityRanking && (
          <div style={{ marginTop: 16 }}>
            <table>
              <thead>
                <tr>
                  <th>排名</th>
                  <th>干预</th>
                  <th>优先级得分</th>
                  <th>效应量</th>
                  <th>确定性</th>
                  <th>可达性</th>
                  <th>成本效率</th>
                  <th>失真区</th>
                </tr>
              </thead>
              <tbody>
                {(rc.priority_ranking || []).map((r) => (
                  <tr key={'pr-' + r.intervention_id}>
                    <td><strong>{r.rank}</strong></td>
                    <td>{t('intervention', r.intervention_id)}</td>
                    <td><strong>{r.priority_score?.toFixed(3)}</strong></td>
                    <td className="muted">{r.breakdown?.effect_size?.toFixed(2)}</td>
                    <td className="muted">{r.breakdown?.certainty?.toFixed(2)}</td>
                    <td className="muted">{r.breakdown?.reach?.toFixed(2)}</td>
                    <td className="muted">{r.breakdown?.cost_efficiency?.toFixed(2)}</td>
                    <td>
                      {r.in_distorted_region
                        ? <span className="badge" style={{ color: '#f5a623', borderColor: '#f5a623' }}>失真</span>
                        : <span className="badge green">正常</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}