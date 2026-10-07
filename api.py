"""FastAPI service layer: auth (API key + role), ingestion, Q&A, entities, checks, comparison, review, export."""
import csv
import hashlib
import io
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .config import load_config
from .pipeline import HLDService

cfg = load_config()
app = FastAPI(title="AUTOSAR HLD Document Analysis Assistant", version="1.0.0")
_services = {}


def svc(project):
    if project not in _services:
        _services[project] = HLDService(cfg, project)
    return _services[project]


def user(x_api_key: Optional[str] = Header(default=None)):
    a = cfg["auth"]
    if not a.get("enabled"):
        return {"user": "anonymous", "role": "engineer"}
    u = a["keys"].get(x_api_key or "")
    if not u:
        raise HTTPException(401, "Missing or invalid X-API-Key")
    return u


def engineer(u=Depends(user)):
    if u["role"] != "engineer":
        raise HTTPException(403, "Engineer role required")
    return u


class Query(BaseModel):
    question: str
    doc_keys: Optional[List[str]] = None


class Review(BaseModel):
    question: str
    answer: str
    sources: list = []
    decision: str  # accepted | edited | rejected
    edited_answer: str = ""
    comment: str = ""


@app.get("/health")
def health():
    return {"status": "ok", **svc(cfg.get("project", "default")).info()}


@app.post("/projects/{project}/documents")
async def upload(project: str, file: UploadFile = File(...), u=Depends(engineer)):
    data = await file.read()
    if not (file.filename or "").lower().endswith(".pdf") or not data.startswith(b"%PDF"):
        raise HTTPException(400, "Only PDF files are accepted")
    if len(data) > cfg["upload"]["max_mb"] * 1024 * 1024:
        raise HTTPException(413, "File too large")
    s = svc(project)
    dest = Path(cfg["paths"]["data_dir_abs"]) / "uploads" / s.project
    dest.mkdir(parents=True, exist_ok=True)
    p = dest / f"{hashlib.sha256(data).hexdigest()[:16]}.pdf"
    p.write_bytes(data)
    try:
        res = s.ingest(p, u["user"])
    except Exception as ex:  # noqa: BLE001
        raise HTTPException(422, f"Could not ingest document: {ex}") from ex
    res["filename"] = file.filename
    return res


@app.get("/projects/{project}/documents")
def documents(project: str, u=Depends(user)):
    return svc(project).docs()


@app.post("/projects/{project}/query")
def query(project: str, q: Query, u=Depends(user)):
    if not q.question.strip():
        raise HTTPException(400, "Empty question")
    return svc(project).query(q.question, q.doc_keys, u["user"])


def _kb(project, doc_key):
    try:
        return svc(project).kb(doc_key)
    except KeyError as ex:
        raise HTTPException(404, f"Unknown document {doc_key}") from ex


@app.get("/projects/{project}/entities")
def entities(project: str, doc_key: str, u=Depends(user)):
    kb = _kb(project, doc_key)
    return {k: kb[k] for k in ("components", "ports", "interfaces", "signals", "connections", "constraints", "dids")}


@app.get("/projects/{project}/checks")
def checks(project: str, doc_key: str, u=Depends(user)):
    _kb(project, doc_key)
    return svc(project).checks(doc_key)


@app.get("/projects/{project}/compare")
def compare(project: str, old: str, new: str, u=Depends(user)):
    _kb(project, old), _kb(project, new)
    return svc(project).compare(old, new)


@app.post("/projects/{project}/reviews")
def review(project: str, r: Review, u=Depends(engineer)):
    if r.decision not in ("accepted", "edited", "rejected"):
        raise HTTPException(400, "decision must be accepted, edited or rejected")
    svc(project).review(r.model_dump(), u["user"])
    return {"status": "recorded"}


@app.get("/projects/{project}/reviews")
def reviews(project: str, u=Depends(user)):
    return svc(project).db.reviews(project)


@app.get("/projects/{project}/audit")
def audit(project: str, u=Depends(engineer)):
    return svc(project).db.audit_log(project)


@app.get("/projects/{project}/export", response_class=PlainTextResponse)
def export(project: str, kind: str, doc_key: str = "", u=Depends(user)):
    """kind = checks | ports | components | signals | connections  (CSV)."""
    if kind == "checks":
        rows = svc(project).checks(doc_key)
    elif kind in ("components", "ports", "signals", "connections", "interfaces", "constraints", "dids"):
        rows = _kb(project, doc_key)[kind]
    else:
        raise HTTPException(400, "unknown export kind")
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return buf.getvalue()
