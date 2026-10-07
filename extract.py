"""Architecture-entity extraction: tables -> structured knowledge base (with page provenance)."""
import re

FIELDS = {
    "components": ["name", "type", "responsibility"],
    "ports": ["component", "port", "direction", "interface"],
    "interfaces": ["name", "kind", "element", "datatype"],
    "signals": ["name", "message", "can_id", "length_bits", "dir", "cycle", "mapped_port"],
    "connections": ["provider", "requirer", "purpose"],
    "constraints": ["id", "requirement", "value"],
    "dids": ["did", "name", "owner", "length"],
    "revisions": ["version", "date", "change"],
    "glossary": ["term", "meaning"],
}
SWC_RE = re.compile(r"\bSWC_[A-Za-z0-9]+")
CAMEL_RE = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b")


def build_kb(parsed):
    kb = {k: [] for k in FIELDS}
    kb.update({"doc_id": None, "version": None, "title": None, "date": None, "status": None,
               "source_file": parsed["filename"], "sha256": parsed["sha256"], "pages": parsed["pages"]})
    seen = set()
    for t in parsed["tables"]:
        typ = t["type"]
        if typ == "doc_control":
            ctl = {r[0].lower(): r[1] for r in t["rows"] if len(r) >= 2}
            kb["doc_id"] = ctl.get("document id")
            kb["title"] = ctl.get("document title")
            kb["version"] = ctl.get("version")
            kb["date"] = ctl.get("date")
            kb["status"] = ctl.get("status")
            continue
        for r in t["rows"]:
            rec = dict(zip(FIELDS[typ], r))
            if typ == "signals":
                try:
                    rec["length_bits"] = int(rec["length_bits"])
                except (ValueError, KeyError):
                    pass
            key = (typ, tuple(r))
            if key in seen:
                continue
            seen.add(key)
            rec["page"], rec["section"] = t["page"], t["section"]
            kb[typ].append(rec)
    # text-derived references (for consistency checks)
    refs, camel = {}, {}
    for b in parsed["text_blocks"]:
        for m in SWC_RE.findall(b["text"]):
            refs.setdefault(m, {"name": m, "page": b["page"], "section": b["section"]})
        if not b.get("heading"):
            for m in CAMEL_RE.findall(b["text"]):
                camel.setdefault(m, {"token": m, "page": b["page"], "section": b["section"]})
    kb["referenced_swcs"] = list(refs.values())
    kb["camel_tokens"] = list(camel.values())
    kb["sections"] = parsed["sections"]
    if not kb["doc_id"]:
        kb["doc_id"] = parsed["filename"].rsplit(".", 1)[0]
    kb["version"] = kb["version"] or "unknown"
    kb["doc_key"] = f"{kb['doc_id']}@{kb['version']}"
    return kb
