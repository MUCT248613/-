import React, { useEffect, useState, useMemo, useRef } from 'react'
import { useParams } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import api from '../api.js'
import { t, localName } from '../i18n.js'

// The backend social graph only exposes homophily edge *weights*
// (friendship strength, 0-1). Label edges honestly by tie strength;
// relationship types (romantic / conflict) belong to the relationship
// state machine module and are not part of this graph.
function edgeType(w) {
  if (w > 0.66) return { label: '强联结', color: '#38c7a4' }
  if (w > 0.4) return { label: '中联结', color: '#4f8cff' }
  return { label: '弱联结', color: '#8fa0bd' }
}

function tierCounts(edges) {
  const c = { strong: 0, mid: 0, weak: 0 }
  for (const e of edges) {
    c[e.weight > 0.66 ? 'strong' : e.weight > 0.4 ? 'mid' : 'weak']++
  }
  return c
}

// Achievement -> color (blue low -> green high)
function achColor(score) {
  const t = Math.min(1, Math.max(0, (score - 30) / 60))
  const r = Math.round(79 + (56 - 79) * t)
  const g = Math.round(140 + (199 - 140) * t)
  const b = Math.round(255 + (164 - 255) * t)
  return `rgb(${r},${g},${b})`
}

// Simple force-directed layout (repulsion + springs + centering), computed
// in time-sliced chunks so the main thread never freezes on large graphs.
function layoutNetworkChunked(nodes, edges, width, height, iterations, onDone, isCancelled) {
  const pos = {}
  const N = nodes.length
  // Seed positions on a circle for stability
  nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / N
    const r = Math.min(width, height) * 0.35
    pos[n.node_id] = {
      x: width / 2 + r * Math.cos(angle) + (Math.random() - 0.5) * 10,
      y: height / 2 + r * Math.sin(angle) + (Math.random() - 0.5) * 10,
      vx: 0,
      vy: 0,
    }
  })

  const idx = {}
  nodes.forEach((n, i) => (idx[n.node_id] = i))
  const k = Math.sqrt((width * height) / Math.max(1, N)) * 0.6
  let it = 0

  const runChunk = () => {
    const end = Math.min(iterations, it + 25)
    for (; it < end; it++) {
    const temp = 1 - it / iterations
    // Repulsion (O(n^2), fine for demo sizes)
    for (let i = 0; i < N; i++) {
      const a = pos[nodes[i].node_id]
      for (let j = i + 1; j < N; j++) {
        const b = pos[nodes[j].node_id]
        let dx = a.x - b.x
        let dy = a.y - b.y
        let dist = Math.sqrt(dx * dx + dy * dy) || 0.01
        const force = (k * k) / dist
        dx /= dist
        dy /= dist
        a.vx += dx * force
        a.vy += dy * force
        b.vx -= dx * force
        b.vy -= dy * force
      }
    }
    // Springs along edges
    for (const e of edges) {
      const a = pos[e.source]
      const b = pos[e.target]
      if (!a || !b) continue
      let dx = a.x - b.x
      let dy = a.y - b.y
      let dist = Math.sqrt(dx * dx + dy * dy) || 0.01
      const force = (dist * dist) / k * (0.5 + e.weight * 0.5)
      dx /= dist
      dy /= dist
      a.vx -= dx * force
      a.vy -= dy * force
      b.vx += dx * force
      b.vy += dy * force
    }
    // Centering + integrate
    for (const n of nodes) {
      const p = pos[n.node_id]
      p.vx += (width / 2 - p.x) * 0.02
      p.vy += (height / 2 - p.y) * 0.02
      const vlen = Math.sqrt(p.vx * p.vx + p.vy * p.vy) || 0.01
      const maxStep = 12 * temp + 1
      const scale = Math.min(1, maxStep / vlen)
      p.x += p.vx * scale * 0.05
      p.y += p.vy * scale * 0.05
      p.x = Math.min(width - 20, Math.max(20, p.x))
      p.y = Math.min(height - 20, Math.max(20, p.y))
      p.vx = 0
      p.vy = 0
    }
    }
    if (isCancelled && isCancelled()) return
    if (it < iterations) {
      setTimeout(runChunk, 0)
    } else {
      onDone(pos)
    }
  }
  runChunk()
}

