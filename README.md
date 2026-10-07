# Evaluation evidence
* `metrics.json` - all metrics with run configuration (embedder, generation mode, hashes). **Check `run.embedder` and `run.llm_mode` first.**
* `qa_results.csv` - every question, answer, confidence, groundedness, citation checks, cited pages (main and held-out sets).
* `retrieval_ablation.csv` - BM25 vs dense vs hybrid (Hit@k, MRR, evidence recall).
* `extraction_report.csv`, `checks_report.csv` - extraction P/R/F1 per category; every flagged consistency item with page.
* `sample_outputs.md` - selected answers with citations, including failures and out-of-scope refusals.
* `metrics.png`, `runs.jsonl` - chart and run history.

The files currently in this folder come from the **offline fallback configuration** (hash embeddings + extractive generation). Replace them by running `python Code/evaluation/evaluate.py --embedder bge --llm ollama` and `python Code/scripts/build_report.py`.
