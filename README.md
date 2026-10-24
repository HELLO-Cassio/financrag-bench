# FinanCRAG Bench

面向中国境内零售银行公开合规文本的 GraphRAG 研究项目。当前阶段：**E1 仓库初始化 / 范围与法规清单准备**。

本仓库按《E1 执行手册》v1.0（2026-10-24）组织。研究关注“业务行为 → 监管要求 → 依据条款”的证据链，为后续解析、建图、问答与鲁棒性实验准备可追溯语料。

> 当前没有已核验入库的法规。`manifest.csv` 仅含正式表头；候选文件单独保存在候选清单中。基础检查通过不代表 E1 验收通过。尚未评审、冻结或移交 E2。

## 从这里开始

1. 阅读 [范围声明](docs/scope.md)，团队确认业务边界和时间基准。
2. 按 [候选清单](docs/candidates.md) 和 [搜索关键词](docs/搜索关键词.md) 寻找官方原文。
3. 每份材料建一个 `data/raw/DOCxx/` 目录；核对后写入 [法规清单](docs/manifest.csv)。填写规则见 [数据字典](docs/data_dictionary.md)。
4. 记录文件关系、版本核验和五类题证据，再运行校验。
5. 按 [E1 验收清单](docs/E1_checklist.md) 完成人工复核、导师评审及 [E2 交接](docs/handoff_E1_E2.md)。

## 目录

```text
financrag-bench/
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── docs/
│   ├── scope.md                  # 当前范围草案
│   ├── manifest.csv              # 正式数据入口，18 列
│   ├── candidates.md             # 未核验候选，不进入解析
│   ├── data_dictionary.md        # 字段、词表与来源要求
│   ├── relations.csv             # 依据/适用/例外/修订关系证据
│   ├── verification_log.csv      # 版本与来源核验记录
│   ├── coverage_matrix.md       # 五类题的实际证据矩阵
│   ├── E1_checklist.md
│   ├── handoff_E1_E2.md
│   ├── 搜索关键词.md
│   └── templates/               # 手册配套模板
├── data/raw/                    # 每份原文一个 DOCxx 文件夹
├── scripts/                     # 标准库脚本，无第三方依赖
├── tests/                       # 校验器回归检查
└── .github/                     # 自动检查、任务和评审模板
```

## 本地检查（Python 3.10+）

在仓库根目录执行：

```sh
python scripts/validate_manifest.py docs/manifest.csv --mode draft
python -m unittest discover -s tests -v
```

录入文件后，计算其哈希（将路径替换为真实文件）：

```sh
python scripts/hash_file.py data/raw/DOC01/DOC01_简称_类型_版本状态.pdf
```

E1 冻结前必须运行：

```sh
python scripts/validate_manifest.py docs/manifest.csv --mode release
```

`draft` 允许空清单和标注“待核”的元数据，但检查已有文件及哈希；`release` 拒绝空清单、待核状态和不满足数量要求的数据。自动检查不判断法规实际效力，也不能代替导师评审、附件完整性检查或五类题人工验收。

## 协作与阶段

| 阶段 | 当前状态 | 完成依据 |
|---|---|---|
| 仓库搭建 | 已准备 | 文件、模板、脚本与本地检查 |
| E1 范围确认 | 草案 | 团队确认及评审记录 |
| E1 法规采集 | 未开始 | 15–25 份官方文件及可追溯元数据 |
| E1 版本冻结 | 未完成 | 自动检查、人工验收、`E1-v1.0` 标签 |
| E2 / E3 / E5 / E9 | 未开始 | 先完成 E1；不在本次初始化中虚构实验实现 |

本项目使用团队已创建的 [GitHub 仓库](https://github.com/HELLO-Cassio/financrag-bench)，沿用其现有可见性设置。团队协作和冻结流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。本项目尚未选定开源许可证；官方法规和第三方材料的权利归属不因入库而改变。研究基准不提供个案法律意见。
