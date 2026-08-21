# -*- coding: utf-8 -*-
with open('frontend/src/pages/DashboardPage.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add collapsible state variables
old_state = '  const [data, setData] = useState(null)'
new_state = old_state + '\n  const [showEffectSizes, setShowEffectSizes] = useState(false)\n  const [showPriorityRanking, setShowPriorityRanking] = useState(false)'
content = content.replace(old_state, new_state, 1)

# 2. Read the collapsible sections from file
with open('scripts/collapsible_sections.jsx', 'r', encoding='utf-8') as f:
    collapsible = f.read()

# 3. Insert before the final closing tags
idx = content.rfind("navigate('/')")
if idx == -1:
    print("ERROR: could not find navigate('/')")
    exit(1)

end_pattern = content.find('    </div>\n  )\n}', idx)
if end_pattern == -1:
    print("ERROR: could not find end pattern")
    exit(1)

content = content[:end_pattern] + collapsible + '\n' + content[end_pattern:]
print(f"Inserted collapsible sections at position {end_pattern}")

with open('frontend/src/pages/DashboardPage.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: DashboardPage.jsx patched")