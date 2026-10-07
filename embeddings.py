"""Tokenisation and embedding back-ends.

* BGEEmbedder  - BAAI/bge-small-en-v1.5 via sentence-transformers (primary; local after one-time download)
* HashEmbedder - deterministic offline lexical hashing embedder (fallback when BGE cannot be loaded)
"""
import logging
import re
import zlib
from collections import Counter

import numpy as np

log = logging.getLogger(__name__)

STOPWORDS = set("""a an the of in on at to for by from with and or if is are was were be been being do does did
what which who whom whose when where why how there their it its this that these those as than then into out
can could will would should may might must has have had list describe explain tell give show about between
long many much happen happens fast steps step flow""".split())


def stem(t):
    if len(t) > 4 and t.endswith("ing"):
        return t[:-3]
    if len(t) > 4 and t.endswith("ed"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def _parts(word):
    out = []
    for seg in re.split(r"[_\.\-]", word):
        for sub in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", seg):
            out.append(sub.lower())
    return out


def part_tokens(text):
    """Stemmed sub-word tokens (identifiers split on _ . - and camelCase)."""
    toks = []
    for w in re.findall(r"[A-Za-z0-9]+(?:[_\.\-][A-Za-z0-9]+)*", text or ""):
        toks.extend(stem(p) for p in _parts(w))
    return toks


def tokenize(text):
    """Full lower-cased identifiers + stemmed sub-word tokens (BM25 and hashing)."""
    toks = []
    for w in re.findall(r"[A-Za-z0-9]+(?:[_\.\-][A-Za-z0-9]+)*", text or ""):
        parts = [stem(p) for p in _parts(w)]
        if len(parts) != 1 or w.lower() != parts[0]:
            toks.append(w.lower())
        toks.extend(parts)
    return toks


def content_tokens(text):
    return [t for t in part_tokens(text) if t not in STOPWORDS and len(t) > 1]


class HashEmbedder:
    def __init__(self, dim=1024):
        self.dim = dim
        self.name = f"hash{dim}"

    def _vec(self, text):
        v = np.zeros(self.dim, dtype=np.float32)
        for tok, c in Counter(tokenize(text)).items():
            h = zlib.crc32(tok.encode())
            v[h % self.dim] += np.log1p(c)
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_documents(self, texts):
        return [self._vec(t).tolist() for t in texts]

    def embed_query(self, text):
        return self._vec(text).tolist()


class BGEEmbedder:
    def __init__(self, model, instruction):
        from sentence_transformers import SentenceTransformer  # heavy import, only when needed
        self.model = SentenceTransformer(model)
        self.instruction = instruction
        self.name = model.split("/")[-1].lower()

    def embed_documents(self, texts):
        return self.model.encode(texts, normalize_embeddings=True, batch_size=32).tolist()

    def embed_query(self, text):
        return self.model.encode([self.instruction + text], normalize_embeddings=True)[0].tolist()


def get_embedder(cfg):
    e = cfg["embedding"]
    prov = e.get("provider", "auto")
    if prov in ("bge", "auto"):
        try:
            return BGEEmbedder(e["model"], e.get("query_instruction", ""))
        except Exception as ex:  # noqa: BLE001
            if prov == "bge":
                raise
            log.warning("BGE embedder unavailable (%s); using offline hash embedder", ex)
    return HashEmbedder(e.get("hash_dim", 1024))
