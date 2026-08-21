import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api.js'
import { t } from '../i18n.js'

const VERDICT_LABELS = {
  pass: { text: '\u901a\u8fc7', color: '#38c7a4' },
  marginal: { text: '\u8fb9\u7f18', color: '#f5a623' },
  fail: { text: '\u672a\u901a\u8fc7', color: '#e74c3c' },
}

const DECISION_STYLES = {
  go: { label: 'GO\uff08\u63a8\u8350\u8fdb\u5165\u5b9e\u8bc1\uff09', color: '#38c7a4', bg: 'rgba(56,199,164,0.1)' },
  conditional: { label: 'CONDITIONAL\uff08\u6709\u6761\u4ef6\u63a8\u8350\uff09', color: '#f5a623', bg: 'rgba(245,166,35,0.1)' },
  no_go: { label: 'NO-GO\uff08\u6682\u4e0d\u63a8\u8350\uff09', color: '#e74c3c', bg: 'rgba(231,76,60,0.1)' },
}

const CHECK_LABELS = {
  effect_threshold: '\u6548\u5e94\u91cf |g| \u2265 0.20',
  ci_significance: '95% CI \u4e0d\u8de8\u96f6\uff08\u53cc\u5411\uff09',
  fidelity: '\u975e\u9ad8\u5931\u771f\u533a',
  feasibility: '\u4f18\u5148\u7ea7 \u2265 0.40',
}

function fmt(v) {
  if (v === null || v === undefined) return '\u2014'
  if (typeof v === 'number') return v.toFixed(4)
  return String(v)
}

