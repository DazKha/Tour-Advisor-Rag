# RAG Quality Baseline Improvement Design

**Date:** 2026-10-23

## Objective

Improve the retrieval and answer-generation quality of the Vietravel tour assistant, evaluate the final candidate on the existing 30-case dataset, and publish that candidate as the only baseline used in the take-home report.

The work is limited to RAG retrieval, answer generation, structured-output reliability, and the metrics required by `reference/De_1_Tro_ly_tu_van_tour_RAG.docx`. It does not add or expand guardrail-specific tests.

## Source Requirements

The take-home brief requires:

- an evaluation set with at least 30 normal, difficult/deceptive, and out-of-scope questions;
- accuracy;
- the rate of incorrect or fabricated answers;
- p50 and p95 latency; and
- estimated cost per 1,000 questions.

The existing 30-case dataset remains fixed during optimization so that metric changes reflect system behavior rather than changed expectations. Difficult, deceptive, and out-of-scope cases remain in the dataset, but this work will not create a separate guardrail test track.

## Metric Definitions

The final report will use the following explicit mapping:

| Report requirement | Metric |
|---|---|
| Accuracy | Ragas Answer Correctness mean over finite scores |
| Incorrect or fabricated answer rate | `1 - Faithfulness` and the percentage of evaluated cases whose Faithfulness score is below `1.0` |
| Retrieval quality | Ragas Context Precision with reference and Context Recall |
| Generation quality | Ragas Faithfulness, Answer Relevancy, and Answer Correctness |
| Latency | End-to-end p50 and p95 across all attempted evaluation cases |
| Cost | Observed generation and judge token cost, plus projected cost per 1,000 attempted questions |

Every Ragas metric must include its finite-score numerator and total case count. Missing judge scores remain missing and are never converted to zero. The final report must disclose any same-family judge bias and any provider failures that reduce score coverage.

Gemini embedding cost is reported separately when usage data is available. If the provider does not expose that usage, the report states that embedding cost is excluded rather than estimating an unsupported value.

## Technical Scope

### Retrieval

The retrieval investigation starts from the cases whose correct reference chunks were absent or diluted in the prior run. Changes may cover:

- exact tour resolution for explicit and conversational references;
- preserving the active tour across follow-up turns;
- section-aware retrieval for child price, itinerary, price, inclusion, exclusion, payment, visa, and baggage questions;
- deterministic inclusion of full-itinerary evidence only when the question requests the full program; and
- limiting irrelevant chunks that reduce Context Precision.

Retrieval changes must preserve stable chunk IDs and the existing source-authority rules. The evaluation dataset and reference context IDs are not changed to improve scores.

### Generation

Generation work covers:

- making the answer prompt focus on the user's requested facts;
- requiring every factual claim and number to be supported by approved context;
- keeping answers concise enough to avoid irrelevant claims;
- preserving valid citations; and
- making structured DeepSeek output resilient to malformed JSON without silently inventing an answer.

Parser recovery must be bounded. A malformed structured response may receive one repair or retry attempt. If it still fails, the evaluation records the provider/parser error and does not fabricate a successful result.

### Excluded Work

This iteration does not:

- add guardrail-specific unit tests;
- redesign safety policy or the user interface;
- modify source PDFs, reviewed chunk IDs, or reference answers to raise metrics;
- create a before/after comparison report; or
- repeatedly tune against Ragas judge output without a fixed iteration limit.

## Evaluation Flow

1. Reproduce and classify current retrieval and generation failures by case.
2. Add focused regression tests for retrieval, generation, and structured-output behavior only.
3. Apply one root-cause change at a time and run the relevant offline tests.
4. Run the full 30-case evaluation with Ragas disabled, capturing completion count, latency, token usage, and deterministic diagnostics.
5. Repeat for at most three full deterministic evaluation rounds.
6. Stop early when two consecutive rounds improve none of the retrieval or generation failures by at least one case, or when p95 latency rises more than 20% above 15,095 ms without a clear quality gain.
7. Select the best complete candidate. A reportable candidate must complete all 30 graph cases.
8. Run Ragas once for the selected candidate, with sufficient provider balance for all five metrics.
9. Publish the final artifacts and update the README with only the selected baseline.

The final Ragas run is not repeated solely to chase a more favorable stochastic judge score. A failed or partial judge run may be retried only after correcting an external provider issue such as insufficient balance.

## Baseline Selection

The selected baseline prioritizes:

1. completion of all 30 graph cases;
2. retrieval coverage and precision;
3. generation correctness and faithfulness;
4. answer relevancy; and
5. latency, with p95 regression constrained as described above.

If no candidate satisfies every desired quality level within three rounds, the highest-quality complete candidate becomes the baseline. The final report states its remaining errors and limitations without showing a before/after comparison.

Canonical output files are:

- `results/eval_results.json` for per-case outputs;
- `results/eval_summary.json` for aggregate metrics, latency, usage, cost, and limitations; and
- `README.md` for the report-ready evaluation summary.

## Verification

Verification is proportional to the selected scope:

- focused retrieval tests validate tour scoping, follow-up resolution, section coverage, and irrelevant-context control;
- generation tests validate grounded concise answers, citation preservation, and bounded parser recovery;
- evaluation tests validate metric calculations, strict JSON serialization, finite-score counts, hallucination-rate derivation, latency percentiles, and cost projection;
- a 30-case provider-backed run validates end-to-end completion and latency; and
- one final Ragas run produces Context Precision, Context Recall, Faithfulness, Answer Relevancy, and Answer Correctness.

No completion claim is made from unit tests alone. Final reported numbers must come from the saved provider-backed artifacts.

## Reporting Rules

The README and final report present only the new baseline. They include:

- dataset size and completed-case count;
- all five Ragas metrics with finite-score coverage;
- accuracy and incorrect/fabricated-answer metrics using the definitions above;
- p50/p95 latency;
- observed cost and estimated cost per 1,000 questions;
- remaining failure patterns and likely causes; and
- limitations, including judge bias, missing provider usage, or incomplete metric coverage.

The old baseline remains available through Git history and is not summarized in the new report.
