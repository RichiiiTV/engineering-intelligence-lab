# M5 reproducible scorecard

Gate: PASS; unrun slots: 0.

| Provider | Mode | Case | Status | Checks | Tokens | Calls | Seconds | USD estimate |
|---|---|---|---|---|---:|---:|---:|---:|
| offline | single | other-station | completed | pass | 3300 | - | 4.937000000034459 | unknown |
| offline | single | other-station | completed | pass | 3300 | - | 5.187999999965541 | unknown |
| offline | single | no-increase | completed | pass | 3300 | - | 5.625 | unknown |
| offline | single | no-increase | completed | pass | 3300 | - | 5.437000000034459 | unknown |
| offline | single | conflicting-records | completed | pass | 3300 | - | 4.734000000054948 | unknown |
| offline | single | conflicting-records | completed | pass | 3300 | - | 5.0 | unknown |
| offline | single | missing-document | completed | pass | 3300 | - | 5.157000000006519 | unknown |
| offline | single | missing-document | completed | pass | 3300 | - | 4.733999999938533 | unknown |
| offline | delegated | other-station | completed | pass | 5500 | - | 5.702999999979511 | unknown |
| offline | delegated | other-station | completed | pass | 5500 | - | 5.717999999993481 | unknown |
| offline | delegated | no-increase | completed | pass | 5500 | - | 5.157000000006519 | unknown |
| offline | delegated | no-increase | completed | pass | 5500 | - | 5.655999999959022 | unknown |
| offline | delegated | conflicting-records | completed | pass | 5500 | - | 6.0 | unknown |
| offline | delegated | conflicting-records | completed | pass | 5500 | - | 6.327999999979511 | unknown |
| offline | delegated | missing-document | completed | pass | 5500 | - | 5.297000000020489 | unknown |
| offline | delegated | missing-document | completed | pass | 5500 | - | 4.859000000054948 | unknown |

Offline rows calibrate the harness; their tokens and timings are scripted, not provider measurements. Unknown costs are not zero. Rates are supplied by the operator; energy/hardware costs are excluded. Live runs use identical fixtures, question, limits and output caps across modes. Small samples are descriptive, not statistical rankings. Failed and unrun slots never count as passes.

Each measured row has run.json, trace.json, evidence.json and score.json. Trace spans omit content; evidence files contain only synthetic fixture data. See scorecard.json for versions, hashes, limits and measurement settings. Rescoring uses only these JSON files and makes no model calls.

## Descriptive mode comparison

| Provider | Mode | Passed / runs | Median seconds | Mean charged tokens | Quality gate |
|---|---|---:|---:|---:|---|
| offline | delegated | 8 / 8 | 5.679 | 5500.0 | pass |
| offline | single | 8 / 8 | 5.079 | 3300.0 | pass |
