#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Adapted from skJack/kelip-paper-reading (925953b15813f18b25eeb1a1dca9790f54a47498).
# Copyright (c) 2026 skJack. MIT; see THIRD_PARTY_NOTICES.md.
"""
Prepare local paper materials without running paper code.

  python fetch_paper.py 2510.10125v3 --root ./papers
  python fetch_paper.py paper.pdf --dest ./papers/local-paper
  python fetch_paper.py ./papers/2510.10125v3
  python fetch_paper.py ./papers/2510.10125v3 --code VERIFIED_URL --fetch-code

PDF, available raw/flattened LaTeX, text, outline, metadata and figure crops are
prepared automatically. Code links are candidates until verified by the caller.
--code records a verified URL; --fetch-code explicitly enables a read-only clone.
Defaults: user --dest/--root, existing related_work/, PAPERS_DIR, then papers/.
Versioned arXiv materials are isolated by ID and version. Unidentified PDFs use
a content hash. Re-running an existing directory keeps its recorded version.
"""
import argparse
import datetime
import gzip
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True  # import extract_figures 时别在 skill 目录里留 __pycache__

UA = "paper-overview/0.2 (academic paper reader)"
NEW_ID = r'\d{4}\.\d{4,5}(?:v\d+)?'
OLD_ID = r'[a-z][a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?'
ARXIV_RE = re.compile(rf'(?<![\d.])({NEW_ID}|{OLD_ID})(?!\d)')
GREEK = {"π": "pi", "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "λ": "lambda",
         "μ": "mu", "σ": "sigma", "τ": "tau", "φ": "phi", "ω": "omega", "θ": "theta", "ρ": "rho"}
STOP = {"a", "an", "the", "of", "for", "and", "to", "in", "on", "with", "via", "from", "by", "is", "are", "towards",
        "toward", "at", "as", "its", "using", "we", "our"}


def log(msg):
    print(msg, flush=True)


# ---------------- 网络 ----------------

def http_get(urls, timeout=30, tries=1):
    """依次试这几个地址，返回 (内容, 最终地址)。全失败就抛最后一个错。"""
    if isinstance(urls, str):
        urls = [urls]
    last = None
    for url in urls:
        for i in range(tries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return r.read(), r.geturl()
            except Exception as e:  # noqa: BLE001 —— 网络错误五花八门，统一重试
                last = e
                time.sleep(1.5 * (i + 1))
    raise last


# ---------------- 输入解析 ----------------

def parse_target(target):
    p = Path(os.path.expanduser(target))
    if p.is_dir():
        return {"kind": "dir", "path": p.resolve()}
    if p.is_file() and p.suffix.lower() == ".pdf":
        m = ARXIV_RE.search(p.name)
        return {"kind": "local-pdf", "path": p.resolve(), "arxiv": m.group(1) if m else None}
    m = ARXIV_RE.search(target)
    if m and ("arxiv" in target.lower() or "huggingface.co/papers" in target or "alphaxiv" in target
              or "papers.cool" in target or re.fullmatch(r'\s*(arXiv:)?' + m.group(1) + r'\s*', target, re.I)):
        return {"kind": "arxiv", "arxiv": m.group(1)}
    if target.startswith(("http://", "https://")):
        return {"kind": "url-pdf", "url": target}
    sys.exit(f"认不出这个输入：{target}（要 arXiv ID / 链接 / PDF 路径 / 已有目录）")


def tidy_title(t):
    """arXiv 标题里会带 LaTeX：'$π_0$: A Vision-...' → 'π0: A Vision-...'"""
    def inline(m):
        x = m.group(1)
        for k, v in {"\\pi": "π", "\\alpha": "α", "\\beta": "β", "\\lambda": "λ", "\\mu": "μ", "\\tau": "τ"}.items():
            x = x.replace(k, v)
        return re.sub(r'[_^{}\\]', '', x)
    return " ".join(re.sub(r'\$([^$]*)\$', inline, t).split())


def slugify(title, fallback):
    if not title:
        return fallback.replace("/", "-")
    t = "".join(GREEK.get(c, c) for c in title)
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    head, _, rest = t.partition(":")
    words = lambda s: [w for w in re.split(r'[^A-Za-z0-9]+', s.lower()) if w and w not in STOP]
    if rest and len(head.split()) <= 3:  # "π0: A Vision-Language-Action ..." → 方法名在冒号前
        name = []
        for w in words(head):
            if w.isdigit() and name:
                name[-1] += w
            else:
                name.append(w)
        parts = ["-".join(name)] + words(rest)[:3]
    else:
        parts = words(t)[:5]
    slug = "-".join(p for p in parts if p)[:60].strip("-")
    return slug or fallback.replace("/", "-")


def pick_dest(args, slug):
    if args.dest:
        return Path(os.path.expanduser(args.dest)).resolve()
    if args.root:
        return (Path(os.path.expanduser(args.root)) / slug).resolve()
    if Path("related_work").is_dir():
        return (Path("related_work") / slug).resolve()
    if os.environ.get("PAPERS_DIR"):
        return (Path(os.path.expanduser(os.environ["PAPERS_DIR"])) / slug).resolve()
    return (Path("papers") / slug).resolve()


# ---------------- arXiv：元数据、PDF、源码 ----------------

def arxiv_meta(aid):
    try:
        xml, _ = http_get([f"https://export.arxiv.org/api/query?id_list={aid}",
                           f"http://export.arxiv.org/api/query?id_list={aid}"], timeout=8)
    except Exception as e:  # noqa: BLE001
        log(f"  ⚠ arXiv API 没连上（{e}），元数据从 PDF 里凑")
        return {}
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    try:
        e = ET.fromstring(xml).find("a:entry", ns)
    except ET.ParseError:
        return {}
    if e is None:
        return {}
    txt = lambda tag: " ".join((e.findtext(tag, default="", namespaces=ns) or "").split())
    idurl = txt("a:id")
    if "arxiv.org/abs/" not in idurl:
        return {}
    ver = re.search(r'v(\d+)$', idurl)
    return {
        "arxiv_id": aid.split("v")[0] if re.match(NEW_ID, aid) else re.sub(r'v\d+$', '', aid),
        "version": f"v{ver.group(1)}" if ver else "",
        "title": tidy_title(txt("a:title")),
        "authors": [" ".join(a.findtext("a:name", default="", namespaces=ns).split()) for a in e.findall("a:author", ns)],
        "published": txt("a:published")[:10],
        "updated": txt("a:updated")[:10],
        "abstract": txt("a:summary"),
        "comment": txt("x:comment"),
        "journal_ref": txt("x:journal_ref"),
        "categories": [c.get("term") for c in e.findall("a:category", ns)],
        "abs_url": f"https://arxiv.org/abs/{aid}",
    }


def hf_paper(aid):
    """Hugging Face Papers 收录了作者认领的代码仓库和项目页；连不上就算了。"""
    try:
        raw, _ = http_get(f"https://huggingface.co/api/papers/{aid.split('v')[0]}", timeout=12, tries=1)
        d = json.loads(raw)
        return {"github": d.get("githubRepo") or "", "project": d.get("projectPage") or ""}
    except Exception:  # noqa: BLE001
        return {}


def safe_extract(raw, dest):
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as tf:
        for m in tf.getmembers():
            target = (dest / m.name).resolve()
            if m.issym() or m.islnk() or m.isdev() or not target.is_relative_to(root):
                continue  # 符号链接、设备文件、../ 越界：一律不解
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif m.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with tf.extractfile(m) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)


