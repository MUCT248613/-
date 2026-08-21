
      {/* Collapsible: Effect Sizes Detail */}
      <div className="card">
        <div 
          style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
          onClick={() => setShowEffectSizes(!showEffectSizes)}
        >
          <h3 style={{ margin: 0 }}>{'\u{1f4ca} \u6548\u5e94\u91cf\u8be6\u60c5'}</h3>
          <span style={{ fontSize: 18, color: '#4f8cff' }}>{showEffectSizes ? '\u25b2' : '\u25bc'}</span>
        </div>
        {showEffectSizes && (
          <div style={{ marginTop: 16 }}>
            <table>
              <thead>
                <tr>
                  <th>{'\u5e72\u9884'}</th>
                  <th>{'\u573a\u666f'}</th>
                  <th>{"Hedges' g"}</th>
                  <th>{"95% CI"}</th>
                  <th>{'\u6837\u672c\u91cf'}</th>
                </tr>
              </thead>
              <tbody>
                {(rc.effect_sizes || []).map((es) => (
                  <tr key={`es-${es.intervention_id}-${es.scene}`}>
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
        )}
      </div>

      {/* Collapsible: Priority Ranking Detail */}
      <div className="card">
        <div 
          style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
          onClick={() => setShowPriorityRanking(!showPriorityRanking)}
        >
          <h3 style={{ margin: 0 }}>{'\u{1f3c6} \u4f18\u5148\u7ea7\u6392\u5e8f\u8be6\u60c5'}</h3>
          <span style={{ fontSize: 18, color: '#4f8cff' }}>{showPriorityRanking ? '\u25b2' : '\u25bc'}</span>
        </div>
        {showPriorityRanking && (
          <div style={{ marginTop: 16 }}>
            <table>
              <thead>
                <tr>
                  <th>{'\u6392\u540d'}</th>
                  <th>{'\u5e72\u9884'}</th>
                  <th>{'\u4f18\u5148\u7ea7\u5f97\u5206'}</th>
                  <th>{'\u6548\u5e94\u91cf'}</th>
                  <th>{'\u786e\u5b9a\u6027'}</th>
                  <th>{'\u53ef\u8fbe\u6027'}</th>
                  <th>{'\u6210\u672c\u6548\u7387'}</th>
                  <th>{'\u5931\u771f\u533a'}</th>
                </tr>
              </thead>
              <tbody>
                {(rc.priority_ranking || []).map((r) => (
                  <tr key={`pr-${r.intervention_id}`}>
                    <td><strong>{r.rank}</strong></td>
                    <td>{t('intervention', r.intervention_id)}</td>
                    <td><strong>{r.priority_score?.toFixed(3)}</strong></td>
                    <td className="muted">{r.breakdown?.effect_size?.toFixed(2)}</td>
                    <td className="muted">{r.breakdown?.certainty?.toFixed(2)}</td>
                    <td className="muted">{r.breakdown?.reach?.toFixed(2)}</td>
                    <td className="muted">{r.breakdown?.cost_efficiency?.toFixed(2)}</td>
                    <td>
                      {r.in_distorted_region
                        ? <span className="badge" style={{ color: '#f5a623', borderColor: '#f5a623' }}>{'\u5931\u771f'}</span>
                        : <span className="badge green">{'\u6b63\u5e38'}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>