# 虚拟学生试验台 v6.0 (VirtualStudent Sandbox)

> 基于国产开源大模型（通义千问）的 AI Scientist 多智能体教育仿真平台  
> 赛题：XH-202619《基于国产开源大模型的 AI Scientist 的研发与应用》

## 项目概述

本平台通过多智能体仿真（学生 S-Model / 教师 T-Model / 家长 P-Model）生成虚拟学生全生命周期学习轨迹，
结合认知引擎（BKT + ACT-R）、因果推断（虚拟效应量 Hedges' g）和科学假设自动生成，
为教育研究者提供 **"虚拟预筛 → 真人试验"** 的闭环研究范式。

## v6.0 结项基线

v6.0 是当前前端、后端、配置、导出材料和设计文档统一使用的结项版本。该版本重点完成：

- 历史运行采用 `meta.json` 摘要索引和完整运行包按需懒加载，避免启动时解压全部历史仿真。
- 稳健性页面改用轻量 `GET /api/robustness`，不再遍历所有 run 生成完整报告。
- 报告结果写入磁盘缓存；已加载历史运行受 LRU 上限约束，降低内存持续增长。
- 新运行在后台线程执行，前端显示阶段进度，不阻塞创建接口。
- 学生、教师、家长画像生成采用受控并发和批处理；Qwen 请求超时为 30 秒，失败时可确定性降级。
- 前端网络布局分块执行，降低大型网络图阻塞主线程的风险。
- 所有模拟输出定位为假设候选或方向性证据，不替代真人 RCT。

项目版本的单一事实来源为后端 `src/__init__.py` 的 `__version__` 和前端 `frontend/src/version.js` 的 `APP_VERSION`。发布时还需同步 `config/base.yaml` 与 `frontend/package.json`。

## 核心特性

| 特性 | 说明 |
|------|------|
| 多智能体画像 | 23 域 219 字段全方位档案，千问 LLM 驱动生成 |
| 三方关系建模 | 学生-教师-家长关系网络可视化与影响力分析 |
| 认知引擎 | BKT 知识追踪 + ACT-R 遗忘曲线，确定性可复现 |
| 真实数据校准 | ASSISTments / EdNet 数据加载器，透明回退合成数据 |
| 五场景仿真 | 学校 / 社交 / 课外班 / 自学 / 家庭 |
| 中介效应分解 | 效果路径分析：干预通过哪些渠道生效（教师/家长/直接/课外/自学） |
| 因果推断 | 虚拟效应量 + 95% CI + 失真地图 + 优先级排序 |
| 稳健性检验 | 种子敏感性与样本量敏感性分析 |
| 科学假设生成 | M8 自动生成可证伪假设（教师/家长/场景分化） |
| 演示模式 | 自动语音导览 + 逐页解说 + 重点标注 |
| 比赛材料生成 | 一键导出 A4 摘要 / PPT 大纲 / 演示脚本 |
| 人在回路 | 专家审阅反馈闭环 (HITL) |
| 隐私强制 | P/R/S 三级 PrivacyGuard，S 级永不泄露 |

## 技术栈

- **后端**: Python 3.12, FastAPI, uvicorn (port 6668)
- **前端**: React 18, Vite 5, react-router-dom (port 4000)
- **LLM**: 通义千问 (DashScope OpenAI-compatible API)
- **数据**: gzip JSON 完整运行包 + meta/report/robustness sidecar (`data/runs/`)；DuckDB 数据层已预留 (`src/data_layer.py`)
- **测试**: pytest (100+ tests)

## 快速启动

### 后端

