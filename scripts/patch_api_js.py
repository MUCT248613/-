with open('frontend/src/api.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Add getTriadNetwork after getNetworkEvolution
old = '''  getNetworkEvolution: (runId, from = 0, to = 90) =>
    request(`/api/runs/${runId}/network/evolution?from=${from}&to=${to}`),'''

new = '''  getNetworkEvolution: (runId, from = 0, to = 90) =>
    request(`/api/runs/${runId}/network/evolution?from=${from}&to=${to}`),
  // Triad network (student-teacher-parent)
  getTriadNetwork: (runId, interventionId) => {
    const q = interventionId ? `?intervention_id=${encodeURIComponent(interventionId)}` : ''
    return request(`/api/runs/${runId}/triad_network${q}`)
  },'''

content = content.replace(old, new)

with open('frontend/src/api.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: api.js patched")
