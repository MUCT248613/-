import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api.js'
import { t, localName, localGrade } from '../i18n.js'

// Domain grouping for the profile card. The archive served by the API is
// already PrivacyGuard-filtered: the S-level D11 domain is stripped (FR-A8).
const DOMAIN_TABS = [
  { key: 'basic', label: '基本信息' },
  { key: 'academic', label: '学业' },
  { key: 'motivation', label: '动机' },
  { key: 'personality', label: '人格' },
  { key: 'interests', label: '兴趣' },
  { key: 'cognitive', label: '认知参数' },
  { key: 'family', label: '家庭' },
  { key: 'teacher', label: '教师' },
  { key: 'influence', label: '影响通路' },
  { key: 'full_archive', label: '全方位档案(P/R级)' },
]

function fmt(v) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') return Number.isInteger(v) ? v : v.toFixed(3)
  return String(v)
}

// 影响通路：教师/家长在模拟中如何影响该学生。通道效率公式与
// src/delivery/intervention_delivery.py 保持一致：
//   teacher_mediated = 0.7 * fidelity；parent_mediated = 0.5 * involvement_level。
function InfluencePanel({ student, teacher, parent }) {
  const tvec = (teacher && teacher.simulation_vector) || {}
  const pvec = (parent && parent.simulation_vector) || {}
  const tEff = tvec.fidelity != null ? 0.7 * tvec.fidelity : null
  const pEff = pvec.involvement_level != null ? 0.5 * pvec.involvement_level : null
  const bar = (v) => (
    <span style={{ background: '#1b2740', borderRadius: 4, height: 8, width: 140, display: 'inline-block', verticalAlign: 'middle', marginLeft: 8 }}>
      <span style={{ display: 'block', background: '#4f8cff', borderRadius: 4, height: 8, width: `${Math.round(Math.max(0, Math.min(1, v)) * 100)}%` }} />
    </span>
  )
  return (
    <div>
      <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
        模拟中教师与家长通过干预通道影响学生结果：教师通道预期执行效率 = 0.7 × 执行保真度；家长通道 = 0.5 × 参与水平。数值来自该学生的分配教师/主要家长画像。
      </p>
      <table>
        <tbody>
          <tr><td className="muted">教师通道（T-Model）</td><td>{teacher ? `${localName(teacher.name)} · ${t('teachingStyle', teacher.teaching_style)}` : '未分配教师'}</td></tr>
          <tr><td className="muted">执行保真度 fidelity</td><td>{tvec.fidelity != null ? <>{fmt(tvec.fidelity)}{bar(tvec.fidelity)}</> : '—'}</td></tr>
          <tr><td className="muted">教师通道预期效率</td><td>{tEff != null ? fmt(tEff) : '—'}</td></tr>
          <tr><td className="muted">家长通道（P-Model）</td><td>{parent ? `${localName(parent.name)} · ${parent.involvement_style || '—'}` : '未分配家长'}</td></tr>
          <tr><td className="muted">参与水平 involvement</td><td>{pvec.involvement_level != null ? <>{fmt(pvec.involvement_level)}{bar(pvec.involvement_level)}</> : '—'}</td></tr>
          <tr><td className="muted">支持质量 support_quality</td><td>{pvec.support_quality != null ? fmt(pvec.support_quality) : '—'}</td></tr>
          <tr><td className="muted">家长通道预期效率</td><td>{pEff != null ? fmt(pEff) : '—'}</td></tr>
        </tbody>
      </table>
    </div>
  )
}