def fetch_source(aid, src_dir):
    """返回 'tar' / 'single-tex' / 'pdf-only' / 'failed'。"""
    try:
        data, _ = http_get([f"https://arxiv.org/e-print/{aid}", f"https://export.arxiv.org/e-print/{aid}"], timeout=20)
    except Exception as e:  # noqa: BLE001
        log(f"  ⚠ 源码没下下来（{e}）")
        return "failed"
    if data[:4] == b"%PDF":
        return "pdf-only"
    raw = data
    if data[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(data)
        except OSError:
            pass
    try:
        safe_extract(raw, src_dir)
        if any(src_dir.rglob("*.tex")):
            return "tar"
    except tarfile.TarError:
        pass
    if raw[:4] == b"%PDF":
        return "pdf-only"
    text = raw.decode("utf-8", errors="replace")
    if "\\documentclass" in text or "\\begin{document}" in text:
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "main.tex").write_text(text, encoding="utf-8")
        return "single-tex"
    return "failed"


def arxiv_id_from_pdf(pdf):
    """arXiv 生成的 PDF 第一页左边有竖排的 'arXiv:2410.24164v4 [cs.LG] ...' 水印。"""
    try:
        import pymupdf as fitz
        with fitz.open(str(pdf)) as d:
            m = re.search(r'arXiv:\s*(' + NEW_ID + ')', d[0].get_text())
            return m.group(1) if m else None
    except Exception:  # noqa: BLE001
        return None


