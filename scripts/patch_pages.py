import os

# 1. CounterfactualPage.jsx
path = 'frontend/src/pages/CounterfactualPage.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Title: "反事实对比" -> "假设推演（What-If）"
content = content.replace('<h2>反事实对比</h2>', '<h2>假设推演（What-If）</h2>')
# Description
content = content.replace(
    '同一起点 + 固定种子 · 单变量分流 · 基线 vs 干预后轨迹对比',
    '同一起点 + 固定种子 · 单变量分流 · 基线 vs 假设条件下的轨迹对比'
)
# Section header
content = content.replace('<h3>创建反事实分支</h3>', '<h3>创建假设分支</h3>')
# "反事实 ID" in table
content = content.replace("反事实 ID", "假设分支 ID")
# Error message
content = content.replace('请至少修改一个反事实变量', '请至少修改一个假设变量')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"OK: {path}")

# 2. DistortionMapPage.jsx
path = 'frontend/src/pages/DistortionMapPage.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Title
content = content.replace(
    r"{'\u{1f5d3}\ufe0f \u5931\u771f\u70ed\u529b\u56fe'}",
    r"{'\u{1f5d3}\ufe0f \u53ef\u4fe1\u5ea6\u70ed\u529b\u56fe'}"
)
# Also handle the plain text version if present
content = content.replace('失真热力图', '可信度热力图')
# Loading text
content = content.replace('正在加载失真地图', '正在加载可信度热力图')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"OK: {path}")

# 3. HITLPage.jsx
path = 'frontend/src/pages/HITLPage.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('<h2>人在回路（HITL）</h2>', '<h2>专家审阅</h2>')
content = content.replace(
    '专家审阅与反馈（FR-F5）· 对干预/假设/画像/失真进行人工判定 · 闭环改进',
    '专家审阅与反馈（FR-F5）· 对干预/假设/画像/可信度进行人工判定 · 闭环改进'
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"OK: {path}")

# 4. CalibrationPage.jsx
path = 'frontend/src/pages/CalibrationPage.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('<h2>校准诊断</h2>', '<h2>模型可信度</h2>')
content = content.replace('正在加载校准诊断', '正在加载模型可信度分析')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"OK: {path}")
