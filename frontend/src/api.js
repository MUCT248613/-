// API client for VirtualStudent Sandbox v5.0 backend (FastAPI, port 6668)
// In dev, Vite proxies /api -> http://localhost:6668 (see vite.config.js).
// Set VITE_API_BASE to override (e.g. direct cross-origin access).
import { localizeApiError } from './i18n.js'

const BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(`API ${res.status}: ${localizeApiError(detail)}`)
  }
  return res.json()
}

export const api = {
  health: () => request('/api/health'),
  listRuns: () => request('/api/runs'),
  createRun: (payload) =>
    request('/api/runs', { method: 'POST', body: JSON.stringify(payload) }),
  getRun: (runId) => request(`/api/runs/${runId}`),
  listStudents: (runId, page = 1, pageSize = 20) =>
    request(`/api/runs/${runId}/students?page=${page}&page_size=${pageSize}`),
  getStudent: (runId, sid) => request(`/api/runs/${runId}/students/${sid}`),
  getTimeline: (runId, sid) =>
    request(`/api/runs/${runId}/students/${sid}/timeline`),
  getLifeCourse: (runId, sid, from = 0, to = 90) =>
    request(`/api/runs/${runId}/students/${sid}/life_course?from=${from}&to=${to}`),
  getTeacher: (runId, tid) => request(`/api/runs/${runId}/teachers/${tid}`),
  getSceneComparison: (runId) => request(`/api/runs/${runId}/scene_comparison`),
  getSubgroups: (runId, dims) =>
    request(`/api/runs/${runId}/subgroups?dims=${encodeURIComponent(dims)}`),
  getNetwork: (runId, day = 0) =>
    request(`/api/runs/${runId}/network?day=${day}`),
  getNetworkEvolution: (runId, from = 0, to = 90) =>
    request(`/api/runs/${runId}/network/evolution?from=${from}&to=${to}`),
  createCounterfactual: (runId, payload) =>
    request(`/api/runs/${runId}/counterfactual`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getCounterfactualComparison: (runId, cfId) =>
    request(`/api/runs/${runId}/counterfactual/${cfId}/comparison`),
  getReport: (runId) => request(`/api/runs/${runId}/report`),
  // FR-F7: Parents
  listParents: (runId, page = 1, pageSize = 20) =>
    request(`/api/runs/${runId}/parents?page=${page}&page_size=${pageSize}`),
  getParent: (runId, pid) => request(`/api/runs/${runId}/parents/${pid}`),
  // FR-F2: Calibration diagnostics
  getCalibration: (runId) => request(`/api/runs/${runId}/calibration`),
  // FR-F3: Distortion map
  getDistortionMap: (runId) => request(`/api/runs/${runId}/distortion_map`),
  // FR-F4: Pre-screening report
  getPrescreening: (runId) => request(`/api/runs/${runId}/prescreening`),
  // FR-F5: Human-in-the-loop
  getHITLFeedback: (runId) => request(`/api/runs/${runId}/hitl/feedback`),
  submitHITLFeedback: (runId, payload) =>
    request(`/api/runs/${runId}/hitl/feedback`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  // LLM configuration
  getLLMConfig: () => request('/api/llm/config'),
  updateLLMConfig: (payload) =>
    request('/api/llm/config', { method: 'POST', body: JSON.stringify(payload) }),
}

export default api
