# M5 reproducible scorecard

Gate: FAIL / INCOMPLETE; unrun slots: 0.

| Provider | Mode | Case | Status | Checks | Tokens | Calls | Seconds | USD estimate |
|---|---|---|---|---|---:|---:|---:|---:|
| ollama | single | other-station | budget_exceeded | completed, contract, metrics, causal_calibration, citations | 34605 | - | 39.98499999998603 | unknown |
| ollama | single | other-station | budget_exceeded | completed, contract, metrics, causal_calibration, citations | 34620 | - | 37.81299999996554 | unknown |
| ollama | single | no-increase | budget_exceeded | completed, contract, metrics, causal_calibration, citations | 33911 | - | 36.71899999992456 | unknown |
| ollama | single | no-increase | budget_exceeded | completed, contract, metrics, causal_calibration, citations | 42115 | - | 41.45299999997951 | unknown |
| ollama | single | conflicting-records | budget_exceeded | completed, contract, metrics, causal_calibration, citations | 11811 | - | 18.781000000075437 | unknown |
| ollama | single | conflicting-records | budget_exceeded | completed, contract, metrics, causal_calibration, citations | 30439 | - | 56.95299999997951 | unknown |
| ollama | single | missing-document | completed | pass | 16109 | - | 21.95299999997951 | unknown |
| ollama | single | missing-document | completed | pass | 23352 | - | 44.76599999994505 | unknown |

Offline rows calibrate the harness; their tokens and timings are scripted, not provider measurements. Unknown costs are not zero. Rates are supplied by the operator; energy/hardware costs are excluded. Live runs use identical fixtures, question, limits and output caps across modes. Small samples are descriptive, not statistical rankings. Failed and unrun slots never count as passes.

Each measured row has run.json, trace.json, evidence.json and score.json. Trace spans omit content; evidence files contain only synthetic fixture data. See scorecard.json for versions, hashes, limits and measurement settings. Rescoring uses only these JSON files and makes no model calls.

## Descriptive mode comparison

| Provider | Mode | Passed / runs | Median seconds | Mean charged tokens | Quality gate |
|---|---|---:|---:|---:|---|
| ollama | single | 2 / 8 | 38.899 | 28370.2 | fail; do not rank performance |
