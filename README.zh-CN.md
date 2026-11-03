# Paper Overview｜论文精读与复现评估

[English](README.md) | 简体中文

一个可复用的论文精读技能，按固定的 11 项顺序讲解：问题、流程图、框架图、方法、核心、局限、研究启发与数据集、官方代码、复现难度、创新点和具体场景。

这套流程围绕**问题、机制与证据**展开，适用于不同学科的算法、实证、理论、定性和综述类论文，并根据研究类型调整分析重点。

## 你会得到什么

- 以论文正文、附录和已核实官方资料为依据的结构化讲解。
- 两张用途不同的图：**流程图**解释步骤顺序，**框架图**解释组成部分及其关系。
- 每张展示的图后紧接读图讲解：阅读顺序、关键元素、箭头或坐标含义、具体路径或结果对照，以及与当前问题的联系；不只贴图或复述图注。
- 对关键方法、公式、假设和评价条件的说明。
- 清楚区分作者报告、材料核实、分析推断和研究建议。
- 与研究类型相匹配的代码、数据及复现条件评估。
- 先询问是否需要的交互式代码讲解，用具体样本逐步对照输入、关键计算与输出。

## 安装

### 在本地 Codex 中安装

将仓库克隆到用户技能目录。

**macOS / Linux**

```bash
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/VinceTree/Paper-overview.git "$HOME/.agents/skills/paper-overview"
```

**Windows PowerShell**

```powershell
New-Item -ItemType Directory -Force -Path "$HOME/.agents/skills" | Out-Null
git clone https://github.com/VinceTree/Paper-overview.git "$HOME/.agents/skills/paper-overview"
```

如只希望在某个项目中使用，将仓库放在 `<项目目录>/.agents/skills/paper-overview`。保留 `SKILL.md`、`scripts/`、`references/`、`requirements.txt`、第三方声明和 `agents/` 的相对位置。如果技能没有出现，可重启 Codex。

上述路径依据 [OpenAI 官方技能文档](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)。也可以让内置的 `$skill-installer` 从本 GitHub 仓库安装该技能。

### 直接使用说明文件

如果你的助手可以读取此仓库，可以要求它先阅读 [SKILL.md](SKILL.md)，再按其中链接的参考文件执行。技能自动发现方式和调用语法取决于所用应用。

本仓库提供材料准备工具，依赖 Python 3.10+ 与 PyMuPDF；获取代码时另需 Git，不包含模型运行环境。缺少依赖时说明情况并使用可用网页 / PDF 阅读工具，详见[材料工具指南](references/material-tools.md)。

## 自动准备论文材料

阅读开始时准备 PDF、可用原始与展开 LaTeX、逐页文本、大纲、元数据和经检查的裁图。
标题或 DOI 先解析到官方论文地址；代码地址先作为候选，经作者来源核实后才可称为官方。

```text
python scripts/fetch_paper.py 2510.10125v3 --root ./papers
python scripts/fetch_paper.py <材料目录> --code <已核实仓库> --fetch-code
python scripts/extract_figures.py <材料目录> --dpi 220
python scripts/crop.py <材料目录>/paper.pdf --page 4 0.08 0.10 0.92 0.65 -o detail.png
```

进入用户要求的代码讲解分支时才执行代码获取命令。`--code` 记录调用者核实过的地址，
只有 `--fetch-code` 才启用克隆；`--code-ref` 可选择 tag / commit，元数据记录实际提交。
关闭 Git LFS 自动下载；不执行论文代码，不自动下载数据集与权重或安装论文依赖。

目录优先沿用用户及项目约定，否则依次使用已有 `related_work/`、`PAPERS_DIR`、`papers/`。
PDF 与源码绑定同一 arXiv 版本，目录隔离版本并记录校验和；人工图表保留，自动裁图另存。
裁图仍须亲自检查，必要时手动修复。降级行为见[材料工具指南](references/material-tools.md)，
讲解深度示例见[Ctrl-World 静态实例](references/ctrl-world-walkthrough.md)。

开发验证使用独立环境安装 `requirements.txt`，再执行 `python -m unittest discover -s tests -v`。
测试使用小型 PDF 与本地 Git 仓库，不使用模型或数据集。

## 快速开始

提供论文标题、链接、arXiv 编号、DOI、PDF 或正文。在 Codex 中，可使用 `$paper-overview` 显式调用已安装的技能。

```text
使用 $paper-overview 讲解这篇论文：<论文链接或 PDF>。
按完整的 11 项顺序展开，分别绘制流程图和框架图，
核实主要结论、官方资源和复现条件。
```

默认使用**简体中文**，也可以明确指定英文或其他语言。未要求文件时，讲解直接在对话中交付。

提供以下可选背景，可以让讲解更贴近你的需求：

```text
使用 $paper-overview 讲解 <论文>。
我的知识背景是 <背景>，研究问题是 <问题>。
保留全部 11 项，重点解释方法和证据。
评估在 <可用资源> 条件下能够完成哪些复现验证。
```

## 11 项讲解结构

正式讲解前，先确认论文身份、所读版本、发表状态和来源链接，并用一句话说明主要贡献。

