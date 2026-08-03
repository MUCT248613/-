import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ErrorBar, ReferenceLine, Cell, Legend,
} from 'recharts'
import api from '../api.js'
import { t } from '../i18n.js'

const SCENE_COLORS = {
  school: '#4f8cff',
  shadow_edu: '#f5a623',
  home: '#ef5b6b',
  self_study: '#a06bff',
}

export default function ScenesPage() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .getSceneComparison(id)
      .then(setData)
      .catch((e) => setError(e.message))
  }, [id])

  const chartData = data
    ? Object.entries(data.scenes).map(([scene, v]) => ({
        scene: t('scene', scene),
        rawScene: scene,
        g: v.g,
        n: v.n,
        ciLower: v.ci_lower,
        ciUpper: v.ci_upper,
        // recharts ErrorBar expects [lowerDeviation, upperDeviation]
        error: [v.g - v.ci_lower, v.ci_upper - v.g],
      }))
    : []

  return (
    <div>
      <div className="page-header">
        <h2>场景比较</h2>
        <p>同一干预在学校 / 课外班 / 家庭 / 自学四场景的效应量（Hedges' g）对比 + 95% CI</p>
      </div>

      {error && <div className="error-box">{error}</div>}
      {!data && !error && <div className="loading">加载中…</div>}

      {data && (
        <>
          <div className="card">
            <h3>干预类型：{t('interventionType', data.intervention_type)}</h3>
            <ResponsiveContainer width="100%" height={360}>
              <BarChart data={chartData} margin={{ top: 20, right: 30, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2c3a55" />
                <XAxis dataKey="scene" stroke="#8fa0bd" />
                <YAxis stroke="#8fa0bd" label={{ value: "Hedges' g", angle: -90, position: 'insideLeft', fill: '#8fa0bd' }} />
                <Tooltip
                  contentStyle={{ background: '#1a2233', border: '1px solid #2c3a55', borderRadius: 8 }}
                  formatter={(value, name) => (name === 'g' ? [Number(value).toFixed(3), "Hedges' g"] : value)}
                />
                <ReferenceLine y={0} stroke="#8fa0bd" />
                <ReferenceLine y={0.2} stroke="#38c7a4" strokeDasharray="4 4" label={{ value: '小效应 0.2', fill: '#38c7a4', fontSize: 11 }} />
                <Bar dataKey="g" name="g" radius={[6, 6, 0, 0]}>
                  {chartData.map((d) => (
                    <Cell key={d.rawScene} fill={SCENE_COLORS[d.rawScene] || '#4f8cff'} />
                  ))}
                  <ErrorBar dataKey="error" width={8} strokeWidth={2} stroke="#e6ecf7" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h3>明细</h3>
            <table>
              <thead>
                <tr><th>场景</th><th>g</th><th>95% CI</th><th>样本量 n</th><th>显著性</th></tr>
              </thead>
              <tbody>
                {chartData.map((d) => (
                  <tr key={d.rawScene}>
                    <td>{d.scene}</td>
                    <td>{d.g.toFixed(3)}</td>
                    <td>[{d.ciLower.toFixed(3)}, {d.ciUpper.toFixed(3)}]</td>
                    <td>{d.n}</td>
                    <td>
                      {d.ciLower > 0 ? (
                        <span className="badge green">显著（CI 不含 0）</span>
                      ) : (
                        <span className="badge">不显著</span>
                      )}
                    </td>
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
