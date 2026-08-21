# -*- coding: utf-8 -*-
with open('frontend/src/App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add import
old_import = "import QualityPage from './pages/QualityPage.jsx'"
new_import = old_import + "\nimport MediationPage from './pages/MediationPage.jsx'"
content = content.replace(old_import, new_import)

# 2. Add nav entry in 干预分析 section after 可信度热力图
old_nav = r"      { to: 'distortion', label: '\u53ef\u4fe1\u5ea6\u70ed\u529b\u56fe' },"
new_nav = old_nav + "\n      { to: 'mediation', label: '\\u6548\\u679c\\u8def\\u5f84' },"
content = content.replace(old_nav, new_nav)

# 3. Add route after quality route
old_route = '          <Route path="quality" element={<QualityPage />} />'
new_route = old_route + '\n          <Route path="mediation" element={<MediationPage />} />'
content = content.replace(old_route, new_route)

with open('frontend/src/App.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: App.jsx patched with mediation")