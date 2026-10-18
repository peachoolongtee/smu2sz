#!/usr/bin/env python3
"""Fill the official FinTechathon 2026 .docx templates from our markdown deliverables.

Usage (from the repo root):
  uv run --project services/api python scripts/build_deliverables.py
  uv run --project services/api python scripts/build_deliverables.py --refresh-evidence
  uv run --project services/api python scripts/build_deliverables.py --repo-url https://github.com/<org>/<repo>/blob/<ref>

What it does:
  1. With --refresh-evidence, rewrites the generated blocks in docs/deliverables/execution_evidence.md
     (between <!-- BEGIN:name --> and <!-- END:name --> markers) from services/api/evals/e2e/latest/.
     Nothing else in the markdown is touched.
  2. Fills three official templates (docs/research/templates/international-*-en.docx):
       technical_document.md          -> out/Technical_Document.docx
       execution_evidence.md          -> out/Execution_Evidence.docx
       docs/SECURITY_SELF_ASSESSMENT.md -> out/Security_Self_Assessment.docx
     Each "## NN Heading" in the markdown must match a template heading, and each "### Prompt" a template
     prompt; the text under a prompt replaces that prompt's "Write here" placeholder. The template's title,
     header table, headings, prompts and footer are kept. The header table gets [TEAM: ...] placeholders.
  3. Verifies every output: it reopens the file, checks that every template heading and prompt is present
     and followed by content, and that no "Write here" or "Please complete" placeholder is left.
     Exits 1 on any failure.

Markdown supported: paragraphs, **bold**, *italic*, `code`, [links](url), bullet and numbered lists
(nested by two-space indent), pipe tables, fenced code blocks, #### sub-headings, "> " quotes and
<!-- figure: file.png | caption --> (embedded when the file exists; end with " | page" to put a tall
diagram on a page of its own at 6.2 in wide). A code block right after
<!-- ascii-fallback --> is dropped when the preceding figure was embedded.
"""

from __future__ import annotations

import argparse

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.image.image import Image as DocxImage
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.shared import Inches, Pt
from docx.text.paragraph import Paragraph

ROOT = Path(__file__).resolve().parents[1]
DELIV = ROOT / "docs" / "deliverables"
OUT = DELIV / "out"
TEMPLATES = ROOT / "docs" / "research" / "templates"
E2E = ROOT / "services" / "api" / "evals" / "e2e" / "latest"
E2E_REL = "services/api/evals/e2e/latest"

HEADER = {
    "Team name": "ISMOGGER",
    "Competition track": "International AI Track — Topic E: SME Finance Copilot",
    "Submission date": "20 October 2026",
}
BODY_PT = Pt(10)
MAX_FIG_HEIGHT_IN = 4.8
PAGE_FIG_HEIGHT_IN = 8.9  # "| page" figures: the tallest a figure may be with its caption on a Letter page

JOBS = [
    ("technical_document.md", "international-technical-document-en.docx", "Technical_Document.docx"),
    ("execution_evidence.md", "international-execution-evidence-en.docx", "Execution_Evidence.docx"),
    ("../SECURITY_SELF_ASSESSMENT.md", "international-security-self-assessment-en.docx", "Security_Self_Assessment.docx"),
]

CODE_FONT = "Courier New"  # present on Windows and macOS
# Chinese text needs an East Asian font named on every style, or a reader without a fallback drops the characters.
CJK_FONT = "Microsoft YaHei"
PLACEHOLDERS = ("Write here", "Please complete")
TITLES = {
    "Technical_Document.docx": "Technical Document",
    "Execution_Evidence.docx": "Execution Evidence",
    "Security_Self_Assessment.docx": "Security Self-Assessment",
}


# ------------------------------------------------------------------ evidence tables (from the e2e run)


def yuan(fen: int) -> str:
    sign = "-" if fen < 0 else ""
    fen = abs(fen)
    return f"{sign}¥{fen // 100:,}.{fen % 100:02d}"