def title_from_pdf(pdf):
    """非 arXiv 的 PDF：先看文档属性里的标题，不像标题就取第一页上半部分字号最大的那几行。"""
    try:
        import pymupdf as fitz
        with fitz.open(str(pdf)) as d:
            t = (d.metadata or {}).get("title") or ""
            if len(t) > 12 and not re.search(r'untitled|microsoft word|\.pdf$|\.dvi$|^p\d+$', t, re.I):
                return " ".join(t.split())
            page = d[0]
            spans = []
            for b in page.get_text("dict")["blocks"]:
                for l in b.get("lines", []):
                    for sp in l["spans"]:
                        if sp["text"].strip() and sp["bbox"][1] < 0.45 * page.rect.height:
                            spans.append((round(sp["size"], 1), sp["bbox"][1], sp["text"].strip()))
            if not spans:
                return ""
            big = max(x[0] for x in spans)
            words = [x[2] for x in sorted(spans, key=lambda x: x[1]) if x[0] >= big - 0.5]
            return " ".join(" ".join(words).split())[:200]
    except Exception:  # noqa: BLE001
        return ""


# ---------------- LaTeX：拍平、宏、大纲 ----------------

VERB_ENVS = r'verbatim|Verbatim|lstlisting|minted|alltt'


def strip_comments(text):
    text = re.sub(r'\\begin\{comment\}.*?\\end\{comment\}', '', text, flags=re.S)
    out, verb = [], False
    for line in text.split("\n"):
        if re.search(r'\\begin\{(' + VERB_ENVS + r')\}', line):
            verb = True
        if verb:
            out.append(line)
            if re.search(r'\\end\{(' + VERB_ENVS + r')\}', line):
                verb = False
            continue
        if re.match(r'\s*%', line):  # 整行注释直接丢，不留空行
            continue
        out.append(re.sub(r'(?<!\\)%.*$', '', line))
    return "\n".join(out)


def drop_iffalse(text):
    """去掉 \\iffalse ... \\fi 包起来的废稿（会数嵌套的 \\ifxxx）。"""
    out, i = [], 0
    for m in re.finditer(r'\\iffalse\b', text):
        if m.start() < i:
            continue
        depth, j = 1, m.end()
        for t in re.finditer(r'\\(if(?!thenelse)[a-zA-Z@]*|fi)\b', text[m.end():]):
            depth += 1 if t.group(1) != "fi" else -1
            if depth == 0:
                j = m.end() + t.end()
                break
        else:
            continue
        out.append(text[i:m.start()])
        i = j
    out.append(text[i:])
    return "".join(out)


INPUT_RE = re.compile(r'\\(?:input|include|subfile)\s*\{([^}]+)\}|\\(?:sub)?import\s*\{([^}]*)\}\s*\{([^}]+)\}'
                      r'|\\input\s+([^\s{}\\]+)')


def flatten(path, root, seen=None, depth=0):
    path, root = path.resolve(), root.resolve()
    if not path.is_relative_to(root):
        return "% [skipped: source include outside source directory]"
    seen = seen or set()
    if depth > 12 or path in seen:
        return ""
    seen.add(path)
    text = drop_iffalse(strip_comments(path.read_text(encoding="utf-8", errors="ignore")))

    def repl(m):
        if m.group(1):
            name, base = m.group(1).strip(), path.parent
        elif m.group(3):
            name, base = m.group(3).strip(), (path.parent / m.group(2).strip())
        else:
            name, base = m.group(4).strip(), path.parent
        for cand in (base / name, root / name, base / (name + ".tex"), root / (name + ".tex")):
            if cand.resolve().is_relative_to(root) and cand.is_file() and cand.suffix in (".tex", ".bbl", ".tikz", ".pgf", ""):
                if cand.suffix in (".tikz", ".pgf"):
                    return f"% [图：{cand.relative_to(root)}]"
                return flatten(cand.resolve(), root, seen, depth + 1)
        return "% [unresolved or out-of-root include] " + m.group(0)

    return INPUT_RE.sub(repl, text)


def find_main_tex(src):
    src = src.resolve()
    readme = src / "00README.json"
    if readme.exists():
        try:
            for s in json.loads(readme.read_text()).get("sources", []):
                if s.get("usage") == "toplevel" and (src / s["filename"]).resolve().is_relative_to(src) and (src / s["filename"]).exists():
                    return src / s["filename"]
        except (ValueError, KeyError):
            pass
    cands = []
    for p in src.rglob("*.tex"):
        if not p.resolve().is_relative_to(src):
            continue
        if ".stale" in p.parts:
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(r'^\s*\\documentclass', txt, re.M):
            score = (10 if "\\begin{document}" in txt else 0) \
                + (3 if p.stem.lower() in ("main", "paper", "ms", "arxiv", "manuscript", "root") else 0) \
                + (2 if p.parent == src else 0) + min(len(txt) / 20000, 3)
            cands.append((score, str(p)))
    return Path(max(cands)[1]) if cands else None


DEF_RE = re.compile(r'\\(?:(?:re)?newcommand|providecommand|DeclareRobustCommand|DeclareMathOperator)\*?|\\def\s*(?=\\)')


