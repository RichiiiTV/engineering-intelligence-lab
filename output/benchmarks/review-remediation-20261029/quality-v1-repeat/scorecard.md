# M5 reproducible scorecard

Gate: FAIL / INCOMPLETE; unrun slots: 0.

| Provider | Mode | Case | Status | Checks | Tokens | Calls | Seconds | USD estimate |
|---|---|---|---|---|---:|---:|---:|---:|
| ollama | single | known-cause | completed | pass | 17040 | 5 | 19.609 | unknown |
| ollama | single | known-cause | completed | pass | 17004 | 5 | 19.671 | unknown |
| ollama | single | ambiguous | completed | pass | 16009 | 5 | 19.469 | unknown |
| ollama | single | ambiguous | completed | pass | 15927 | 5 | 19.297 | unknown |
| ollama | single | injection | completed | pass | 16234 | 5 | 20.046 | unknown |
| ollama | single | injection | completed | pass | 12747 | 4 | 17.954 | unknown |
| ollama | delegated | known-cause | completed | pass | 20054 | 7 | 39.016 | unknown |
| ollama | delegated | known-cause | completed | evidence | 20245 | 7 | 39.547 | unknown |
| ollama | delegated | ambiguous | completed | pass | 19678 | 7 | 45.328 | unknown |
| ollama | delegated | ambiguous | completed | evidence | 19204 | 7 | 40.578 | unknown |
| ollama | delegated | injection | completed | pass | 20341 | 7 | 51.062 | unknown |
| ollama | delegated | injection | completed | evidence | 19224 | 7 | 38.469 | unknown |

Offline rows calibrate the harness; their tokens and timings are scripted, not provider measurements. Unknown costs are not zero. Rates are supplied by the operator; energy/hardware costs are excluded. Live runs use identical fixtures, question, limits and output caps across modes. Small samples are descriptive, not statistical rankings. Failed and unrun slots never count as passes.

Each measured row has run.json, trace.json, evidence.json and score.json. Trace spans omit content; evidence files contain only synthetic fixture data. See scorecard.json for versions, hashes, limits and measurement settings. Rescoring uses only these JSON files and makes no model calls.

## Descriptive mode comparison

| Provider | Mode | Passed / runs | Median seconds | Mean charged tokens | Quality gate |
|---|---|---:|---:|---:|---|
| ollama | delegated | 3 / 6 | 40.062 | 19791.0 | fail; do not rank performance |
| ollama | single | 6 / 6 | 19.539 | 15826.8 | pass |
