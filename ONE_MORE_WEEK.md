# What I would do with one more week

1. **MySQL.** Move from SQLite to MySQL with a genuinely read-only database user for the SQL tool, add it to `docker compose`, and build and test the Docker images in CI.
2. **Better language understanding.** Replace the keyword router and question parser with an LLM classifier and slot extractor, validated by the same deterministic checks. The evaluation failures (cross-topic comparison, publisher-aware filters, paraphrased privacy requests) all come from this layer.
3. **Multi-turn context.** Carry the topic and region across messages so "and for APAC?" works.
4. **Retrieval quality.** Real hybrid search with BM25, a cross-encoder re-ranker, and table and chart extraction from PDFs.
5. **Confidence calibration.** Fit the confidence score against labelled outcomes instead of hand-set weights.
6. **Observability.** Langfuse traces, cost dashboards and an alert on injection attempts and escalation volume.
7. **Evaluation.** Grow the set to 100+ questions with paraphrases, run it in CI and fail the build on regressions.
