with open('frontend/src/App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add import for TriadNetworkPage after NetworkPage import
old_import = "import NetworkPage from './pages/NetworkPage.jsx'"
new_import = """import NetworkPage from './pages/NetworkPage.jsx'
import TriadNetworkPage from './pages/TriadNetworkPage.jsx'"""
content = content.replace(old_import, new_import)

# 2. Add TriadNetworkPage to NAV_SECTIONS under "虚拟群体" after "社会网络"
old_nav_network = """      { to: 'network', label: '\u793e\u4f1a\u7f51\u7edc' },
    ]"""
new_nav_network = """      { to: 'network', label: '\u793e\u4f1a\u7f51\u7edc' },
      { to: 'triad_network', label: '\u4e09\u65b9\u5173\u7cfb\u7f51\u7edc' },
    ]"""
content = content.replace(old_nav_network, new_nav_network)

# 3. Rename labels in NAV_SECTIONS
# "反事实推演" -> "假设推演（What-If）"
content = content.replace(
    "{ to: 'counterfactual', label: '\u53cd\u4e8b\u5b9e\u63a8\u6f14' }",
    "{ to: 'counterfactual', label: '\u5047\u8bbe\u63a8\u6f14\uff08What-If\uff09' }"
)
# "失真热力图" -> "可信度热力图"
content = content.replace(
    "{ to: 'distortion', label: '\u5931\u771f\u70ed\u529b\u56fe' }",
    "{ to: 'distortion', label: '\u53ef\u4fe1\u5ea6\u70ed\u529b\u56fe' }"
)
# "子群差异分析" -> "人群细分对比"
content = content.replace(
    "{ to: 'subgroups', label: '\u5b50\u7fa4\u5dee\u5f02\u5206\u6790' }",
    "{ to: 'subgroups', label: '\u4eba\u7fa4\u7ec6\u5206\u5bf9\u6bd4' }"
)
# "人在回路" -> "专家审阅"
content = content.replace(
    "{ to: 'hitl', label: '\u4eba\u5728\u56de\u8def' }",
    "{ to: 'hitl', label: '\u4e13\u5bb6\u5ba1\u9605' }"
)
# "校准验证" -> "模型可信度"
content = content.replace(
    "{ to: 'calibration', label: '\u6821\u51c6\u9a8c\u8bc1' }",
    "{ to: 'calibration', label: '\u6a21\u578b\u53ef\u4fe1\u5ea6' }"
)

# 4. Add Route for triad_network after network route
old_route = '<Route path="network" element={<NetworkPage />} />'
new_route = """<Route path="network" element={<NetworkPage />} />
          <Route path="triad_network" element={<TriadNetworkPage />} />"""
content = content.replace(old_route, new_route)

# 5. Rename the sidebar section title for "专家审阅" group
# The section title uses unicode: ⚙️ 专家审阅
# Current: title: '\u2699\ufe0f \u4e13\u5bb6\u5ba1\u9605'
# This is already correct! The section title is already "专家审阅"
# But we need to check if the original was different
# Looking at the original: '\u2699\ufe0f \u4e13\u5bb6\u5ba1\u9605' = "⚙️ 专家审阅"
# That's already the target name. Good.

with open('frontend/src/App.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: App.jsx patched")
