# M5 reproducible scorecard

Gate: FAIL / INCOMPLETE; unrun slots: 0.

| Provider | Mode | Case | Status | Checks | Tokens | Calls | Seconds | USD estimate |
|---|---|---|---|---|---:|---:|---:|---:|
| ollama | single | other-station | completed | metrics, causal_calibration, citations | 11176 | - | 19.53200000000652 | unknown |
| ollama | single | other-station | completed | metrics, causal_calibration, citations | 11123 | - | 19.28200000000652 | unknown |
| ollama | single | no-increase | completed | metrics, causal_calibration, citations | 11120 | - | 19.390999999945052 | unknown |
| ollama | single | no-increase | completed | metrics, causal_calibration, citations | 11229 | - | 20.093999999924563 | unknown |
| ollama | single | conflicting-records | completed | metrics, causal_calibration, citations | 11576 | - | 20.108999999938533 | unknown |
| ollama | single | conflicting-records | completed | metrics, causal_calibration, citations | 11590 | - | 19.39000000001397 | unknown |
| ollama | single | missing-document | completed | pass | 5575 | - | 14.016000000061467 | unknown |
| ollama | single | missing-document | completed | pass | 5575 | - | 14.35999999998603 | unknown |

Offline rows calibrate the harness; their tokens and timings are scripted, not provider measurements. Unknown costs are not zero. Rates are supplied by the operator; energy/hardware costs are excluded. Live runs use identical fixtures, question, limits and output caps across modes. Small samples are descriptive, not statistical rankings. Failed and unrun slots never count as passes.

Each measured row has run.json, trace.json, evidence.json and score.json. Trace spans omit content; evidence files contain only synthetic fixture data. See scorecard.json for versions, hashes, limits and measurement settings. Rescoring uses only these JSON files and makes no model calls.

## Descriptive mode comparison

| Provider | Mode | Passed / runs | Median seconds | Mean charged tokens | Quality gate |
|---|---|---:|---:|---:|---|
| ollama | single | 2 / 8 | 19.390 | 9870.5 | fail; do not rank performance |
