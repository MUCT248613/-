
      {/* Virtual vs Literature comparison */}
      <div className="card" style={{ background: 'linear-gradient(135deg, #1a2233 0%, #1e2a3f 100%)', border: '1px solid #2c3a55' }}>
        <h3>{'\u{1f4da} \u865a\u62df vs \u6587\u732e\u57fa\u7ebf\u5bf9\u6bd4'}</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 20, alignItems: 'center' }}>
          {/* Virtual BKT params */}
          <div>
            <div style={{ fontSize: 13, color: '#4f8cff', fontWeight: 600, marginBottom: 8 }}>{'\u{1f4bb} \u865a\u62df\u5b66\u751f\u5e73\u5747 BKT \u53c2\u6570'}</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 13 }}>
              <div><span className="muted">p_know:</span> <strong>{rc.calibration?.bkt_params_virtual?.p_know?.toFixed(3) || '\u2014'}</strong></div>
              <div><span className="muted">p_learn:</span> <strong>{rc.calibration?.bkt_params_virtual?.p_learn?.toFixed(3) || '\u2014'}</strong></div>
              <div><span className="muted">p_slip:</span> <strong>{rc.calibration?.bkt_params_virtual?.p_slip?.toFixed(3) || '\u2014'}</strong></div>
              <div><span className="muted">p_guess:</span> <strong>{rc.calibration?.bkt_params_virtual?.p_guess?.toFixed(3) || '\u2014'}</strong></div>
            </div>
          </div>

          {/* Cognitive distance */}
          <div style={{ textAlign: 'center', padding: '0 16px', borderLeft: '1px solid #2c3a55', borderRight: '1px solid #2c3a55' }}>
            <div style={{ fontSize: 11, color: '#8fa0bd', marginBottom: 4 }}>{'\u8ba4\u77e5\u8ddd\u79bb'}</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: rc.calibration?.cognitive_distance < 0.10 ? '#38c7a4' : rc.calibration?.cognitive_distance < 0.18 ? '#f5a623' : '#e74c3c' }}>
              {rc.calibration?.cognitive_distance?.toFixed(3) || '\u2014'}
            </div>
            <div style={{ fontSize: 12, marginTop: 4 }}>
              {rc.calibration?.cognitive_distance < 0.10 ? (
                <span className="badge green">{'\u2713 \u901a\u8fc7'}</span>
              ) : rc.calibration?.cognitive_distance < 0.18 ? (
                <span className="badge" style={{ color: '#f5a623', borderColor: '#f5a623' }}>{'\u26a0 \u8fb9\u7f18'}</span>
              ) : (
                <span className="badge" style={{ color: '#e74c3c', borderColor: '#e74c3c' }}>{'\u2717 \u672a\u901a\u8fc7'}</span>
              )}
            </div>
          </div>

          {/* Literature baseline */}
          <div>
            <div style={{ fontSize: 13, color: '#38c7a4', fontWeight: 600, marginBottom: 8 }}>{'\u{1f4d6} \u6587\u732e\u57fa\u7ebf\u53c2\u6570\uff085\u7bc7\u7814\u7a76\u805a\u5408\uff09'}</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 13 }}>
              <div><span className="muted">p_know:</span> <strong>0.380</strong></div>
              <div><span className="muted">p_learn:</span> <strong>0.250</strong></div>
              <div><span className="muted">p_slip:</span> <strong>0.100</strong></div>
              <div><span className="muted">p_guess:</span> <strong>0.200</strong></div>
            </div>
          </div>
        </div>
        <div style={{ marginTop: 12, padding: '8px 12px', background: 'rgba(245,166,35,0.1)', borderRadius: 6, border: '1px solid rgba(245,166,35,0.3)', fontSize: 12, color: '#f5a623' }}>
          {'\u26a0\ufe0f \u4ee5\u4e0a\u4e3a\u865a\u62df\u4eff\u771f\u7ed3\u679c\uff0c\u9700\u771f\u4eba\u8bd5\u9a8c\u9a8c\u8bc1\uff0c\u4e0d\u53ef\u76f4\u63a5\u5916\u63a8'}
        </div>
      </div>