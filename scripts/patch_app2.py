with open('frontend/src/App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# The file contains literal \uXXXX escape sequences as text in JSX strings.
# We need to match them as literal text, not as decoded unicode.

# "反事实推演" -> "假设推演（What-If）"
content = content.replace(
    r"label: '\u53cd\u4e8b\u5b9e\u63a8\u6f14'",
    r"label: '\u5047\u8bbe\u63a8\u6f14\uff08What-If\uff09'"
)

# "失真热力图" -> "可信度热力图"
content = content.replace(
    r"label: '\u5931\u771f\u70ed\u529b\u56fe'",
    r"label: '\u53ef\u4fe1\u5ea6\u70ed\u529b\u56fe'"
)

# "子群差异分析" -> "人群细分对比"
content = content.replace(
    r"label: '\u5b50\u7fa4\u5dee\u5f02\u5206\u6790'",
    r"label: '\u4eba\u7fa4\u7ec6\u5206\u5bf9\u6bd4'"
)

# "人在回路" -> "专家审阅"
content = content.replace(
    r"label: '\u4eba\u5728\u56de\u8def'",
    r"label: '\u4e13\u5bb6\u5ba1\u9605'"
)

# "校准验证" -> "模型可信度"
content = content.replace(
    r"label: '\u6821\u51c6\u9a8c\u8bc1'",
    r"label: '\u6a21\u578b\u53ef\u4fe1\u5ea6'"
)

# Also add triad_network to NAV under "虚拟群体" after "社会网络"
# Check if it's already there
if 'triad_network' not in content.split('NAV_SECTIONS')[1].split(']')[0]:
    content = content.replace(
        r"{ to: 'network', label: '\u793e\u4f1a\u7f51\u7edc' },",
        r"{ to: 'network', label: '\u793e\u4f1a\u7f51\u7edc' }," + "\n" +
        r"      { to: 'triad_network', label: '\u4e09\u65b9\u5173\u7cfb\u7f51\u7edc' },"
    )

with open('frontend/src/App.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: App.jsx labels patched")
