import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api.js'
import { t } from '../i18n.js'

const CAT_COLORS = {
  none: '#38c7a4',
  overestimate: '#e74c3c',
  underestimate: '#f39c12',
  variance_mismatch: '#9b59b6',
  shape_mismatch: '#3498db',
}

export default function DistortionMapPage() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    let cancelled = false
    api
      .getDistortionMap(id)
      .then((r) => !cancelled && setData(r))
      .catch((e) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [id])

  if (error) return <div className="error-box">{error}</div>
  if (!data) return <div className="loading">正在加载失真地图…</div>

  const cells = filter === 'all'
    ? data.cells
    : filter === 'distorted'
      ? data.cells.filter((c) => c.category !== 'none')
      : data.cells.filter((c) => c.category === 'none')

  return (
    <div>
      <div className="page-header">
        <h2>失真地图</h2>
        <p>
          干预 × 场景 × 指标族 失真热力图（FR-F3）· 高失真区证据已被 M6 排序降权
        </p>
      </div>

      <div className="card">
        <h3>概览</h3>
        <div className="row">
          <div className="stat">
            <span className="v">{data.cells.length}</span>
            <span className="l">总单元数</span>
          </div>
          <div className="stat">
            <span className="v" style={{ color: '#e74c3c' }}>{data.n_high_distortion}</span>
            <span className="l">高失真单元</span>
          </div>
          <div className="stat">
            <span className="v">{data.interventions.length}</span>
            <span className="l">干预数</span>
          </div>
          <div className="stat">
            <span className="v">{data.scenes.length}</span>
            <span className="l">场景数</span>
          </div>
        </div>
        <div className="muted" style={{ fontSize: 13, marginTop: 8 }}>{data.summary}</div>
      </div>

      <div className="card">
        <h3>
          失真单元明细
          <span style={{ marginLeft: 12, fontSize: 12 }}>
            <button className={filter === 'all' ? '' : 'secondary'} style={{ fontSize: 11, padding: '3px 8px' }} onClick={() => setFilter('all')}>全部</button>{' '}
            <button className={filter === 'distorted' ? '' : 'secondary'} style={{ fontSize: 11, padding: '3px 8px' }} onClick={() => setFilter('distorted')}>仅失真</button>{' '}
            <button className={filter === 'clean' ? '' : 'secondary'} style={{ fontSize: 11, padding: '3px 8px' }} onClick={() => setFilter('clean')}>仅正常</button>
          </span>
        </h3>
        <table>
          <thead>
            <tr><th>干预</th><th>场景</th><th>指标族</th><th>差距幅度</th><th>失真类别</th></tr>
          </thead>
          <tbody>
            {cells.slice(0, 60).map((c, i) => (
              <tr key={i}>
                <td>{t('intervention', c.intervention)}</td>
                <td>{t('scene', c.scene)}</td>
                <td>{t('gapMetric', c.metric)}</td>
                <td className="muted">{c.gap_magnitude?.toFixed(4)}</td>
                <td>
                  <span
                    className="badge"
                    style={{
                      color: CAT_COLORS[c.category] || '#999',
                      borderColor: CAT_COLORS[c.category] || '#999',
                    }}
                  >
                    {t('distortion', c.category)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {cells.length > 60 && (
          <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
            仅显示前 60 条，共 {cells.length} 条。
          </div>
        )}
      </div>

      <div className="card">
        <h3>图例</h3>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {Object.entries(CAT_COLORS).map(([cat, color]) => (
            <span key={cat} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 12, height: 12, borderRadius: 2, background: color, display: 'inline-block' }} />
              {t('distortion', cat)}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