```bash
# 安装依赖（Python 3.12，版本已锁定验证）
pip install -r requirements.txt

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

> API Key 保存后仅以掩码形式回显，不会明文返回给前端。后端会把本地配置保存到 `config/llm_config.json`；该文件已加入 `.gitignore`，不得提交、打包或截图。若 key 曾暴露，必须在百炼控制台立即轮换。

## 项目结构

```
├── src/
│   ├── api/              # FastAPI 后端 (main.py + models.py + real_run.py)
│   ├── persona_service/  # 画像生成 (student/teacher/parent + 23域档案)
│   ├── cognitive_engine.py # 认知引擎 (BKT + ACT-R，已接入 L-Model 日仿真)
│   ├── l_model/          # L-Model 时间轴 + 反事实引擎
│   ├── delivery/         # 干预投放 (I1-I5，目录为 YAML 单一事实来源)
│   ├── gap/              # 差距分析 (M5)
│   ├── rank/             # 优先级排序 (M6)
│   ├── report/           # 报告卡 (M7) + 科学假设 (M8)
│   ├── privacy/          # PrivacyGuard P/R/S 三级强制
│   ├── pipeline/         # DAG 管线编排（预留模块，未接入 API）
│   ├── calibrate/        # 认知参数校准 (文献基线对比)
│   ├── data_loader.py    # 真实数据加载器 (ASSISTments/EdNet，预留接入)
│   └── llm/              # 千问 LLM 客户端 (在线/离线双模)
├── frontend/src/
│   ├── pages/            # 20+ 个功能页面
│   │   ├── DashboardPage.jsx      # 执行摘要（优化布局）
│   │   ├── TriadNetworkPage.jsx   # 三方关系网络
│   │   ├── MediationPage.jsx      # 效果路径分析
│   │   ├── RobustnessPage.jsx     # 稳健性检验
│   │   ├── DemoModePage.jsx       # 演示模式（语音导览）
│   │   └── ExportCenterPage.jsx   # 比赛材料生成中心
│   ├── api.js            # API 客户端
│   └── i18n.js           # 集中式本地化
├── config/               # YAML 配置 (base + intervention_delivery)
├── data/real/            # 真实数据集放置目录 (见 README)
├── tests/                # pytest 测试套件
├── 技术设计文档-虚拟学生试验台-v6.0.md
├── 需求说明文档-虚拟学生试验台-v6.0.md
├── 虚拟学生全方位档案设计文档-v6.0.md
└── PROJECT_COMPLETION_SUMMARY_V6.0.md # v6.0 结项状态与待办
```

## 性能与历史运行说明

- `GET /api/runs` 只读取小型 meta sidecar，历史运行数量增加时不会逐个解压 `.json.gz`。
- 首次打开某个历史 run 仍需解压该 run 的完整包；随后由内存 LRU 缓存加速重复访问。
- `GET /api/robustness` 只读取稳健性摘要，不触发完整 report 或 LLM 调用。
- 报告首次生成可能包含 LLM 延迟，后续访问优先使用 `*.report.json` 缓存。
- 大规模 run 的首次打开耗时取决于压缩包大小、磁盘和内存；正式结项材料应提供固定条件下的 p50/p95 实测，而不是固定秒数承诺。
## 前端页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 执行摘要 | /runs/:id/dashboard | 核心发现 + 预筛决策 + 虚拟vs文献对比（优化布局） |
| 三方关系图 | /runs/:id/triad_network | 学生-教师-家长关系网络可视化 |
| 效果路径 | /runs/:id/mediation | 中介效应分解：干预通过哪些渠道生效 |
| 稳健性检验 | /runs/:id/robustness | 种子敏感性与样本量敏感性分析 |
| 演示模式 | /runs/:id/demo | 自动语音导览 + 逐页解说 |
| 比赛材料 | /runs/:id/export | 一键导出 A4 摘要 / PPT 大纲 / 演示脚本 |
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
| 失真地图 | /runs/:id/distortion | 干预x场景x指标失真热力图 (FR-F3) |
| 预筛报告 | /runs/:id/prescreening | Go/No-Go 决策支持 + 排除原因 (FR-F4) |
| 人在回路 | /runs/:id/hitl | 专家反馈闭环 (FR-F5) |

## 自定义干预与反事实变量（YAML 单一事实来源）

实验臂与反事实“如果会怎样”变量全部声明在 `config/intervention_delivery.yaml`，
前后端共读同一份词表，**增减干预无需改代码**：

- 在 `interventions:` 节追加一个条目（字段：`label` / `type` / `description` /
  `target_scene` / `default_channel` / `effect_achievement` / `effect_motivation` /
  `evidence_hedges_g` / `cost_yuan` / `action`），下次运行即自动成为新实验臂，
  进入效应量估计、优先级排序与预筛决策（GO / 条件性 / NO-GO）。
  - `effect_*` 为完美执行下整个干预期的预期总增益（0–100 成绩分），
    引擎按天均摊并按 通道效率 × 中介者质量 逐层衰减。
  - `evidence_hedges_g` 为学习科学元分析参考值，仅用于报告与排序。
- 在 `counterfactual_modifications:` 节追加条目（`key` / `label` / `effects`），
  反事实对比页的下拉框会自动多出一个分流选项。
- 前端通过 `GET /api/catalog` 在运行时拉取上述目录，无需重新构建后端。
- **研究者入口（按运行）**：首页展开“自定义候选干预”填写候选（名称/通道/场景/剂量/证据 g/成本/动作），
  或在 `POST /api/runs` 的 `interventions` 字段提交同构清单；
  该运行即仅评估你提交的候选（对照组自动保留），
  报告与预筛按你的命名展示你的方案。
  剂量可为负以表达风险因素（如社区帮派暴露），`exposure_rate` &lt;1 引入
  个体级暴露随机（估计量为 ITT 口径）；预筛四条标准为双向
  （显著有害同样被确认）。

## 真实数据接入（预留）

> 当前版本中，真实数据加载器（`src/data_loader.py`）为预留模块，尚未接入仿真运行管线；
> 运行结果均基于合成画像（标注 `source=synthetic`）。接入规划见技术设计文档。

将 ASSISTments / EdNet 公开数据集 CSV 文件放入 `data/real/` 目录，供加载器识别：
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

## 演示模式使用说明

演示模式提供自动语音导览功能，适合现场展示或录制演示视频。

### 启动演示模式

1. 完成一次运行后，在执行摘要页面点击「演示模式」按钮
2. 或直接访问 `/runs/:id/demo` 路由

### 功能特性

- **自动语音导览**：基于 Web Speech API，逐页朗读解说词
- **逐页导航**：支持前进/后退/暂停/继续
- **重点标注**：自动高亮当前页面的关键数据
- **建议停留时间**：每页显示推荐停留时长

### 演示脚本

如需自定义解说词或录制视频，可先导出演示脚本：
- 进入「比赛材料」→「材料生成中心」
- 点击「下载演示脚本（TXT）」
- 脚本包含逐页解说词、建议停留时间、重点标注

## 比赛材料生成指南

比赛材料生成中心提供三种一键导出功能，所有材料均基于当前运行数据生成。

### 访问方式

- 在执行摘要页面点击「比赛材料」按钮
- 或直接访问 `/runs/:id/export` 路由

### 导出选项

#### 1. A4 一页纸摘要（HTML）

- **格式**：HTML 页面，已针对 A4 打印优化
- **内容**：项目标题、一句话结论、统计卡片、Top 3 效应量表格、图表占位符
- **使用方式**：下载后在浏览器打开，点击「打印为 PDF」按钮即可生成 PDF

#### 2. 5 页 PPT 大纲（Markdown）

- **格式**：Markdown 文件
- **内容**：
  - 第1页：问题与定位
  - 第2页：虚拟学生生成（4层架构）
  - 第3页：核心发现（Top 3 效应量 + 预筛决策）
  - 第4页：质量保障（校准、失真图、稳健性）
  - 第5页：结论与建议
- **使用方式**：评委可直接复制 Markdown 内容到 PPT

#### 3. 演示视频脚本（TXT）

- **格式**：纯文本文件
- **内容**：逐页解说词 + 建议停留时间 + 重点标注 + 常见问题准备
- **使用方式**：适合录制演示视频或现场演示时参考

### 注意事项

- 所有材料均标注「⚠️ 以上为虚拟仿真结果，需真人试验验证，不可直接外推」
- 材料生成完全在前端完成，不依赖后端
- 建议先生成演示脚本熟悉内容，再进入演示模式

## 许可证

本项目为"挑战杯"竞赛参赛作品，仅供学术评审使用。