def _cell(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ").strip()


def _short(s: str, n: int = 110) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def read_segments(latest: Path) -> list[dict]:
    """Split evidence.jsonl into per-task segments: task, run, operations, security events, chain."""
    segs: list[dict] = []
    for raw in (latest / "evidence.jsonl").read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        r = json.loads(raw)
        if r["record"] == "task":
            segs.append({"task": r, "run": None, "ops": [], "events": [], "chain": None})
        elif r["record"] == "run":
            segs[-1]["run"] = r
        elif r["record"] == "operation":
            segs[-1]["ops"].append(r)
        elif r["record"] == "security_event":
            segs[-1]["events"].append(r)
        elif r["record"] == "chain":
            segs[-1]["chain"] = r
    return segs


def op_action(op: dict) -> str:
    p = json.loads(op["payload_json"])
    bits = [f"`{op['kind']}`"]
    for k in ("facility_id", "receivable_id", "offer_id", "approval_id"):
        if p.get(k):
            bits.append(str(p[k]))
    if isinstance(p.get("amount_fen"), int):
        bits.append(yuan(p["amount_fen"]))
    return " ".join(bits) + f" (by {op['requested_by']})"


def op_result(op: dict) -> str:
    codes = [v.get("code", "") for v in op.get("violations") or [] if isinstance(v, dict)]
    head = f"**{op['status']}**, {op['tier'].replace('_', ' ').title()}" if op.get("tier") else f"**{op['status']}**"
    if codes:
        head += " · " + ", ".join(f"`{c}`" for c in codes if c)
    return head + ": " + _short(op.get("message", ""), 100)


def evidence_blocks(latest: Path) -> dict[str, str]:
    segs = read_segments(latest)
    runs = [s["run"] for s in segs if s["run"]]
    run = runs[0] if runs else {}
    shas = sorted({r.get("git_sha") for r in runs})
    stamps = sorted(r.get("recorded_at", "") for r in runs)
    ops = [o for s in segs for o in s["ops"]]
    events = [e for s in segs for e in s["events"]]
    passed = sum(1 for s in segs if s["task"]["status"] == "PASSED")
    turns = sum(len(s["task"]["turns"]) for s in segs)
    status: dict[str, int] = {}
    for o in ops:
        status[o["status"]] = status.get(o["status"], 0) + 1
    valid = sum(1 for s in segs if s["chain"] and s["chain"]["chain_valid"])

    header = [
        "| Field | Value |",
        "| --- | --- |",
        f"| Project | {run.get('project', '')} |",
        f"| Competition | {run.get('competition', '')} |",
        f"| Scenario | `{run.get('scenario', '')}` (sha256 `{run.get('scenario_sha256', '')[:16]}…`) |",
        f"| Offers fixture | sha256 `{run.get('offers_sha256', '')[:16]}…` |",
        f"| Mandate | version {run.get('mandate_version', '')}, Ed25519 signature `{run.get('mandate_signature', '')[:16]}…` |",
        f"| Model mode | `{run.get('llm_mode', '')}` (recorded model outputs; no network) |",
        f"| Code version | git `{', '.join(s for s in shas if s)}` |",
        f"| Recorded (wall clock, UTC; outside every hash) | {stamps[0] if stamps else ''} to {stamps[-1] if stamps else ''} |",
        f"| Tasks | **{passed}/{len(segs)} passed**, {turns} `/nl` turns |",
        f"| Operations logged | {len(ops)}: " + ", ".join(f"{v} {k}" for k, v in sorted(status.items())) + " |",
        f"| Security events logged | {len(events)} |",
        f"| Hash chains | {valid}/{len(segs)} report `chain_valid: true` |",
    ]

    tasks = ["| Task | What it shows | Operations (executed / logged) | Security events | Result | Evidence |",
             "| --- | --- | --- | --- | --- | --- |"]
    for s in segs:
        t = s["task"]
        ex = sum(1 for o in s["ops"] if o["status"] == "EXECUTED")
        tasks.append(
            f"| `{t['task']}` | {_cell(_short(t['title'], 120))} | {ex} / {len(s['ops'])} | {len(s['events'])} | "
            f"{t['status']} | [evidence](../../{E2E_REL}/evidence/{t['task']}.jsonl) |"
        )

    log = ["| Task | Timestamp (simulated day) | Seq | Action | Result | Link |",
           "| --- | --- | --- | --- | --- | --- |"]
    for s in segs:
        name = s["task"]["task"]
        for o in s["ops"]:
            shot = o.get("screenshot") or f"evidence/{name}.jsonl"
            log.append(
                f"| `{name}` | Day {o['day']} | {o['seq']} | {_cell(op_action(o))} | {_cell(op_result(o))} | "
                f"[turn card](../../{E2E_REL}/{shot}) |"
            )
        for e in s["events"]:
            span = ""
            if e.get("spans"):
                span = f" · span “{_short(e['spans'][0].get('text', ''), 40)}”"
            cp = e.get("counterparty_id") or "n/a"
            log.append(
                f"| `{name}` | Day {e['day']} | event | Security event `{e['kind']}` ({cp}) | "
                f"{_cell(_short(e['action_taken'], 60) + span)} | "
                f"[evidence](../../{E2E_REL}/evidence/{name}.jsonl) |"
            )
        if not s["ops"] and not s["events"]:
            outs = "; ".join(f"turn {x['n']}: {x['intent']} → {x.get('outcome') or 'no verdict'}" for x in s["task"]["turns"])
            card = s["task"]["turns"][-1].get("transcript", f"evidence/{name}.jsonl") if s["task"]["turns"] else ""
            log.append(
                f"| `{name}` | Day 0 | none | `/nl` request only; no operation built | {_cell(outs)} | "
                f"[turn card](../../{E2E_REL}/{card}) |"
            )
    return {"evidence-run": "\n".join(header), "evidence-tasks": "\n".join(tasks), "evidence-log": "\n".join(log)}


def refresh_evidence(md_path: Path, latest: Path) -> None:
    text = md_path.read_text(encoding="utf-8")
    for name, block in evidence_blocks(latest).items():
        pat = re.compile(rf"(<!-- BEGIN:{name} -->).*?(<!-- END:{name} -->)", re.S)
        if not pat.search(text):
            raise SystemExit(f"marker BEGIN/END:{name} not found in {md_path}")
        text = pat.sub(lambda m, b=block: m.group(1) + "\n" + b + "\n" + m.group(2), text)
    md_path.write_text(text, encoding="utf-8")
    print(f"refreshed evidence tables in {md_path.relative_to(ROOT)} from {latest.relative_to(ROOT)}")


# ------------------------------------------------------------------ markdown parsing


@dataclass
class Block:
    kind: str  # para, bullet, number, table, code, heading, figure, quote, fallback
    text: str = ""
    level: int = 0
    rows: list[list[str]] = field(default_factory=list)
    number: int = 0


LIST_RE = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")


def parse_blocks(lines: list[str]) -> list[Block]:
    blocks: list[Block] = []
    i = 0
    para: list[str] = []
    last_list_indent: int | None = None

    def flush() -> None:
        if para:
            blocks.append(Block("para", " ".join(x.strip() for x in para)))
            para.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("```"):
            flush()
            j = i + 1
            code: list[str] = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                code.append(lines[j])
                j += 1
            blocks.append(Block("code", "\n".join(code)))
            i = j + 1
            last_list_indent = None
            continue
        m_fig = re.match(r"^<!--\s*figure:\s*(\S+)\s*\|\s*(.*?)(?:\s*\|\s*(page))?\s*-->$", s)
        if m_fig:
            flush()
            blocks.append(Block("figure", m_fig.group(2), rows=[[m_fig.group(1), m_fig.group(3) or ""]]))
            i += 1
            continue
        if s == "<!-- ascii-fallback -->":
            flush()
            blocks.append(Block("fallback"))
            i += 1
            continue
        if s.startswith("<!--"):
            flush()
            while i < len(lines) and "-->" not in lines[i]:
                i += 1
            i += 1
            continue
        if not s:
            flush()
            # an indented paragraph after a blank line continues the previous list item
            i += 1
            continue
        if s == "---":
            flush()
            i += 1
            continue
        if s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                cells = [c.strip() for c in re.split(r"(?<!\\)\|", row.strip("|"))]
                cells = [c.replace("\\|", "|") for c in cells]
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            blocks.append(Block("table", rows=rows))
            last_list_indent = None
            continue
        m_h = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m_h:
            flush()
            blocks.append(Block("heading", m_h.group(2).strip(), level=len(m_h.group(1))))
            i += 1
            last_list_indent = None
            continue
        if s.startswith(">"):
            flush()
            q = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append(Block("quote", " ".join(q)))
            continue
        m_l = LIST_RE.match(line)
        if m_l:
            flush()
            indent = len(m_l.group(1))
            level = indent // 2
            text = m_l.group(3)
            j = i + 1
            # continuation lines (indented, not a new item, not blank)
            while j < len(lines) and lines[j].strip() and not LIST_RE.match(lines[j]) \
                    and lines[j].startswith(" " * (indent + 2)) and not lines[j].strip().startswith(("|", "```")):
                text += " " + lines[j].strip()
                j += 1
            marker = m_l.group(2)
            if marker[0].isdigit():
                blocks.append(Block("number", text, level=level, number=int(marker[:-1])))
            else:
                blocks.append(Block("bullet", text, level=level))
            last_list_indent = indent
            i = j
            continue
        if last_list_indent is not None and line.startswith(" " * (last_list_indent + 2)) and blocks \
                and blocks[-1].kind in ("bullet", "number", "para_in_list"):
            # a paragraph inside a list item (after a blank line)
            flush()
            text = s
            j = i + 1
            while j < len(lines) and lines[j].strip() and lines[j].startswith(" " * (last_list_indent + 2)) \
                    and not LIST_RE.match(lines[j]):
                text += " " + lines[j].strip()
                j += 1
            blocks.append(Block("para_in_list", text, level=last_list_indent // 2))
            i = j
            continue
        last_list_indent = None
        para.append(line)
        i += 1
    flush()
    return blocks


@dataclass
class Section:
    heading: str
    intro: list[str] = field(default_factory=list)
    prompts: list[tuple[str, list[str]]] = field(default_factory=list)


def split_markdown(md: str) -> tuple[list[str], list[Section]]:
    """-> (preamble lines, sections). The preamble drops the title, template banner lines and the first table."""
    pre: list[str] = []
    sections: list[Section] = []
    in_code = False
    for line in md.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        if not in_code and line.startswith("## "):
            sections.append(Section(line[3:].strip()))
            continue
        if not in_code and line.startswith("### ") and sections:
            sections[-1].prompts.append((line[4:].strip(), []))
            continue
        if not sections:
            if line.startswith("# ") or line.startswith("2026 FINTECHATHON") or line.startswith("International AI Track |"):
                continue
            pre.append(line)
            continue
        sec = sections[-1]
        if sec.prompts:
            sec.prompts[-1][1].append(line)
        else:
            sec.intro.append(line)
    # the first table of the preamble is the template's header table, which fill_header() writes
    start = next((i for i, x in enumerate(pre) if x.strip().startswith("|")), None)
    if start is not None:
        end = start
        while end < len(pre) and pre[end].strip().startswith("|"):
            end += 1
        pre = pre[:start] + pre[end:]
    return pre, sections


# ------------------------------------------------------------------ docx rendering


INLINE_RE = re.compile(r"(`[^`]+`|\*\*.+?\*\*|(?<![\w*])\*(?!\s)[^*]+?\*(?![\w*])|\[[^\]]+\]\([^)]+\))")


class Renderer:
    def __init__(self, doc: docx.document.Document, md_dir: Path, repo_url: str | None, compact: bool = False) -> None:
        self.doc = doc
        self.md_dir = md_dir
        self.repo_url = repo_url.rstrip("/") if repo_url else None
        self.last_figure_embedded = False
        # compact: 10 pt body, tight spacing and height-capped figures (the technical document)
        self.compact = compact

    def tighten(self, p: Paragraph) -> None:
        if not self.compact:
            return
        f = p.paragraph_format
        f.space_before, f.space_after, f.line_spacing = Pt(0), Pt(3), 1.08
        for r in p.runs:
            if r.font.size is None:
                r.font.size = BODY_PT

    # -- inline
    def inline(self, par: Paragraph, text: str, bold: bool = False, italic: bool = False, size: Pt | None = None) -> None:
        for tok in INLINE_RE.split(text):
            if not tok:
                continue
            if tok.startswith("`") and tok.endswith("`") and len(tok) > 1:
                r = par.add_run(tok[1:-1])
                r.font.name = CODE_FONT
                r.font.size = size or Pt(9)
                r.bold, r.italic = bold or None, italic or None
            elif tok.startswith("**") and tok.endswith("**") and len(tok) > 4:
                self.inline(par, tok[2:-2], bold=True, italic=italic, size=size)
            elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
                self.inline(par, tok[1:-1], bold=bold, italic=True, size=size)
            elif tok.startswith("[") and "](" in tok:
                label, url = re.match(r"\[([^\]]+)\]\(([^)]+)\)", tok).groups()
                self.link(par, label, url, size)
            else:
                r = par.add_run(tok)
                r.bold, r.italic = bold or None, italic or None
                if size:
                    r.font.size = size

    def resolve_url(self, url: str) -> str | None:
        if re.match(r"^[a-z]+://", url):
            return url
        if self.repo_url:
            path = (self.md_dir / url).resolve()
            try:
                rel = path.relative_to(ROOT)
            except ValueError:
                return None
            return f"{self.repo_url}/{rel.as_posix()}"
        return None

    def link(self, par: Paragraph, label: str, url: str, size: Pt | None) -> None:
        target = self.resolve_url(url)
        if target is None:
            # a repo-relative path with no --repo-url: print the path so it can still be followed
            path = (self.md_dir / url).resolve()
            try:
                shown = path.relative_to(ROOT).as_posix()
            except ValueError:
                shown = url
            r = par.add_run(f"{label} ({shown})" if label != shown else shown)
            r.font.size = size or Pt(8)
            return
        rid = par.part.relate_to(target, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
        h = OxmlElement("w:hyperlink")
        h.set(qn("r:id"), rid)
        r = OxmlElement("w:r")
        rpr = OxmlElement("w:rPr")
        color = OxmlElement("w:color")
        color.set(qn("w:val"), "315FD8")
        u = OxmlElement("w:u")
        u.set(qn("w:val"), "single")
        rpr.append(color)
        rpr.append(u)
        if size:
            sz = OxmlElement("w:sz")
            sz.set(qn("w:val"), str(int(size.pt * 2)))
            rpr.append(sz)
        r.append(rpr)
        t = OxmlElement("w:t")
        t.text = label
        t.set(qn("xml:space"), "preserve")
        r.append(t)
        h.append(r)
        par._p.append(h)

    # -- blocks, inserted before `anchor`
    def para_before(self, anchor: Paragraph, style: str | None = None) -> Paragraph:
        return anchor.insert_paragraph_before("", style=style)

    def render(self, blocks: list[Block], anchor: Paragraph) -> int:
        count = 0
        skip_next_code = False
        for b in blocks:
            if b.kind == "fallback":
                skip_next_code = self.last_figure_embedded
                continue
            if b.kind == "code" and skip_next_code:
                skip_next_code = False
                continue
            skip_next_code = False
            count += 1
            if b.kind == "para":
                p = self.para_before(anchor)
                self.inline(p, b.text)
            elif b.kind == "para_in_list":
                p = self.para_before(anchor)
                p.paragraph_format.left_indent = Inches(0.5 + 0.25 * b.level)
                self.inline(p, b.text)
            elif b.kind == "bullet":
                style = ["List Bullet 2", "List Bullet 3", "List Bullet 3"][min(b.level, 2)]
                p = self.para_before(anchor, style)
                p.paragraph_format.left_indent = Inches(0.55 + 0.25 * b.level)
                p.paragraph_format.first_line_indent = Inches(-0.2)
                p.paragraph_format.tab_stops.add_tab_stop(Inches(0.55 + 0.25 * b.level))
                self.inline(p, b.text)
            elif b.kind == "number":
                p = self.para_before(anchor)
                p.paragraph_format.left_indent = Inches(0.5 + 0.25 * b.level)
                p.paragraph_format.first_line_indent = Inches(-0.2)
                p.add_run(f"{b.number}. ")
                self.inline(p, b.text)
            elif b.kind == "heading":
                style = "Heading 2" if b.level <= 3 else "Heading 3"
                p = self.para_before(anchor, style)
                self.inline(p, b.text)
            elif b.kind == "quote":
                p = self.para_before(anchor, "Quote")
                self.inline(p, b.text)
            elif b.kind == "code":
                self.code(anchor, b.text)
            elif b.kind == "table":
                self.table(anchor, b.rows)
            elif b.kind == "figure":
                self.figure(anchor, b.rows[0][0], b.text, page=b.rows[0][1] == "page")
            if b.kind in ("para", "para_in_list", "bullet", "number"):
                self.tighten(p)
        return count

    def code(self, anchor: Paragraph, text: str) -> None:
        p = self.para_before(anchor)
        ppr = p._p.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "F3F5F9")
        ppr.append(shd)
        p.paragraph_format.space_after = Pt(6)
        lines = text.split("\n")
        size = Pt(7) if max((len(x) for x in lines), default=0) > 90 else Pt(8)
        for n, line in enumerate(lines):
            r = p.add_run(line)
            r.font.name = CODE_FONT
            r.font.size = size
            r._element.rPr.rFonts.set(qn("w:eastAsia"), CODE_FONT)
            if n < len(lines) - 1:
                r.add_break(WD_BREAK.LINE)

    def table(self, anchor: Paragraph, rows: list[list[str]]) -> None:
        if not rows:
            return
        ncols = max(len(r) for r in rows)
        t = self.doc.add_table(rows=len(rows), cols=ncols)
        t.style = self.doc.styles["Table Grid"]
        size = Pt(8) if ncols >= 5 or len(rows) > 20 else Pt(9)
        for ri, row in enumerate(rows):
            for ci in range(ncols):
                cell = t.cell(ri, ci)
                p = cell.paragraphs[0]
                self.inline(p, row[ci] if ci < len(row) else "", bold=(ri == 0), size=size)
                if self.compact:
                    f = p.paragraph_format
                    f.space_before, f.space_after, f.line_spacing = Pt(1), Pt(1), 1.0
                    if ncols == 2:
                        cell.width = Inches(1.9 if ci == 0 else 4.6)
                if ri == 0:
                    tcpr = cell._tc.get_or_add_tcPr()
                    shd = OxmlElement("w:shd")
                    shd.set(qn("w:val"), "clear")
                    shd.set(qn("w:color"), "auto")
                    shd.set(qn("w:fill"), "E8EEFB")
                    tcpr.append(shd)
        # repeat the header row on each page, and keep every row on one page
        for cell in t.rows[0].cells:  # a header row never ends a page on its own
            for par in cell.paragraphs:
                par.paragraph_format.keep_with_next = True
        trpr = t.rows[0]._tr.get_or_add_trPr()
        th = OxmlElement("w:tblHeader")
        th.set(qn("w:val"), "true")
        trpr.append(th)
        for row, cells in zip(t.rows, rows, strict=False):
            if sum(len(c) for c in cells) > 360:
                continue  # a long row may break across pages rather than leave most of a page empty
            cs = OxmlElement("w:cantSplit")
            cs.set(qn("w:val"), "true")
            row._tr.get_or_add_trPr().insert(0, cs)
        self.widths(t, rows, ncols)
        anchor._p.addprevious(t._tbl)
        spacer = self.para_before(anchor)
        spacer.paragraph_format.space_after = Pt(2)

    @staticmethod
    def widths(t, rows: list[list[str]], ncols: int) -> None:
        """Columns sized by their text: each at least as wide as its longest unbreakable word (a code name cannot wrap), the
        rest of the page shared by how much text each column holds."""
        total, per_char = 6.5, 0.068  # inches of usable width; inches per character at 8 to 9 pt
        floor, weight = [], []
        for ci in range(ncols):
            cells = [re.sub(r"[*]", "", r[ci]) if ci < len(r) else "" for r in rows]
            words = [w for c in cells for w in re.split(r"[\s]+", c.replace("`", "")) if w]
            # the cell's padding plus its longest word; a long path may wrap, so it does not claim more than 1.4 in
            floor.append(min(1.4, max(0.5, 0.18 + per_char * max((len(w) for w in words), default=4))))
            lens = sorted(len(c) for c in cells)
            weight.append(max(4.0, min(80.0, lens[len(lens) * 3 // 4] if lens else 4.0)))
        spare = total - sum(floor)
        if spare <= 0:
            width = [f * total / sum(floor) for f in floor]
        else:
            # share the spare room by text length, but no column wider than its text needs on one line
            need = [max(0.0, per_char * w * 1.1 - f) for f, w in zip(floor, weight, strict=True)]
            width = list(floor)
            for _ in range(4):
                open_cols = [k for k in range(ncols) if need[k] > 1e-6]
                if spare <= 1e-6 or not open_cols:
                    break
                share = sum(weight[k] for k in open_cols)
                for k in open_cols:
                    add = min(need[k], spare * weight[k] / share)
                    width[k] += add
                    need[k] -= add
                spare = total - sum(width)
            if spare > 1e-6:
                width = [w + spare * weight[k] / sum(weight) for k, w in enumerate(width)]
        t.autofit = False
        for ci, w in enumerate(width):
            for cell in t.columns[ci].cells:
                cell.width = Inches(w)

    def figure(self, anchor: Paragraph, name: str, caption: str, page: bool = False) -> None:
        path = (self.md_dir / name)
        self.last_figure_embedded = path.exists()
        if not path.exists():
            return
        p = self.para_before(anchor)
        width = Inches(6.4)
        if page:
            # a tall diagram on a page of its own: 6.2 in wide, capped so that it and its caption fit one page
            img = DocxImage.from_file(str(path))
            width = Inches(min(6.2, PAGE_FIG_HEIGHT_IN * img.px_width / img.px_height))
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.page_break_before = True
        elif self.compact:
            img = DocxImage.from_file(str(path))
            # cap the height so a tall screenshot does not take a whole page
            width = Inches(min(6.2, MAX_FIG_HEIGHT_IN * img.px_width / img.px_height))
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(str(path), width=width)
        c = self.para_before(anchor, "Caption")
        c.add_run(caption)


# ------------------------------------------------------------------ template filling


def body_paragraphs(doc) -> list[Paragraph]:
    return [Paragraph(el, doc) for el in doc.element.body.iterchildren() if el.tag == qn("w:p")]


def fill_header(doc) -> None:
    table = doc.tables[0]
    for row in table.rows:
        label = row.cells[0].text.strip()
        value = HEADER.get(label)
        if value is None:
            continue
        cell = row.cells[1]
        p = cell.paragraphs[0]
        runs = p.runs
        if runs:
            runs[0].text = value
            for r in runs[1:]:
                r.text = ""
        else:
            p.add_run(value)


def fill(md_path: Path, template: Path, out_path: Path, repo_url: str | None) -> None:
    doc = docx.Document(str(template))
    fill_header(doc)
    md = md_path.read_text(encoding="utf-8")
    pre, sections = split_markdown(md)
    r = Renderer(doc, md_path.parent, repo_url, compact=md_path.name == "technical_document.md")
    paras = body_paragraphs(doc)
    headings = [p for p in paras if p.style.name == "Heading 1"]
    if pre and any(x.strip() for x in pre) and headings:
        r.render(parse_blocks(pre), headings[0])
    for sec in sections:
        h = next((p for p in body_paragraphs(doc) if p.style.name == "Heading 1" and p.text.strip() == sec.heading), None)
        if h is None and sec.heading.startswith("Appendix"):
            append_section(doc, r, sec)
            continue
        if h is None:
            raise SystemExit(f"{md_path.name}: heading '{sec.heading}' is not in the template {template.name}")
        after = _following(doc, h)
        if sec.intro and any(x.strip() for x in sec.intro) and after is not None:
            r.render(parse_blocks(sec.intro), after)
        for prompt, lines in sec.prompts:
            bullet = _find_prompt(doc, h, prompt)
            if bullet is None:
                raise SystemExit(f"{md_path.name}: prompt '{prompt}' is not under '{sec.heading}' in {template.name}")
            placeholder = _following(doc, bullet)
            if placeholder is None or placeholder.text.strip() != "Write here":
                raise SystemExit(f"{template.name}: no 'Write here' after '{prompt}'")
            n = r.render(parse_blocks(lines), placeholder)
            if n == 0:
                raise SystemExit(f"{md_path.name}: prompt '{prompt}' has no content")
            placeholder._p.getparent().remove(placeholder._p)
    finish(doc, TITLES.get(out_path.name, out_path.stem.replace("_", " ")), contents="<!-- contents -->" in md)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))


def append_section(doc, r: Renderer, sec: Section) -> None:
    """An "## Appendix ..." section the template does not have: added at the end, its "###" lines as sub-headings."""
    end = doc.add_paragraph("")
    h = end.insert_paragraph_before(sec.heading, style="Heading 1")
    h.paragraph_format.page_break_before = sec.heading.startswith("Appendix A")  # the appendices start on a new page together
    if sec.intro:
        r.render(parse_blocks(sec.intro), end)
    for prompt, lines in sec.prompts:
        r.render([Block("heading", prompt, level=3)] + parse_blocks(lines), end)
    end._p.getparent().remove(end._p)


def _field(par: Paragraph, instr: str, shown: str = "1") -> None:
    """A Word field (PAGE, NUMPAGES, TOC); Word computes it when the document is opened or updated."""
    for kind, text in (("begin", None), ("instr", instr), ("separate", None), ("text", shown), ("end", None)):
        run = OxmlElement("w:r")
        if kind == "instr":
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = f" {text} "
        elif kind == "text":
            el = OxmlElement("w:t")
            el.text = text
        else:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        run.append(el)
        par._p.append(run)


def finish(doc, title: str, contents: bool) -> None:
    """East Asian fonts on every style, page numbers in the footer, metadata; a contents field where asked."""
    for style in doc.styles:
        el = getattr(style, "element", None)
        if el is None or style.type not in (1, 2):  # paragraph and character styles
            continue
        rpr = el.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            fonts = OxmlElement("w:rFonts")
            rpr.insert(0, fonts)
        fonts.set(qn("w:eastAsia"), CJK_FONT)
    defaults = doc.styles.element.find(qn("w:docDefaults"))
    if defaults is not None:
        rpr = defaults.find(f"{qn('w:rPrDefault')}/{qn('w:rPr')}")
        if rpr is not None:
            fonts = rpr.find(qn("w:rFonts"))
            if fonts is None:
                fonts = OxmlElement("w:rFonts")
                rpr.insert(0, fonts)
            fonts.set(qn("w:eastAsia"), CJK_FONT)
    footer = doc.sections[0].footer
    p = footer.add_paragraph()
    p.alignment = 1  # centred
    p.add_run("Page ")
    _field(p, "PAGE")
    p.add_run(" of ")
    _field(p, "NUMPAGES")
    for run in p.runs:
        run.font.size = Pt(8)
    if contents:
        marker = next((q for q in body_paragraphs(doc) if q.text.strip() == "Contents"), None)
        if marker is not None:
            toc = marker.insert_paragraph_before("")
            marker._p.addnext(toc._p)
            _field(toc, 'TOC \\o "1-3" \\h \\z \\u', "Open in Word and update fields to show the contents.")
    cp = doc.core_properties
    cp.title = f"FLOW (TermsLedger): {title}"
    cp.subject = "2026 FinTechathon, International AI Track, Topic E"
    cp.author = cp.last_modified_by = "TermsLedger team"
    cp.keywords = "FLOW; TermsLedger; security; FinTechathon 2026"
    now = datetime.now(UTC).replace(microsecond=0, tzinfo=None)
    cp.created = cp.modified = now
    cp.revision = 1


WORD_PS = r"""
$ErrorActionPreference = 'Stop'
$w = New-Object -ComObject Word.Application
$w.Visible = $false
$w.DisplayAlerts = 0
try {
  foreach ($f in $args) {
    $d = $w.Documents.Open($f, $false, $false)
    foreach ($n in 1..3) {
      try { $st = $d.Styles.Item("TOC $n"); $st.Font.Size = 9; $st.ParagraphFormat.SpaceBefore = 0; $st.ParagraphFormat.SpaceAfter = 0 } catch {}
    }
    foreach ($t in $d.TablesOfContents) { $t.Update() }
    $d.Fields.Update() | Out-Null
    foreach ($s in $d.Sections) { foreach ($ft in $s.Footers) { $ft.Range.Fields.Update() | Out-Null } }
    $d.Save()
    $pdf = [IO.Path]::ChangeExtension($f, '.pdf')
    $d.ExportAsFixedFormat($pdf, 17, $false, 0, 0, 0, 0, 0, $true, $true, 1, $true, $true, $false)
    $n = $d.ComputeStatistics(2)
    $d.Close($false)
    Write-Output "$f pages=$n"
  }
} finally { $w.Quit() }
"""


def word_pass(paths: list[Path]) -> None:
    """Windows with Word only: update the contents and page fields, save, and export a PDF with fonts embedded."""
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "word_pass.ps1"
        script.write_text(WORD_PS, encoding="utf-8")
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script),
                            *(str(p.resolve()) for p in paths)], capture_output=True, text=True, check=False)
    print(r.stdout.strip() or r.stderr.strip())


def _following(doc, par: Paragraph) -> Paragraph | None:
    el = par._p.getnext()
    while el is not None and el.tag != qn("w:p"):
        el = el.getnext()
    return Paragraph(el, doc) if el is not None else None


def _find_prompt(doc, heading: Paragraph, prompt: str) -> Paragraph | None:
    el = heading._p.getnext()
    while el is not None:
        if el.tag == qn("w:p"):
            p = Paragraph(el, doc)
            if p.style.name == "Heading 1":
                return None
            if p.style.name == "List Bullet" and p.text.strip() == prompt:
                return p
        el = el.getnext()
    return None


# ------------------------------------------------------------------ verification


def template_outline(template: Path) -> list[tuple[str, str]]:
    doc = docx.Document(str(template))
    out = []
    for p in body_paragraphs(doc):
        if p.style.name in ("Heading 1", "List Bullet"):
            out.append((p.style.name, p.text.strip()))
    return out


def verify(out_path: Path, template: Path) -> list[str]:
    problems: list[str] = []
    doc = docx.Document(str(out_path))  # reopens: a broken package raises here
    paras = body_paragraphs(doc)
    texts = [(p.style.name, p.text.strip()) for p in paras]
    tpl = docx.Document(str(template))
    for want in template_outline(template):
        if want not in texts:
            problems.append(f"missing template {want[0]} '{want[1]}'")
    # every prompt must be followed by content, not by the next prompt, a heading or the end
    prompts = {text for style, text in template_outline(template) if style == "List Bullet"}
    for p in paras:
        if p.style.name != "List Bullet" or p.text.strip() not in prompts:
            continue
        nxt = p._p.getnext()
        if nxt is None or nxt.tag not in (qn("w:p"), qn("w:tbl")):
            problems.append(f"prompt '{p.text.strip()}' has no content after it")
        elif nxt.tag == qn("w:p"):
            q = Paragraph(nxt, doc)
            if q.style.name == "Heading 1" or (q.style.name == "List Bullet" and q.text.strip() in prompts):
                problems.append(f"prompt '{p.text.strip()}' has no content after it")
    cells = [c.text.strip() for t in doc.tables for row in t.rows for c in row.cells]
    for ph in PLACEHOLDERS:
        if any(t == ph for _, t in texts) or any(c == ph for c in cells):
            problems.append(f"placeholder '{ph}' left in the document")
    for label in HEADER:
        row = next((r for r in doc.tables[0].rows if r.cells[0].text.strip() == label), None)
        if row is None or not row.cells[1].text.strip():
            problems.append(f"header row '{label}' missing or empty")
    tpl_title = [p.text for p in body_paragraphs(tpl)][:2]
    if [p.text for p in paras][:2] != tpl_title:
        problems.append("template title lines changed")
    footer = " ".join(p.text for p in doc.sections[0].footer.paragraphs)
    if "newer version prevails" not in footer:
        problems.append("template footer missing")
    if sys.platform == "darwin":
        # an independent reader (Cocoa's DOCX importer) must also open it
        r = subprocess.run(["textutil", "-convert", "txt", "-stdout", str(out_path)], capture_output=True, text=True)
        if r.returncode != 0 or "01 " not in r.stdout:
            problems.append("textutil could not read the document")
    return problems


def team_placeholders(out_path: Path) -> list[str]:
    """The distinct [TEAM: ...] markers left in a built document (deliberate; listed, not a failure)."""
    doc = docx.Document(str(out_path))
    texts = [p.text for p in doc.paragraphs] + [c.text for t in doc.tables for row in t.rows for c in row.cells]
    return sorted(set(re.findall(r"\[TEAM:[^\]]*\]", "\n".join(texts))))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh-evidence", action="store_true", help="regenerate the evidence tables from the e2e run first")
    ap.add_argument("--latest", default=str(E2E), help="scenario-run directory (default: services/api/evals/e2e/latest)")
    ap.add_argument("--word", action="store_true",
                    help="Windows with Word: update the contents and page numbers, and export a PDF beside each file")
    ap.add_argument("--repo-url", default=None,
                    help="base URL for repo links, e.g. https://github.com/<org>/<repo>/blob/<ref> (default: print paths)")
    args = ap.parse_args()

    if args.refresh_evidence:
        refresh_evidence(DELIV / "execution_evidence.md", Path(args.latest).resolve())

    failed = False
    built: list[Path] = []
    for md_name, tpl_name, out_name in JOBS:
        md_path = (DELIV / md_name).resolve()
        template = TEMPLATES / tpl_name
        out_path = OUT / out_name
        fill(md_path, template, out_path, args.repo_url)
        built.append(out_path)
        problems = verify(out_path, template)
        rel = out_path.relative_to(ROOT)
        if problems:
            failed = True
            print(f"FAIL {rel}")
            for p in problems:
                print("   -", p)
        else:
            n = len(template_outline(template))
            print(f"OK   {rel}  ({n} template headings and prompts present, no placeholders left)")
        team = team_placeholders(out_path)
        if team:
            print(f"     {len(team)} [TEAM: ...] placeholder(s) for the team to fill:")
            for t in team:
                print(f"       {t}")
    if args.word and not failed:
        word_pass(built)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
