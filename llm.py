"""Answer generation: local Ollama LLM (primary) or deterministic extractive generator (offline fallback)."""
import logging
import re

import requests

from .config import read_prompt
from .embeddings import content_tokens

log = logging.getLogger(__name__)
SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def format_sources(sources):
    lines = []
    for s in sources:
        lines.append(f"[{s['id']}] (v{s['version']}, page {s['page']}, section {s['section']}, {s['type']}) {s['body']}")
    return "\n".join(lines)


class LLMUnavailable(Exception):
    pass


class OllamaLLM:
    mode = "ollama"

    def __init__(self, cfg):
        self.cfg, self.c = cfg, cfg["llm"]
        self.system = read_prompt(cfg, "system_prompt.txt")
        self.template = read_prompt(cfg, "answer_prompt.txt")

    def available(self):
        try:
            r = requests.get(self.c["host"] + "/api/tags", timeout=1.5)
            names = [m["name"] for m in r.json().get("models", [])]
            return any(n == self.c["model"] or n.startswith(self.c["model"].split(":")[0]) for n in names)
        except Exception:  # noqa: BLE001
            return False

    def generate(self, question, sources, retriever=None):
        user = self.template.format(question=question, sources=format_sources(sources))
        try:
            r = requests.post(self.c["host"] + "/api/chat", timeout=self.c["timeout_s"], json={
                "model": self.c["model"], "stream": False,
                "messages": [{"role": "system", "content": self.system}, {"role": "user", "content": user}],
                "options": {"temperature": self.c["temperature"], "num_ctx": self.c["num_ctx"]}})
            r.raise_for_status()
            return r.json()["message"]["content"].strip()
        except Exception as ex:  # noqa: BLE001
            raise LLMUnavailable(str(ex)) from ex


class ExtractiveGenerator:
    """No-LLM generator: returns the most relevant source sentences, each tagged with its citation."""
    mode = "extractive"

    def __init__(self, cfg):
        self.max_sents = cfg["generation"]["extractive_max_sentences"]

    def generate(self, question, sources, retriever=None):
        q = content_tokens(question)
        qset = set(q)
        w = {t: (retriever.idf(t) if retriever else 1.0) for t in qset}
        total = sum(w.values()) or 1.0
        out, cands = [], []
        for s in sources:
            if s["type"] == "kb":
                out.append(f"{s['body']} [{s['id']}]")
        steps = re.search(r"\b(steps?|flow|sequence|procedure)\b", question.lower())
        used_full = False
        for s in sources:
            if s["type"] == "kb":
                continue
            if steps and s["type"] == "text" and not used_full:
                out.append(f"{s['body'][:1500]} [{s['id']}]")
                used_full = True
                continue
            pieces = [s["body"]] if s["type"] == "table" else SENT.split(s["body"])
            for p in pieces:
                have = set(content_tokens(p))
                sc = sum(w[t] for t in qset & have) / total
                if sc > 0:
                    cands.append((sc, s["rank_pos"], p.strip(), s["id"]))
        cands.sort(key=lambda c: (-c[0], c[1]))
        picked = [c for c in cands if c[0] >= 0.3][: self.max_sents] or cands[:1]
        for _, _, text, sid in picked:
            out.append(f"{text} [{sid}]")
        return "\n".join(out)


def get_llm(cfg):
    prov = cfg["llm"].get("provider", "auto")
    if prov in ("ollama", "auto"):
        o = OllamaLLM(cfg)
        if prov == "ollama" or o.available():
            return o
        log.warning("Ollama model not reachable; using extractive generator")
    return ExtractiveGenerator(cfg)
