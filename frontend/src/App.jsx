import React, { useEffect, useState } from 'react'
import { Routes, Route, NavLink, Navigate, useParams, useNavigate } from 'react-router-dom'
import api from './api.js'
import { t, registerLabels } from './i18n.js'
import { APP_VERSION_LABEL } from './version.js'
import HomePage from './pages/HomePage.jsx'
import PersonasPage from './pages/PersonasPage.jsx'
import ParentsPage from './pages/ParentsPage.jsx'
import TeachersPage from './pages/TeachersPage.jsx'
import TimelinePage from './pages/TimelinePage.jsx'
import ScenesPage from './pages/ScenesPage.jsx'
import SubgroupsPage from './pages/SubgroupsPage.jsx'
import TriadNetworkPage from './pages/TriadNetworkPage.jsx'
import QualityPage from './pages/QualityPage.jsx'
import RobustnessPage from './pages/RobustnessPage.jsx'
import LifeCoursePage from './pages/LifeCoursePage.jsx'
import CounterfactualPage from './pages/CounterfactualPage.jsx'
import ReportPage from './pages/ReportPage.jsx'
import CalibrationPage from './pages/CalibrationPage.jsx'
import DistortionMapPage from './pages/DistortionMapPage.jsx'
import PrescreeningPage from './pages/PrescreeningPage.jsx'
import HITLPage from './pages/HITLPage.jsx'
import LLMSettingsPage from './pages/LLMSettingsPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import RunComparePage from './pages/RunComparePage.jsx'
import DemoModePage from './pages/DemoModePage.jsx'
import ExportCenterPage from './pages/ExportCenterPage.jsx'

const NAV_SECTIONS = [
  {
    title: '📊 关键发现',
    items: [{ to: 'dashboard', label: '执行摘要' }]
  },
  {
    title: '👥 虚拟群体',
    items: [
      { to: 'personas', label: '学生画像' },
      { to: 'teachers', label: '教师档案' },
      { to: 'parents', label: '家长档案' },
      { to: 'triad_network', label: '三方关系图' },
    ]
  },
  {
    title: '🔬 干预分析',
    items: [
      { to: 'scenes', label: '场景效应对比' },
      { to: 'subgroups', label: '人群细分对比' },
      { to: 'counterfactual', label: '假设推演（What-If）' },
    ]
  },
  {
    title: '📈 时间序列',
    items: [
      { to: 'timeline', label: '学习轨迹回放' },
    ]
  },
  {
    title: '🔍 质量与决策',
    items: [
      { to: 'prescreening', label: '预筛决策' },
      { to: 'quality', label: '模型可信度' },
      { to: 'distortion', label: '可信度热力图' },
      { to: 'robustness', label: '稳健性检验' },
    ]
  },
  {
    title: '⚙️ 专家审阅',
    items: [{ to: 'hitl', label: '专家审阅' }]
  },
  {
    title: '📋 比赛材料',
    items: [{ to: 'export', label: '材料生成中心' }]
  },
]

function Shell() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [run, setRun] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    if (!id) return
    api.getRun(id)
      .then((r) => {
        if (cancelled) return
        setRun(r)
        const meta = r.intervention_meta || []
        if (meta.length) {
          const labels = {}
          for (const m of meta) if (m.id && m.label) labels[m.id] = m.label
          registerLabels('intervention', labels)
        }
      })
      .catch((e) => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [id])

  useEffect(() => {
    api.getCatalog()
      .then((cat) => {
        const labels = {}
        for (const it of cat.interventions || []) {
          if (it.id && it.label) labels[it.id] = it.label
        }
        registerLabels('intervention', labels)
      })
      .catch(() => {})
  }, [])

  if (error) {
    return (
      <div className="main">
        <div className="error-box">{error}</div>
        <button onClick={() => navigate('/')}>{'\u8fd4\u56de\u9996\u9875'}</button>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>{'\u865a\u62df\u5b66\u751f\u8bd5\u9a8c\u53f0'}</h1>
        <div className="sub">{APP_VERSION_LABEL} {'\u00b7'} {'\u591a\u667a\u80fd\u4f53\u4eff\u771f\u5e73\u53f0'}</div>
        <div className="sub" style={{ marginBottom: 8 }}>
          {'\u5f53\u524d\u8fd0\u884c\uff1a'}<span className="badge accent">{id}</span>
        </div>
        {run && (
          <div className="sub">
            {'\u72b6\u6001'} <span className="badge green">{t('status', run.status)}</span>
            <br />
            {'\u5b66\u751f'} {run.n_students} {'\u00b7'} {'\u6559\u5e08'} {run.n_teachers} {'\u00b7'} {run.sim_days} {'\u5929'}
          </div>
        )}
        <nav>
          {NAV_SECTIONS.map((section, sIdx) => (
            <div key={sIdx} style={{ marginBottom: 10 }}>
              <div className="nav-section-title">{section.title}</div>
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={`/runs/${id}/${item.to}`}
                  className={({ isActive }) => (isActive ? 'active' : '')}
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
          <NavLink to="/" className={({ isActive }) => (isActive ? 'active' : '')}
            style={{ marginTop: 8, borderTop: '1px solid #2c3a55', paddingTop: 8 }}>
            {'\u2190 \u8fd4\u56de\u8fd0\u884c\u7ba1\u7406'}
          </NavLink>
        </nav>
      </aside>
      <main className="main">
        <Routes>
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="report" element={<ReportPage />} />
          <Route path="personas" element={<PersonasPage />} />
          <Route path="parents" element={<ParentsPage />} />
          <Route path="teachers" element={<TeachersPage />} />
          <Route path="timeline" element={<TimelinePage />} />
          <Route path="scenes" element={<ScenesPage />} />
          <Route path="subgroups" element={<SubgroupsPage />} />
          <Route path="triad_network" element={<TriadNetworkPage />} />
          <Route path="life_course" element={<LifeCoursePage />} />
          <Route path="counterfactual" element={<CounterfactualPage />} />
          <Route path="quality" element={<QualityPage />} />
          <Route path="robustness" element={<RobustnessPage />} />
          <Route path="calibration" element={<CalibrationPage />} />
          <Route path="distortion" element={<DistortionMapPage />} />
          <Route path="prescreening" element={<PrescreeningPage />} />
          <Route path="hitl" element={<HITLPage />} />
          <Route path="*" element={<Navigate to="dashboard" replace />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/settings" element={<LLMSettingsPage />} />
      <Route path="/compare" element={<RunComparePage />} />
      <Route path="/runs/:id/demo" element={<DemoModePage />} />
      <Route path="/runs/:id/export" element={<ExportCenterPage />} />
      <Route path="/runs/:id/*" element={<Shell />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
