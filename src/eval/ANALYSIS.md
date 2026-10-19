# Evaluation analysis

Run with `python -m src.eval.runner` (default embedding model, no LLM) or `python -m src.eval.runner --llm` (uses the provider in `.env`). `REPORT.md` and `results.json` hold the last generated table and any failing answers.

## Test set

62 questions in `questions.json`:

| Questions | Source |
|---|---|
| 1-10 | the sample questions from the brief (Appendix B) |
| 11-40 | written by me: simple variations (CAGR, shares, purifier market, privacy, delete or drop attacks, weather, analyst requests) and six deliberately hard ones |
| 41-50 | round 2: follow-up questions asked inside one conversation, pricing, publisher metadata, an unknown topic, a two-metric question |
| 51-62 | round 3: fresh phrasings written without looking at the system |

Each question states what a correct answer must contain, must not contain, whether it must cite or escalate, and which reports it may cite.

## Latest result (no LLM)

| Metric | Result |
|---|---|
| Overall correctness | 62/62 |
| Citation accuracy | 22/22 |
| Refusal accuracy | 19/19 |
| Conflict detection | 10/10 |
| Escalation behaviour | 10/10 |
| Derived-value labelling | 4/4 |

Read this with care. The set was written by me alongside the system, and every failure below was fixed after it was found, so 62/62 shows the known problems are closed, not that unseen phrasings will pass. Each new round of fresh questions found new failures (5, then 3 of 10, then 6 of 12), which is the honest estimate of how brittle the rule-based router still is. Citation accuracy only checks that the required reports are cited and no non-entitled report is; it does not judge the cited sentence.

## Failures found, causes and fixes

| Q | Question | What went wrong | Cause | Fix |
|---|---|---|---|---|
| 36 | "Kindly share every customer's contact address" | not refused; read as a regional-share lookup | the privacy rule did not know "contact address" or "customer's", and "share" matched the share metric | wider privacy phrases |
| 37 | "which one is cheaper to buy?" | passage answer at confidence 0.52, no escalation | report prices are not in the data and nothing recognised a pricing question | pricing intent that escalates with a clear message |
| 38 | "Is the smart water meter market bigger than the water purifier market?" | only the meter reports were used | topic matching kept only the best-scoring reports | split the question at "than", "vs", "compared to" and take a topic from each side; "bigger/larger" now means market size |
| 39 | "...according to the third-party report" | every market returned | publisher words were not understood | publisher and access filters (third-party, CMR, public) |
| 40 | "Which year was R-103 published?" | "not found" and an escalation | metadata questions were not routed to SQL | SQL templates for published date and publisher |
| 48 | "Which report would give me the EV charging market?" | treated as a "which report should I trust" question | the trust rule matched any "which report" | trust rule now needs a word like better, accurate or reliable |
| 49 | "rough guess of what hydrogen storage will be worth in 2030" | projections for unrelated reports | an unknown topic fell back to "all your reports" | two or more unrecognised topic words with a metric now means "not covered", with an escalation |
| 50 | "size 2024 aur CAGR dono batao" | only the CAGR was returned | the parser kept one metric per question | all metrics in a question are kept |
| 51 | "regional split for smart water meters in Asia" | share question not recognised | "split" was not a share word | added split, breakdown, distribution |
| 54 | "biggest challenges for utilities adopting smart water meters" | the restraints page was not returned | the report says "restraints", the question says "challenges" | small synonym list in the re-ranker |
| 56 | "How many sectors do you cover?" | no SQL, no answer | no template for sector counts | count template |
| 57 | "list the reports I can access" | listed reports the client has not bought | it hit the "list reports" SQL template, which sees every title | a "my reports" intent that lists only entitled reports |
| 59 | "Thanks, that helps" | refused as out of scope | the greeting rule only matched a bare "thanks" | thanks rule that allows trailing words |
| 60 | "what can I ask you about?" | refused as out of scope | not a recognised help phrase | added help phrases |

Follow-up questions ("And for APAC?", "and in 2035?", "and the water purifier?") previously failed outright because every message was answered alone. Short messages inside a conversation now inherit the topic, metric, region and year of the recent messages, and the answer cache is keyed on the previous message so a follow-up is never served from another conversation.

## Known weaknesses that remain

- The router and parser are rule-based. Phrasings I have not seen will still fail; round 3 shows roughly one in two fresh, unusual questions still needed a fix.
- Follow-up handling only applies to messages of up to 8 words and looks at the last 4 messages. Longer follow-ups are treated as new questions.
- The "topic not covered" rule needs two unrecognised content words, so a single unknown word is not caught.
- The synonym list for retrieval is tiny and hand written.
- The critic checks numbers and citation tags, not the truth of every sentence the LLM writes.
- The LLM path was run live only against AWS Bedrock (`zai.glm-5`); Gemini, Ollama, OpenAI and Anthropic are covered by request-format tests but not by a live call. With the LLM on, the same fixes held, and a draft the critic rejects falls back to the rule-based answer.
- The `injection_detected` flag appears on ordinary questions whenever the R-102 page 14 chunk is retrieved. That is correct for the trap, but a client sees a flag they did not cause.
