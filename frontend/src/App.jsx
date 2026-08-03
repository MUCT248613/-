import React, { useEffect, useState, useCallback } from 'react'
import { Routes, Route, NavLink, Navigate, useParams, useNavigate } from 'react-router-dom'
import api from './api.js'
import { t } from './i18n.js'
import HomePage from './pages/HomePage.jsx'
import PersonasPage from './pages/PersonasPage.jsx'
import ParentsPage from './pages/ParentsPage.jsx'
import TimelinePage from './pages/TimelinePage.jsx'
import ScenesPage from './pages/ScenesPage.jsx'
import SubgroupsPage from './pages/SubgroupsPage.jsx'
import NetworkPage from './pages/NetworkPage.jsx'
import LifeCoursePage from './pages/LifeCoursePage.jsx'
import CounterfactualPage from './pages/CounterfactualPage.jsx'
import ReportPage from './pages/ReportPage.jsx'
import CalibrationPage from './pages/CalibrationPage.jsx'
import DistortionMapPage from './pages/DistortionMapPage.jsx'
import PrescreeningPage from './pages/PrescreeningPage.jsx'
import HITLPage from './pages/HITLPage.jsx'
import LLMSettingsPage from './pages/LLMSettingsPage.jsx'

const NAV_ITEMS = [
  { to: 'report', label: '成果输出中心' },
  { to: 'personas', label: '画像浏览' },
  { to: 'parents', label: '家长档案' },
  { to: 'timeline', label: 'L-Model 时间轴' },
  { to: 'scenes', label: '场景比较' },
  { to: 'subgroups', label: '子群切片' },
  { to: 'network', label: '社会网络' },
  { to: 'life_course', label: '生命历程回放' },
  { to: 'counterfactual', label: '反事实对比' },
  { to: 'calibration', label: '校准诊断' },
  { to: 'distortion', label: '失真地图' },
  { to: 'prescreening', label: '预筛报告' },
  { to: 'hitl', label: '人在回路' },
]

function Shell() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [run, setRun] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    if (!id) return
    api
      .getRun(id)
      .then((r) => {
        if (!cancelled) setRun(r)
      })
      .catch((e) => {
        if (!cancelled) setError(e.message)
      })
    return () => {
      cancelled = true
    }
  }, [id])

  if (error) {
    return (
      <div className="main">
        <div className="error-box">{error}</div>
        <button onClick={() => navigate('/')}>返回首页</button>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>虚拟学生试验台</h1>
        <div className="sub">v5.0 · 多智能体仿真平台</div>
        <div className="sub" style={{ marginBottom: 8 }}>
          当前运行：<span className="badge accent">{id}</span>
        </div>
        {run && (
          <div className="sub">
            状态 <span className="badge green">{t('status', run.status)}</span>
            <br />
            学生 {run.n_students} · 教师 {run.n_teachers} · {run.sim_days} 天
          </div>
        )}
        <nav>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={`/runs/${id}/${item.to}`}
              className={({ isActive }) => (isActive ? 'active' : '')}
            >
              {item.label}
            </NavLink>
          ))}
          <NavLink to="/" className={({ isActive }) => (isActive ? 'active' : '')}>
            ← 返回运行管理
          </NavLink>
        </nav>
      </aside>
      <main className="main">
        <Routes>
          <Route path="report" element={<ReportPage />} />
          <Route path="personas" element={<PersonasPage />} />
          <Route path="parents" element={<ParentsPage />} />
          <Route path="timeline" element={<TimelinePage />} />
          <Route path="scenes" element={<ScenesPage />} />
          <Route path="subgroups" element={<SubgroupsPage />} />
          <Route path="network" element={<NetworkPage />} />
          <Route path="life_course" element={<LifeCoursePage />} />
          <Route path="counterfactual" element={<CounterfactualPage />} />
          <Route path="calibration" element={<CalibrationPage />} />
          <Route path="distortion" element={<DistortionMapPage />} />
          <Route path="prescreening" element={<PrescreeningPage />} />
          <Route path="hitl" element={<HITLPage />} />
          <Route path="*" element={<Navigate to="personas" replace />} />
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
      <Route path="/runs/:id/*" element={<Shell />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