function DomainPanel({ student, domain, teacher, parent }) {
  const sv = student.simulation_vector || {}
  switch (domain) {
    case 'basic':
      return (
        <table>
          <tbody>
            <tr><td className="muted">学生 ID</td><td>{student.student_id}</td></tr>
            <tr><td className="muted">姓名</td><td>{localName(student.name)}</td></tr>
            <tr><td className="muted">年龄</td><td>{fmt(student.age)}</td></tr>
            <tr><td className="muted">性别</td><td>{t('gender', student.gender) ?? '—'}</td></tr>
            <tr><td className="muted">年级</td><td>{localGrade(student.grade) ?? '—'}</td></tr>
          </tbody>
        </table>
      )
    case 'academic':
      return (
        <table>
          <tbody>
            <tr><td className="muted">学业成就分</td><td>{fmt(student.achievement_score)}</td></tr>
            <tr><td className="muted">知识掌握概率（p_know）</td><td>{fmt(sv.p_know)}</td></tr>
            <tr><td className="muted">学习转移概率（p_learn）</td><td>{fmt(sv.p_learn)}</td></tr>
          </tbody>
        </table>
      )
    case 'motivation':
      return (
        <table>
          <tbody>
            <tr><td className="muted">动机水平</td><td>{fmt(student.motivation_level)}</td></tr>
            <tr><td className="muted">动机水平（仿真值）</td><td>{fmt(sv.motivation)}</td></tr>
          </tbody>
        </table>
      )
    case 'personality':
      return (
        <div>
          {(student.personality_tags || []).map((tag) => (
            <span key={tag} className="badge accent">{t('personality', tag)}</span>
          ))}
          {(student.personality_tags || []).length === 0 && <span className="muted">无标签</span>}
        </div>
      )
    case 'interests':
      return (
        <div>
          {(student.interests || []).map((tag) => (
            <span key={tag} className="badge green">{t('interests', tag)}</span>
          ))}
          {(student.interests || []).length === 0 && <span className="muted">无兴趣记录</span>}
        </div>
      )
    case 'cognitive':
      return (
        <table>
          <tbody>
            <tr><td className="muted">知识掌握概率（p_know）</td><td>{fmt(sv.p_know)}</td></tr>
            <tr><td className="muted">学习转移概率（p_learn）</td><td>{fmt(sv.p_learn)}</td></tr>
            <tr><td className="muted">失误概率（p_slip）</td><td>{fmt(sv.p_slip)}</td></tr>
            <tr><td className="muted">猜测概率（p_guess）</td><td>{fmt(sv.p_guess)}</td></tr>
            <tr><td className="muted">动机水平</td><td>{fmt(sv.motivation)}</td></tr>
          </tbody>
        </table>
      )
    case 'family':
      return (
        <table>
          <tbody>
            <tr><td className="muted">主要家长 ID</td><td>{fmt(student.primary_parent_id)}</td></tr>
          </tbody>
        </table>
      )
    case 'teacher':
      return (
        <table>
          <tbody>
            <tr><td className="muted">分配教师 ID</td><td>{fmt(student.assigned_teacher_id)}</td></tr>
            {teacher && (
              <>
                <tr><td className="muted">教师姓名</td><td>{localName(teacher.name)}</td></tr>
                <tr><td className="muted">教龄（年）</td><td>{fmt(teacher.experience_years)}</td></tr>
                <tr><td className="muted">教学风格</td><td>{t('teachingStyle', teacher.teaching_style)}</td></tr>
              </>
            )}
          </tbody>
        </table>
      )
    case 'influence':
      return <InfluencePanel student={student} teacher={teacher} parent={parent} />
    case 'full_archive':
      return <FullArchivePanel student={student} />
    default:
      return null
  }
}

// 档案字段值的友好格式化：布尔→是/否、数组→顿号连接、对象→“中文键：值”
// 分号连接，避免出现原始 JSON 字符串（对非技术用户不友好）。
// key 可选：传入字段键后可对个别“英文原值”做本地化（如年级 Grade 8→八年级）。
function fmtArchiveValue(v, key) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'boolean') return v ? '是' : '否'
  if (Array.isArray(v)) return v.length ? v.join('、') : '—'
  if (typeof v === 'object') {
    return Object.entries(v)
      .map(([k, val]) => `${t('archiveField', k)}：${fmtArchiveValue(val, k)}`)
      .join('；')
  }
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(3)
  if (key === 'grade') return localGrade(v) ?? String(v)
  return String(v)
}