def macro_defs(text):
    """正文前面定义的宏：返回 [(名字, 完整定义)]。"""
    from extract_figures import read_group
    out = []
    for m in DEF_RE.finditer(text):
        i = m.end()
        while i < len(text) and text[i] in " \t\n":
            i += 1
        if i >= len(text):
            break
        if text[i] == "{":
            j, name = read_group(text, i)
            name = name.strip()
        elif text[i] == "\\":
            nm = re.match(r'\\[A-Za-z@]+|\\.', text[i:])
            name, j = nm.group(0), i + nm.end()
        else:
            continue
        if not name.startswith("\\"):
            continue
        k = j
        if m.group(0).startswith("\\def"):
            pm = re.match(r'[^{]*', text[k:])
            k += pm.end()
        else:
            for _ in range(2):  # [参数个数][默认值]
                ws = re.match(r'\s*\[[^\]]*\]', text[k:])
                if ws:
                    k += ws.end()
        ws = re.match(r'\s*', text[k:])
        k += ws.end()
        if k < len(text) and text[k] == "{":
            end, _ = read_group(text, k)
            out.append((name, " ".join(text[m.start():end].split())))
    return out


def strip_bib(body):
    body = re.sub(r'\\begin\{thebibliography\}.*?\\end\{thebibliography\}', '', body, flags=re.S)
    body = re.sub(r'\\(?:bibliography|bibliographystyle|addbibresource)\s*\{[^}]*\}', '', body)
    return re.sub(r'\\printbibliography(\[[^\]]*\])?', '', body)


def build_tex(dest):
    src = dest / "source"
    main = find_main_tex(src) if src.is_dir() else None
    if not main:
        return None
    full = flatten(main.resolve(), src.resolve())
    b = full.find("\\begin{document}")
    e = full.rfind("\\end{document}")
    pre, body = (full[:b], full[b + len("\\begin{document}"):e if e > b else None]) if b >= 0 else ("", full)
    body = strip_bib(body)
    body = re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', body).strip("\n")
    used = []
    seen = set()
    for name, d in macro_defs(pre):
        if name in seen:
            continue
        if re.search(re.escape(name) + r'(?![A-Za-z@])', body):
            seen.add(name)
            used.append(d)
    head = [f"% paper.tex —— 由 source/{main.relative_to(src)} 拍平：\\input 已展开，注释、废稿（\\iffalse）、参考文献已去掉。",
            "% 读正文就读这个文件；行号和 outline.md 对得上。",
            f"% ==== 正文用到的自定义宏（{len(used)} 个；看不懂的记号先查这里）===="]
    head += used
    head += ["% ==== 正文 ===="]
    (dest / "paper.tex").write_text("\n".join(head) + "\n" + body + "\n", encoding="utf-8")
    return {"main": str(main.relative_to(dest)), "macros": len(used),
            "lines": len(head) + body.count("\n") + 1}


EQ_ENVS = r'equation|align|gather|multline|eqnarray|flalign'