export default function QualityPage() {
  const { id } = useParams()
  const [calibData, setCalibData] = useState(null)
  const [calibError, setCalibError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api.getCalibration(id)
      .then((r) => !cancelled && setCalibData(r))
      .catch((e) => !cancelled && setCalibError(e.message))
    return () => { cancelled = true }
  }, [id])

  return (
    <div>
      <div className="page-header">
        <h2>{'🔍 模型可信度'}</h2>
        <p>{'校准诊断 · 保真度评估 · 证据质量'}</p>
      </div>

      {/* ============ Calibration ============ */}
      {(
        <>
          {calibError && <div className="error-box">{calibError}</div>}
          {!calibData && !calibError && <div className="loading">{'\u6b63\u5728\u52a0\u8f7d\u6a21\u578b\u53ef\u4fe1\u5ea6\u5206\u6790\u2026'}</div>}

          {calibData && (() => {
            const verdict = VERDICT_LABELS[calibData.verdict] || VERDICT_LABELS.marginal
            return (
              <>
                <div className="card">
                  <h3>{'\u603b\u4f53\u5224\u5b9a'}</h3>
                  <div className="row">
                    <div className="stat">
                      <span className="v" style={{ color: verdict.color }}>{verdict.text}</span>
                      <span className="l">{'\u6821\u51c6\u5224\u5b9a'}</span>
                    </div>
                    <div className="stat">
                      <span className="v">{fmt(calibData.cognitive_distance)}</span>
                      <span className="l">{'\u8ba4\u77e5\u8ddd\u79bb'}</span>
                    </div>
                    <div className="stat">
                      <span className="v">{calibData.data_source === 'literature' ? '\u6587\u732e\u57fa\u7ebf' : (calibData.data_source === 'real' ? '\u771f\u5b9e\u6570\u636e' : '\u5408\u6210\u6570\u636e')}</span>
                      <span className="l">{'\u53c2\u7167\u6765\u6e90'}</span>
                    </div>
                  </div>
                  <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                    {'\u5224\u5b9a\u6807\u51c6\uff1a\u8ba4\u77e5\u8ddd\u79bb < 0.10 \u901a\u8fc7\uff0c0.10\u20130.18 \u8fb9\u7f18\uff0c> 0.18 \u672a\u901a\u8fc7\u3002'}
                    {'\u53c2\u7167\u57fa\u7ebf\u4e3a\u5df2\u53d1\u8868 BKT/\u77e5\u8bc6\u8ffd\u8e2a\u6587\u732e\u7684\u516c\u5f00\u70b9\u4f30\u8ba1\u3002'}
                  </div>
                </div>

                {calibData.reference_basis && (
                  <div className="card">
                    <h3>{'\u6587\u732e\u53c2\u7167\u57fa\u7ebf\uff08'}{calibData.reference_basis.n_studies}{' \u9879\u7814\u7a76\uff09'}</h3>
                    <table>
                      <thead>
                        <tr><th>{'\u7814\u7a76'}</th><th>{'\u6570\u636e\u96c6'}</th><th>p_know</th><th>p_learn</th><th>p_slip</th><th>p_guess</th></tr>
                      </thead>
                      <tbody>
                        {(calibData.reference_basis.studies || []).map((s) => (
                          <tr key={s.study_id}>
                            <td title={s.citation}><strong>{s.study_id}</strong></td>
                            <td className="muted">{s.dataset}</td>
                            <td>{fmt(s.params.p_know)}</td>
                            <td>{fmt(s.params.p_learn)}</td>
                            <td>{fmt(s.params.p_slip)}</td>
                            <td>{fmt(s.params.p_guess)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>{calibData.reference_basis.note}</div>
                  </div>
                )}

                <div className="card">
                  <h3>{'BKT \u53c2\u6570\u5bf9\u6bd4\uff08\u865a\u62df vs \u53c2\u8003\uff09'}</h3>
                  <table>
                    <thead>
                      <tr><th>{'\u53c2\u6570'}</th><th>{'\u865a\u62df\u503c'}</th><th>{'\u53c2\u8003\u503c'}</th><th>{'\u7edd\u5bf9\u5dee'}</th><th>{'\u72b6\u6001'}</th></tr>
                    </thead>
                    <tbody>
                      {(calibData.diagnostics || []).map((d) => (
                        <tr key={d.parameter}>
                          <td><strong>{d.parameter}</strong></td>
                          <td>{fmt(d.virtual_value)}</td>
                          <td>{fmt(d.reference_value)}</td>
                          <td>{fmt(d.absolute_diff)}</td>
                          <td>
                            {d.status === 'ok'
                              ? <span className="badge green">{'\u6b63\u5e38'}</span>
                              : <span className="badge" style={{ color: '#f5a623', borderColor: '#f5a623' }}>{'\u504f\u79bb'}</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="card">
                  <h3>{'KS \u68c0\u9a8c\u7ed3\u679c'}</h3>
                  <table>
                    <thead>
                      <tr><th>{'\u53c2\u6570'}</th><th>{'KS \u7edf\u8ba1\u91cf'}</th><th>{'p \u503c'}</th><th>{'\u7ed3\u8bba'}</th></tr>
                    </thead>
                    <tbody>
                      {Object.entries(calibData.ks_test_results || {}).map(([param, ks]) => (
                        <tr key={param}>
                          <td><strong>{param}</strong></td>
                          <td>{fmt(ks.ks_statistic)}</td>
                          <td>{fmt(ks.p_value)}</td>
                          <td>
                            {ks.p_value > 0.05
                              ? <span className="badge green">{'\u4e0d\u62d2\u7edd H\u2080\uff08\u5206\u5e03\u4e00\u81f4\uff09'}</span>
                              : <span className="badge" style={{ color: '#e74c3c', borderColor: '#e74c3c' }}>{'\u62d2\u7edd H\u2080\uff08\u5206\u5e03\u504f\u79bb\uff09'}</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                    {'H\u2080\uff1a\u865a\u62df\u53c2\u6570\u5206\u5e03\u4e0e\u53c2\u8003\u5206\u5e03\u65e0\u663e\u8457\u5dee\u5f02\uff08\u03b1 = 0.05\uff09\u3002'}
                  </div>
                </div>

                <div className="card">
                  <h3>{'\u4eba\u683c\u5206\u5e03\u53c2\u6570'}</h3>
                  <table>
                    <tbody>
                      {Object.entries(calibData.persona_distribution || {}).map(([key, val]) => (
                        <tr key={key}>
                          <td className="muted" style={{ width: 120 }}>{key}</td>
                          <td>
                            {typeof val === 'object'
                              ? `\u03bc = ${fmt(val.mu)}, \u03c3 = ${fmt(val.sigma)}`
                              : fmt(val)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )
          })()}
        </>
      )}

    </div>
  )
}