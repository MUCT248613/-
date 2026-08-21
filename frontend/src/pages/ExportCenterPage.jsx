import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../api.js'
import { t } from '../i18n.js'
import { APP_VERSION_LABEL } from '../version.js'

export default function ExportCenterPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api.getRun(id),
      api.getReport(id),
      api.getPrescreening(id),
    ])
      .then(([run, report, prescreening]) => {
        if (cancelled) return
        setData({ run, report, prescreening })
        setLoading(false)
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e.message)
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [id])

  const generateA4Summary = () => {
    if (!data) return
    const { run, report, prescreening } = data
    const rc = report.report_card || {}
    const effectSizes = (rc.effect_sizes || [])
      .sort((a, b) => Math.abs(b.hedges_g) - Math.abs(a.hedges_g))
      .slice(0, 3)

    const bestIntv = effectSizes[0]
    const conclusion = bestIntv && prescreening.go_count > 0
      ? `本次运行发现 ${t('intervention', bestIntv.intervention_id)} 在 ${t('scene', bestIntv.scene)} 场景效果最佳（g=${bestIntv.hedges_g.toFixed(2)}），建议优先实证。`
      : prescreening.conditional_count > 0
      ? `本次运行发现 ${prescreening.conditional_count} 个干预有条件性推荐，需补充条件后可考虑实证。`
      : `本次运行未发现显著有效的干预方案，建议调整假设后重新测试。`

    const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>虚拟学生试验台 ${APP_VERSION_LABEL} - 执行摘要</title>
<style>
  @page { size: A4; margin: 20mm; }
  body { font-family: "Microsoft YaHei", "SimHei", sans-serif; font-size: 12pt; line-height: 1.6; color: #333; }
  h1 { font-size: 20pt; color: #2c5aa0; border-bottom: 3px solid #2c5aa0; padding-bottom: 8px; margin-bottom: 20px; }
  h2 { font-size: 14pt; color: #2c5aa0; margin-top: 20px; margin-bottom: 10px; }
  .conclusion { background: #f0f7ff; border-left: 4px solid #2c5aa0; padding: 12px; margin: 16px 0; font-size: 13pt; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; }
  th { background: #2c5aa0; color: white; padding: 8px; text-align: left; }
  td { border: 1px solid #ddd; padding: 8px; }
  tr:nth-child(even) { background: #f9f9f9; }
  .stats { display: flex; gap: 20px; margin: 16px 0; }
  .stat-box { flex: 1; background: #f5f5f5; padding: 12px; text-align: center; border-radius: 4px; }
  .stat-value { font-size: 18pt; font-weight: bold; color: #2c5aa0; }
  .stat-label { font-size: 10pt; color: #666; }
  .chart-placeholder { background: #f0f0f0; border: 2px dashed #ccc; padding: 40px; text-align: center; color: #999; margin: 16px 0; }
  .footer { margin-top: 30px; padding-top: 12px; border-top: 1px solid #ddd; font-size: 9pt; color: #999; text-align: center; }
  @media print { body { font-size: 11pt; } .no-print { display: none; } }
</style>
</head>
<body>
<h1>虚拟学生试验台 ${APP_VERSION_LABEL} - 执行摘要</h1>
<div class="stats">
  <div class="stat-box">
    <div class="stat-value">${run.n_students}</div>
    <div class="stat-label">虚拟学生</div>
  </div>
  <div class="stat-box">
    <div class="stat-value">${effectSizes.length}</div>
    <div class="stat-label">干预方案</div>
  </div>
  <div class="stat-box">
    <div class="stat-value" style="color: #38c7a4;">${prescreening.go_count || 0}</div>
    <div class="stat-label">GO 推荐</div>
  </div>
  <div class="stat-box">
    <div class="stat-value" style="color: #f5a623;">${prescreening.conditional_count || 0}</div>
    <div class="stat-label">CONDITIONAL</div>
  </div>
  <div class="stat-box">
    <div class="stat-value" style="color: #ef5b6b;">${prescreening.no_go_count || 0}</div>
    <div class="stat-label">NO-GO</div>
  </div>
</div>

<h2>核心发现</h2>
<div class="conclusion">${conclusion}</div>

<h2>Top 3 干预效应量</h2>
<table>
  <thead>
    <tr><th>干预</th><th>场景</th><th>Hedges' g</th><th>95% CI</th><th>样本量</th></tr>
  </thead>
  <tbody>
    ${effectSizes.map(es => `<tr>
      <td>${t('intervention', es.intervention_id)}</td>
      <td>${t('scene', es.scene)}</td>
      <td><strong>${es.hedges_g.toFixed(3)}</strong></td>
      <td>[${es.ci_lower.toFixed(3)}, ${es.ci_upper.toFixed(3)}]</td>
      <td>${es.sample_size}</td>
    </tr>`).join('')}
  </tbody>
</table>

<h2>关键图表</h2>
<div class="chart-placeholder">[效应量对比图 - 请从系统截图]</div>
<div class="chart-placeholder">[预筛决策分布图 - 请从系统截图]</div>

<div class="footer">
  生成时间：${new Date().toLocaleString('zh-CN')} | 运行 ID：${id}<br>
  虚拟学生试验台 ${APP_VERSION_LABEL} - 多智能体仿真平台
</div>

<div class="no-print" style="margin-top: 30px; text-align: center;">
  <button onclick="window.print()" style="padding: 10px 20px; font-size: 12pt; cursor: pointer;">打印为 PDF</button>
</div>
</body>
</html>`

    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `虚拟学生试验台_摘要_${id}.html`
    a.click()
    URL.revokeObjectURL(url)
  }

  const generatePPTOutline = () => {
    if (!data) return
    const { run, report, prescreening } = data
    const rc = report.report_card || {}
    const effectSizes = (rc.effect_sizes || [])
      .sort((a, b) => Math.abs(b.hedges_g) - Math.abs(a.hedges_g))
      .slice(0, 3)

    const bestIntv = effectSizes[0]
    const conclusion = bestIntv && prescreening.go_count > 0
      ? `${t('intervention', bestIntv.intervention_id)} 在 ${t('scene', bestIntv.scene)} 场景效果最佳（g=${bestIntv.hedges_g.toFixed(2)}），建议优先实证`
      : prescreening.conditional_count > 0
      ? `${prescreening.conditional_count} 个干预有条件性推荐`
      : `未发现显著有效的干预方案`

    const markdown = `# 虚拟学生试验台 ${APP_VERSION_LABEL} 研究报告

---

## 第1页：问题与定位

**研究问题**
- 如何通过虚拟仿真预测教育干预的真实效果？
- 如何在不进行真人试验的情况下筛选最有潜力的干预方案？

**项目定位**
- 虚拟学生试验台：基于多智能体仿真的教育干预预筛平台
- 目标：降低真人试验成本，加速有效干预方案的发现

---

## 第2页：虚拟学生生成

**4层人格生成架构**
- L1：基础骨架（人口统计学特征）
- L2：LLM 身份种子（个性、动机、学习风格）
- L3：衍生层（社会关系、家庭背景）
- L4：一致性引擎（确保人格内部一致且独特）

**本次运行规模**
- 虚拟学生：${run.n_students} 人
- 虚拟教师：${run.n_teachers} 人
- 模拟天数：${run.sim_days} 天

---

## 第3页：核心发现

**干预效应量 Top 3**
${effectSizes.map((es, idx) => `${idx + 1}. **${t('intervention', es.intervention_id)}**（${t('scene', es.scene)}）
   - Hedges' g = ${es.hedges_g.toFixed(3)} [${es.ci_lower.toFixed(3)}, ${es.ci_upper.toFixed(3)}]
   - 样本量：${es.sample_size}`).join('\n\n')}

**预筛决策分布**
- GO（推荐实证）：${prescreening.go_count || 0} 个
- CONDITIONAL（有条件推荐）：${prescreening.conditional_count || 0} 个
- NO-GO（暂不推荐）：${prescreening.no_go_count || 0} 个

---

## 第4页：质量保障

**校准验证**
- 虚拟学生 BKT 参数与文献基线的认知距离
- 确保虚拟群体在认知层面与真实学生具有可比性

**可信度诊断**
- 失真热力图：识别哪些干预-场景组合的结论可能不可靠
- 稳健性检验：验证结论是否依赖于特定随机种子或样本量

**预筛标准**
- 效应量阈值：|g| >= 0.20
- 置信区间：95% CI 不跨零
- 非高失真区
- 优先级得分 >= 0.40

---

## 第5页：结论与建议

**核心结论**
${conclusion}

**下一步行动**
${prescreening.go_count > 0 ? `- 优先对 ${t('intervention', bestIntv?.intervention_id || '')} 进行真人试验验证
- 在 ${t('scene', bestIntv?.scene || '')} 场景下实施
- 样本量建议：至少 30 人/组` : `- 调整干预假设后重新测试
- 考虑增加虚拟学生数量以提高统计功效
- 探索其他干预类型或场景组合`}

**重要提示**
⚠️ 以上为虚拟仿真结果，需真人试验验证，不可直接外推

---

*生成时间：${new Date().toLocaleString('zh-CN')}*
*运行 ID：${id}*
`

    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `虚拟学生试验台_PPT大纲_${id}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const generateDemoScript = () => {
    if (!data) return
    const { run, report, prescreening } = data
    const rc = report.report_card || {}
    const effectSizes = (rc.effect_sizes || [])
      .sort((a, b) => Math.abs(b.hedges_g) - Math.abs(a.hedges_g))
      .slice(0, 3)

    const bestIntv = effectSizes[0]

    const script = `虚拟学生试验台 ${APP_VERSION_LABEL} 演示脚本
=====================================

【开场】（30秒）
"各位评委好，今天为大家展示虚拟学生试验台 ${APP_VERSION_LABEL} —— 一个基于多智能体仿真的教育干预预筛平台。"

---

【第1站：执行摘要】（建议停留：2分钟）
页面：执行摘要（Dashboard）

解说词：
"这是本次运行的执行摘要。我们生成了 ${run.n_students} 名虚拟学生，测试了 ${effectSizes.length} 个干预方案。"

${bestIntv ? `"核心发现是：${t('intervention', bestIntv.intervention_id)} 在 ${t('scene', bestIntv.scene)} 场景下效果最佳，Hedges' g 达到 ${bestIntv.hedges_g.toFixed(2)}，建议优先进行真人试验验证。"` : ''}

重点标注：
- 一句话结论卡片（蓝色高亮）
- Top 3 效应量柱状图
- 预筛决策分布饼图

---

【第2站：虚拟学生画像】（建议停留：1.5分钟）
页面：学生画像（Personas）

解说词：
"虚拟学生通过4层架构生成：基础骨架、LLM身份种子、衍生层、一致性引擎。每个人格都是独特且内部一致的。"

"点击任意学生可以查看详细信息，包括认知参数、人格特征、家庭背景等。"

重点标注：
- 学生列表表格
- 点击展开详情
- 展示人格多样性

---

【第3站：干预分析】（建议停留：2.5分钟）
页面：场景效应对比（Scenes）

解说词：
"这是场景效应对比页面。不同干预在不同场景下的效果差异明显。"

${bestIntv ? `"例如，${t('intervention', bestIntv.intervention_id)} 在 ${t('scene', bestIntv.scene)} 场景下的效应量最高，这提示我们干预的效果高度依赖于实施场景。"` : ''}

重点标注：
- 场景对比柱状图
- 效应量数值
- 置信区间误差线

---

【第4站：效果路径】（建议停留：2分钟）
页面：效果路径分析（Mediation）

解说词：
"效果路径分析展示了干预通过哪些渠道生效。例如，教师中介的干预可能通过提升学生动机来改善成绩。"

"不同颜色代表不同通道：绿色是教师中介，橙色是家长中介，蓝色是直接效应。"

重点标注：
- SVG 路径流程图
- 通道颜色区分
- 中介变量标注

---

【第5站：质量诊断】（建议停留：1.5分钟）
页面：质量与决策（Quality）

解说词：
"质量诊断页面展示了结论的可信度。失真热力图帮助我们识别哪些结论可能不可靠。"

"虚拟 vs 文献对比卡片展示了虚拟学生的 BKT 参数与文献基线的差异，确保我们的虚拟群体在认知层面是合理的。"

重点标注：
- 认知距离数值
- pass/marginal/fail 判定
- ⚠️ 警示提示

---

【第6站：预筛决策】（建议停留：1.5分钟）
页面：预筛报告（Prescreening）

解说词：
"预筛报告是最终的决策支持工具。我们设置了4个标准：效应量阈值、置信区间、失真区检查、优先级得分。"

${prescreening.go_count > 0 ? `"本次运行有 ${prescreening.go_count} 个干预通过了所有标准，被标记为 GO，推荐进入真人试验。"` : ''}

${prescreening.no_go_count > 0 ? `"同时，我们排除了 ${prescreening.no_go_count} 个不靠谱的假设，节省了真人试验的成本。"` : ''}

重点标注：
- GO/CONDITIONAL/NO-GO 分布
- 排除原因列
- 判定标准说明

---

【收尾】（30秒）
"以上就是虚拟学生试验台的核心功能展示。通过虚拟仿真，我们可以在不进行真人试验的情况下，快速筛选出最有潜力的干预方案，大幅降低研究成本。"

"需要注意的是，虚拟结果需要真人试验验证，不可直接外推。但它可以指导我们优先测试哪些干预，提高研究效率。"

"谢谢各位评委！"

---

【演示时间控制】
- 总时长：约 12-15 分钟
- 每站建议停留已标注
- 可根据评委反应灵活调整

【重点强调】
1. 虚拟学生的真实性（4层架构）
2. 效应量的科学性（Hedges' g + 95% CI）
3. 质量保障的严谨性（校准、失真图、稳健性）
4. 预筛决策的实用性（降低真人试验成本）

【常见问题准备】
Q: 虚拟学生和真实学生有什么区别？
A: 虚拟学生基于真实教育心理学理论生成，但毕竟是仿真。我们的校准验证确保虚拟群体在关键认知参数上与文献基线一致。

Q: 效应量可以外推到真实场景吗？
A: 不可以直接外推。虚拟仿真的价值在于预筛 —— 帮助我们识别哪些干预值得真人试验，而不是替代真人试验。

Q: 如何确保结论的可靠性？
A: 我们通过多重质量保障：校准验证、失真热力图、稳健性检验、预筛标准。只有同时通过所有标准的干预才会被推荐。
`

    const blob = new Blob([script], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `虚拟学生试验台_演示脚本_${id}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) return <div className="loading">加载中...</div>
  if (error) return <div className="error-box">{error}</div>
  if (!data) return null

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 24px 48px' }}>
      <div className="page-header">
        <h2>📦 比赛材料生成中心</h2>
        <p>一键生成比赛所需的各种材料</p>
      </div>

      <div className="card" style={{ background: 'linear-gradient(135deg, #1a2233 0%, #222d42 100%)', border: '1px solid #4f8cff' }}>
        <div style={{ fontSize: 16, fontWeight: 600, color: '#4f8cff', marginBottom: 12 }}>
          💡 使用说明
        </div>
        <div style={{ fontSize: 14, lineHeight: 1.8 }}>
          本页面提供三种比赛材料导出功能，所有材料均基于当前运行（{id}）的数据生成。
          点击下方按钮即可下载对应格式的材料。
        </div>
      </div>

      <div className="card">
        <h3>📄 A4 一页纸摘要</h3>
        <div className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
          生成 HTML 格式的摘要页面，包含项目标题、一句话结论、Top 3 效应量表格、预筛决策统计。
          样式已针对 A4 打印优化，可直接在浏览器中打印为 PDF。
        </div>
        <button onClick={generateA4Summary} style={{ fontSize: 14, padding: '10px 20px' }}>
          📥 下载 A4 摘要（HTML）
        </button>
      </div>

      <div className="card">
        <h3>📊 5 页 PPT 大纲</h3>
        <div className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
          生成 Markdown 格式的 PPT 大纲，每页一个核心发现：
          第1页：问题与定位；第2页：虚拟学生生成；第3页：核心发现；第4页：质量保障；第5页：结论与建议。
          评委可以直接复制内容到 PPT。
        </div>
        <button onClick={generatePPTOutline} style={{ fontSize: 14, padding: '10px 20px' }}>
          📥 下载 PPT 大纲（Markdown）
        </button>
      </div>

      <div className="card">
        <h3>🎬 演示视频脚本</h3>
        <div className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
          生成文本格式的演示脚本，包含逐页解说词、建议停留时间、重点标注。
          适合录制演示视频或现场演示时参考。
        </div>
        <button onClick={generateDemoScript} style={{ fontSize: 14, padding: '10px 20px' }}>
          📥 下载演示脚本（TXT）
        </button>
      </div>

      <div className="card">
        <h3>🚀 快速操作</h3>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <button onClick={() => navigate(`/runs/${id}/dashboard`)}>
            📊 返回执行摘要
          </button>
          <button className="secondary" onClick={() => navigate(`/runs/${id}/demo`)}>
            🎭 进入演示模式
          </button>
          <button className="secondary" onClick={() => navigate('/')}>
            🏠 返回首页
          </button>
        </div>
      </div>
    </div>
  )
}
