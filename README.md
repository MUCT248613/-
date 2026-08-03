# 虚拟学生试验台 v5.0 (VirtualStudent Sandbox)

> 基于国产开源大模型（通义千问）的 AI Scientist 多智能体教育仿真平台  
> 赛题：XH-202619《基于国产开源大模型的 AI Scientist 的研发与应用》

## 项目概述

本平台通过多智能体仿真（学生 S-Model / 教师 T-Model / 家长 P-Model）生成虚拟学生全生命周期学习轨迹，
结合认知引擎（BKT + ACT-R）、因果推断（虚拟效应量 Hedges' g）和科学假设自动生成，
为教育研究者提供 **"虚拟预筛 → 真人试验"** 的闭环研究范式。

## 核心特性

| 特性 | 说明 |
|------|------|
| 多智能体画像 | 23 域 219 字段全方位档案，千问 LLM 驱动生成 |
| 认知引擎 | BKT 知识追踪 + ACT-R 遗忘曲线，确定性可复现 |
| 真实数据校准 | ASSISTments / EdNet 数据加载器，透明回退合成数据 |
| 五场景仿真 | 学校 / 社交 / 课外班 / 自学 / 家庭 |
| 因果推断 | 虚拟效应量 + 95% CI + 失真地图 + 优先级排序 |
| 科学假设生成 | M8 自动生成可证伪假设（教师/家长/场景分化） |
| 人在回路 | 专家审阅反馈闭环 (HITL) |
| 隐私强制 | P/R/S 三级 PrivacyGuard，S 级永不泄露 |

## 技术栈

- **后端**: Python 3.12, FastAPI, uvicorn (port 6668)
- **前端**: React 18, Vite 5, react-router-dom (port 4000)
- **LLM**: 通义千问 (DashScope OpenAI-compatible API)
- **数据**: DuckDB (生产) / 内存 (演示)
- **测试**: pytest (73+ tests)

## 快速启动

### 后端

```bash
# 安装依赖
pip install fastapi uvicorn numpy pyyaml pydantic

# 启动后端 (port 6668)
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 6668 --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev    # 开发模式 (port 4000, 代理 /api → 6668)
npm run build  # 生产构建
```

### 测试

```bash
pytest tests/ -v
```

## 大模型配置（界面配置，无需改文件）

大模型（通义千问）**完全通过前端界面配置**，不需要修改任何配置文件或设置环境变量：

1. 启动前后端后，打开首页 `http://localhost:4000`
2. 点击「后端状态」卡片中的 **⚙ 大模型配置** 按钮（或直接访问 `/settings`）
3. 页面已预设阿里云百炼（DashScope）的 Base URL 与常用模型名，只需填写 **API Key** 并保存
4. 保存后页面会显示「已连接 · 实时模型」；未填 Key 时系统自动使用确定性离线模式，全部功能照常运行

> API Key 保存后仅以掩码形式回显（如 `sk-t****cdef`），不会明文返回。配置存于后端运行时内存，后端重启后需重新填写。

## 项目结构

```
├── src/
│   ├── api/              # FastAPI 后端 (main.py + models.py)
│   ├── persona_service/  # 画像生成 (student/teacher/parent + 23域档案)
│   ├── cognitive/        # 认知引擎 (BKT + ACT-R)
│   ├── l_model/          # L-Model 时间轴 + 反事实引擎
│   ├── delivery/         # 干预投放 (I1-I4, YAML 可扩展)
│   ├── gap/              # 差距分析 (M5)
│   ├── rank/             # 优先级排序 (M6)
│   ├── report/           # 报告卡 (M7) + 科学假设 (M8)
│   ├── privacy/          # PrivacyGuard P/R/S 三级强制
│   ├── pipeline/         # DAG 管线编排
│   ├── calibrate/        # 认知参数校准
│   ├── data_loader.py    # 真实数据加载器 (ASSISTments/EdNet)
│   └── llm/              # 千问 LLM 客户端 (在线/离线双模)
├── frontend/src/
│   ├── pages/            # 13 个功能页面
│   ├── api.js            # API 客户端
│   └── i18n.js           # 集中式本地化
├── config/               # YAML 配置 (base + intervention_delivery)
├── data/real/            # 真实数据集放置目录 (见 README)
├── tests/                # pytest 测试套件
├── 技术设计文档-虚拟学生试验台-v5.0.md
├── 需求说明文档-虚拟学生试验台-v5.0.md
└── 虚拟学生全方位档案设计文档-v5.0.md
```

## 前端页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 成果输出中心 | /runs/:id/report | M7 报告卡 + M8 研究计划 + 教学建议 |
| 画像浏览 | /runs/:id/personas | 学生/教师档案 + 23 域全方位档案 |
| 家长档案 | /runs/:id/parents | 家长画像浏览 (FR-F7) |
| L-Model 时间轴 | /runs/:id/timeline | 日粒度事件流 |
| 场景比较 | /runs/:id/scenes | 五场景效应量对比 |
| 子群切片 | /runs/:id/subgroups | 24 维度多选切片 |
| 社会网络 | /runs/:id/network | 同伴网络可视化 |
| 生命历程回放 | /runs/:id/life_course | 90 天轨迹曲线 |
| 反事实对比 | /runs/:id/counterfactual | 因果推断分支 |
| 校准诊断 | /runs/:id/calibration | BKT 参数校准 (FR-F2) |
| 失真地图 | /runs/:id/distortion | 干预×场景×指标失真热力图 (FR-F3) |
| 预筛报告 | /runs/:id/prescreening | Go/No-Go 决策支持 (FR-F4) |
| 人在回路 | /runs/:id/hitl | 专家反馈闭环 (FR-F5) |

## 真实数据接入

将 ASSISTments / EdNet 公开数据集 CSV 文件放入 `data/real/` 目录即可自动识别：
- `skill_builder_data_corrected.csv` (ASSISTments 2009-2010)
- `2015_100_skill_builders_main_problems.csv` (ASSISTments 2015)
- `ednet_kt1.csv` 或 `KT1/u*.csv` (EdNet KT1)

详见 `data/real/README.md`。无真实数据时系统透明回退至合成数据（标注 `source=synthetic`）。

## C9 SFT 备选方案说明

比赛要求 C9（SFT 微调）为可选加分项。本平台采用以下替代策略：

1. **Prompt Engineering + RAG**: 当前通过精心设计的提示词模板 + 检索增强生成实现画像差异化，
   无需微调即可充分利用千问能力。
2. **离线确定性回退**: 无 API Key 时使用确定性 mock（基于 seed），保证测试/演示可复现。
3. **SFT 扩展路径**: 若需进一步微调，可收集平台生成的画像-轨迹对作为 SFT 训练数据，
   对千问进行领域适配。接口已预留（`src/llm/` 模块的 `LLMClient` 支持切换 endpoint）。

此设计确保系统在无 GPU/无微调条件下仍完整可用，满足比赛"国产开源大模型应用"要求。

## 隐私与安全

- **P/R/S 三级分类**: 所有字段按 Public / Restricted / Sensitive 分级
- **S 级永不泄露**: API 响应、LLM 提示词、导出文件三重拦截
- **D11 域剥离**: 23 域档案中 D11（隐私与敏感信息）在 API 层自动剥离
- **静态扫描**: `PrivacyGuard.scan_log()` 可检测文本中的 S 级泄露

## 许可证

本项目为"挑战杯"竞赛参赛作品，仅供学术评审使用。
