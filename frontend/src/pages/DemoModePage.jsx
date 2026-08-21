import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../api.js'

const DEMO_PAGES = [
  { path: 'dashboard', title: '执行摘要', duration: 8000, narration: '这是执行摘要页面，展示本次运行的核心发现和决策建议。评委可以在30秒内了解关键结论。' },
  { path: 'personas', title: '学生画像', duration: 6000, narration: '学生画像页面展示虚拟学生的23域219字段完整档案，包括认知参数、家庭背景、社交网络等。' },
  { path: 'network', title: '社会网络', duration: 6000, narration: '社会网络可视化展示学生间的同伴关系，节点颜色表示成绩水平，连线粗细表示关系强度。' },
  { path: 'scenes', title: '场景效应对比', duration: 6000, narration: '场景效应对比展示同一干预在不同场景（学校/家庭/课外班/自学）的效果差异。' },
  { path: 'counterfactual', title: '反事实推演', duration: 8000, narration: '反事实推演允许研究者自由设定变量效果值，观察假设性干预的因果效应。' },
  { path: 'distortion', title: '失真热力图', duration: 6000, narration: '失真热力图展示干预×场景的失真程度，高失真区证据在排序时会被降权。' },
  { path: 'prescreening', title: '预筛决策', duration: 8000, narration: '预筛决策页面给出GO/CONDITIONAL/NO-GO建议，帮助研究者决定是否进行真人试验。' },
  { path: 'report', title: '成果输出中心', duration: 8000, narration: '成果输出中心集中交付运行报告卡、教学改进建议和科学假设与研究计划。' },
]

export default function DemoModePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [timeLeft, setTimeLeft] = useState(0)
  const timerRef = useRef(null)
  const countdownRef = useRef(null)

  const currentPage = DEMO_PAGES[currentIndex]
  const iframeUrl = `/runs/${id}/${currentPage.path}`

  useEffect(() => {
    if (!isPlaying) return
    setTimeLeft(currentPage.duration / 1000)
    timerRef.current = setTimeout(() => {
      if (currentIndex < DEMO_PAGES.length - 1) {
        setCurrentIndex(currentIndex + 1)
      } else {
        setIsPlaying(false)
      }
    }, currentPage.duration)
    return () => clearTimeout(timerRef.current)
  }, [isPlaying, currentIndex])

  useEffect(() => {
    if (!isPlaying) return
    countdownRef.current = setInterval(() => {
      setTimeLeft((prev) => Math.max(0, prev - 1))
    }, 1000)
    return () => clearInterval(countdownRef.current)
  }, [isPlaying, currentIndex])

  const startDemo = () => {
    setCurrentIndex(0)
    setIsPlaying(true)
  }

  const pauseDemo = () => setIsPlaying(false)
  const resumeDemo = () => setIsPlaying(true)
  const nextSlide = () => {
    if (currentIndex < DEMO_PAGES.length - 1) {
      setCurrentIndex(currentIndex + 1)
    }
  }
  const prevSlide = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1)
    }
  }
  const exitDemo = () => navigate(`/runs/${id}/dashboard`)

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#0f1420' }}>
      {/* Top control bar */}
      <div style={{ background: '#1a2233', borderBottom: '1px solid #2c3a55', padding: '12px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, color: '#4f8cff' }}>演示模式</h2>
          <div style={{ fontSize: 12, color: '#8fa0bd', marginTop: 4 }}>
            {currentIndex + 1} / {DEMO_PAGES.length} · {currentPage.title}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {!isPlaying ? (
            <button onClick={currentIndex === 0 && timeLeft === 0 ? startDemo : resumeDemo}>
              {currentIndex === 0 && timeLeft === 0 ? '开始演示' : '继续'}
            </button>
          ) : (
            <button className="secondary" onClick={pauseDemo}>暂停</button>
          )}
          <button className="secondary" onClick={prevSlide} disabled={currentIndex === 0}>上一页</button>
          <button className="secondary" onClick={nextSlide} disabled={currentIndex === DEMO_PAGES.length - 1}>下一页</button>
          <button className="secondary" onClick={exitDemo}>退出演示</button>
          {isPlaying && (
            <div style={{ fontSize: 14, color: '#38c7a4', fontWeight: 600, minWidth: 40, textAlign: 'center' }}>
              {timeLeft}s
            </div>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ height: 4, background: '#2c3a55' }}>
        <div style={{ height: '100%', background: '#4f8cff', width: `${((currentIndex + 1) / DEMO_PAGES.length) * 100}%`, transition: 'width 0.3s ease' }} />
      </div>

      {/* Main content area */}
      <div style={{ flex: 1, position: 'relative' }}>
        <iframe
          src={iframeUrl}
          style={{ width: '100%', height: '100%', border: 'none' }}
          title={currentPage.title}
        />
      </div>

      {/* Bottom narration bar */}
      <div style={{ background: '#1a2233', borderTop: '1px solid #2c3a55', padding: '12px 20px' }}>
        <div style={{ fontSize: 13, color: '#e6ecf7', lineHeight: 1.6 }}>
          {currentPage.narration}
        </div>
      </div>
    </div>
  )
}
