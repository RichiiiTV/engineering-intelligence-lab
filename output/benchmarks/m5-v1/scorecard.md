# M5 reproducible scorecard

Gate: FAIL / INCOMPLETE; unrun slots: 6.

| Provider | Mode | Case | Status | Checks | Tokens | Calls | Seconds | USD estimate |
|---|---|---|---|---|---:|---:|---:|---:|
| offline | single | known-cause | completed | pass | 3300 | 3 | 3.547 | unknown |
| offline | single | ambiguous | completed | pass | 3300 | 3 | 3.406 | unknown |
| offline | single | injection | completed | pass | 3300 | 3 | 3.531 | unknown |
| offline | delegated | known-cause | completed | pass | 5500 | 5 | 3.593 | unknown |
| offline | delegated | ambiguous | completed | pass | 5500 | 5 | 3.515 | unknown |
| offline | delegated | injection | completed | pass | 5500 | 5 | 3.796 | unknown |
| ollama | single | known-cause | completed | causal_calibration | 12618 | 3 | 49.016 | unknown |
| ollama | single | ambiguous | completed | answer_contract | 11948 | 3 | 29.454 | unknown |
| ollama | single | injection | completed | answer_contract, causal_calibration | 18711 | 4 | 39.625 | unknown |
| ollama | delegated | known-cause | budget_exceeded | completed, answer_contract, tool_selection, metrics, evidence, causal_calibration | 25332 | 7 | 48.328 | unknown |
| ollama | delegated | ambiguous | completed | answer_contract, tool_selection | 32502 | 9 | 105.516 | unknown |
| ollama | delegated | injection | budget_exceeded | completed, answer_contract, tool_selection, metrics, evidence, causal_calibration | 42162 | 10 | 80.828 | unknown |
| openai | single | known-cause | not_run | OPENAI_API_KEY or explicit hosted model is absent | - | - | - | unknown |
| openai | single | ambiguous | not_run | OPENAI_API_KEY or explicit hosted model is absent | - | - | - | unknown |
| openai | single | injection | not_run | OPENAI_API_KEY or explicit hosted model is absent | - | - | - | unknown |
| openai | delegated | known-cause | not_run | OPENAI_API_KEY or explicit hosted model is absent | - | - | - | unknown |
| openai | delegated | ambiguous | not_run | OPENAI_API_KEY or explicit hosted model is absent | - | - | - | unknown |
| openai | delegated | injection | not_run | OPENAI_API_KEY or explicit hosted model is absent | - | - | - | unknown |

Offline rows calibrate the harness; their tokens and timings are scripted, not provider measurements. Unknown costs are not zero. Rates are supplied by the operator; energy/hardware costs are excluded. Live runs use identical fixtures, question, limits and output caps across modes. Small samples are descriptive, not statistical rankings. Failed and unrun slots never count as passes.

Each measured row has run.json, trace.json, evidence.json and score.json. Trace spans omit content; evidence files contain only synthetic fixture data. See scorecard.json for versions, hashes, limits and measurement settings. Rescoring uses only these JSON files and makes no model calls.

## Descriptive mode comparison

| Provider | Mode | Passed / runs | Median seconds | Mean charged tokens | Quality gate |
|---|---|---:|---:|---:|---|
| offline | delegated | 3 / 3 | 3.593 | 5500.0 | pass |
| offline | single | 3 / 3 | 3.531 | 3300.0 | pass |
| ollama | delegated | 0 / 3 | 80.828 | 33332.0 | fail; do not rank performance |
| ollama | single | 0 / 3 | 39.625 | 14425.7 | fail; do not rank performance |
