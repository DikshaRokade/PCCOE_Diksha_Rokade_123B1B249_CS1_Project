"""HLDService: single entry point used by the API, CLI and evaluation scripts."""
import json
import logging
import re
from pathlib import Path

from .checks import run_checks
from .compare import compare_docs
from .config import load_config
from .db import Database
from .embeddings import get_embedder
from .extract import build_kb
from .ingest import parse_pdf
from .llm import get_llm
from .rag import RAGPipeline
from .retriever import Retriever
from .store import VectorStore

log = logging.getLogger(__name__)
_SHARED = {}


class KBLoader:
    def __init__(self, svc):
        self.svc = svc

    def all_keys(self):
        return [d["doc_key"] for d in self.svc.db.docs(self.svc.project)]

    def load(self, doc_key):
        p = self.svc.kb_path(doc_key)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


class HLDService:
    def __init__(self, cfg=None, project=None):
        self.cfg = cfg or load_config()
        self.project = re.sub(r"[^A-Za-z0-9_-]", "_", project or self.cfg.get("project", "default"))
        sig = json.dumps([self.cfg["embedding"], self.cfg["llm"]], sort_keys=True)
        if _SHARED.get("sig") != sig:  # models are loaded once per process
            _SHARED.update(sig=sig, embedder=get_embedder(self.cfg), llm=get_llm(self.cfg))
        self.embedder, self.llm = _SHARED["embedder"], _SHARED["llm"]
        self.store = VectorStore(self.cfg, self.embedder, self.project)
        self.retriever = Retriever(self.cfg, self.store, self.embedder)
        self.db = Database(self.cfg)
        self.kb_dir = Path(self.cfg["paths"]["data_dir_abs"]) / "kb" / self.project
        self.kb_dir.mkdir(parents=True, exist_ok=True)
        self.rag = RAGPipeline(self.cfg, self.retriever, self.llm, KBLoader(self))

    def info(self):
        return {"project": self.project, "embedder": self.embedder.name, "llm_mode": self.llm.mode,
                "llm_model": self.cfg["llm"]["model"] if self.llm.mode == "ollama" else None}

    def kb_path(self, doc_key):
        return self.kb_dir / (doc_key.replace("@", "_v") + ".json")

    def ingest(self, pdf_path, user="cli"):
        c = self.cfg["chunking"]
        parsed = parse_pdf(pdf_path, c["max_chars"], c["overlap_sentences"])
        kb = build_kb(parsed)
        self.store.delete_doc(kb["doc_key"])
        self.store.add_chunks(kb["doc_key"], kb["doc_id"], kb["version"], parsed["chunks"])
        self.kb_path(kb["doc_key"]).write_text(json.dumps(kb, indent=1), encoding="utf-8")
        self.db.upsert_doc(self.project, kb, len(parsed["chunks"]), user)
        self.db.audit(self.project, user, "ingest", f"{kb['doc_key']} sha256={kb['sha256'][:12]} chunks={len(parsed['chunks'])}")
        self.retriever.invalidate()
        return {"doc_key": kb["doc_key"], "pages": kb["pages"], "chunks": len(parsed["chunks"]),
                "components": len(kb["components"]), "ports": len(kb["ports"]), "signals": len(kb["signals"]),
                "connections": len(kb["connections"])}

    def docs(self):
        return self.db.docs(self.project)

    def kb(self, doc_key):
        kb = self.rag.kb_loader.load(doc_key)
        if kb is None:
            raise KeyError(doc_key)
        return kb

    def query(self, question, doc_keys=None, user="cli", mode=None):
        res = self.rag.answer(question, doc_keys, mode=mode)
        self.db.audit(self.project, user, "query", f"{question} | abstained={res['abstained']} conf={res['confidence']}")
        return res

    def checks(self, doc_key):
        return run_checks(self.kb(doc_key))

    def compare(self, old_key, new_key):
        return compare_docs(self.kb(old_key), self.kb(new_key))

    def review(self, payload, user):
        self.db.add_review(self.project, user, payload)
        self.db.audit(self.project, user, "review", f"{payload['decision']} | {payload['question']}")
