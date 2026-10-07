"""ChromaDB persistent vector store (one collection per project + embedder)."""
import re
from pathlib import Path

import chromadb


def _where(doc_keys):
    if not doc_keys:
        return None
    return {"doc_key": doc_keys[0]} if len(doc_keys) == 1 else {"doc_key": {"$in": list(doc_keys)}}


class VectorStore:
    def __init__(self, cfg, embedder, project):
        path = Path(cfg["paths"]["data_dir_abs"]) / "chroma"
        path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(path))
        name = re.sub(r"[^A-Za-z0-9_-]", "_", f"{project}__{embedder.name}")[:60]
        self.col = self.client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"}, embedding_function=None)
        self.embedder = embedder

    def delete_doc(self, doc_key):
        self.col.delete(where={"doc_key": doc_key})

    def add_chunks(self, doc_key, doc_id, version, chunks):
        if not chunks:
            return
        embs = self.embedder.embed_documents([c["text"] for c in chunks])
        self.col.upsert(
            ids=[f"{doc_key}#{c['idx']}" for c in chunks],
            documents=[c["text"] for c in chunks],
            embeddings=embs,
            metadatas=[{"doc_key": doc_key, "doc_id": doc_id, "version": version, "page": c["page"],
                        "section": c["section"], "type": c["type"], "prefix_len": len(c["prefix"])} for c in chunks])

    def all_chunks(self, doc_keys=None):
        r = self.col.get(where=_where(doc_keys), include=["documents", "metadatas"])
        return r["ids"], r["documents"], r["metadatas"]

    def dense_search(self, qvec, k, doc_keys=None):
        n = self.col.count()
        if n == 0:
            return []
        r = self.col.query(query_embeddings=[qvec], n_results=min(k, n), where=_where(doc_keys),
                           include=["documents", "metadatas", "distances"])
        return [{"id": i, "text": d, "meta": m, "score": 1 - dist}
                for i, d, m, dist in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0])]

    def count(self, doc_key=None):
        return len(self.all_chunks([doc_key])[0]) if doc_key else self.col.count()
