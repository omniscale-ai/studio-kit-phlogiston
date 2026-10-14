#!/usr/bin/env python3
"""Shared parsing and matching for scripts/lit_run.py and scripts/lit_gate.py.
Stdlib only. Matching follows artifacts/LITERATURE/rules.md rule 11: every
string is normalised before comparison (see norm_text, norm_doi); a `doi`
item matches a DOI exactly, every other type matches as a substring."""
from __future__ import annotations

import html
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote

TYPES = ("doi", "title", "term", "benchmark", "author")
MODES = ("none", "allowed", "blind")
DASHES = ("", "—", "-", "–")

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_FENCE = re.compile(r"^[ \t]*(```|~~~).*?^[ \t]*\1[ \t]*$", re.S | re.M)
_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_DOI = re.compile(r"10\.\d+/[^\s<>\"']+")
_TRAIL = ".,;:>)]"


def strip_noncontent(text: str) -> str:
    """Text without HTML comments and fenced code blocks."""
    text = (text or "").replace("\r\n", "\n")
    return _COMMENT.sub("", _FENCE.sub("", text))


def section(text: str, name: str) -> str:
    text = strip_noncontent(text)
    m = re.search(rf"^##\s+(?:\d+\.\s+)?{re.escape(name)}\s*\n(.*?)(?=^##\s|\Z)", text, re.S | re.M)
    return m.group(1) if m else ""


