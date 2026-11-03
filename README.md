# Paper Overview

English | [简体中文](README.zh-CN.md)

A reusable agent skill for understanding a research paper through 11 ordered sections: the problem, workflow, framework, methods, core idea, limitations, research opportunities, public resources, reproduction requirements, contributions, and concrete scenarios.

The skill connects **questions, mechanisms, and evidence**. It supports papers across disciplines and adapts its analysis to algorithmic, empirical, theoretical, qualitative, and review research.

## What you get

- A structured explanation grounded in the paper, appendices, and verified official resources.
- Two separate diagrams: a **flowchart** for the sequence of steps and a **framework diagram** for components and relationships.
- Explanations of key methods, equations, assumptions, and evaluation conditions.
- A clear distinction between author-reported results, inspected materials, analytical inferences, and proposed research directions.
- An assessment of available code, data, and reproduction requirements appropriate to the research type.
- An optional interactive code walkthrough that asks first, then traces a concrete sample through inputs, key computations, and outputs.

## Installation

### Local Codex installation

Clone this repository into your user skills directory.

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

For a project-scoped installation, place the repository at `<project>/.agents/skills/paper-overview` instead. Keep `SKILL.md`, `scripts/`, `references/`, `requirements.txt`, `THIRD_PARTY_NOTICES.md`, and `agents/` together. If the skill does not appear, restart Codex.

These paths follow the [official OpenAI skills documentation](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills). You can also ask the built-in `$skill-installer` to install the skill from this GitHub repository.

### Direct use

If your assistant can read this repository, ask it to read [SKILL.md](SKILL.md) and follow its linked references. Automatic discovery and invocation syntax depend on the host application.

This repository includes material preparation tools (Python 3.10+ and PyMuPDF; Git is optional for code retrieval). It does not bundle a model runtime. Missing dependencies are reported; available web/PDF readers can be used as a fallback. See [material tools](references/material-tools.md).

## Automatic material preparation

At the start of reading, prepare the PDF, available raw/flattened LaTeX, page text, outline, metadata and inspected figure crops. Resolve titles and DOI pages to an official paper link first. Code links remain unverified candidates until checked against author sources.

```text
python scripts/fetch_paper.py 2510.10125v3 --root ./papers
python scripts/fetch_paper.py <material-directory> --code <verified-repository> --fetch-code
python scripts/extract_figures.py <material-directory> --dpi 220
python scripts/crop.py <material-directory>/paper.pdf --page 4 0.08 0.10 0.92 0.65 -o detail.png
```

Run the code-fetch command only when entering a requested code walkthrough. `--code` records a caller-verified URL; `--fetch-code` explicitly enables cloning. `--code-ref` selects a tag/commit, and metadata records the actual commit. Git LFS downloads are disabled. Paper source code, datasets and weights are not executed or automatically installed/downloaded.

User/project directory choices take precedence; otherwise the script uses `related_work/` when present, then `PAPERS_DIR`, then `papers/`. arXiv PDF and source use the same version, with separate version directories and PDF checksums. Original user figures are preserved in favor of a separate automatic directory. Crops require visual inspection and may need manual correction. See [material tools](references/material-tools.md) for fallback behavior and [the Ctrl-World static example](references/ctrl-world-walkthrough.md).

For tool development, use a dedicated environment, install `requirements.txt`, and run `python -m unittest discover -s tests -v`. The tests use small PDF fixtures and a local Git repository, not models or datasets.

## Quick start

Provide a paper title, URL, arXiv identifier, DOI, PDF, or full text. In Codex, invoke the installed skill with `$paper-overview`.

```text
Use $paper-overview to explain this paper in English: <paper URL or PDF>.
Follow all 11 sections, draw separate flowchart and framework diagrams,
and verify the main claims, official resources, and reproduction requirements.
```

The default output language is **Simplified Chinese**. Request English or another language explicitly when needed. Answers are delivered in the conversation unless you request a file.

Optional context helps tailor the explanation:

```text
Use $paper-overview to explain <paper> in English.
My background is <background>, and my research question is <question>.
Preserve all 11 sections and focus on the method and evidence.
For reproduction, assess what can be checked with <available resources>.
```

## The 11-section structure

Each explanation begins with the paper's identity, version, publication status, source links, and a one-sentence account of its main contribution.

