# Model, prompt and configuration details

| Item | Value |
|---|---|
| LLM | Qwen2.5-7B-Instruct, Ollama tag `qwen2.5:7b-instruct`, local; configurable in `config.yaml` (`llm.model`) |
| Generation settings | temperature 0, num_ctx 4096, answers from numbered sources only |
| Embedding model | BAAI/bge-small-en-v1.5 (sentence-transformers, normalised, query instruction prefix) |
| Fallbacks | `hash1024` embedder and extractive generator when the above are unavailable (recorded in every run) |
| Vector store | ChromaDB persistent client, cosine, collection `<project>__<embedder>` |
| Lexical retrieval | BM25Okapi over identifier-aware tokens; fusion RRF k=60; top_k 6; candidate_k 20 |
| Chunking | sections split to max 900 characters, 1-sentence overlap; one chunk per table row |
| Relevance gate | abstain if < 60 % of query content terms appear in the evidence |
| Prompts | `prompts/system_prompt.txt`, `prompts/answer_prompt.txt` |
| Tools | `kb_tools.py` (ports, dependencies, signals, interfaces, DIDs), `checks.py` (R1-R7), `compare.py` |

**Reproducibility:** each evaluation run logs the config hash, input data hash, embedder and generation mode in `Evaluation_Results/runs.jsonl` and `metrics.json`.
**Intended use:** decision support for engineers reviewing HLDs. Not for compliance or release decisions without human review.
