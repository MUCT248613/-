import React, { useEffect, useState, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api.js'
import { t } from '../i18n.js'

// Color scale for distortion magnitude
function heatColor(gap, category) {
  if (category === 'none') return 'rgba(56, 199, 164, 0.3)'
  if (category === 'overestimate') {
    const intensity = Math.min(1, gap / 0.5)
    return `rgba(231, 76, 60, ${0.3 + intensity * 0.6})`
  }
  if (category === 'underestimate') {
    const intensity = Math.min(1, gap / 0.5)
    return `rgba(243, 156, 18, ${0.3 + intensity * 0.6})`
  }
  if (category === 'variance_mismatch') {
    const intensity = Math.min(1, gap / 0.5)
    return `rgba(155, 89, 182, ${0.3 + intensity * 0.6})`
  }
  return 'rgba(52, 152, 219, 0.3)'
}

export default function DistortionMapPage() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all')
  const [viewMode, setViewMode] = useState('heatmap') // 'heatmap' | 'table'

  useEffect(() => {
    let cancelled = false
    api.getDistortionMap(id)
      .then((r) => !cancelled && setData(r))
      .catch((e) => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [id])

  // Build heatmap matrix
  const heatmapData = useMemo(() => {
    if (!data) return null
    const interventions = data.interventions
    const scenes = data.scenes
    const matrix = {}
    interventions.forEach((intv) => {
      matrix[intv] = {}
      scenes.forEach((scene) => {
        const cell = data.cells.find(
          (c) => c.intervention === intv && c.scene === scene
        )
        matrix[intv][scene] = cell || { gap_magnitude: 0, category: 'none' }
      })
    })
    return { interventions, scenes, matrix }
  }, [data])

  if (error) return <div className="error-box">{error}</div>
  if (!data) return <div className="loading">{'\u6b63\u5728\u52a0\u8f7d\u5931\u771f\u5730\u56fe\u2026'}</div>

  const cells = filter === 'all'
    ? data.cells
    : filter === 'distorted'
      ? data.cells.filter((c) => c.category !== 'none')
      : data.cells.filter((c) => c.category === 'none')

  const cellSize = 60
  const labelWidth = 120
  const labelHeight = 80

  return (
    <div>
      <div className="page-header">
        <h2>{'\u{1f5d3}\ufe0f \u53ef\u4fe1\u5ea6\u70ed\u529b\u56fe'}</h2>
        <p>
          {'\u5e72\u9884 \u00d7 \u573a\u666f \u5931\u771f\u70ed\u529b\u56fe \u00b7 \u9ad8\u5931\u771f\u533a\u8bc1\u636e\u5df2\u88ab M6 \u6392\u5e8f\u964d\u6743'}
        </p>
      </div>

      <div className="card">
        <h3>{'\u6982\u89c8'}</h3>
        <div className="row">
          <div className="stat">
            <span className="v">{data.cells.length}</span>
            <span className="l">{'\u603b\u5355\u5143\u6570'}</span>
          </div>
          <div className="stat">
            <span className="v" style={{ color: '#e74c3c' }}>{data.n_high_distortion}</span>
            <span className="l">{'\u9ad8\u5931\u771f\u5355\u5143'}</span>
          </div>
          <div className="stat">
            <span className="v">{data.interventions.length}</span>
            <span className="l">{'\u5e72\u9884\u6570'}</span>
          </div>
          <div className="stat">
            <span className="v">{data.scenes.length}</span>
            <span className="l">{'\u573a\u666f\u6570'}</span>
          </div>
        </div>
        <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          {data.summary}
        </div>
      </div>

      {/* View mode toggle */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>{'\u5931\u771f\u5206\u5e03'}</h3>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className={viewMode === 'heatmap' ? '' : 'secondary'}
              onClick={() => setViewMode('heatmap')}
              style={{ fontSize: 12 }}
            >
              {'\u{1f5d3}\ufe0f \u70ed\u529b\u56fe'}
            </button>
            <button
              className={viewMode === 'table' ? '' : 'secondary'}
              onClick={() => setViewMode('table')}
              style={{ fontSize: 12 }}
            >
              {'\u{1f4cb} \u8868\u683c'}
            </button>
          </div>
        </div>

        <div style={{ marginBottom: 12 }}>
          <select value={filter} onChange={(e) => setFilter(e.target.value)} style={{ fontSize: 12 }}>
            <option value="all">{'\u663e\u793a\u5168\u90e8'}</option>
            <option value="distorted">{'\u4ec5\u663e\u793a\u5931\u771f\u5355\u5143'}</option>
            <option value="normal">{'\u4ec5\u663e\u793a\u6b63\u5e38\u5355\u5143'}</option>
          </select>
        </div>

        {/* Heatmap view */}
        {viewMode === 'heatmap' && heatmapData && (
          <div style={{ overflowX: 'auto' }}>
            <svg width={labelWidth + heatmapData.scenes.length * cellSize}
                 height={labelHeight + heatmapData.interventions.length * cellSize}>
              {/* Scene labels (top) */}
              {heatmapData.scenes.map((scene, i) => (
                <text
                  key={`scene-${i}`}
                  x={labelWidth + i * cellSize + cellSize / 2}
                  y={labelHeight - 10}
                  textAnchor="middle"
                  fontSize={11}
                  fill="#8fa0bd"
                  transform={`rotate(-30, ${labelWidth + i * cellSize + cellSize / 2}, ${labelHeight - 10})`}
                >
                  {t('scene', scene)}
                </text>
              ))}

              {/* Intervention labels (left) + cells */}
              {heatmapData.interventions.map((intv, i) => (
                <g key={`intv-${i}`}>
                  <text
                    x={labelWidth - 10}
                    y={labelHeight + i * cellSize + cellSize / 2 + 4}
                    textAnchor="end"
                    fontSize={11}
                    fill="#8fa0bd"
                  >
                    {t('intervention', intv)}
                  </text>
                  {heatmapData.scenes.map((scene, j) => {
                    const cell = heatmapData.matrix[intv][scene]
                    const isVisible = filter === 'all' ||
                      (filter === 'distorted' && cell.category !== 'none') ||
                      (filter === 'normal' && cell.category === 'none')
                    return (
                      <g key={`cell-${i}-${j}`}>
                        <rect
                          x={labelWidth + j * cellSize}
                          y={labelHeight + i * cellSize}
                          width={cellSize - 2}
                          height={cellSize - 2}
                          fill={isVisible ? heatColor(cell.gap_magnitude, cell.category) : '#1a2233'}
                          stroke="#2c3a55"
                          strokeWidth={1}
                          rx={4}
                        />
                        {isVisible && cell.gap_magnitude > 0 && (
                          <text
                            x={labelWidth + j * cellSize + cellSize / 2 - 1}
                            y={labelHeight + i * cellSize + cellSize / 2 + 4}
                            textAnchor="middle"
                            fontSize={10}
                            fill="#e6ecf7"
                            fontWeight={600}
                          >
                            {cell.gap_magnitude.toFixed(2)}
                          </text>
                        )}
                      </g>
                    )
                  })}
                </g>
              ))}
            </svg>
          </div>
        )}

        {/* Table view */}
        {viewMode === 'table' && (
          <table>
            <thead>
              <tr>
                <th>{'\u5e72\u9884'}</th>
                <th>{'\u573a\u666f'}</th>
                <th>{'\u6307\u6807'}</th>
                <th>{'\u5931\u771f\u5ea6'}</th>
                <th>{'\u7c7b\u522b'}</th>
              </tr>
            </thead>
            <tbody>
              {cells.map((cell, idx) => (
                <tr key={idx}>
                  <td>{t('intervention', cell.intervention)}</td>
                  <td>{t('scene', cell.scene)}</td>
                  <td>{cell.metric}</td>
                  <td>
                    <span style={{
                      color: cell.category === 'none' ? '#38c7a4' :
                             cell.category === 'overestimate' ? '#e74c3c' :
                             cell.category === 'underestimate' ? '#f39c12' : '#9b59b6'
                    }}>
                      {cell.gap_magnitude.toFixed(3)}
                    </span>
                  </td>
                  <td>
                    <span className="badge" style={{
                      background: cell.category === 'none' ? 'rgba(56,199,164,0.2)' :
                                  cell.category === 'overestimate' ? 'rgba(231,76,60,0.2)' :
                                  cell.category === 'underestimate' ? 'rgba(243,156,18,0.2)' :
                                  'rgba(155,89,182,0.2)',
                      color: cell.category === 'none' ? '#38c7a4' :
                             cell.category === 'overestimate' ? '#e74c3c' :
                             cell.category === 'underestimate' ? '#f39c12' : '#9b59b6',
                    }}>
                      {cell.category === 'none' ? '\u6b63\u5e38' :
                       cell.category === 'overestimate' ? '\u9ad8\u4f30' :
                       cell.category === 'underestimate' ? '\u4f4e\u4f30' :
                       cell.category === 'variance_mismatch' ? '\u65b9\u5dee\u5931\u914d' : cell.category}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Legend */}
      <div className="card">
        <h3>{'\u56fe\u4f8b'}</h3>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 20, height: 20, background: 'rgba(56, 199, 164, 0.3)', borderRadius: 4 }}></div>
            <span>{'\u6b63\u5e38'}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 20, height: 20, background: 'rgba(231, 76, 60, 0.7)', borderRadius: 4 }}></div>
            <span>{'\u9ad8\u4f30\u533a'}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 20, height: 20, background: 'rgba(243, 156, 18, 0.7)', borderRadius: 4 }}></div>
            <span>{'\u4f4e\u4f30\u533a'}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 20, height: 20, background: 'rgba(155, 89, 182, 0.7)', borderRadius: 4 }}></div>
            <span>{'\u65b9\u5dee\u5931\u914d'}</span>
          </div>
        </div>
        <div className="muted" style={{ fontSize: 11, marginTop: 8 }}>
          {'\u989c\u8272\u8d8a\u6df1\u8868\u793a\u5931\u771f\u5ea6\u8d8a\u9ad8\uff0c\u6570\u5b57\u4e3a\u5931\u771f\u5ea6\u91cf\u503c'}
        </div>
      </div>
    </div>
  )
}