def build_outline(dest, meta):
    import extract_figures as ef  # noqa: F811
    L = [f"# 大纲 · {meta.get('title', '')}", ""]
    tex = dest / "paper.tex"
    if tex.exists():
        lines = tex.read_text(encoding="utf-8").split("\n")
        secs = ef.latex_sections(lines)
        levels = {}
        for i, line in enumerate(lines, 1):
            mm = re.search(r'\\(section|subsection|subsubsection)\*?\s*[\[{]', line)
            if mm:
                levels[i] = ["section", "subsection", "subsubsection"].index(mm.group(1))
        n = len(lines)
        L.append("行号指 `paper.tex`。读某一节：`sed -n '起,止p' paper.tex`（或用 Read 的 offset/limit）。")
        L.append("")
        abs_line = next((i for i, l in enumerate(lines, 1) if "\\begin{abstract}" in l), None)
        if abs_line:
            L.append(f"- L{abs_line} 摘要")
        app_line = next((i for i, l in enumerate(lines, 1) if re.match(r'\s*\\appendix\b', l)), None)
        for k, (i, num, title) in enumerate(secs):
            lvl = levels.get(i, 0)
            end = n
            for j, _, _ in secs[k + 1:]:
                if levels.get(j, 0) <= lvl:
                    end = j - 1
                    break
            if app_line and i > app_line and (k == 0 or secs[k - 1][0] < app_line):
                L.append(f"- L{app_line} —— 附录 ——")
            shown = title or ("（无标题，多半是附录开头）" if app_line and i > app_line else "（无标题）")
            L.append(f"{'  ' * lvl}- L{i}–{end} {(num + ' ') if num else ''}{shown}")
        # 公式：训练那一站找 loss 用
        eqs = []
        for m in re.finditer(r'\\begin\{(' + EQ_ENVS + r')(\*?)\}(.*?)\\end\{\1\2\}', "\n".join(lines), re.S):
            ln = "\n".join(lines).count("\n", 0, m.start()) + 1
            content = m.group(3)
            labels = re.findall(r'\\label\{([^}]+)\}', content)
            content = " ".join(re.sub(r'\\label\{[^}]+\}', '', content).split())
            eqs.append((ln, labels, content))
        for m in re.finditer(r'(?m)^\s*\\\[(.*?)\\\]', "\n".join(lines), re.S):
            ln = "\n".join(lines).count("\n", 0, m.start()) + 1
            eqs.append((ln, [], " ".join(m.group(1).split())))
        eqs.sort()
        if eqs:
            L += ["", f"## 公式（{len(eqs)} 个，按出现顺序；L 后面是所在小节）", ""]
            for ln, labels, content in eqs:
                lab = f" `{', '.join(labels)}`" if labels else ""
                prev = content[:110] + ("…" if len(content) > 110 else "")
                L.append(f"- L{ln} {ef.section_of(secs, ln)}{lab}：{prev}")
        L += ["", f"图表的页码、caption、在哪节被引用：见 `{ef.figures_dir(dest).name}/index.md`。"]
    else:
        L.append("没有 LaTeX 源码：正文读 `paper.txt`（按页分好了），公式只能看 PDF 渲染（`crop.py paper.pdf --page N`）。")
        L.append("")
        try:
            import pymupdf as fitz
            with fitz.open(str(dest / "paper.pdf")) as d:
                toc = d.get_toc()
            for lvl, title, page in toc:
                L.append(f"{'  ' * (lvl - 1)}- 第 {page} 页 · {title}")
            if not toc:
                L.append("（PDF 没有书签。用 `grep -n` 在 paper.txt 里找 Introduction / Method / Experiments 这类标题。）")
        except Exception:  # noqa: BLE001
            pass
        L += ["", f"图表的页码和 caption：见 `{ef.figures_dir(dest).name}/index.md`。"]
    (dest / "outline.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def build_txt(dest):
    try:
        import pymupdf as fitz
    except ImportError:
        if shutil.which("pdftotext"):
            subprocess.run(["pdftotext", "-layout", str(dest / "paper.pdf"), str(dest / "paper.txt")], check=False)
        return None
    from extract_figures import clean
    parts = []
    with fitz.open(str(dest / "paper.pdf")) as d:
        n = len(d)
        for i, page in enumerate(d, 1):
            text = "\n".join(l for l in clean(page.get_text()).split("\n")
                             if not l.strip() or l.count("\ufffd") < 0.3 * len(l.strip()))  # 图里字体抽出来的乱码行
            parts.append(f"\n===== 第 {i} 页 =====\n" + text)
    (dest / "paper.txt").write_text("".join(parts), encoding="utf-8")
    return n


# ---------------- 代码 / 项目页链接 ----------------

URL_RE = re.compile(r'https?://[^\s<>"\'{}|\\^`\[\]]+')
SKIP_OWNERS = {"sponsors", "features", "orgs", "topics", "settings", "marketplace", "about", "login"}


def norm_url(u):
    u = u.rstrip(".,;:)]}>'\"")
    u = re.sub(r'#.*$', '', u)
    return u.rstrip("/")


def classify(u):
    m = re.search(r'github\.com/([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+)', u)
    if m:
        owner, repo = m.group(1), re.sub(r'\.git$', '', m.group(2))
        if owner.lower() in SKIP_OWNERS or repo.lower().endswith(".github.io"):
            return None, None  # 项目页模板（nerfies.github.io 之类）的致谢链接
        return "code", f"https://github.com/{owner}/{repo}"
    if re.search(r'huggingface\.co/(?!papers)', u):
        return "hf", u
    if ".github.io" in u or "sites.google.com" in u or re.search(r'project|page|website', u, re.I):
        return "project", u
    return "other", u


def collect_links(dest, meta, hf):
    score = defaultdict(lambda: {"score": 0, "from": []})

    def add(u, w, src, hint=""):
        if not u.startswith(("http://", "https://")):
            u = "https://" + u
        kind, url = classify(norm_url(u))
        if kind == "other" and re.search(r'project|website|videos|homepage', hint, re.I):
            kind = "project"
        if not kind or re.search(r'arxiv\.org|doi\.org|creativecommons', url or ""):
            return
        if kind == "other" and src in ("arXiv 备注", "摘要", "HF Papers"):
            kind = "project"
        s = score[(kind, url)]
        s["score"] += w
        if src not in s["from"]:
            s["from"].append(src)

    for u in URL_RE.findall(meta.get("comment", "")):
        add(u, 5, "arXiv 备注")
    for u in URL_RE.findall(meta.get("abstract", "")):
        add(u, 5, "摘要")
    if hf.get("github"):
        add(hf["github"], 6, "HF Papers")
    if hf.get("project"):
        add(hf["project"], 4, "HF Papers")
    try:
        import pymupdf as fitz
        with fitz.open(str(dest / "paper.pdf")) as d:
            for pno, page in enumerate(d):
                first = pno < 2
                for ln in page.get_links():
                    if ln.get("uri"):
                        add(ln["uri"], 4 if first else 0.5, "首页链接" if first else "正文链接")
                if first:
                    for u in URL_RE.findall(page.get_text()):
                        add(u, 3, "首页文字")
    except Exception:  # noqa: BLE001
        pass
    tex = dest / "paper.tex"
    if tex.exists():
        for line in tex.read_text(encoding="utf-8", errors="ignore").split("\n"):
            if re.search(r'code|github|release|available|project|website|open[- ]?source', line, re.I):
                for u in set(re.findall(r'\\(?:url|href)\{([^}]+)\}', line) + URL_RE.findall(line)):
                    add(u, 2, "正文提到", hint=line)
    out = defaultdict(list)
    merged = {}
    for (kind, url), s in score.items():  # 同一个地址先后被归成 other / project 时合并到 project
        key = url
        if key in merged and merged[key][0] == "project":
            merged[key][1]["score"] += s["score"]
            continue
        if key in merged and kind == "project":
            s["score"] += merged[key][1]["score"]
        merged[key] = (kind, s)
    for url, (kind, s) in sorted(merged.items(), key=lambda kv: -kv[1][1]["score"]):
        if kind == "other" and s["score"] < 2:  # 正文里顺手提到的商品 / 数据集网页，不是这篇的东西
            continue
        out[kind].append({"url": url, "score": round(s["score"], 1), "from": s["from"]})
    return dict(out)


def code_from_project_page(url):
    try:
        raw, _ = http_get(url, timeout=15, tries=1)
    except Exception:  # noqa: BLE001
        return None
    cnt = defaultdict(int)
    for u in URL_RE.findall(raw.decode("utf-8", errors="ignore")):
        kind, norm = classify(norm_url(u))
        if kind == "code":
            cnt[norm] += 1
    return max(cnt, key=cnt.get) if cnt else None


# ---------------- 主流程 ----------------

def atomic_write(path, data):
    """Publish complete bytes; an interrupted request never becomes a cached file."""
    import tempfile
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".download-", suffix=".part", delete=False) as f:
            tmp = Path(f.name)
            f.write(data)
        tmp.replace(path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def pdf_identity(data):
    import pymupdf as fitz
    if not data.startswith(b"%PDF"):
        raise ValueError("Downloaded material is not a PDF")
    with fitz.open(stream=data, filetype="pdf") as doc:
        if not len(doc):
            raise ValueError("Empty PDF")
        m = re.search(r'arXiv:\s*(' + NEW_ID + '|' + OLD_ID + ')', doc[0].get_text())
        return m.group(1) if m else None


def split_version(aid):
    if not aid:
        return None, ""
    m = re.search(r'v[0-9]+$', aid)
    return (aid[:m.start()], m.group(0)) if m else (aid, "")


def prepare_source(aid, dest):
    """Only publish a complete source directory; never mix versions or partial trees."""
    import tempfile
    src = dest / "source"
    if src.exists():
        return "cached" if any(src.rglob("*.tex")) else "existing-unusable"
    staging = Path(tempfile.mkdtemp(prefix=".source-", dir=dest)).resolve()
    try:
        result = fetch_source(aid, staging)
        if result in ("tar", "single-tex"):
            staging.rename(src)
        return result
    finally:
        if staging.exists() and staging.is_relative_to(dest.resolve()):
            shutil.rmtree(staging)


def canonical_repo(url):
    return url.rstrip("/").removesuffix(".git").lower()


def obtain_code(url, code_dir, ref=None):
    """Fetch only a caller-verified repository, without executing its files."""
    import tempfile
    if ref and ref.startswith("-"):
        raise ValueError("Code reference cannot start with '-'")
    if not shutil.which("git"):
        raise ValueError("Git is required for --fetch-code")
    code_dir = code_dir.resolve()
    if code_dir.exists() and any(code_dir.iterdir()):
        origin = subprocess.run(["git", "-C", str(code_dir), "config", "--get", "remote.origin.url"],
                                capture_output=True, text=True, check=True).stdout.strip()
        if canonical_repo(origin) != canonical_repo(url):
            raise ValueError("Existing code directory has a different origin; use --code-dir")
        commit = subprocess.run(["git", "-C", str(code_dir), "rev-parse", "HEAD"],
                                capture_output=True, text=True, check=True).stdout.strip()
        if ref:
            expected = subprocess.run(["git", "-C", str(code_dir), "rev-parse", ref + "^{commit}"],
                                      capture_output=True, text=True, check=True).stdout.strip()
            if expected != commit:
                raise ValueError("Existing checkout differs from --code-ref; use a new --code-dir")
        return commit
    code_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".code-", dir=code_dir.parent)).resolve()
    env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1", GIT_TERMINAL_PROMPT="0")
    try:
        subprocess.run(["git", "clone", "--depth", "1", "--single-branch", "--", url, str(staging)],
                       env=env, capture_output=True, text=True, timeout=300, check=True)
        if ref:
            subprocess.run(["git", "-C", str(staging), "fetch", "--depth", "1", "origin", ref],
                           env=env, capture_output=True, text=True, timeout=300, check=True)
            subprocess.run(["git", "-C", str(staging), "checkout", "--detach", "FETCH_HEAD"],
                           env=env, capture_output=True, text=True, check=True)
        commit = subprocess.run(["git", "-C", str(staging), "rev-parse", "HEAD"],
                                capture_output=True, text=True, check=True).stdout.strip()
        if code_dir.exists():
            code_dir.rmdir()  # only an empty destination is eligible
        staging.rename(code_dir)
        return commit
    finally:
        if staging.exists() and staging.is_relative_to(code_dir.parent):
            shutil.rmtree(staging)


