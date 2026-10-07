#!/usr/bin/env python3
"""Reproducible evaluation of the AUTOSAR HLD RAG assistant.

    python Code/evaluation/evaluate.py --embedder bge --llm ollama     # final run on your machine
    python Code/evaluation/evaluate.py --embedder hash --llm extractive  # offline fallback run

Writes metrics.json, qa_results.csv, retrieval_ablation.csv, extraction_report.csv, checks_report.csv,
sample_outputs.md, metrics.png and appends to runs.jsonl (lightweight experiment tracking).
"""
import argparse
import csv
import hashlib
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Code" / "src"))
INPUT, GT = ROOT / "Input_Data", ROOT / "Input_Data" / "ground_truth"
K1, K2 = "BDC-HLD-001@1.0", "BDC-HLD-001@1.1"
CATS = ["components", "ports", "interfaces", "signals", "connections", "constraints", "dids"]


def prf(pred, gold):
    pred, gold = set(pred), set(gold)
    tp = len(pred & gold)
    p = tp / len(pred) if pred else (1.0 if not gold else 0.0)
    r = tp / len(gold) if gold else 1.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0,
            "tp": tp, "pred": len(pred), "gold": len(gold)}


def norm(s):
    return " ".join(s.lower().split())


def sha(paths):
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(Path(p).read_bytes())
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--embedder", default="auto", choices=["auto", "bge", "hash"])
    ap.add_argument("--llm", default="auto", choices=["auto", "ollama", "extractive"])
    ap.add_argument("--llm-model", default=None)
    ap.add_argument("--out", default=str(ROOT / "Evaluation_Results"))
    a = ap.parse_args()
    os.environ["HLD_DATA_DIR"] = tempfile.mkdtemp()
    from hldrag.checks import run_checks
    from hldrag.compare import compare_kbs
    from hldrag.config import config_hash, load_config
    from hldrag.pipeline import HLDService
    ov = {"embedding": {"provider": a.embedder}, "llm": {"provider": a.llm}}
    if a.llm_model:
        ov["llm"]["model"] = a.llm_model
    cfg = load_config(overrides=ov)
    s = HLDService(cfg, "eval")
    t_ing = time.time()
    for v in ("1.0", "1.1"):
        s.ingest(INPUT / f"BDC_HLD_v{v}.pdf", "eval")
    ingest_s = round(time.time() - t_ing, 2)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    qa = json.loads((GT / "qa_set.json").read_text())
    ho = json.loads((GT / "qa_heldout.json").read_text())
    M = {"run": {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), **s.info(), "config_hash": config_hash(cfg),
                 "retrieval_mode": cfg["retrieval"]["mode"], "top_k": cfg["retrieval"]["top_k"],
                 "data_sha": sha(list(INPUT.glob("*.pdf")) + [GT / "qa_set.json"]), "ingest_seconds_2docs": ingest_s,
                 "n_questions": len(qa), "n_heldout": len(ho)}}

    # 1. retrieval ablation (answerable questions, v1.0 only)
    ans_q = [q for q in qa if q["answerable"]]
    abl, rows = {}, []
    for mode in ("bm25", "dense", "hybrid"):
        hit = {1: 0, 3: 0, 6: 0}
        rr, erec = [], []
        for q in ans_q:
            hits = s.retriever.search(q["question"], [K1], mode=mode, top_k=6)
            texts = [norm(h["text"]) for h in hits]
            first = next((i for i, t in enumerate(texts, 1) if any(norm(e) in t for e in q["evidence"])), None)
            for k in hit:
                hit[k] += bool(first and first <= k)
            rr.append(1 / first if first else 0.0)
            erec.append(sum(any(norm(e) in t for t in texts) for e in q["evidence"]) / len(q["evidence"]))
        n = len(ans_q)
        abl[mode] = {"hit@1": round(hit[1] / n, 3), "hit@3": round(hit[3] / n, 3), "hit@6": round(hit[6] / n, 3),
                     "mrr": round(statistics.mean(rr), 3), "evidence_recall@6": round(statistics.mean(erec), 3)}
        rows.append({"mode": mode, **abl[mode]})
    M["retrieval_ablation"] = abl
    with open(out / "retrieval_ablation.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    # 2. end-to-end QA
    def run_set(qs, tag):
        res = []
        for q in qs:
            r = s.query(q["question"], [K1], "eval")
            a_l = r["answer"].lower()
            if q["answerable"]:
                correct = (not r["abstained"]) and all(m.lower() in a_l for m in q["must_contain"])
                cited = {x for x in __import__("re").findall(r"\[(S\d+)\]", r["answer"])}
                srcs = [x for x in r["sources"] if x["id"] in cited]
                if q["evidence"]:
                    cit_ok = any(norm(e) in norm(x["body"]) for x in srcs for e in q["evidence"]) or \
                        any(x["type"] == "kb" and any(m.lower() in x["body"].lower() for m in q["must_contain"]) for x in srcs)
                else:
                    cit_ok = any(any(m.lower() in x["body"].lower() for m in q["must_contain"]) for x in srcs)
            else:
                correct, cit_ok = r["abstained"], None
            res.append({"set": tag, "id": q["id"], "type": q["type"], "question": q["question"], "answerable": q["answerable"],
                        "correct": correct, "abstained": r["abstained"], "confidence": r["confidence"], "coverage": r["coverage"],
                        "groundedness": r["groundedness"], "citations_valid": r["citations_valid"], "citation_correct": cit_ok,
                        "latency_s": r["latency_s"], "mode": r["mode"], "answer": r["answer"].replace("\n", " // "),
                        "cited_pages": sorted({x["page"] for x in r["sources"] if x["id"] in __import__("re").findall(r"\[(S\d+)\]", r["answer"])})})
        return res

    main_res, ho_res = run_set(qa, "main"), run_set(ho, "heldout")

    def summ(res):
        ans = [r for r in res if r["answerable"]]
        oos = [r for r in res if not r["answerable"]]
        lat = sorted(r["latency_s"] for r in res)
        d = {"n": len(res), "answer_accuracy": round(sum(r["correct"] for r in ans) / len(ans), 3),
             "false_abstention_rate": round(sum(r["abstained"] for r in ans) / len(ans), 3),
             "oos_abstention_rate": round(sum(r["abstained"] for r in oos) / len(oos), 3) if oos else None,
             "avg_groundedness": round(statistics.mean(r["groundedness"] for r in ans if not r["abstained"]), 3) if any(not r["abstained"] for r in ans) else None,
             "citation_validity_rate": round(sum(r["citations_valid"] for r in ans if not r["abstained"]) / max(1, sum(not r["abstained"] for r in ans)), 3),
             "citation_correct_rate": round(sum(bool(r["citation_correct"]) for r in ans) / len(ans), 3),
             "latency_mean_s": round(statistics.mean(lat), 3), "latency_p95_s": lat[int(0.95 * (len(lat) - 1))]}
        by = {}
        for r in ans:
            by.setdefault(r["type"], []).append(r["correct"])
        d["accuracy_by_type"] = {k: round(sum(v) / len(v), 3) for k, v in by.items()}
        return d
    M["qa_main"], M["qa_heldout"] = summ(main_res), summ(ho_res)
    allr = main_res + ho_res
    with open(out / "qa_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(allr[0])); w.writeheader(); w.writerows(allr)

    # 3. extraction fidelity
    ex, rows = {}, []
    for v, key in (("1.0", K1), ("1.1", K2)):
        kb, truth = s.kb(key), json.loads((GT / f"truth_kb_v{v}.json").read_text())
        for cat in CATS:
            fields = list(truth[cat][0])
            m = prf([json.dumps({f: r[f] for f in fields}, sort_keys=True) for r in kb[cat]],
                    [json.dumps(r, sort_keys=True) for r in truth[cat]])
            ex[f"{v}:{cat}"] = m
            rows.append({"version": v, "category": cat, **m})
    tp, pr, go = (sum(x[k] for x in ex.values()) for k in ("tp", "pred", "gold"))
    M["extraction"] = {"micro": prf(range(tp), range(tp)) | {"tp": tp, "pred": pr, "gold": go,
                                                               "precision": round(tp / pr, 4), "recall": round(tp / go, 4)},
                       "per_category": ex}
    with open(out / "extraction_report.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    # 4. consistency checks vs seeded defects
    ck, crow = {}, []
    for v, key in (("1.0", K1), ("1.1", K2)):
        found = run_checks(s.kb(key))
        seeded = json.loads((GT / f"seeded_defects_v{v}.json").read_text())
        tpk = {(c["rule"], c["key"]) for c in found}
        gold = {(d["rule"], d["key"]) for d in seeded}
        ck[v] = prf(tpk, gold) | {"flagged_total": len(found)}
        crow += [{"version": v, **c} for c in found]
    M["consistency_checks"] = ck
    with open(out / "checks_report.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(crow[0])); w.writeheader(); w.writerows(crow)

    # 5. revision comparison
    exp = set(json.loads((GT / "expected_changes_v1.0_to_v1.1.json").read_text()))
    M["revision_comparison"] = prf({c["key"] for c in compare_kbs(s.kb(K1), s.kb(K2))}, exp)

    (out / "metrics.json").write_text(json.dumps(M, indent=1), encoding="utf-8")
    with open(out / "sample_outputs.md", "w", encoding="utf-8") as f:
        f.write(f"# Sample outputs (embedder={M['run']['embedder']}, generation={M['run']['llm_mode']})\n\n")
        for r in [x for x in main_res if x["id"] in ("Q02", "Q04", "Q05", "Q10", "Q21", "Q22", "O02", "O03")] + \
                [x for x in ho_res if x["id"] in ("H05", "H06", "H16")]:
            f.write(f"## {r['id']} - {r['question']}\n- result: {'CORRECT' if r['correct'] else 'INCORRECT'} | confidence: {r['confidence']} "
                    f"| coverage: {r['coverage']} | cited pages: {r['cited_pages']}\n\n> {r['answer']}\n\n")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(10, 3.4))
        modes = list(abl)
        for i, k in enumerate(["hit@1", "hit@3", "hit@6", "mrr"]):
            ax[0].bar([x + i * 0.2 for x in range(3)], [abl[m][k] for m in modes], 0.2, label=k)
        ax[0].set_xticks([x + 0.3 for x in range(3)]); ax[0].set_xticklabels(modes); ax[0].set_ylim(0, 1.05)
        ax[0].set_title("Retrieval ablation"); ax[0].legend(fontsize=7)
        labs = ["QA main", "QA held-out", "Extraction F1", "Checks recall", "Revision F1"]
        vals = [M["qa_main"]["answer_accuracy"], M["qa_heldout"]["answer_accuracy"], M["extraction"]["micro"]["f1"] if "f1" in M["extraction"]["micro"] else M["extraction"]["micro"]["recall"],
                statistics.mean(v["recall"] for v in ck.values()), M["revision_comparison"]["f1"]]
        ax[1].barh(labs, vals, color="#33507a"); ax[1].set_xlim(0, 1.05); ax[1].set_title("Headline metrics")
        for i, v in enumerate(vals):
            ax[1].text(v + 0.01, i, f"{v:.2f}", va="center", fontsize=8)
        fig.tight_layout(); fig.savefig(out / "metrics.png", dpi=140); plt.close(fig)
    except Exception as ex:  # noqa: BLE001
        print("chart skipped:", ex)
    with open(out / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({**M["run"], "qa_main_acc": M["qa_main"]["answer_accuracy"], "qa_heldout_acc": M["qa_heldout"]["answer_accuracy"],
                            "hybrid_mrr": abl["hybrid"]["mrr"]}) + "\n")
    print(json.dumps({k: M[k] for k in ("run", "retrieval_ablation", "qa_main", "qa_heldout", "consistency_checks", "revision_comparison")}, indent=1))
    print("extraction micro:", M["extraction"]["micro"])


if __name__ == "__main__":
    main()
