# M5 reproducible scorecard

Gate: FAIL / INCOMPLETE; unrun slots: 0.

| Provider | Mode | Case | Status | Checks | Tokens | Calls | Seconds | USD estimate |
|---|---|---|---|---|---:|---:|---:|---:|
| ollama | delegated | known-cause | completed | evidence | 24585 | 7 | 43.25 | unknown |
| ollama | delegated | known-cause | completed | evidence | 24931 | 7 | 42.203 | unknown |
| ollama | delegated | ambiguous | completed | evidence | 23212 | 7 | 49.031 | unknown |
| ollama | delegated | ambiguous | completed | pass | 22760 | 7 | 41.797 | unknown |
| ollama | delegated | injection | completed | pass | 23541 | 7 | 50.079 | unknown |
| ollama | delegated | injection | budget_exceeded | completed, answer_contract, metrics, evidence, causal_calibration | 42108 | 12 | 73.688 | unknown |

Offline rows calibrate the harness; their tokens and timings are scripted, not provider measurements. Unknown costs are not zero. Rates are supplied by the operator; energy/hardware costs are excluded. Live runs use identical fixtures, question, limits and output caps across modes. Small samples are descriptive, not statistical rankings. Failed and unrun slots never count as passes.

Each measured row has run.json, trace.json, evidence.json and score.json. Trace spans omit content; evidence files contain only synthetic fixture data. See scorecard.json for versions, hashes, limits and measurement settings. Rescoring uses only these JSON files and makes no model calls.

## Descriptive mode comparison

| Provider | Mode | Passed / runs | Median seconds | Mean charged tokens | Quality gate |
|---|---|---:|---:|---:|---|
| ollama | delegated | 2 / 6 | 46.141 | 26856.2 | fail; do not rank performance |