| 序号 | 项目 | 主要回答的问题 |
| --- | --- | --- |
| 1 | 解决的问题 | 论文针对什么研究缺口或具体问题？ |
| 2 | 流程图 | 先做什么、后做什么？ |
| 3 | 框架图 | 有哪些模块、概念或变量，它们如何关联？ |
| 4 | 解决问题的方法 | 研究或方法怎样开展，如何验证？ |
| 5 | 核心 | 关键思想是什么，依赖哪些成立条件？ |
| 6 | 没有解决的部分 | 还存在哪些局限与证据缺口？ |
| 7 | 启发、可以做的点与数据集 | 可以研究什么、怎样检验、需要什么资源？ |
| 8 | 官方代码 | 实际公开了哪些官方实现或其他研究材料？ |
| 9 | 复现难度 | 检查、复算、独立重复或扩展研究需要什么条件？ |
| 10 | 创新点 | 相比最接近的已有工作，新意在哪里，有什么证据？ |
| 11 | 问题的场景 | 在一个具体案例中，问题与方法怎样展开？ |

第 2、3 项先显示对应论文原图，标注图号、PDF 页码和来源并亲自检查裁剪；再额外绘制两张 Mermaid 概括图，明确原图与概括图的对应关系，不支持 Mermaid 时用文本图。缺少对应原图时说明。图的内容随研究类型变化，例如理论论文可以绘制证明流程与命题依赖关系。不适用的项目保留标题并解释原因。

逐项写作要求见[完整讲解模板](references/overview-template.md)。

## 可选的交互式代码讲解

有适用代码时，助手会先完成 11 项概览，在末尾询问：

> 需要我结合代码，用一个具体样本按执行顺序讲一遍吗？可以选择“需要”或“暂时不用”。

回答“需要”后，才开始对照代码：**样本与入口 → 关键计算 → 输出与下一轮**。
每轮围绕一个阶段，用短片段、具体数值与形状变化解释，讲完等待你继续、追问或跳转。
模块表须覆盖来源与初始化、总参数 / 可训练参数及依据、分阶段更新方式、实际输入输出与单位、设计理由和固定版本代码位置。
全程使用真实配置尺寸与可访问的真实样本，大型张量只展示必要切片，不默认缩成玩具尺寸。缺失数值明确标未知。
多轮系统至少走首次和一次后续调用，解释观测、状态、缓存的变化；跨回复记录完成进度。回答“暂时不用”或尚未回答时，不展开代码讲解。

也可以直接说：

```text
需要，结合官方代码，用一条具体样本按执行顺序讲一遍，每轮讲完等我继续。
```

如果最初的请求已明确要求对照代码，助手会直接开始，无需重复确认；要求一次讲完也会遵循。
没有适用代码时不询问；官方实现缺失或无法访问时，会说明情况，并可让你选择按论文伪代码演示，
不会把示意代码当成官方实现。代码讲解只涉及阅读与解释，不会自动安装依赖或运行实验。

详细节奏与示例见[代码讲解指南](references/code-walkthrough.md)。这部分参考并改编自
[skJack/kelip-paper-reading](https://github.com/skJack/kelip-paper-reading)，来源版本与 MIT 许可见
[第三方声明](THIRD_PARTY_NOTICES.md)。

## 证据与范围

- 尽可能阅读正文与相关附录；资料无法访问时，说明缺失内容和实际阅读范围。
- 为重要结论链接对应章节、图表、公式或代码文件。
- 性能数字保留指标、实验条件和评价协议，并说明不确定性与缺失证据。
- 核实官方资源归属、公开范围和版本；区分代码阅读、运行验证和完整复现。
- 将后续研究想法写成可检验的建议，并按需要评估数据权限、补采、设备和计算条件。

这套流程聚焦单篇论文。论文列表查找、全文翻译、系统性文献综述和正式同行评审需要使用其他流程。讲解论文本身不授权安装依赖、运行实验、上传材料或推送代码。

详细核查要求见[证据与复现核查指南](references/verification.md)。

## 仓库结构

```text
Paper-overview/
├── README.md                         # 英文说明
├── README.zh-CN.md                   # 简体中文说明
├── SKILL.md                          # 技能元数据与执行流程
├── THIRD_PARTY_NOTICES.md             # 改编来源与第三方许可
├── scripts/                         # fetch_paper.py / extract_figures.py / crop.py
├── requirements.txt                 # PyMuPDF
├── tests/                           # Offline behavioral checks
├── agents/
│   └── openai.yaml                   # 展示信息与默认提示词
└── references/
    ├── material-tools.md             # Material preparation and original figures
    ├── ctrl-world-walkthrough.md      # Real-dimension static example
    ├── code-walkthrough.md           # 用户确认后的交互式代码讲解
    ├── overview-template.md          # 11 项详细讲解模板
    └── verification.md               # 证据与复现核查要求
```

当前技能指令与参考文件使用简体中文，输出语言可以在请求中指定。调整工作流程时，请同步检查 [SKILL.md](SKILL.md)、[讲解模板](references/overview-template.md)、[代码讲解指南](references/code-walkthrough.md)、[核查指南](references/verification.md) 以及两版 README 的一致性。
