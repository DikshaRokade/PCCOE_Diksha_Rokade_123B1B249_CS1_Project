"""RAG pipeline: KB tools + hybrid retrieval -> relevance gate -> grounded generation -> citation validation."""
import re
import time

from .kb_tools import KBTools
from .llm import ExtractiveGenerator, LLMUnavailable
from .retriever import Retriever

ABSTAIN = "Insufficient evidence in the approved documents to answer this question."
CITE = re.compile(r"\[(S\d+)\]")


class RAGPipeline:
    def __init__(self, cfg, retriever, llm, kb_loader):
        self.cfg, self.retriever, self.llm, self.kb_loader = cfg, retriever, llm, kb_loader
        self.fallback = ExtractiveGenerator(cfg)

    def answer(self, question, doc_keys=None, mode=None):
        t0 = time.time()
        rc, gc = self.cfg["retrieval"], self.cfg["generation"]
        facts = []
        for dk in doc_keys or self.kb_loader.all_keys():
            kb = self.kb_loader.load(dk)
            if kb:
                facts += KBTools(kb).facts_for(question)
        hits = self.retriever.search(question, doc_keys, mode=mode)
        cov = Retriever.coverage(question, [h["text"] for h in hits] + [f["text"] for f in facts])
        multi = len({h["meta"]["version"] for h in hits} | {f["version"] for f in facts}) > 1
        sources = []
        for f in facts:
            sources.append({"type": "kb", "version": f["version"], "page": f["page"], "section": f["section"],
                            "body": f["text"], "score": 1.0, "doc_key": f["doc_key"]})
        for h in hits:
            m = h["meta"]
            sources.append({"type": m["type"], "version": m["version"], "page": m["page"], "section": m["section"],
                            "body": h["text"][m["prefix_len"]:], "score": round(h["rrf"], 4), "doc_key": m["doc_key"]})
        sources = sources[: gc["max_context_sources"] + len(facts)]
        for i, s in enumerate(sources, 1):
            s["id"], s["rank_pos"] = f"S{i}", i
        res = {"question": question, "sources": sources, "coverage": round(cov, 3), "needs_review": True}
        if cov < rc["min_query_coverage"] or not sources:
            return {**res, "answer": ABSTAIN, "abstained": True, "confidence": "none", "mode": "gate",
                    "groundedness": 1.0, "citations_valid": True, "latency_s": round(time.time() - t0, 3)}
        mode_used = self.llm.mode
        try:
            text = self.llm.generate(question, sources, self.retriever)
        except LLMUnavailable:
            text, mode_used = self.fallback.generate(question, sources, self.retriever), "extractive(fallback)"
        valid_ids = {s["id"] for s in sources}
        used = CITE.findall(text)
        invalid = [u for u in used if u not in valid_ids]
        for u in invalid:
            text = text.replace(f"[{u}]", "")
        if "INSUFFICIENT_EVIDENCE" in text:
            return {**res, "answer": ABSTAIN, "abstained": True, "confidence": "none", "mode": mode_used,
                    "groundedness": 1.0, "citations_valid": True, "latency_s": round(time.time() - t0, 3)}
        lines = [l for l in re.split(r"(?<=[.!?])\s+(?!\[)|\n", text) if l.strip() and not l.startswith("(Evidence")]
        cited = [l for l in lines if CITE.search(l)]
        groundedness = round(len(cited) / len(lines), 3) if lines else 0.0
        conf = "high" if cov >= 0.85 and groundedness >= 0.99 and not invalid else ("medium" if groundedness > 0.5 else "low")
        if multi:
            text += "\n(Evidence spans more than one document version - check the version of each source.)"
        return {**res, "answer": text.strip(), "abstained": False, "confidence": conf, "mode": mode_used,
                "groundedness": groundedness, "citations_valid": not invalid and bool(used),
                "latency_s": round(time.time() - t0, 3)}
