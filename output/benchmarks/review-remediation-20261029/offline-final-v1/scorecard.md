# M5 reproducible scorecard

Gate: PASS; unrun slots: 0.

| Provider | Mode | Case | Status | Checks | Tokens | Calls | Seconds | USD estimate |
|---|---|---|---|---|---:|---:|---:|---:|
| offline | single | known-cause | completed | pass | 3300 | 3 | 4.593 | unknown |
| offline | single | known-cause | completed | pass | 3300 | 3 | 6.203 | unknown |
| offline | single | ambiguous | completed | pass | 3300 | 3 | 5.25 | unknown |
| offline | single | ambiguous | completed | pass | 3300 | 3 | 5.531 | unknown |
| offline | single | injection | completed | pass | 3300 | 3 | 5.297 | unknown |
| offline | single | injection | completed | pass | 3300 | 3 | 4.953 | unknown |
| offline | delegated | known-cause | completed | pass | 5500 | 5 | 5.844 | unknown |
| offline | delegated | known-cause | completed | pass | 5500 | 5 | 5.609 | unknown |
| offline | delegated | ambiguous | completed | pass | 5500 | 5 | 5.437 | unknown |
| offline | delegated | ambiguous | completed | pass | 5500 | 5 | 5.75 | unknown |
| offline | delegated | injection | completed | pass | 5500 | 5 | 4.859 | unknown |
| offline | delegated | injection | completed | pass | 5500 | 5 | 5.125 | unknown |

Offline rows calibrate the harness; their tokens and timings are scripted, not provider measurements. Unknown costs are not zero. Rates are supplied by the operator; energy/hardware costs are excluded. Live runs use identical fixtures, question, limits and output caps across modes. Small samples are descriptive, not statistical rankings. Failed and unrun slots never count as passes.

Each measured row has run.json, trace.json, evidence.json and score.json. Trace spans omit content; evidence files contain only synthetic fixture data. See scorecard.json for versions, hashes, limits and measurement settings. Rescoring uses only these JSON files and makes no model calls.

## Descriptive mode comparison

| Provider | Mode | Passed / runs | Median seconds | Mean charged tokens | Quality gate |
|---|---|---:|---:|---:|---|
| offline | delegated | 6 / 6 | 5.523 | 5500.0 | pass |
| offline | single | 6 / 6 | 5.274 | 3300.0 | pass |