| # | Section | Main question |
| --- | --- | --- |
| 1 | Problem addressed | What gap or research question does the paper address? |
| 2 | Flowchart | What happens first, next, and last? |
| 3 | Framework diagram | What are the components, concepts, or variables, and how are they related? |
| 4 | Methods | How does the study or method work, and how is it validated? |
| 5 | Core idea | What key idea and conditions make the approach work? |
| 6 | Unresolved issues | What limitations and evidence gaps remain? |
| 7 | Insights, research opportunities, and datasets | What could be investigated next, how could it be tested, and what resources are needed? |
| 8 | Official code | What official implementations or other research materials are actually available? |
| 9 | Reproduction difficulty | What is needed to check, reproduce, independently repeat, or extend the work? |
| 10 | Contributions and novelty | What differs from the closest prior work, and what evidence supports it? |
| 11 | Concrete scenario | How does the problem and proposed approach play out in a specific case? |

Sections 2 and 3 display the relevant original paper figures, with figure numbers, PDF pages, sources, and visual inspection, followed by two additional Mermaid summary diagrams (text diagrams as a fallback). The summaries explicitly map back to the original figures. Missing originals are disclosed. Their structure follows the research: for example, a theoretical paper can show a proof workflow and proposition dependencies. Inapplicable sections retain their titles and explain why they do not apply.

See the [full explanation template](references/overview-template.md) for section-by-section guidance.

## Optional interactive code walkthrough

When applicable code is available, the assistant first completes the 11-section overview, then asks:

> Would you like a code walkthrough that follows a concrete sample in execution order? You can answer “yes” or “not now.”

Answering “yes” starts the walkthrough: **sample and entry point → key computations → output and the next iteration**.
Each reply covers one stage using short snippets, concrete values, and shape changes, then waits for you to continue, ask a question, or jump ahead.
A complete module table covers origin/initialization, total and trainable parameters with evidence, stage-specific updates, real input/output shapes and units, design reasons, and fixed-revision code locations. Walkthroughs use the actual configuration dimensions and accessible real samples, showing small slices of large tensors without shrinking their dimensions. Unknown values are disclosed rather than invented. Iterative systems trace at least the first and a subsequent call, including observation, state and cache changes; progress is tracked across replies.
An unanswered question or “not now” does not start the walkthrough.

You can also request it directly:

```text
Yes, follow one concrete sample through the official code in execution order.
Explain one stage per reply and wait for me to continue.
```

If your original request already asks for a code walkthrough, the assistant starts without asking again. You can also ask for the whole walkthrough in one reply.
Papers without applicable code do not trigger the question. If the official implementation is missing or inaccessible, the assistant explains that limitation and can offer a paper-based pseudocode demonstration, clearly distinguished from official code.
The walkthrough reads and explains code; it does not automatically install dependencies or run experiments.

See the [code walkthrough guide](references/code-walkthrough.md) for pacing and an example. This guidance is adapted from
[skJack/kelip-paper-reading](https://github.com/skJack/kelip-paper-reading); the source revision and MIT license are recorded in
[third-party notices](THIRD_PARTY_NOTICES.md).

## Evidence and scope

- Read the full paper and relevant appendices when accessible; disclose unavailable materials and the actual reading scope.
- Link important claims to their supporting sections, figures, tables, equations, or code files.
- Report numerical results with their metrics, conditions, and evaluation protocol; identify uncertainty and missing evidence.
- Check official resource ownership, availability, and versions. Distinguish code inspection from executed tests and full reproduction.
- Present new research ideas as testable proposals; assess access, collection, equipment, and compute requirements where relevant.

The workflow focuses on one paper. A paper list, full-text translation, systematic literature review, or formal peer review needs a different workflow. Explaining a paper does not by itself authorize dependency installation, experiment execution, uploads, or code pushes.

See the [verification guide](references/verification.md) for detailed checks.

## Repository structure

```text
Paper-overview/
├── README.md                         # English guide
├── README.zh-CN.md                   # Simplified Chinese guide
├── SKILL.md                          # Skill metadata and workflow
├── THIRD_PARTY_NOTICES.md             # Adaptation sources and third-party license
├── scripts/                         # fetch_paper.py / extract_figures.py / crop.py
├── requirements.txt                 # PyMuPDF
├── tests/                           # Offline behavioral checks
├── agents/
│   └── openai.yaml                   # Display metadata and default prompt
└── references/
    ├── material-tools.md             # Material preparation and original figures
    ├── ctrl-world-walkthrough.md      # Real-dimension static example
    ├── code-walkthrough.md           # Interactive code walkthrough after user opt-in
    ├── overview-template.md          # Detailed 11-section template
    └── verification.md               # Evidence and reproduction checks
```

The skill instructions and references are currently written in Simplified Chinese. Output language can be specified in the request. When adapting the workflow, keep [SKILL.md](SKILL.md), the [template](references/overview-template.md), the [code walkthrough guide](references/code-walkthrough.md), the [verification guide](references/verification.md), and both README versions consistent.
