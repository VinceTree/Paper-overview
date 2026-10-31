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

For a project-scoped installation, place the repository at `<project>/.agents/skills/paper-overview` instead. Keep `SKILL.md`, `references/`, and `agents/` together. If the skill does not appear, restart Codex.

These paths follow the [official OpenAI skills documentation](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills). You can also ask the built-in `$skill-installer` to install the skill from this GitHub repository.

### Direct use

If your assistant can read this repository, ask it to read [SKILL.md](SKILL.md) and follow its linked references. Automatic discovery and invocation syntax depend on the host application.

This repository contains instructions and reference documents. It has no application build step or bundled model runtime. Paper retrieval, PDF reading, and web verification use the tools available in your assistant.

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

The two diagrams use Mermaid by default, with text diagrams as a fallback. Their structure follows the research: for example, a theoretical paper can show a proof workflow and proposition dependencies. Inapplicable sections retain their titles and explain why they do not apply.

See the [full explanation template](references/overview-template.md) for section-by-section guidance.

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
├── agents/
│   └── openai.yaml                   # Display metadata and default prompt
└── references/
    ├── overview-template.md          # Detailed 11-section template
    └── verification.md               # Evidence and reproduction checks
```

The skill instructions and references are currently written in Simplified Chinese. Output language can be specified in the request. When adapting the workflow, keep [SKILL.md](SKILL.md), the [template](references/overview-template.md), the [verification guide](references/verification.md), and both README versions consistent.