def split_row(line: str) -> list:
    """Cells of a table line: split on unescaped pipes, `\\|` unescaped."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", s)]


def table_rows(sec: str, first_only: bool = False) -> list:
    """Data rows of the tables in a section, headers and separators dropped.
    With first_only only the first table counts."""
    tables, cur = [], None
    for line in sec.splitlines():
        s = line.strip()
        if s.startswith("|"):
            if cur is None:
                cur = []
                tables.append(cur)
            if not set(s) <= set("|-: "):
                cur.append(split_row(s))
        else:
            cur = None
    if first_only:
        tables = tables[:1]
    return [r for t in tables for r in t[1:]]


def table_list(sec: str) -> list:
    """Every table of a section as (header cells, data rows); separators dropped."""
    tables, cur = [], None
    for line in sec.splitlines():
        s = line.strip()
        if s.startswith("|"):
            if cur is None:
                cur = []
                tables.append(cur)
            if not set(s) <= set("|-: "):
                cur.append(split_row(s))
        else:
            cur = None
    return [(t[0], t[1:]) for t in tables if t]


def col_index(head: list, name: str):
    """Index of the column whose header (Markdown stripped, case-insensitive) is `name`, else None."""
    for i, h in enumerate(head):
        if re.sub(r"\s+", " ", strip_md(h)).strip().lower() == name:
            return i
    return None


def prose_of(sec: str) -> str:
    """Section text outside Markdown tables and outside inline code (fences and
    comments are already removed by `section`)."""
    txt = "\n".join(ln for ln in sec.splitlines() if not ln.strip().startswith("|"))
    return re.sub(r"(`+).+?\1", " ", txt, flags=re.S)


def without_first_table(sec: str) -> str:
    """The section with the lines of its first table removed."""
    out, state = [], 0          # 0 before, 1 inside, 2 after the first table
    for line in sec.splitlines():
        is_t = line.strip().startswith("|")
        if state == 0 and is_t:
            state = 1
            continue
        if state == 1:
            if is_t:
                continue
            state = 2
        out.append(line)
    return "\n".join(out)


def strip_md(s: str) -> str:
    """Markdown emphasis and code marks removed (for labels and cells)."""
    s = _LINK.sub(lambda m: f"{m.group(1)} {m.group(2)}", s or "")
    s = s.replace("`", "").replace("**", "").replace("__", "")
    s = re.sub(r"(?<!\w)_+|_+(?!\w)", "", s).replace("*", "")
    return re.sub(r"\s+", " ", s).strip()


def strip_cf(s: str) -> str:
    """Characters of Unicode category Cf (zero-width, soft hyphen, ...) removed."""
    return "".join(c for c in (s or "") if unicodedata.category(c) != "Cf")


def norm_text(s: str) -> str:
    """Normal form used before every comparison: links expanded to text and
    url, percent-unquoted, HTML entities decoded, <br> read as whitespace,
    Cf characters removed, emphasis marks stripped, accents folded (NFKD,
    combining marks dropped), NFKC, whitespace collapsed, lowercase."""
    s = unquote(_LINK.sub(lambda m: f"{m.group(1)} {m.group(2)}", s or ""))
    s = re.sub(r"<br\s*/?>", " ", html.unescape(s), flags=re.I)
    s = strip_cf(s)
    s = unicodedata.normalize("NFKD", strip_md(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return unicodedata.normalize("NFKC", s).lower()


def norm_doi(s: str) -> str:
    t = norm_text(s)
    t = re.sub(r"^(?:<)?(?:https?://)?(?:www\.)?(?:dx\.)?doi\.org/", "", t)
    t = re.sub(r"^doi:\s*", "", t)
    m = _DOI.search(t)
    if m:
        t = m.group(0)
    return t.strip().rstrip(_TRAIL).strip()


def embedded_dois(s: str) -> list:
    """DOIs embedded in a string such as an OA link (normalised)."""
    out = []
    for m in _DOI.finditer(norm_text(s)):
        d = re.split(r"[?#]", m.group(0))[0]
        cands = {d, re.sub(r"(/pdf|/full|/abstract|\.pdf)$", "", d)}
        out += [c.rstrip(_TRAIL) for c in cands]
    return out


def _placeholder_cell(c: str) -> bool:
    c = c.strip()
    return bool(re.match(r"^\{.*\}$", c, re.S)) or c in ("{…}", "{...}")


def parse_plan(text: str) -> dict:
    """{'id', 'mode', 'excluded': [(item, type, reason)], 'problems': [str]}"""
    problems = []
    text = strip_noncontent(text)
    m = re.search(r"^\*\*ID\*\*:\s*`([^`]+)`", text, re.M)
    pid = m.group(1) if m else None
    if not pid:
        problems.append("PLAN has no `**ID**: `...`` line")
    sec = section(text, "Prior Knowledge")
    m = re.search(r"\*\*Literature mode\*\*:\s*`?(none|allowed|blind)\b", sec, re.I)
    mode = m.group(1).lower() if m else None
    if not mode:
        problems.append("PLAN section 2 has no Literature mode of none, allowed or blind")
    excl = []
    m = re.search(r"\*\*Excluded\*\*:(.*?)(?=^\*\*LITERATURE drawn on\*\*|\Z)", sec, re.S | re.M)
    if m:
        for i, r in enumerate(table_rows(m.group(1)), 1):
            if r and all(_placeholder_cell(c) for c in r):
                continue                      # the template's placeholder row
            if any(_placeholder_cell(c) or "{…}" in c or "{...}" in c for c in r):
                problems.append(f"PLAN Excluded row {i} still holds a {{…}} placeholder")
                continue
            if len(r) < 3:
                problems.append(f"PLAN Excluded row {i} has fewer than 3 cells")
                continue
            if not r[0] or r[1].lower() not in TYPES:
                problems.append(f"PLAN Excluded row {i} has an empty item or a type outside {TYPES}")
                continue
            excl.append((r[0], r[1].lower(), r[2]))
    return {"id": pid, "mode": mode, "excluded": excl, "problems": problems}


def load_plan(path) -> dict:
    return parse_plan(Path(path).read_text(encoding="utf-8-sig"))


def hit_index(excluded, dois=(), texts=(), doi_in_text=False, link_texts=()):
    """Index (0-based) of the first Excluded item that matches, else None.
    `dois` are DOI cells (exact match for `doi` items); `texts` are free
    strings (substring match for the other types). `link_texts` are OA link
    cells: a `doi` item also matches exactly a DOI embedded in them. With
    doi_in_text a `doi` item also matches as a substring of `texts`
    (Request, queries). Everything is normalised first."""
    low = [norm_text(t) for t in texts if t]
    nd = {norm_doi(d) for d in dois if norm_doi(d) not in DASHES}
    for t in tuple(link_texts) + tuple(dois):
        nd.update(embedded_dois(t or ""))
    for i, (item, typ, _reason) in enumerate(excluded):
        if typ == "doi":
            nit = norm_doi(item)
            if not nit:
                continue
            if nit in nd or (doi_in_text and any(nit in t for t in low)):
                return i
        else:
            it = norm_text(item)
            if it and any(it in t for t in low):
                return i
    return None
