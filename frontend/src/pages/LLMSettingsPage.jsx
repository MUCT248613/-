// LLM Settings page - configure the Qwen model backend (Aliyun Bailian / DashScope)
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api.js'

// Default preset for the Aliyun Bailian (百炼) Token Plan OpenAI-compatible
// endpoint. Token Plan (套餐计费) uses a dedicated base URL, distinct from the
// pay-as-you-go (按量计费) DashScope endpoint; model names are identical.
const DEFAULT_BASE_URL = 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'
// DashScope model ids are case-sensitive and must be LOWERCASE. flash is the
// default: fast and cheap, adequate for persona generation (no need for plus/max).
const DEFAULT_MODEL = 'qwen3.7-flash'
const PAYG_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'

export default function LLMSettingsPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [config, setConfig] = useState(null)
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL)
  const [model, setModel] = useState(DEFAULT_MODEL)
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [calls, setCalls] = useState([])

  useEffect(() => {
    let cancelled = false
    api
      .getLLMConfig()
      .then((cfg) => {
        if (cancelled) return
        setConfig(cfg)
        setBaseUrl(cfg.base_url || DEFAULT_BASE_URL)
        setModel(cfg.default_model || DEFAULT_MODEL)
      })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  const loadCalls = () => {
    api.getLLMCalls().then((r) => setCalls(r.calls || [])).catch(() => {})
  }

  useEffect(() => {
    loadCalls()
  }, [])

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const r = await api.testLLM()
      setTestResult(r)
      loadCalls()
    } catch (e) {
      setTestResult({ status: 'error', reason: e.message })
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const payload = { base_url: baseUrl, default_model: model }
      if (apiKey.trim()) payload.api_key = apiKey.trim()
      const cfg = await api.updateLLMConfig(payload)
      setConfig(cfg)
      setApiKey('')
      setSaved(true)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    setBaseUrl(DEFAULT_BASE_URL)
    setModel(DEFAULT_MODEL)
  }

  if (loading) return <div className="main loading">加载中…</div>

  // 常用模型仅作输入建议（datalist），模型名可自由填写
  const modelOptions = [...(config?.available_models || [])]

  return (
    <div className="main" style={{ maxWidth: 860, margin: '0 auto' }}>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div>
          <h2>大模型配置</h2>
          <p>
            配置驱动身份种子生成与叙事合成的 Qwen 大模型 · 已预设阿里云百炼 Token Plan（套餐）端点，填写 API Key 即可启用
          </p>
        </div>
        <button className="secondary" onClick={() => navigate('/')} style={{ flexShrink: 0 }}>
          ← 返回首页
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}
      {saved && (
        <div className="privacy-note" style={{ color: 'var(--accent-2)', borderColor: 'var(--accent-2)', background: 'rgba(56,199,164,0.1)' }}>
          {config?.is_live
            ? '✓ 配置已保存，大模型已连接（实时模式）'
            : '✓ 配置已保存（当前仍为离线模式，请检查 API Key 是否正确）'}
        </div>
      )}

      <div className="card">
        <h3>连接状态</h3>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span className="muted">当前状态：</span>
          {config?.is_live ? (
            <span className="badge green">已连接 · 实时模型</span>
          ) : (
            <span className="badge">离线模式（确定性 Mock）</span>
          )}
          {config?.api_key_set && <span className="badge accent">API Key：{config.api_key_masked}</span>}
        </div>
        <p className="muted" style={{ fontSize: 12, marginTop: 8, marginBottom: 0 }}>
          未配置 API Key 时系统自动使用确定性离线模式，全部功能仍可运行（用于测试与演示）。
          "已连接"仅表示配置就绪；点击"测试连接"会真实调用一次模型以验证端点 / Key / 模型名是否可用。
        </p>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 10 }}>
          <button className="secondary" onClick={handleTest} disabled={testing}>
            {testing ? '测试中…' : '测试连接（真实调用一次）'}
          </button>
          {testResult?.status === 'ok' && (
            <span className="badge green">
              调用成功 · {testResult.model} · {testResult.latency_ms}ms · 回复: {testResult.reply}
            </span>
          )}
          {testResult?.status === 'offline' && <span className="badge">离线模式：{testResult.reason}</span>}
          {testResult?.status === 'error' && (
            <span className="badge" style={{ color: '#ef5b6b', borderColor: '#ef5b6b' }}>
              调用失败：{testResult.reason}
            </span>
          )}
        </div>
        {testResult?.suggestion && (
          <div className="privacy-note" style={{ marginTop: 8, color: '#f5a623', borderColor: '#f5a623', background: 'rgba(245,166,35,0.1)' }}>
            {testResult.suggestion}
          </div>
        )}
        {calls.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>
              最近调用记录（{calls.length} 条，含离线 Mock）：
            </div>
            <table>
              <thead>
                <tr><th>时间</th><th>模型</th><th>类型</th><th>Tokens (入/出)</th><th>耗时</th></tr>
              </thead>
              <tbody>
                {calls.slice(0, 10).map((c, i) => (
                  <tr key={i}>
                    <td>{new Date(c.timestamp_ms).toLocaleString()}</td>
                    <td>{c.model}</td>
                    <td>{c.live ? '实时调用' : '离线 Mock'}</td>
                    <td>{c.prompt_tokens}/{c.completion_tokens}</td>
                    <td>{c.latency_ms}ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h3>模型参数</h3>

        <div className="field">
          <label>Base URL</label>
          <input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder={DEFAULT_BASE_URL}
            style={{ width: '100%' }}
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
            <button className="secondary" style={{ fontSize: 11 }} onClick={() => setBaseUrl(DEFAULT_BASE_URL)}>
              填入 Token Plan 端点
            </button>
            <button className="secondary" style={{ fontSize: 11 }} onClick={() => setBaseUrl(PAYG_BASE_URL)}>
              填入按量计费端点
            </button>
          </div>
          <span className="muted" style={{ fontSize: 11 }}>
            Token Plan（套餐）端点只接受套餐绑定 Key；普通百炼 Key 请用按量计费端点。两者模型名相同。
          </span>
        </div>

        <div className="field">
          <label>模型名称</label>
          <input
            list="llm-model-options"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={DEFAULT_MODEL}
            style={{ width: '100%' }}
          />
          <datalist id="llm-model-options">
            {modelOptions.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
          <span className="muted" style={{ fontSize: 11 }}>可从常用模型中选择，也可直接输入任意模型名称（如 qwen3.7-max，注意必须小写）</span>
        </div>

        <div className="field">
          <label>API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={config?.api_key_set ? '已配置（留空则保持不变）' : '粘贴阿里云百炼 Token Plan API Key'}
            style={{ width: '100%' }}
            autoComplete="off"
          />
          <span className="muted" style={{ fontSize: 11 }}>
            在{' '}
            <a href="https://bailian.console.aliyun.com/" target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>
              阿里云百炼控制台
            </a>{' '}
            获取。保存后不会明文回显。
          </span>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={handleSave} disabled={saving}>
            {saving ? '保存中…' : '保存配置'}
          </button>
          <button className="secondary" onClick={handleReset}>恢复百炼默认</button>
        </div>
      </div>
    </div>
  )
}
