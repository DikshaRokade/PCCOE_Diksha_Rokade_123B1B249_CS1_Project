"""Revision comparison between two knowledge bases (entity-level and section-text-level)."""
import re

IDENT = {
    "components": lambda r: r["name"],
    "ports": lambda r: f'{r["component"]}.{r["port"]}',
    "interfaces": lambda r: f'{r["name"]}.{r["element"]}',
    "signals": lambda r: r["name"],
    "connections": lambda r: f'{r["provider"]}->{r["requirer"]}',
    "constraints": lambda r: r["id"],
    "dids": lambda r: r["did"],
}
SINGULAR = {"components": "component", "ports": "port", "interfaces": "interface", "signals": "signal",
            "connections": "connection", "constraints": "constraint", "dids": "did"}
IGNORE = {"page", "section"}


def _clean(r):
    return {k: v for k, v in r.items() if k not in IGNORE}


def compare_kbs(old, new):
    changes = []
    for cat, idf in IDENT.items():
        o = {idf(r): r for r in old.get(cat, [])}
        n = {idf(r): r for r in new.get(cat, [])}
        s = SINGULAR[cat]
        for k in sorted(n.keys() - o.keys()):
            changes.append({"key": f"{s}:added:{k}", "category": cat, "change": "added", "id": k,
                            "new": _clean(n[k]), "page": n[k].get("page")})
        for k in sorted(o.keys() - n.keys()):
            changes.append({"key": f"{s}:removed:{k}", "category": cat, "change": "removed", "id": k,
                            "old": _clean(o[k]), "page": o[k].get("page")})
        for k in sorted(o.keys() & n.keys()):
            diffs = {f: [o[k].get(f), n[k].get(f)] for f in set(_clean(o[k])) | set(_clean(n[k]))
                     if o[k].get(f) != n[k].get(f)}
            if diffs:
                changes.append({"key": f"{s}:changed:{k}", "category": cat, "change": "changed", "id": k,
                                "fields": diffs, "page": n[k].get("page")})
    return changes


def _sents(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text) if s.strip()]


def compare_sections(old, new):
    o = {s["section"]: s for s in old.get("sections", [])}
    n = {s["section"]: s for s in new.get("sections", [])}
    out = []
    for sec in n:
        if sec not in o:
            out.append({"section": sec, "change": "section added", "added": _sents(n[sec]["text"])[:3], "removed": [],
                        "page": n[sec]["page"]})
            continue
        so, sn = _sents(o[sec]["text"]), _sents(n[sec]["text"])
        added = [s for s in sn if s not in so]
        removed = [s for s in so if s not in sn]
        if added or removed:
            out.append({"section": sec, "change": "text changed", "added": added, "removed": removed,
                        "page": n[sec]["page"]})
    for sec in o:
        if sec not in n:
            out.append({"section": sec, "change": "section removed", "added": [], "removed": _sents(o[sec]["text"])[:3],
                        "page": o[sec]["page"]})
    return out


def compare_docs(old, new):
    return {"old": old["doc_key"], "new": new["doc_key"], "entity_changes": compare_kbs(old, new),
            "text_changes": compare_sections(old, new)}