export default function NetworkPage() {
  const { id } = useParams()
  const [network, setNetwork] = useState(null)
  const [evolution, setEvolution] = useState(null)
  const [dayIdx, setDayIdx] = useState(0)
  const [selectedNode, setSelectedNode] = useState(null)
  const [nodeProfile, setNodeProfile] = useState(null)
  const [error, setError] = useState(null)
  const [topK, setTopK] = useState(5)

  // ---- Pan / zoom / node-drag interaction (SVG-level, not browser zoom) ----
  const svgRef = useRef(null)
  const [view, setView] = useState({ x: 0, y: 0, k: 1 }) // translate + scale of the <g> layer
  const [nodeOverrides, setNodeOverrides] = useState({}) // node_id -> {x,y} after dragging
  const dragRef = useRef(null) // {mode:'pan'|'node', ...}

  const W = 860
  const H = 520
  const K_MIN = 0.3
  const K_MAX = 8

  useEffect(() => {
    api.getNetworkEvolution(id, 0, 90).then(setEvolution).catch((e) => setError(e.message))
  }, [id])

  const days = useMemo(
    () => (evolution ? evolution.snapshots.map((s) => s.day) : [0]),
    [evolution],
  )

  useEffect(() => {
    let cancelled = false
    api
      .getNetwork(id, days[dayIdx] ?? 0)
      .then((n) => !cancelled && setNetwork(n))
      .catch((e) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [id, dayIdx, days])

  // Display sparsification: keep only each student's top-K strongest ties.
  // Dense legacy runs (everyone linked to everyone) stay readable this way.
  const visibleEdges = useMemo(() => {
    if (!network) return []
    if (!topK) return network.edges
    const perNode = {}
    for (const e of network.edges) {
      ;(perNode[e.source] || (perNode[e.source] = [])).push(e)
      ;(perNode[e.target] || (perNode[e.target] = [])).push(e)
    }
    const keep = new Set()
    for (const nid of Object.keys(perNode)) {
      perNode[nid]
        .sort((a, b) => b.weight - a.weight)
        .slice(0, topK)
        .forEach((e) => keep.add(e))
    }
    return network.edges.filter((e) => keep.has(e))
  }, [network, topK])

  const visTiers = useMemo(() => tierCounts(visibleEdges), [visibleEdges])
  const allTiers = useMemo(() => (network ? tierCounts(network.edges) : null), [network])

  const [positions, setPositions] = useState({})
  const [layingOut, setLayingOut] = useState(false)
  const layoutSeq = useRef(0)

  useEffect(() => {
    if (!network) {
      setPositions({})
      return undefined
    }
    const seq = ++layoutSeq.current
    setLayingOut(true)
    layoutNetworkChunked(
      network.nodes, visibleEdges, W, H, 250,
      (pos) => {
        if (layoutSeq.current !== seq) return
        setPositions(pos)
        setLayingOut(false)
      },
      () => layoutSeq.current !== seq,
    )
    return () => {
      layoutSeq.current += 1
    }
  }, [network, visibleEdges])

  const layoutReady = Object.keys(positions).length > 0

  // Effective position of a node (drag override takes precedence over layout)
  const posOf = (nodeId) => nodeOverrides[nodeId] || positions[nodeId]

  // Convert a client (mouse) coordinate to SVG viewBox units (pre-<g>-transform)
  const clientToSvg = (clientX, clientY) => {
    const svg = svgRef.current
    if (!svg) return { x: 0, y: 0 }
    const pt = svg.createSVGPoint()
    pt.x = clientX
    pt.y = clientY
    const ctm = svg.getScreenCTM()
    if (!ctm) return { x: 0, y: 0 }
    const sp = pt.matrixTransform(ctm.inverse())
    return { x: sp.x, y: sp.y }
  }

  // Reset per-node drag overrides whenever a new network snapshot loads
  useEffect(() => {
    setNodeOverrides({})
  }, [network])

  // Wheel zoom (attached natively so we can preventDefault the page scroll/zoom)
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return undefined
    const onWheel = (e) => {
      e.preventDefault()
      const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15
      const p = clientToSvg(e.clientX, e.clientY)
      setView((v) => {
        const k2 = Math.min(K_MAX, Math.max(K_MIN, v.k * factor))
        const wx = (p.x - v.x) / v.k
        const wy = (p.y - v.y) / v.k
        return { k: k2, x: p.x - wx * k2, y: p.y - wy * k2 }
      })
    }
    svg.addEventListener('wheel', onWheel, { passive: false })
    return () => svg.removeEventListener('wheel', onWheel)
  }, [network])

  // Zoom centered on the canvas middle (for the toolbar buttons)
  const zoomBy = (factor) => {
    setView((v) => {
      const k2 = Math.min(K_MAX, Math.max(K_MIN, v.k * factor))
      const cx = W / 2
      const cy = H / 2
      const wx = (cx - v.x) / v.k
      const wy = (cy - v.y) / v.k
      return { k: k2, x: cx - wx * k2, y: cy - wy * k2 }
    })
  }
  const resetView = () => setView({ x: 0, y: 0, k: 1 })

  // ---- Drag handling (background = pan, node = move node) ----
  const onDragMove = (e) => {
    const d = dragRef.current
    if (!d) return
    const p = clientToSvg(e.clientX, e.clientY)
    if (d.mode === 'pan') {
      const dx = p.x - d.startX
      const dy = p.y - d.startY
      if (Math.abs(dx) + Math.abs(dy) > 2) d.moved = true
      setView((v) => ({ ...v, x: d.origX + dx, y: d.origY + dy }))
    } else if (d.mode === 'node') {
      const wx = (p.x - d.tx) / d.k
      const wy = (p.y - d.ty) / d.k
      setNodeOverrides((o) => ({ ...o, [d.nodeId]: { x: wx - d.offX, y: wy - d.offY } }))
      d.moved = true
    }
  }

  const endDrag = () => {
    const d = dragRef.current
    window.removeEventListener('mousemove', onDragMove)
    window.removeEventListener('mouseup', endDrag)
    // A node press without movement counts as a click -> select the node
    if (d && d.mode === 'node' && !d.moved) selectNode(d.nodeId)
    dragRef.current = null
  }

  const startPan = (e) => {
    if (e.button !== 0) return
    const p = clientToSvg(e.clientX, e.clientY)
    dragRef.current = {
      mode: 'pan', startX: p.x, startY: p.y, origX: view.x, origY: view.y, moved: false,
    }
    window.addEventListener('mousemove', onDragMove)
    window.addEventListener('mouseup', endDrag)
  }

  const startNodeDrag = (e, nodeId) => {
    if (e.button !== 0) return
    e.stopPropagation() // don't trigger background pan
    const p = clientToSvg(e.clientX, e.clientY)
    const base = posOf(nodeId) || { x: 0, y: 0 }
    const wx = (p.x - view.x) / view.k
    const wy = (p.y - view.y) / view.k
    dragRef.current = {
      mode: 'node', nodeId,
      k: view.k, tx: view.x, ty: view.y,
      offX: wx - base.x, offY: wy - base.y, moved: false,
    }
    window.addEventListener('mousemove', onDragMove)
    window.addEventListener('mouseup', endDrag)
  }

  const selectNode = async (nodeId) => {
    setSelectedNode(nodeId)
    setNodeProfile(null)
    try {
      const p = await api.getStudent(id, nodeId)
      setNodeProfile(p)
    } catch {
      setNodeProfile(null)
    }
  }

  const evoData = evolution
    ? evolution.snapshots.map((s) => ({
        day: s.day,
        density: Number(s.density.toFixed(4)),
        clustering: Number(s.avg_clustering.toFixed(4)),
      }))
    : []

  return (
    <div>
      <div className="page-header">
        <h2>社会网络可视化</h2>
        <p>力导向图 · 节点按学业成就着色 · 边按联结强度分色 · 每人默认仅显示 Top-5 强关系 · 时间轴回放演化</p>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="card">
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 8 }}>
          <span className="badge" style={{ color: '#38c7a4', borderColor: '#38c7a4' }}>
            — 强联结 {visTiers.strong}{allTiers ? ` / 全部 ${allTiers.strong}` : ''}
          </span>
          <span className="badge" style={{ color: '#4f8cff', borderColor: '#4f8cff' }}>
            — 中联结 {visTiers.mid}{allTiers ? ` / 全部 ${allTiers.mid}` : ''}
          </span>
          <span className="badge" style={{ color: '#8fa0bd', borderColor: '#8fa0bd' }}>
            — 弱联结 {visTiers.weak}{allTiers ? ` / 全部 ${allTiers.weak}` : ''}
          </span>
          <span className="muted" style={{ fontSize: 12 }}>节点颜色：蓝=低成就 → 绿=高成就</span>
        </div>
        <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
          边 = 同伴友谊强度（同质性演化）；恋爱/冲突等关系类型由关系状态机模块跟踪，当前未接入本图。
          Top-K 口径只保留每人最亲近的若干条边，显示颜色会偏向强联结；切换"显示全部边"可查看完整强度分布。
          升级前生成的旧运行，其边权仍为旧逻辑产物（普遍偏强），重新运行后生效新分布。
        </div>

        {!network && !error && <div className="loading">加载中…</div>}

        {network && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <button type="button" onClick={() => zoomBy(1.3)}>放大 +</button>
            <button type="button" onClick={() => zoomBy(1 / 1.3)}>缩小 −</button>
            <button type="button" onClick={resetView}>重置视图</button>
            <select value={topK} onChange={(e) => setTopK(Number(e.target.value))}>
              <option value={3}>每人 Top-3 关系</option>
              <option value={5}>每人 Top-5 关系</option>
              <option value={8}>每人 Top-8 关系</option>
              <option value={0}>显示全部边</option>
            </select>
            <span className="muted" style={{ fontSize: 12 }}>
              缩放 {Math.round(view.k * 100)}% · 滚轮缩放 · 空白处拖动平移 · 拖动节点调整位置 · 点击节点查看画像
            </span>
          </div>
        )}

        {network && (
          <svg
            ref={svgRef}
            width="100%"
            viewBox={`0 0 ${W} ${H}`}
            style={{ background: '#141b2b', borderRadius: 8, cursor: 'grab', touchAction: 'none', display: 'block' }}
            onMouseDown={startPan}
          >
            <g transform={`translate(${view.x},${view.y}) scale(${view.k})`}>
              {!layoutReady && (
                <text x={W / 2} y={H / 2} fill="#8fa0bd" textAnchor="middle">
                  布局计算中…
                </text>
              )}
              {layoutReady && visibleEdges.map((e, i) => {
                const a = posOf(e.source)
                const b = posOf(e.target)
                if (!a || !b) return null
                const et = edgeType(e.weight)
                return (
                  <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={et.color} strokeWidth={0.6 + e.weight * 2.2} opacity={0.25 + e.weight * 0.55} />
                )
              })}
              {layoutReady && network.nodes.map((n) => {
                const p = posOf(n.node_id)
                if (!p) return null
                return (
                  <circle
                    key={n.node_id}
                    cx={p.x}
                    cy={p.y}
                    r={selectedNode === n.node_id ? 9 : 6}
                    fill={achColor(n.achievement_score)}
                    stroke={selectedNode === n.node_id ? '#fff' : '#0f1420'}
                    strokeWidth={selectedNode === n.node_id ? 2 : 1}
                    style={{ cursor: 'pointer' }}
                    onMouseDown={(e) => startNodeDrag(e, n.node_id)}
                  >
                    <title>{`${n.node_id} · 成就 ${n.achievement_score.toFixed(1)}`}</title>
                  </circle>
                )
              })}
            </g>
          </svg>
        )}

        {network && (
          <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
            第 {days[dayIdx] ?? 0} 天 · 节点 {network.nodes.length} · 显示边 {visibleEdges.length} / 总边 {network.edges.length} ·
            密度 {network.density.toFixed(3)} · 平均聚类 {network.avg_clustering.toFixed(3)} ·
            连通分量 {network.n_components}
          </div>
        )}

        {evolution && (
          <div style={{ marginTop: 12 }}>
            <label>时间轴回放（天）：{days[dayIdx] ?? 0}</label>
            <input
              type="range"
              min={0}
              max={days.length - 1}
              value={dayIdx}
              onChange={(e) => setDayIdx(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>
        )}
      </div>

      {evolution && (
        <div className="card">
          <h3>网络指标演化</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={evoData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2c3a55" />
              <XAxis dataKey="day" stroke="#8fa0bd" />
              <YAxis stroke="#8fa0bd" />
              <Tooltip contentStyle={{ background: '#1a2233', border: '1px solid #2c3a55', borderRadius: 8 }} />
              <Legend />
              <Line type="monotone" dataKey="density" name="密度" stroke="#4f8cff" dot={false} />
              <Line type="monotone" dataKey="clustering" name="平均聚类" stroke="#38c7a4" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {selectedNode && (
        <div className="card">
          <h3>节点画像 · {selectedNode}</h3>
          {nodeProfile ? (
            <table>
              <tbody>
                <tr><td className="muted">姓名</td><td>{localName(nodeProfile.name)}</td></tr>
                <tr><td className="muted">性别</td><td>{t('gender', nodeProfile.gender)}</td></tr>
                <tr><td className="muted">成就分</td><td>{nodeProfile.achievement_score?.toFixed(1)}</td></tr>
                <tr><td className="muted">动机</td><td>{nodeProfile.motivation_level?.toFixed(2)}</td></tr>
                <tr><td className="muted">人格标签</td><td>{(nodeProfile.personality_tags || []).map((tag) => t('personality', tag)).join('、')}</td></tr>
              </tbody>
            </table>
          ) : (
            <div className="muted">加载画像中…</div>
          )}
        </div>
      )}
    </div>
  )
}
