import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api.js'
import { t } from '../i18n.js'

// 20+ slicing dimensions (demo backend implements ses/gender/personality;
// others return empty and are flagged as "no data in demo").
const ALL_DIMS = [
  'ses', 'gender', 'personality', 'grade', 'age', 'school_type', 'region',
  'urban_rural', 'only_child', 'parent_education', 'parent_involvement',
  'shadow_edu_hours', 'sleep_hours', 'screen_time', 'exercise', 'reading_habit',
  'math_anxiety', 'self_efficacy', 'growth_mindset', 'peer_support',
  'teacher_style', 'class_size', 'commute_time', 'breakfast_habit',
]

const DIM_LABELS = {
  ses: '社会经济地位',
  gender: '性别',
  personality: '人格',
  grade: '年级',
  age: '年龄',
  school_type: '学校类型',
  region: '地区',
  urban_rural: '城乡',
  only_child: '独生子女',
  parent_education: '家长学历',
  parent_involvement: '家长参与度',
  shadow_edu_hours: '课外班时长',
  sleep_hours: '睡眠时长',
  screen_time: '屏幕时间',
  exercise: '运动',
  reading_habit: '阅读习惯',
  math_anxiety: '数学焦虑',
  self_efficacy: '自我效能',
  growth_mindset: '成长型思维',
  peer_support: '同伴支持',
  teacher_style: '教师风格',
  class_size: '班级规模',
  commute_time: '通勤时间',
  breakfast_habit: '早餐习惯',
}

export default function SubgroupsPage() {
  const { id } = useParams()
  const [selected, setSelected] = useState(['ses', 'gender', 'personality'])
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const toggle = (d) =>
    setSelected((prev) => (prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d]))

  useEffect(() => {
    if (!selected.length) {
      setResults([])
      return
    }
    let cancelled = false
    setLoading(true)
    api
      .getSubgroups(id, selected.join(','))
      .then((r) => !cancelled && setResults(r))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [id, selected])

  return (
    <div>
      <div className="page-header">
        <h2>子群切片</h2>
        <p>20+ 维度多选 · 实时刷新各子群效应量 · 失真标注</p>
      </div>

      <div className="card">
        <h3>选择切片维度（已选 {selected.length}）</h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {ALL_DIMS.map((d) => (
            <button
              key={d}
              className={selected.includes(d) ? '' : 'secondary'}
              style={{ fontSize: 12, padding: '5px 10px' }}
              onClick={() => toggle(d)}
            >
              {DIM_LABELS[d] || d}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}
      {loading && <div className="loading">加载中…</div>}

      {!loading &&
        results.map((r) => (
          <div className="card" key={r.dimension}>
            <h3>{DIM_LABELS[r.dimension] || r.dimension}（{r.dimension}）</h3>
            {r.groups.length === 0 ? (
              <div className="muted">演示后端暂无该维度数据。</div>
            ) : (
              <table>
                <thead>
                  <tr><th>子群</th><th>n</th><th>平均成就</th><th>效应量 g</th><th>失真标注</th></tr>
                </thead>
                <tbody>
                  {r.groups.map((g) => (
                    <tr key={g.label}>
                      <td>{t('subgroupLabel', g.label)}</td>
                      <td>{g.n}</td>
                      <td>{g.mean_ach.toFixed(1)}</td>
                      <td>{g.effect_size.toFixed(3)}</td>
                      <td>
                        {g.n < 120 ? (
                          <span className="badge" style={{ borderColor: '#f5a623', color: '#f5a623' }}>
                            小样本失真风险
                          </span>
                        ) : (
                          <span className="badge green">正常</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))}
    </div>
  )
}
