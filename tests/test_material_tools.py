"""Offline behavioral tests; no model, dataset, or paper code is executed."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_paper as fetch
import extract_figures as figures


def make_pdf(version=None, columns=1, captions=True):
    doc = fitz.open()
    p = doc.new_page(width=600, height=800)
    p.insert_text((45, 35), "Material tools fixture", fontsize=18)
    if version:
        p.insert_text((45, 55), "arXiv:2510.10125" + version + " [cs.RO]")
    if captions:
        for col in range(columns):
            x = 45 + col * 270
            w = 240 if columns == 2 else 500
            p.draw_rect((x, 90, x + w, 220), color=(0.1, 0.3, 0.8))
            p.insert_text((x + 10, 140), "Camera -> encoder -> output", fontsize=10)
            caption = f"Figure {col + 1}: Pipeline example."
            if columns == 1:
                caption += " Camera observations pass through the encoder to produce the output."
            p.insert_text((x, 238), caption, fontsize=10)
        for y in (340, 365, 390):
            p.draw_line((45, y), (550, y))
        p.insert_text((45, 328), "Table 1: Measured values.", fontsize=10)
        p.insert_text((55, 357), "Method                         Score", fontsize=10)
        p.insert_text((55, 383), "Baseline                        0.5", fontsize=10)
    for y in range(440, 680, 15):
        for col in range(columns):
            body = "Body text explains the experimental protocol."
            if columns == 1:
                body += " We measure output quality and consistency across repeated observations."
            p.insert_text((45 + 270 * col, y), body, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


class MaterialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="paper-overview-test-")
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def invoke(self, *args, meta_version="v3", network=None, source=True):
        def fake_source(aid, dest):
            if not source:
                return "pdf-only"
            dest.mkdir(exist_ok=True)
            (dest / "main.tex").write_text(
                r"\documentclass{article}\begin{document}\section{Method}"
                + r"\begin{figure}\caption{Pipeline example.}\label{fig:one}\end{figure}"
                + r"\end{document}", encoding="utf-8")
            return "single-tex"
        meta = {"arxiv_id": "2510.10125", "version": meta_version, "title": "Fixture"}
        with patch.object(sys, "argv", ["fetch_paper.py", *map(str, args)]), \
             patch.object(fetch, "arxiv_meta", return_value=meta), \
             patch.object(fetch, "hf_paper", return_value={}), \
             patch.object(fetch, "collect_links", return_value={"code": [{"url": "https://example.com/unverified"}]}), \
             patch.object(fetch, "fetch_source", side_effect=fake_source), \
             patch.object(fetch, "http_get", side_effect=network), \
             contextlib.redirect_stdout(io.StringIO()):
            return fetch.main()

    def test_arxiv_version_pin_and_repeat_without_pdf_download(self):
        dest = self.root / "paper"
        calls = []
        def network(urls, **kwargs):
            calls.append(urls)
            self.assertTrue(all("2510.10125v3" in u for u in urls))
            return make_pdf("v3"), urls[0]
        self.assertEqual(self.invoke("2510.10125v3", "--dest", dest, network=network), 0)
        self.assertEqual(len(calls), 1)
        saved = json.loads((dest / "meta.json").read_text())
        self.assertEqual(saved["version"], "v3")
        self.assertIn("v3", saved["source_url"])
        self.assertEqual(saved["pdf_sha256"], hashlib.sha256((dest / "paper.pdf").read_bytes()).hexdigest())
        self.assertEqual(self.invoke(dest, meta_version="v9", network=AssertionError("no network expected")), 0)
        self.assertEqual(json.loads((dest / "meta.json").read_text())["version"], "v3")

    def test_latest_versions_get_separate_directories(self):
        for version in ("v3", "v4"):
            self.invoke("2510.10125", "--root", self.root, meta_version=version,
                        network=lambda urls, **kw: (make_pdf(version), urls[0]))
        self.assertTrue((self.root / "2510.10125v3/paper.pdf").exists())
        self.assertTrue((self.root / "2510.10125v4/paper.pdf").exists())

    def test_wrong_version_is_rejected_before_publishing(self):
        dest = self.root / "paper"
        with self.assertRaisesRegex(ValueError, "watermark"):
            self.invoke("2510.10125v3", "--dest", dest,
                        network=lambda urls, **kw: (make_pdf("v4"), urls[0]))
        self.assertFalse((dest / "paper.pdf").exists())

    def test_local_pdf_without_source_and_no_default_clone(self):
        local = self.root / "input.pdf"
        local.write_bytes(make_pdf("v3"))
        dest = self.root / "paper"
        with patch.object(fetch, "obtain_code") as clone:
            self.assertEqual(self.invoke(local, "--dest", dest, source=False), 0)
            clone.assert_not_called()
        meta = json.loads((dest / "meta.json").read_text())
        self.assertEqual(meta["source_status"], "pdf-only")
        self.assertFalse(meta["has_latex"])
        self.assertNotIn("official_code", meta)
        self.assertTrue((dest / "paper.txt").exists())
        self.assertEqual(self.invoke(dest, "--fetch-code", source=False), 2)

    def test_pdf_url_and_atomic_failure_recovery(self):
        dest = self.root / "paper"
        with self.assertRaises(OSError):
            self.invoke("https://example.com/paper.pdf", "--dest", dest, network=OSError("interrupted"))
        self.assertFalse((dest / "paper.pdf").exists())
        self.invoke("https://example.com/paper.pdf", "--dest", dest,
                    network=lambda url, **kw: (make_pdf(), url))
        original = (dest / "paper.pdf").read_bytes()
        with patch.object(Path, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                fetch.atomic_write(dest / "paper.pdf", b"replacement")
        self.assertEqual((dest / "paper.pdf").read_bytes(), original)
        self.assertFalse(list(dest.glob("*.part")))

    def test_unknown_local_version_does_not_fetch_latest_source(self):
        local = self.root / "2510.10125.pdf"
        local.write_bytes(make_pdf())
        self.invoke(local, "--root", self.root, network=AssertionError("no network"))
        folders = list(self.root.glob("pdf-*"))
        self.assertEqual(len(folders), 1)
        self.assertFalse((folders[0] / "source").exists())

    def test_existing_pdf_is_not_overwritten(self):
        local = self.root / "input.pdf"
        local.write_bytes(make_pdf())
        dest = self.root / "paper"
        self.invoke(local, "--dest", dest)
        before = (dest / "paper.pdf").read_bytes()
        local.write_bytes(make_pdf("v3"))
        with self.assertRaisesRegex(ValueError, "different PDF"):
            self.invoke(local, "--dest", dest)
        self.assertEqual((dest / "paper.pdf").read_bytes(), before)

    def test_source_extraction_and_include_boundaries(self):
        out = self.root / "source"
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w") as archive:
            for name in ("main.tex", "../source-other/escape.tex", "../../escape.tex"):
                info = tarfile.TarInfo(name)
                body = b"safe"
                info.size = len(body)
                archive.addfile(info, io.BytesIO(body))
            link = tarfile.TarInfo("link.tex")
            link.type = tarfile.SYMTYPE
            link.linkname = "../../escape.tex"
            archive.addfile(link)
        fetch.safe_extract(payload.getvalue(), out)
        self.assertTrue((out / "main.tex").exists())
        self.assertFalse((self.root / "source-other").exists())
        self.assertFalse((out / "link.tex").exists())
        outside = self.root / "secret.tex"
        outside.write_text("DO_NOT_READ")
        (out / "part.tex").write_text("INCLUDED")
        (out / "main.tex").write_text(r"\input{part}\input{../secret}")
        flattened = fetch.flatten(out / "main.tex", out)
        self.assertIn("INCLUDED", flattened)
        self.assertNotIn("DO_NOT_READ", flattened)

    def test_failed_source_is_not_published(self):
        def partial(aid, dest):
            (dest / "partial.tex").write_text("incomplete")
            return "failed"
        with patch.object(fetch, "fetch_source", side_effect=partial):
            self.assertEqual(fetch.prepare_source("2510.10125v3", self.root), "failed")
        self.assertFalse((self.root / "source").exists())
        self.assertFalse(list(self.root.glob(".source-*")))

    def test_figure_layouts_and_user_files_survive_repeated_extraction(self):
        for columns in (1, 2):
            folder = self.root / str(columns)
            folder.mkdir()
            (folder / "paper.pdf").write_bytes(make_pdf(columns=columns))
            manual = folder / "figures"
            manual.mkdir()
            (manual / "fig-01.png").write_bytes(b"manual")
            (folder / "figures-auto").mkdir()
            (folder / "figures-auto/notes.txt").write_text("also manual")
            items = figures.extract(folder, dpi=80, quiet=True)
            self.assertTrue(any(i["kind"] == "figure" and i["mode"] == "裁剪" for i in items))
            self.assertTrue(any(i["kind"] == "table" for i in items))
            output = figures.figures_dir(folder)
            self.assertEqual(output.name, "figures-auto-2")
            extra = output / "custom-crop.png"
            extra.write_bytes(b"user crop")
            figures.extract(folder, dpi=80, quiet=True)
            self.assertEqual(extra.read_bytes(), b"user crop")
            self.assertEqual((manual / "fig-01.png").read_bytes(), b"manual")
            self.assertTrue((output / "_contact.png").exists())

    def test_no_caption_full_page_and_manual_crop_cli(self):
        (self.root / "paper.pdf").write_bytes(make_pdf(captions=False))
        items = figures.extract(self.root, dpi=80, quiet=True)
        self.assertEqual(items[0]["mode"], "整页")
        out = self.root / "detail.png"
        subprocess.run([sys.executable, str(ROOT / "scripts/crop.py"), str(self.root / "paper.pdf"),
                        "--page", "1", "0.1", "0.1", "0.9", "0.8", "-o", str(out)], check=True,
                       capture_output=True)
        self.assertGreater(fitz.Pixmap(str(out)).width, 0)

    def test_opt_in_clone_records_actual_commit(self):
        repo = self.root / "upstream"
        repo.mkdir()
        def git(*args):
            return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()
        git("init")
        git("config", "user.email", "fixture@example.invalid")
        git("config", "user.name", "Fixture")
        (repo / "README.md").write_text("read only")
        git("add", "README.md")
        git("commit", "-m", "fixture")
        expected = git("rev-parse", "HEAD")
        local = self.root / "input.pdf"
        local.write_bytes(make_pdf())
        dest = self.root / "paper"
        self.assertEqual(self.invoke(local, "--dest", dest, "--code", repo, "--fetch-code"), 0)
        meta = json.loads((dest / "meta.json").read_text())
        self.assertEqual(meta["code_commit"], expected)
        self.assertEqual(fetch.obtain_code(str(repo), dest / "code", expected), expected)
        with self.assertRaisesRegex(ValueError, "different origin"):
            fetch.obtain_code("https://example.com/other", dest / "code")
        self.assertEqual(self.invoke(dest, "--code", "https://example.com/new-verified-repo"), 0)
        changed = json.loads((dest / "meta.json").read_text())
        self.assertNotIn("code_commit", changed)
        self.assertNotIn("code_dir", changed)


if __name__ == "__main__":
    unittest.main()