// FR-A1: comprehensive archive display (23 domains internally; the API serves
// 22 -- the S-level D11 domain is stripped by PrivacyGuard per FR-A8). Field
// names are localized to Chinese via i18n and values rendered readably.
function FullArchivePanel({ student }) {
  const domains = student.domains
  if (!domains || Object.keys(domains).length === 0) {
    return <div className="muted">该学生暂无全方位档案数据。</div>
  }
  const [expanded, setExpanded] = useState(null)
  const domainKeys = Object.keys(domains).sort()
  const expandedDomain = expanded ? domains[expanded] : null
  const fields = (expandedDomain && expandedDomain.fields) || {}
  return (
    <div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
        共 {student.domain_count || domainKeys.length} 域 · {student.field_count || '—'} 字段
        （S 级 D11 隐私域已由 PrivacyGuard 剥离 · FR-A8）
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
        {domainKeys.map((dk) => (
          <button
            key={dk}
            className={expanded === dk ? '' : 'secondary'}
            style={{ fontSize: 11, padding: '4px 8px' }}
            onClick={() => setExpanded(expanded === dk ? null : dk)}
          >
            {dk} {domains[dk].label}
          </button>
        ))}
      </div>
      {expanded && expandedDomain && (
        <div className="card" style={{ padding: 12 }}>
          <h4 style={{ margin: '0 0 8px' }}>{expanded} · {expandedDomain.label}</h4>
          <table>
            <tbody>
              {Object.entries(fields).map(([k, v]) => (
                <tr key={k}>
                  <td className="muted" style={{ width: 220, fontSize: 12 }}>{t('archiveField', k)}</td>
                  <td style={{ fontSize: 12 }}>{fmtArchiveValue(v, k)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!expanded && <div className="muted">点击上方域标签展开查看字段明细。</div>}
    </div>
  )
}

export default function PersonasPage() {
  const { id } = useParams()
  const [tab, setTab] = useState('students')
  const [students, setStudents] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)
  const [teacher, setTeacher] = useState(null)
  const [parent, setParent] = useState(null)
  const [domain, setDomain] = useState('basic')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const pageSize = 20

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api
      .listStudents(id, page, pageSize)
      .then((r) => {
        if (cancelled) return
        setStudents(r.students)
        setTotal(r.total)
      })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [id, page])

  const selectStudent = async (s) => {
    setSelected(s)
    setDomain('basic')
    setTeacher(null)
    setParent(null)
    if (s.assigned_teacher_id) {
      try {
        const t = await api.getTeacher(id, s.assigned_teacher_id)
        setTeacher(t)
      } catch {
        setTeacher(null)
      }
    }
    if (s.primary_parent_id) {
      try {
        const pr = await api.getParent(id, s.primary_parent_id)
        setParent(pr)
      } catch {
        setParent(null)
      }
    }
  }

  // Auto-select the first student once the list loads so the “单人档案卡” tab
  // is immediately usable instead of appearing disabled (it was gated on a
  // selection existing, which confused users on first visit).
  useEffect(() => {
    if (selected === null && students.length > 0) {
      selectStudent(students[0])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [students, selected])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div>
      <div className="page-header">
        <h2>画像浏览</h2>
        <p>学生 / 教师档案卡 · 展示 P/R 级字段（S 级 D11 隐私域已剥离）· 虚拟合成数据</p>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="tabs">
        <button className={tab === 'students' ? 'active' : ''} onClick={() => setTab('students')}>
          学生列表
        </button>
        <button className={tab === 'profile' ? 'active' : ''} onClick={() => setTab('profile')} disabled={!selected}>
          单人档案卡
        </button>
      </div>

      {tab === 'students' && (
        <div className="card">
          <h3>学生列表（共 {total} 人）</h3>
          {loading && <div className="loading">加载中…</div>}
          {!loading && (
            <table>
              <thead>
                <tr>
                  <th>ID</th><th>姓名</th><th>性别</th><th>成就分</th><th>动机</th><th>人格标签</th>
                </tr>
              </thead>
              <tbody>
                {students.map((s) => (
                  <tr key={s.student_id} className="clickable" onClick={() => { selectStudent(s); setTab('profile') }}>
                    <td>{s.student_id}</td>
                    <td>{localName(s.name)}</td>
                    <td>{t('gender', s.gender)}</td>
                    <td>{s.achievement_score?.toFixed(1)}</td>
                    <td>{s.motivation_level?.toFixed(2)}</td>
                    <td>{(s.personality_tags || []).map((tag) => t('personality', tag)).join('、')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
            <button className="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
            <span className="muted">第 {page} / {totalPages} 页</span>
            <button className="secondary" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一页</button>
          </div>
        </div>
      )}

      {tab === 'profile' && selected && (
        <div className="card">
          <h3>
            档案卡 · {localName(selected.name)}（{selected.student_id}）
          </h3>
          <div className="tabs">
            {DOMAIN_TABS.map((d) => (
              <button key={d.key} className={domain === d.key ? 'active' : ''} onClick={() => setDomain(d.key)}>
                {d.label}
              </button>
            ))}
          </div>
          <DomainPanel student={selected} domain={domain} teacher={teacher} parent={parent} />
        </div>
      )}
    </div>
  )
}
