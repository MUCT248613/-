import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api.js'
import { t } from '../i18n.js'

// 成果输出中心的三个交付物页签
const TABS = [
  { key: 'report', label: '运行报告卡' },
  { key: 'advice', label: '教学改进建议' },
  { key: 'plan', label: '科学假设与研究计划' },
]

// 触发浏览器下载完整 Markdown 成果报告
function downloadMarkdown(markdown, runId) {
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `成果报告_${runId}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export default function ReportPage() {
  const { id } = useParams()
  const [report, setReport] = useState(null)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('report')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .getReport(id)
      .then((r) => !cancelled && setReport(r))
      .catch((e) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [id])

  const copyMarkdown = async () => {
    if (!report) return
    try {
      await navigator.clipboard.writeText(report.markdown)
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard unavailable */
    }
  }

  if (error) return <div className="error-box">{error}</div>
  if (!report) return <div className="loading">正在汇编研究成果…</div>

  const rc = report.report_card || {}
  const plan = report.research_plan || {}
  const recs = report.recommendations || []
  const ov = rc.overview || {}

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2>成果输出中心</h2>
          <p>
            集中交付物：运行报告卡（M7）· 教学改进建议 · 科学假设与研究计划（M8，比赛硬性 G9）
            <br />
            所有数值来自虚拟模拟，引用零虚构；结论为假设候选，非事实。
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="button" onClick={() => downloadMarkdown(report.markdown, report.run_id)}>
            导出 Markdown 报告
          </button>
          <button type="button" className="secondary" onClick={() => exportAsHTML(report, report.run_id)}>
            导出 HTML (可打印PDF)
          </button>
          <button type="button" className="secondary" onClick={() => {
            const es = (report.report_card?.effect_sizes || []).map(e => ({ name: e.intervention_id, g: e.hedges_g }))
            exportChartAsSVG(es, `效应量_${report.run_id}`)
          }}>
            导出效应量图 (SVG)
          </button>
          <button type="button" className="secondary" onClick={copyMarkdown}>
            {copied ? '已复制 ✓' : '复制到剪贴板'}
          </button>
        </div>
      </div>

      <div className="privacy-note">{rc.privacy_note}</div>

      <div className="tabs">
        {TABS.map((tb) => (
          <button
            key={tb.key}
            type="button"
            className={tab === tb.key ? 'active' : ''}
            onClick={() => setTab(tb.key)}
          >
            {tb.label}
          </button>
        ))}
      </div>

      {/* ============ 运行报告卡 (M7) ============ */}
      {tab === 'report' && (
        <>
          <div className="card">
            <h3>运行概览</h3>
            <div className="row">
              <div className="stat"><span className="v">{ov.n_students}</span><span className="l">虚拟学生数</span></div>
              <div className="stat"><span className="v">{ov.n_teachers}</span><span className="l">虚拟教师数</span></div>
              <div className="stat"><span className="v">{ov.n_parents}</span><span className="l">虚拟家长数</span></div>
              <div className="stat"><span className="v">{ov.sim_days}</span><span className="l">模拟天数</span></div>
              <div className="stat"><span className="v">{rc.calibration?.cognitive_distance ?? '—'}</span><span className="l">认知距离（校准）</span></div>
            </div>
            <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              运行 ID：{report.run_id} · 随机种子：{ov.seed} · 生成时间：{report.generated_at?.replace('T', ' ').slice(0, 19)}
            </div>
          </div>

          <div className="card">
            <h3>虚拟效应量汇总（M4）</h3>
            <table>
              <thead>
                <tr><th>干预</th><th>场景</th><th>Hedges' g</th><th>95% CI</th><th>样本量</th></tr>
              </thead>
              <tbody>
                {(rc.effect_sizes || []).map((es) => (
                  <tr key={`${es.intervention_id}-${es.scene}`}>
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

          <div className="card">
            <h3>
              优先干预排序（M6）
              <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>
                　高失真证据会被降权，绝不给高优先级
              </span>
            </h3>
            <table>
              <thead>
                <tr><th>排名</th><th>干预</th><th>优先级得分</th><th>效应量</th><th>确定性</th><th>可达性</th><th>成本效率</th><th>失真区</th></tr>
              </thead>
              <tbody>
                {(rc.priority_ranking || []).map((r) => (
                  <tr key={r.intervention_id}>
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

          <div className="card">
            <h3>
              差距与失真分析（M5）
              <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>
                　高失真记录 {rc.gap_analysis?.n_high_distortion ?? 0} 条
              </span>
            </h3>
            <table>
              <thead>
                <tr><th>指标族</th><th>干预</th><th>场景</th><th>差距幅度</th><th>失真方向</th></tr>
              </thead>
              <tbody>
                {(rc.gap_analysis?.records || []).slice(0, 12).map((g, i) => (
                  <tr key={i}>
                    <td>{t('gapMetric', g.metric)}</td>
                    <td>{t('intervention', g.intervention_id)}</td>
                    <td>{t('scene', g.scene)}</td>
                    <td className="muted">{g.gap_magnitude?.toFixed(3)}</td>
                    <td>
                      {g.distortion_category === 'none'
                        ? <span className="badge green">无失真</span>
                        : <span className="badge" style={{ color: '#f5a623', borderColor: '#f5a623' }}>{t('distortion', g.distortion_category)}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* ============ 教学改进建议 ============ */}
      {tab === 'advice' && (
        <>
          {recs.map((rec) => (
            <div className="card" key={rec.intervention_id}>
              <h3>
                {rec.rank}. {rec.action}
                <span className="badge accent" style={{ marginLeft: 8 }}>{t('intervention', rec.intervention_id)}</span>
              </h3>
              <table>
                <tbody>
                  <tr><td className="muted" style={{ width: 110 }}>证据</td><td>{rec.evidence}（效应强度：{rec.strength}）</td></tr>
                  <tr><td className="muted">置信度</td><td>{rec.confidence}</td></tr>
                  <tr><td className="muted">失真警告</td><td>{rec.distortion_warning}</td></tr>
                  <tr><td className="muted">优先级得分</td><td>{rec.priority_score?.toFixed(3)}</td></tr>
                </tbody>
              </table>
            </div>
          ))}
          <div className="privacy-note">
            每条建议均携带三要素：证据（效应量 + 95% CI）、置信度、失真警告。位于高失真区的建议仅供方向性参考。
          </div>
        </>
      )}

      {/* ============ 科学假设与研究计划 (M8) ============ */}
      {tab === 'plan' && (
        <>
          <div className="card">
            <h3>{plan.title || '科学假设与研究计划'}</h3>
            {plan.narrative && <p style={{ lineHeight: 1.7 }}>{plan.narrative}</p>}
            <div className="muted" style={{ fontSize: 12 }}>
              生成依据：{plan.generated_from?.n_ranked} 个排序干预 · {plan.generated_from?.n_effect_sizes} 项效应量证据
            </div>
          </div>

          <div className="card">
            <h3>研究假设（均可证伪）</h3>
            {(plan.hypotheses || []).map((h) => (
              <div key={h.id} style={{ marginBottom: 12, lineHeight: 1.7 }}>
                <span className="badge accent">{h.id}</span>
                <span className="badge">{t('intervention', h.intervention_id)}</span>
                <div style={{ marginTop: 4 }}>{h.statement}</div>
              </div>
            ))}
          </div>

          <div className="card">
            <h3>研究计划各节</h3>
            {Object.entries(plan.sections || {}).map(([sec, text]) => (
              <div key={sec} style={{ marginBottom: 14 }}>
                <div style={{ fontWeight: 600, color: '#38c7a4', marginBottom: 4 }}>{sec}</div>
                <div style={{ lineHeight: 1.7 }}>{text}</div>
              </div>
            ))}
          </div>

          <div className="card">
            <h3>虚拟证据引用（零虚构）</h3>
            <table>
              <thead>
                <tr><th>干预</th><th>Hedges' g</th><th>95% CI</th><th>说明</th></tr>
              </thead>
              <tbody>
                {(plan.references || []).map((ref) => (
                  <tr key={ref.intervention_id}>
                    <td>{t('intervention', ref.intervention_id)}</td>
                    <td><strong>{ref.hedges_g?.toFixed(3)}</strong></td>
                    <td className="muted">[{(ref.ci_95?.[0] ?? 0).toFixed(3)}, {(ref.ci_95?.[1] ?? 0).toFixed(3)}]</td>
                    <td className="muted">{ref.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              引用仅为虚拟模拟效应量，不含任何未经核实的外部文献。
            </div>
          </div>
        </>
      )}
    </div>
  )
}
