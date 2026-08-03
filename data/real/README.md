# 真实数据接入说明（FR-D1 / C6 比赛硬性）

本目录用于放置**真实的公开学习日志数据集**。系统的 `RealDataLoader`
（`src/data_loader.py`）会自动发现并解析下列文件名，将真实数据用于 BKT
认知校准（`n1_load_realdata → n2_fit_kc_model`）。

> **科学诚实声明**：本系统**绝不伪造数据**，也**绝不把合成数据标注为真实数据**。
> 当本目录下没有可识别的真实数据集时，流水线会**透明地回退到带 `source="synthetic"`
> 标记的合成日志**，并在运行结果的 `data_source` 字段中如实记录。

## 支持的数据集与文件名

将下列任一文件放入本目录（支持子目录递归发现），系统即按真实数据校准：

| 数据集 | 识别文件名 | 关键列 |
| --- | --- | --- |
| ASSISTments 2009-2010 | `skill_builder_data_corrected.csv` | `order_id`, `user_id`, `correct`, `skill_name` |
| ASSISTments 2015 | `2015_100_skill_builders_main_problems.csv` | `sequence_id`, `user_id`, `correct`, `skill_id` |
| EdNet KT1 | `ednet_kt1.csv` 或 `KT1/u*.csv` | `timestamp`, `action_type`, `item_id`, `correct` |

优先级：ASSISTments 2009-2010 > ASSISTments 2015 > EdNet KT1。

## 数据获取途径（公开）

- **ASSISTments**：https://sites.google.com/site/assistmaborgs/ （需注册免费学术账号）
- **EdNet**：https://github.com/riiid/ednet （CC 协议公开）

下载后将对应 CSV 放入本目录即可，无需修改任何代码。

## 统一内部格式

无论来源如何，加载器都会归一化为每个学习者一条正确性序列：

```json
{"student_id": "u123", "sequence": [1, 0, 1, 1, 0], "kc_id": "algebra", "n_responses": 5}
```

该格式直接被 `CognitiveCalibrator.calibrate()` 消费，用于拟合
`p_know / p_learn / p_slip / p_guess` 四个 BKT 参数。

## 验证

运行 `python -m pytest tests/test_data_loader.py -q` 可在不依赖真实数据文件的
情况下，验证 ASSISTments / EdNet 解析器的正确性（测试用临时 CSV）。