def main():
    import hashlib
    ap = argparse.ArgumentParser(description="Prepare version-bound paper materials; code is opt-in")
    ap.add_argument("target", help="arXiv ID/link, PDF URL/path, or existing material directory")
    ap.add_argument("--dest", help="Exact material directory")
    ap.add_argument("--root", help="Parent directory; defaults to related_work/ if present, otherwise papers/")
    ap.add_argument("--slug", help="Optional directory label; arXiv version is still appended")
    ap.add_argument("--code", help="Repository URL whose official ownership has been verified by the caller")
    ap.add_argument("--code-dir", help="Code destination (default: material directory/code)")
    ap.add_argument("--code-ref", help="Branch, tag, or commit to fetch when cloning code")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--fetch-code", action="store_true", help="Clone verified --code or previously verified official_code")
    group.add_argument("--no-clone", action="store_true", help="Compatibility alias for the default: never clone")
    ap.add_argument("--dpi", type=int, default=220)
    args = ap.parse_args()
    if args.dpi <= 0:
        ap.error("--dpi must be positive")
    if args.code_ref and not args.fetch_code:
        ap.error("--code-ref requires --fetch-code")
    try:
        import pymupdf as fitz  # noqa: F401
    except ImportError:
        ap.error("PyMuPDF is missing. Use an available PDF reader or install requirements.txt in a dedicated environment.")
    t = parse_target(args.target)
    log(f"Resolving paper materials: {args.target}")
    meta, dest, data, pdf_url = {}, None, None, None
    aid = t.get("arxiv")
    if t["kind"] == "dir":
        dest = t["path"]
        manifest = dest / "meta.json"
        meta = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
        data = (dest / "paper.pdf").read_bytes()
        actual = pdf_identity(data)
        base, version = split_version(actual or meta.get("arxiv_id"))
        version = version or meta.get("version", "")
        aid = base + version if base and version else None
        if actual and meta.get("arxiv_id"):
            saved = meta["arxiv_id"] + meta.get("version", "")
            if actual != saved:
                raise ValueError("Cached PDF disagrees with meta.json; use a separate directory")
    elif t["kind"] == "local-pdf":
        data = t["path"].read_bytes()
        aid = pdf_identity(data) or aid
    elif t["kind"] == "url-pdf":
        if args.dest and (Path(args.dest).expanduser() / "meta.json").exists():
            candidate = Path(args.dest).expanduser()
            saved = json.loads((candidate / "meta.json").read_text(encoding="utf-8"))
            if saved.get("input_target") == args.target and (candidate / "paper.pdf").exists():
                meta, data = saved, (candidate / "paper.pdf").read_bytes()
        if data is None:
            data, pdf_url = http_get(t["url"], timeout=180)
        aid = pdf_identity(data)
    if aid and not meta and (data is None or split_version(aid)[1]):
        meta = arxiv_meta(aid)
    base, requested_version = split_version(aid)
    version = requested_version or meta.get("version", "")
    pinned = base + version if base and version else None
    if pinned:
        meta.update(arxiv_id=base, version=version, abs_url=f"https://arxiv.org/abs/{pinned}")
    if t["kind"] == "arxiv":
        log(f"Preparing PDF: {pinned or aid}")
        directory_label = (args.slug + "-" if args.slug else "") + (pinned or aid).replace("/", "-")
        # If the API is unavailable for a versionless input, inspect the PDF watermark before caching it.
        if pinned:
            dest = pick_dest(args, directory_label)
            pdf = dest / "paper.pdf"
            if pdf.exists():
                data = pdf.read_bytes()
        if data is None:
            data, pdf_url = http_get([f"https://arxiv.org/pdf/{pinned or aid}",
                                      f"https://export.arxiv.org/pdf/{pinned or aid}"], timeout=45)
        actual = pdf_identity(data)
        if actual and pinned and actual != pinned:
            raise ValueError("PDF watermark does not match requested arXiv version")
        if actual:
            base, version = split_version(actual)
            pinned = base + version if version else None
            meta.update(arxiv_id=base, version=version)
        if pinned:
            dest = pick_dest(args, (args.slug + "-" if args.slug else "") + pinned.replace("/", "-"))
    digest = hashlib.sha256(data).hexdigest()
    if dest is None:
        label = (pinned or "pdf-" + digest[:16]).replace("/", "-")
        dest = pick_dest(args, (args.slug + "-" if args.slug else "") + label)
    existing_pdf = dest / "paper.pdf"
    if existing_pdf.exists() and hashlib.sha256(existing_pdf.read_bytes()).hexdigest() != digest:
        raise ValueError("Destination contains a different PDF; choose another --dest")
    prior_path = dest / "meta.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8")) if prior_path.exists() else {}
    if prior.get("pdf_sha256") and prior["pdf_sha256"] != digest:
        raise ValueError("Cached PDF checksum disagrees with metadata")
    if prior.get("version") and version and prior["version"] != version:
        raise ValueError("Destination belongs to another paper version")
    # Reuse the manifest belonging to this exact PDF, rather than refreshing its version remotely.
    if prior:
        meta = {**meta, **prior}
    dest.mkdir(parents=True, exist_ok=True)
    if not existing_pdf.exists():
        atomic_write(existing_pdf, data)
    if not meta.get("title"):
        meta["title"] = title_from_pdf(existing_pdf)
    meta.update(input_target=meta.get("input_target", args.target), pdf_sha256=digest,
                pdf_url=meta.get("pdf_url") or pdf_url or (f"https://arxiv.org/pdf/{pinned}" if pinned else None),
                pdf_pages=build_txt(dest), fetched=meta.get("fetched", datetime.date.today().isoformat()))
    source_status = meta.get("source_status", "unavailable")
    if pinned:
        log(f"Preparing source for the same version: {pinned}")
        source_status = prepare_source(pinned, dest)
        meta["source_url"] = f"https://arxiv.org/e-print/{pinned}"
    tex_info = build_tex(dest) if (dest / "source").is_dir() else None
    meta.update(source_status=source_status, has_latex=bool(tex_info),
                main_tex=tex_info["main"] if tex_info else None)
    build_outline(dest, meta)
    links = collect_links(dest, meta, hf_paper(base) if base else {})
    candidates = list(links.get("code", []))
    if not candidates:
        for project in links.get("project", [])[:2]:
            found = code_from_project_page(project["url"])
            if found:
                candidates.append({"url": found, "from": [project["url"]], "verified": False})
    meta.update(links=links, code_candidates=candidates)
    if args.code:
        if canonical_repo(meta.get("official_code", "")) != canonical_repo(args.code):
            for key in ("code_dir", "code_commit", "code_fetched"):
                meta.pop(key, None)
        meta.update(official_code=args.code.rstrip("/").removesuffix(".git"),
                    official_code_from="caller-verified --code", code_verified=True)
    code_error = None
    if args.fetch_code:
        official = meta.get("official_code")
        if not official or not meta.get("code_verified"):
            code_error = "No verified repository: inspect code_candidates, then pass --code URL --fetch-code"
        else:
            code_dir = Path(args.code_dir).expanduser().resolve() if args.code_dir else dest / "code"
            try:
                commit = obtain_code(official, code_dir, args.code_ref)
                meta.update(code_dir=str(code_dir.resolve()), code_commit=commit,
                            code_fetched=datetime.date.today().isoformat())
            except (OSError, ValueError, subprocess.SubprocessError) as e:
                code_error = str(e)
    atomic_write(dest / "meta.json", (json.dumps(meta, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    import extract_figures
    items = extract_figures.extract(dest, dpi=args.dpi, quiet=True)
    log(f"Materials: {dest}")
    log(f"Paper version: {pinned or 'unavailable; PDF identified by SHA-256'}; source: {source_status}")
    log(f"Figures/tables: {len(items)}; inspect {extract_figures.figures_dir(dest) / '_contact.png'}")
    log("Code candidates are unverified. Default: no code fetched.")
    if code_error:
        log("Code not fetched: " + code_error)
        return 2
    if args.fetch_code:
        log(f"Verified code: {meta['code_dir']} @ {meta['code_commit']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        sys.exit(f"Material preparation failed: {error}. Use available web/PDF sources to continue reading.")
