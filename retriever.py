"""Hybrid retrieval: dense (ChromaDB) + BM25, fused with Reciprocal Rank Fusion; query-coverage relevance gate."""
from rank_bm25 import BM25Okapi

from .embeddings import content_tokens, tokenize


class Retriever:
    def __init__(self, cfg, store, embedder):
        self.cfg, self.store, self.embedder = cfg, store, embedder
        self._cache = {}

    def invalidate(self):
        self._cache.clear()

    def _bm25(self, doc_keys):
        key = tuple(sorted(doc_keys)) if doc_keys else ()
        if key not in self._cache:
            ids, docs, metas = self.store.all_chunks(list(key) or None)
            bm = BM25Okapi([tokenize(d) for d in docs]) if docs else None
            self._cache[key] = (bm, ids, docs, metas)
        return self._cache[key]

    def idf(self, token, doc_keys=None):
        bm = self._bm25(doc_keys)[0]
        if bm is None:
            return 1.0
        return max(bm.idf.get(token, max(bm.idf.values(), default=1.0)), 0.05)

    def search(self, query, doc_keys=None, mode=None, top_k=None):
        r = self.cfg["retrieval"]
        mode, top_k = mode or r["mode"], top_k or r["top_k"]
        ck, rrf = r["candidate_k"], r["rrf_k"]
        bm, ids, docs, metas = self._bm25(doc_keys)
        if bm is None:
            return []
        ranks = {}
        info = {}
        if mode in ("hybrid", "dense"):
            for rank, h in enumerate(self.store.dense_search(self.embedder.embed_query(query), ck, doc_keys), 1):
                ranks.setdefault(h["id"], {})["dense"] = rank
                info[h["id"]] = h
        if mode in ("hybrid", "bm25"):
            scores = bm.get_scores(tokenize(query))
            order = sorted(range(len(ids)), key=lambda i: -scores[i])[:ck]
            for rank, i in enumerate(order, 1):
                if scores[i] <= 0:
                    continue
                ranks.setdefault(ids[i], {})["bm25"] = rank
                info.setdefault(ids[i], {"id": ids[i], "text": docs[i], "meta": metas[i], "score": 0.0})
        fused = []
        for cid, rk in ranks.items():
            s = sum(1.0 / (rrf + v) for v in rk.values())
            fused.append({**info[cid], "rrf": s, "dense_rank": rk.get("dense"), "bm25_rank": rk.get("bm25")})
        fused.sort(key=lambda x: -x["rrf"])
        for i, f in enumerate(fused[:top_k], 1):
            f["rank"] = i
        return fused[:top_k]

    @staticmethod
    def coverage(question, texts):
        q = set(content_tokens(question))
        if not q:
            return 0.0
        have = set()
        for t in texts:
            have.update(content_tokens(t))
        return len(q & have) / len(q)
