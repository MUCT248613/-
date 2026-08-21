# -*- coding: utf-8 -*-
with open('frontend/src/App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add QualityPage import after TriadNetworkPage import
old_import = "import TriadNetworkPage from './pages/TriadNetworkPage.jsx'"
new_import = old_import + "\nimport QualityPage from './pages/QualityPage.jsx'"
content = content.replace(old_import, new_import)

# 2. Remove the entire "运行报告" section from NAV_SECTIONS
# The section looks like:
#   {
#     title: '...',
#     items: [{ to: 'report', label: '...' }]
#   },
# We need to find and remove it
import re

# Remove the 运行报告 section (it's the second section in NAV_SECTIONS)
# Pattern: find the section with 'report' in items
pattern = r"  \{\n    title: '[^']*',\n    items: \[\{ to: 'report', label: '[^']*' \}\]\n  \},\n"
content = re.sub(pattern, '', content, count=1)

# 3. Remove life_course from 时间序列 section
# Replace the two-item list with just the timeline item
old_time_items = """      { to: 'timeline', label: '\\u5b66\\u4e60\\u8f68\\u8ff9\\u56de\\u653e' },
      { to: 'life_course', label: '\\u751f\\u547d\\u5386\\u7a0b' },"""
new_time_items = """      { to: 'timeline', label: '\\u5b66\\u4e60\\u8f68\\u8ff9' },"""
content = content.replace(old_time_items, new_time_items)

# 4. Replace calibration + prescreening with quality in 质量诊断 section
old_quality_items = """      { to: 'calibration', label: '\\u6a21\\u578b\\u53ef\\u4fe1\\u5ea6' },
      { to: 'prescreening', label: '\\u9884\\u7b5b\\u51b3\\u7b56' },"""
new_quality_items = """      { to: 'quality', label: '\\u8d28\\u91cf\\u4e0e\\u51b3\\u7b56' },"""
content = content.replace(old_quality_items, new_quality_items)

# 5. Add QualityPage route (keep old routes for direct URL access)
old_routes = """          <Route path="calibration" element={<CalibrationPage />} />"""
new_routes = """          <Route path="quality" element={<QualityPage />} />
          <Route path="calibration" element={<CalibrationPage />} />"""
content = content.replace(old_routes, new_routes)

with open('frontend/src/App.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: App.jsx patched")