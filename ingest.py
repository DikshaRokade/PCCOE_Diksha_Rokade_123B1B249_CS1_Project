"""PDF ingestion: text blocks, headings, tables, section-aware chunking (PyMuPDF)."""
import hashlib
import logging
import re
from pathlib import Path

import pymupdf

log = logging.getLogger(__name__)

TABLE_TYPES = {
    ("component", "type", "responsibility"): "components",
    ("component", "port", "direction", "interface"): "ports",
    ("interface", "kind", "data element / operation", "data type"): "interfaces",
    ("signal", "can message", "can id", "length (bit)", "dir", "cycle (ms)", "mapped port"): "signals",
    ("provider port", "requirer port", "purpose"): "connections",
    ("id", "requirement", "value"): "constraints",
    ("did", "name", "owner component", "length (bytes)"): "dids",
    ("version", "date", "change"): "revisions",
    ("term", "meaning"): "glossary",
    ("field", "value"): "doc_control",
}
TABLE_TITLES = {
    "components": "Component catalogue", "ports": "Port specification", "interfaces": "Interface definition",
    "signals": "CAN signal specification", "connections": "Connection table", "constraints": "Non-functional requirement",
    "dids": "Diagnostic data identifier", "revisions": "Revision history", "glossary": "Glossary entry",
    "doc_control": "Document control",
}


def norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()


def split_text(text, max_chars, overlap=1):
    if len(text) <= max_chars:
        return [text]
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    chunks, cur = [], []
    for s in sents:
        if cur and len(" ".join(cur)) + len(s) + 1 > max_chars:
            chunks.append(" ".join(cur))
            cur = cur[-overlap:] if overlap else []
        cur.append(s)
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def _overlap_area(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(w, 0) * max(h, 0)


def _heading_level(size, bold):
    if size >= 20:
        return 0  # document title
    if bold and size >= 15.5:
        return 1
    if bold and size >= 12.5:
        return 2
    if bold and size >= 11.2:
        return 3
    return None


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_pdf(path, max_chars=900, overlap=1):
    path = Path(path)
    doc = pymupdf.open(path)
    stack = []  # (level, text)
    buffer = []  # (page, text) paragraphs of current section
    chunks, tables, text_blocks, sections = [], [], [], []

    def label():
        return stack[-1][1] if stack else "Front matter"

    def flush():
        if not buffer:
            return
        sec = label()
        body = " ".join(t for _, t in buffer)
        page0 = buffer[0][0]
        sections.append({"section": sec, "page": page0, "text": body})
        for i, part in enumerate(split_text(body, max_chars, overlap)):
            prefix = f"Section {sec} (page {page0}): "
            chunks.append({"type": "text", "page": page0, "section": sec, "prefix": prefix, "body": part,
                           "text": prefix + part, "idx": len(chunks)})
        buffer.clear()

    for pno, page in enumerate(doc, 1):
        ph = page.rect.height
        found = page.find_tables().tables
        tb = [t.bbox for t in found]
        items = []
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            bb = b["bbox"]
            area = max((bb[2] - bb[0]) * (bb[3] - bb[1]), 1e-6)
            if any(_overlap_area(bb, t) > 0.5 * area for t in tb):
                continue
            spans = [s for ln in b["lines"] for s in ln["spans"] if s["text"].strip()]
            if not spans:
                continue
            size = max(s["size"] for s in spans)
            bold = any("bold" in s["font"].lower() for s in spans)
            text = norm(" ".join("".join(s["text"] for s in ln["spans"]) for ln in b["lines"]))
            if bb[1] > ph - 55 and size <= 8.5:  # footer
                continue
            items.append((bb[1], "block", text, size, bold))
        for t in found:
            items.append((t.bbox[1], "table", _table_rows(page, t), 0, False))
        if not any(i[1] == "block" for i in items) and not found:
            ocr = _ocr_page(page)
            if ocr:
                items.append((0, "block", ocr, 10, False))
        items.sort(key=lambda i: i[0])
        for _, kind, payload, size, bold in items:
            if kind == "block":
                lvl = _heading_level(size, bold)
                if lvl is None:
                    buffer.append((pno, payload))
                    text_blocks.append({"page": pno, "section": label(), "text": payload})
                else:
                    flush()
                    if lvl == 0:
                        stack[:] = [(0, payload)]
                    else:
                        while stack and stack[-1][0] >= lvl:
                            stack.pop()
                        stack.append((lvl, payload))
                    text_blocks.append({"page": pno, "section": payload, "text": payload, "heading": True})
            else:
                rows = [[norm(c) for c in r] for r in payload if any(norm(c) for c in r)]
                if not rows:
                    continue
                header = tuple(c.lower() for c in rows[0])
                typ = TABLE_TYPES.get(header)
                if typ is None:
                    log.warning("Unrecognised table header on page %s: %s", pno, header)
                    continue
                body_rows = [r for r in rows[1:] if tuple(c.lower() for c in r) != header]
                sec = label()
                tables.append({"type": typ, "page": pno, "section": sec, "header": rows[0], "rows": body_rows})
                for r in body_rows:
                    prefix = f"{TABLE_TITLES[typ]} (section {sec}, page {pno}): "
                    body = "; ".join(f"{h}: {v}" for h, v in zip(rows[0], r) if v)
                    chunks.append({"type": "table", "page": pno, "section": sec, "prefix": prefix, "body": body,
                                   "text": prefix + body, "idx": len(chunks), "table_type": typ})
    flush()
    return {"path": str(path), "filename": path.name, "sha256": sha256_file(path), "pages": len(doc),
            "chunks": chunks, "tables": tables, "text_blocks": text_blocks, "sections": sections}


def _table_rows(page, t):
    """Cell text via clipped line extraction (keeps identifier underscores in the right place)."""
    rows = []
    for row in t.rows:
        cells = []
        for c in row.cells:
            if c is None:
                cells.append("")
                continue
            r = pymupdf.Rect(c) + (1, 1, -1, -1)
            cells.append(page.get_text("text", clip=r))
        rows.append(cells)
    return rows


def _ocr_page(page):
    """Optional OCR fallback for scanned pages (requires Tesseract). Not evaluated in this project."""
    try:
        tp = page.get_textpage_ocr(language="eng", full=True)
        return norm(page.get_text("text", textpage=tp))
    except Exception as ex:  # noqa: BLE001
        log.warning("OCR unavailable for page %s: %s", page.number + 1, ex)
        return ""
